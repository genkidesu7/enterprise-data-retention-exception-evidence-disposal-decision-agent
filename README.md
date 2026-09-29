# CMN-C2-672 — Enterprise Data Retention Exception Evidence & Disposal Decision Agent

> **Category**: Cat 2 (orchestrates a specific job-to-be-done)
> **Industry**: CMN (cross-industry)
> **Inherits**: `AgentBaseGraph` (L1, direct)
> **Status**: Draft

## Overview

This agent assembles a decision-ready, cited evidence packet and recommendation for a single
retention-exception or disposal request. It retrieves the applicable retention schedule, data
classification, system-of-record metadata, and legal-hold notices, checks for conflicting
obligations, assesses evidence completeness, and drafts a cited recommendation — approve a
time-bound exception, route for legal/privacy review, or proceed to disposal. It never executes
deletion or changes retention settings; the accountable governance reviewer retains final
decision authority.

This is an agent template built with the **AGENTIC STAR** development platform and the
**AgentCore Framework**. It is intended to be taken as a starting point: fork it, adapt it to
your own data and policies, and run it inside your own AGENTIC STAR deployment.

## Why This Template Exists

This template is **one production unit of the Agent 1000 line** — not a standalone
deliverable. The project goal is to make us *capable of producing* 1,000+ templates
per FY26 September capacity. That capability is what unlocks AGENTIC STAR as the
global de facto platform for enterprise agent development.

Of every design decision in this template, ask:

> "Does this make the next template faster, or only this one better?"

If your answer is the latter, reconsider — generalize at Level 2, or refactor the
pattern. A template that is technically beautiful but cannot be replicated quickly
across industries fails the mission. See `/agenticai/project-charter.md` for the
three-layer vision and full purpose context.

## Features

- Normalizes an incoming retention-exception or disposal request (record type, request type,
  business justification)
- Retrieves applicable retention schedule, data classification, and system-of-record metadata
  via RAG
- Checks the request against active legal-hold notices for conflicts
- Assesses evidence completeness and flags missing or stale metadata
- Drafts a cited recommendation with approval routing (approve exception / route for review /
  proceed to disposal)
- Hard S-3 gate: never authorizes deletion execution or a retention-setting change

## Requirements

**This template does not run standalone.** It requires:

| Requirement | Notes |
|---|---|
| **AGENTIC STAR platform** | The agent connects to the platform at start-up. Without it, start-up fails immediately (see *Behaviour without the platform* below). Deployment guides and API documentation: [AGENTIC STAR Developers](https://developers.fd.agenticstar.tm.softbank.jp/) |
| **AgentCore Framework** (`agenticstar-agentcore[openai,marketplace]==1.0.3`) | Installed from the internal package index — see Quick Start. The `openai` extra backs `AzureOpenAIClient`, the one real (non-mock) integration in this agent (see Configuration below). |
| Python | 3.11+ |

```bash
pip install -e .
```

### Behaviour without the platform

The framework is designed to run **only** on AGENTIC STAR. There is no fallback or degraded
mode. If the platform is unreachable or the SDK version does not match, the agent raises
`PlatformRequired` during graph compile / start-up preflight rather than starting in a partially
working state. This is intentional — a half-running agent is worse than one that refuses to start.

Outside AGENTIC STAR (local dev, unit tests, CI) the platform-bound emitter is a no-op —
progress events are silently dropped rather than raising, so the agent's business logic still
runs and can be tested, but progress/audit signals are only observable once actually deployed.
Mock mode (`USE_MOCK=true` / `STG_MOCK_MODE=true`) additionally substitutes stub data for the
decision-brief synthesis call, so no external credentials are required to run the test suite
locally. The retention-schedule and hold-registry lookups are permanently-mocked boundaries and
return stub data regardless of mock mode — only the decision-brief LLM call is ever real.

## Quick Start

```bash
source .venv/bin/activate
uv pip install -e ".[dev]"
python -m pytest tests/ -v
```

Tests run without a platform connection. Running the agent itself does not.

## Usage

Start the API server:

```bash
uvicorn src.api.server:app --reload
```

Invoke the agent with a retention-exception or disposal request. In production, an
upstream AgentGateway establishes caller trust automatically; on a standalone server set
`INVOKE_AUTH_TOKEN` and present it as a bearer token to reach `VERIFIED_EXTERNAL`:

```bash
curl -X POST http://localhost:8000/invoke \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $INVOKE_AUTH_TOKEN" \
  -d '{"input": "Request to retain customer records past the default 5-year schedule pending an active litigation matter"}'
```

## API Endpoints

| Method | Path | Description |
|---|---|---|
| `POST` | `/invoke` | Submit a retention-exception or disposal request; returns a cited decision brief with approval routing. Requires `Authorization: Bearer <INVOKE_AUTH_TOKEN>` when `INVOKE_AUTH_TOKEN` is set on the server (standalone/STG caller auth). |
| `GET` | `/health` | Health check |

## Configuration

- `config/agent.yaml` — agent manifest (`id`, `name`, `category`, `industry`, `base_type`, entry
  point, `requires.secrets`/`requires.extras`) — the AgentRegistry discovery entry point.
  Declares `AZURE_OPENAI_API_KEY`/`AZURE_OPENAI_ENDPOINT`/`AZURE_OPENAI_DEPLOYMENT` under
  `requires.secrets` and `openai` under `requires.extras` for `decision_brief_service.py`'s
  `AzureOpenAIClient` call — the only real (non-mock) integration in this agent.
- `config/config.yaml` — runtime-tunable parameters (`max_retry`, `timeout_s`).
- `retention_policy_service.py` and `hold_registry_service.py` are permanently-mocked
  boundaries (`src/services/`) — they never round-trip to a real source regardless of
  `USE_MOCK`, and need no secrets. Wiring real integrations for them is future work,
  tracked separately from this agent's LLM synthesis path.

## Project Structure

```
.
├── config/
│   ├── agent.yaml                            # Static manifest — AgentRegistry entry point
│   └── config.yaml                           # Runtime parameters (max_retry, timeout_s)
├── docs/                                      # Design spec, test spec (only these two are published)
├── scripts/                                   # CI gate checks (Cat consistency, dep pinning, trust level, etc.)
├── src/
│   ├── api/
│   │   └── server.py                          # FastAPI app — /invoke and /health routes
│   ├── graph/
│   │   ├── graph.py                           # Agent graph entry point (AgentBaseGraph subclass)
│   │   └── domain_workflow_graph.py           # Cat 2 domain workflow (GraphNode composition)
│   ├── nodes/
│   │   ├── pre_process_node.py
│   │   ├── request_normalize_node.py
│   │   ├── policy_metadata_retrieve_node.py
│   │   ├── hold_conflict_check_node.py
│   │   ├── evidence_completeness_assess_node.py
│   │   ├── decision_brief_draft_node.py
│   │   ├── output_validate_node.py
│   │   └── post_process_node.py
│   ├── schemas/
│   │   └── state.py                           # AgentState schema
│   └── services/
│       ├── retention_policy_service.py
│       ├── hold_registry_service.py
│       ├── decision_brief_service.py
│       ├── mock_data.py
│       └── mock_mode.py
└── tests/
    ├── integration/
    ├── proof_of_boundary/                     # PB tests — framework compliance boundaries
    └── unit/
```

See `docs/02_design.md` and `docs/03_test_spec.md` for further project documentation.

## Customising

1. Adjust `config/agent.yaml` and `config/config.yaml` for your own environment and policies.
2. Replace the mock retention-schedule/hold-registry/decision-brief data in `src/services/`
   with your own integrations, and declare the secrets/extras they need in `config/agent.yaml`.
3. Review the node implementations under `src/nodes/` for domain-specific logic.
4. Re-run the test suite.

## License

MIT — see [LICENSE](LICENSE).

## Status of this repository

This repository is published as a reference template, provided **as is, with no warranty** of
any kind, express or implied. It carries no ongoing support: issues and pull requests may not be
reviewed or answered.
