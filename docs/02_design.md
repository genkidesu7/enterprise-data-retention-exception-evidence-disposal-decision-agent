# Template Design Specification

Status: completed
Date: 2026-07-19
Reviewer: TBD

## Position in AgentCore Architecture

- **Agent Class**: `RetentionExceptionDisposalAgent`
- **L1 Base**: AgentBaseGraph (outer graph, direct L1 inheritance; `main` slot composes an
  inner `BaseGraph` — see Composition Pattern below)
- **Three-Layer Separation**:
  - State: flat TypedDict composition (no Pydantic — msgpack incompatible)
  - Node: L1 inheritance (Template Method: `execute(self, state: dict) -> dict` override only)
  - Graph: composition (`register_nodes()` for node substitution)

## Architecture Overview

This is a **Cat 2** agent: it orchestrates a fixed, specific multi-step job-to-be-done
(assembling evidence and drafting a cited recommendation for one retention-exception or
disposal request), not a single reusable capability (Cat 1) and not an autonomous
self-directed loop (Cat 3).

### Two-layer graph structure

**Outer graph** (`src/graph/graph.py`, `RetentionExceptionDisposalAgent(AgentBaseGraph)`):
the standard, framework-owned 5-node backbone. Domain complexity lives entirely inside the
`main` slot via a `GraphNode` subclass (`RetentionDecisionWorkflowGraphNode`).

**Inner graph** (`src/graph/domain_workflow_graph.py`,
`RetentionDecisionWorkflowGraph(BaseGraph)`): implements the 6-step domain pipeline from the
proposal with fully custom node names and topology (not the pre_process/main/post_process
shape), so it inherits `BaseGraph` directly.

### Node Configuration — Outer Graph

| Node | Responsibility | Input State | Output State | Inherits/Overrides |
|------|---------------|-------------|--------------|-------------------|
| initialize | Framework-standard state bootstrap | — | — | InitializeNode (default) |
| pre_process | Validate/sanitize raw request text (S-2 input gate) | `user_input` | `validated_input`, `status` | PreProcessNode |
| main | Runs the inner 6-step domain workflow via GraphNode composition | `validated_input` | `result`, `status`, decision-brief fields (see Data Flow) | RetentionDecisionWorkflowGraphNode (GraphNode) |
| post_process | Final formatting/citation check (S-3 output gate) | `result` | `formatted_output`, `status` | PostProcessNode |
| finalize | Framework-standard state closeout | — | — | FinalizeNode (default) |

### Node Configuration — Inner Graph (`RetentionDecisionWorkflowGraph`)

| Node | Responsibility | Input State | Output State | Inherits/Overrides |
|------|---------------|-------------|--------------|-------------------|
| request_normalize | Parse record type, request type (exception/disposal), business justification | `validated_input` (fallback `user_input`) | `normalized_request`, `status` | FunctionNode |
| policy_metadata_retrieve | RAG retrieval of retention schedule, data classification, system-of-record metadata | `normalized_request` | `policy_metadata`, `status` | FunctionNode |
| hold_conflict_check | Check request against active legal-hold notices / retention obligations | `normalized_request`, `policy_metadata` | `conflict_flags`, `status` | FunctionNode |
| evidence_completeness_assess | Identify missing evidence / conflicting obligations relative to policy | `policy_metadata`, `conflict_flags` | `evidence_gaps`, `status` | FunctionNode |
| decision_brief_draft | Generate cited recommendation (approve exception / route for review / proceed to disposal) | `policy_metadata`, `conflict_flags`, `evidence_gaps` | `decision_brief`, `status` | FunctionNode |
| output_validate | S-3 domain gate: confirm no deletion/setting-change instruction is present; every claim cited | `decision_brief` | `result`, `status` | FunctionNode |

### Data Flow

**Outer backbone (fixed, framework-owned):**
```
START → initialize → pre_process → main → {route} → post_process → finalize → END
                                            ↓ (retry, max 3)
                                          pre_process
```

**Inner graph (linear, `RetentionDecisionWorkflowGraph.add_edges()`):**
```
START → request_normalize → policy_metadata_retrieve → hold_conflict_check
      → evidence_completeness_assess → decision_brief_draft → output_validate → END
```

No conditional branching inside the inner graph — every request runs the full evidence
pipeline; `decision_brief_draft`'s recommendation (approve / route-for-review / disposal) is
a **field value** in the decision brief, not a graph branch. The hard "never recommend
disposal with an unresolved hold" rule is enforced as a data-level check in
`output_validate`, not as routing (see S-3 discussion below), because the framework's
routing is reserved for `AgentStatus`-based control flow (RETRY/ERROR/CONTINUE), not for
domain-recommendation branching.

### State Definition (`src/schemas/state.py`, extends `AgentState`)

| Field | Type | Purpose | Required |
|-------|------|---------|----------|
| `normalized_request` | `dict` | Parsed record type, request type (exception/disposal), justification | No (set by request_normalize) |
| `policy_metadata` | `dict` | Retrieved retention schedule, data classification, SoR metadata, freshness flags | No (set by policy_metadata_retrieve) |
| `conflict_flags` | `list[dict]` | Active legal-hold / obligation conflicts found for this request | No (set by hold_conflict_check) |
| `evidence_gaps` | `list[str]` | Missing evidence / unresolved conflicts relative to policy | No (set by evidence_completeness_assess) |
| `decision_brief` | `dict` | Cited recommendation + routing (`recommendation`, `citations`, `routing`) | No (set by decision_brief_draft) |
| `result` | `dict` | Final validated decision-brief payload returned to the caller | No (set by output_validate / main) |
| `formatted_output` | `dict` | Post-processed/formatted final response | No (set by post_process) |

**State Constraints (mandatory):**
- Flat TypedDict only (primitives + JSON-serializable types); nested `dict`/`list` values
  above are shallow (record IDs, citation strings, policy snippet references — no
  Pydantic/dataclass objects, no `datetime`, no `bytes`).
- No JWT, API keys, credentials in State (checkpoint DB leakage) — the retention-schedule
  store / hold-registry / classification-registry connections are resolved via
  `InvocationContext.credential_handle` inside services, never stored in state fields.
- `InvocationContext` via `config["configurable"]` only (not in State).
- No Pydantic models, dataclass, arbitrary Python objects (msgpack incompatible).

## Framework Utilization

### Shared Components Used
- [x] InvocationContext (correlation_id, session_id, permissions, credential handle)
- [x] ConnectionPolicy (retry/timeout strategy) — retry on transient retrieval/RAG failures
- [x] SecurityViolationError
- [x] S-2: `_extra_security_gate_input()` — domain-specific input check hook
      Implemented on `pre_process`/`request_normalize`: validates that `request_type` is
      one of `exception`/`disposal` and that `business_justification` is non-empty;
      missing/invalid justification routes to the "missing-justification fallback"
      described in the proposal's Risk #3, not a hard reject.
- [x] S-3: `_extra_security_gate_output()` — domain-specific output check hook
      Implemented on `output_validate`/`post_process`: **hard gate** — scans the drafted
      decision brief and raises `SecurityViolationError` if it contains any deletion-
      execution instruction or retention-setting-change instruction, or if
      `recommendation == "proceed_to_disposal"` while `conflict_flags` is non-empty /
      hold-registry status is not conclusively clean. This directly implements the
      proposal's Risk #1 mitigation ("hard S-3 gate blocks any disposal recommendation
      unless hold-registry check returns a clean result").
- [x] S-4: `emit_trace_event()` — at least one domain-specific event inside each `execute()`
      Domain events emitted: `request_normalized`, `policy_metadata_retrieved`,
      `hold_conflict_checked`, `evidence_gaps_identified`, `decision_brief_drafted`,
      `output_validated` (one per inner node, carrying record type / request type /
      conflict-flag count / recommendation — never the underlying policy or hold-notice
      content itself, to avoid leaking sensitive record metadata into the audit trail).

> **S-2/S-3 gate behaviour by node type (ADR-017):** all inner-graph nodes are
> `FunctionNode` subclasses — the framework `@final` gate always runs automatically;
> domain checks are added only via `_extra_security_gate_input()` /
> `_extra_security_gate_output()`, never by overriding the `@final` methods.

### Composition Pattern

- **Pattern**: GraphNode (subgraph) — outer `AgentBaseGraph` composes an inner `BaseGraph`
  via the `main` slot.
- **Composition target**: `RetentionDecisionWorkflowGraphNode` (outer, in `src/graph/graph.py`)
  wraps `RetentionDecisionWorkflowGraph` (inner, in `src/graph/domain_workflow_graph.py`).
- **Error propagation strategy**: `propagate` — a failure in any inner step (e.g. the
  hold-registry or policy-retrieval service being unavailable) should fail the whole
  request rather than silently degrade to a possibly-wrong recommendation. `propagate_hitl`:
  `False` — no HITL interrupt is used in this workflow; the human reviewer acts *after* the
  agent returns its recommendation, not mid-pipeline.

`RetentionDecisionWorkflowGraphNode.extract_input()` passes `validated_input` (falling back
to `user_input`) into `inner_graph.invoke()`. Per the framework's known behavior, the inner
graph receives a **fresh state** containing only `user_input` — every inner node that reads
the request text falls back with
`state.get("validated_input", state.get("user_input", ""))`, per SDK guidance, so the entry
node (`request_normalize`) is not the only place this matters if a later node also needs the
raw text.

`merge_output()` maps the inner graph's `get_output()` (`result`, `status`, `trace_id`,
`correlation_id`, `node_history`) onto the outer state's `result` / `status` fields only —
no other outer-state keys are touched by `main`.

## Import Isolation Confirmation
- [x] Template does not import agenticstar-platform SDK (Level 0)
- [x] Import targets: framework/ and shared/ only (no agents/base/ required)

## Services (`src/services/`)

- **`retention_policy_service.py`** — retrieval against the retention-schedule store,
  data-classification registry, and system-of-record metadata. Used by
  `policy_metadata_retrieve`. Per the agenticstar-deploy skill's hard rule #2 ("every
  service other than the LLM call defaults to mock, including in real/non-mock mode —
  only the LLM call is ever real"), this is a **permanently-mocked boundary**: it never
  round-trips to a real retention-schedule store, regardless of `USE_MOCK`. Wiring an
  actual source is future work, tracked separately from this agent's LLM synthesis path.
- **`hold_registry_service.py`** — queries the legal-hold notice registry for active
  holds matching the normalized request. Used by `hold_conflict_check`. Also a
  **permanently-mocked boundary** for the same reason as above.
- **`decision_brief_service.py`** — the one real (non-mock) integration in this agent.
  Synthesizes the cited recommendation from policy metadata, conflict flags, and
  evidence gaps: a `route_for_review` recommendation is always decided deterministically
  (never the LLM's call) whenever conflict flags or evidence gaps are present; otherwise
  the approve-exception/proceed-to-disposal decision is delegated to `AzureOpenAIClient`
  in real (non-mock) mode. Used by `decision_brief_draft`. Credentials
  (`AZURE_OPENAI_API_KEY`/`AZURE_OPENAI_ENDPOINT`/`AZURE_OPENAI_DEPLOYMENT`, declared in
  `config/agent.yaml`'s `requires.secrets`) are resolved via
  `InvocationContext.secrets.require(...)` — never a raw key in state, logs, or
  function args.

`retention_policy_service.py` and `hold_registry_service.py` support the standard
mock-mode / `get_flag` pattern only insofar as they always return mock data;
`decision_brief_service.py` is the only service whose mock-mode gate actually switches
between mock and a real external call.

## Error Handling

- **RETRY** (transient, bounded by `max_retry=3`): policy-metadata RAG retrieval timeout,
  hold-registry query timeout, LLM synthesis timeout — recoverable by re-running from
  `pre_process`.
- **ERROR** (permanent): malformed request that fails S-2 validation after retry exhaustion;
  `SecurityViolationError` raised by the S-3 disposal-safety gate (this must **not** be
  silently downgraded — it is a deliberate hard stop, per proposal Risk #1).
- **Missing-justification fallback** (proposal Risk #3): if `business_justification` is
  absent/empty, `request_normalize` sets `status` to a distinguishable non-error state and
  `evidence_gaps` includes `"missing_business_justification"`, which `decision_brief_draft`
  surfaces as "route for clarification" rather than treating it as a pipeline failure.
- **Stale-metadata flag** (proposal Risk #2): `policy_metadata_retrieve` includes a
  freshness check; `policy_metadata.stale` is surfaced verbatim in the final decision brief
  rather than silently used as-is.

## Security Considerations

- S-1 input-size limit: enforced automatically by the framework on `user_input` /
  `validated_input` (no additional template code needed).
- S-3 no-execution/no-setting-change gate: see Framework Utilization above — this is the
  single most important security property of this agent and is implemented as a hard,
  non-bypassable check in `output_validate`'s `_extra_security_gate_output()`.
- S-4 audit-clean output: domain trace events listed above; no policy/hold-notice content
  or credentials logged.
- `required_trust_level`: `VERIFIED_EXTERNAL` (matches `config/agent.yaml`) — this agent is
  invoked by authenticated business-team/records-management callers, not anonymous traffic.
- Security rule 05 (input-channel patterns) reviewed — not applicable: this agent
  accepts only free-text `user_input` describing a retention-exception/disposal request;
  it has no file-upload channel and no external-API-response ingestion channel, so
  Channel 1/2 requirements in that rule do not apply.
- Security rule 06 (regulated data) reviewed — not applicable: this is a CMN
  (cross-industry commercial) template, not HCR/INS/GOV, so Rule 6.1 (APPI) and Rule 6.3
  (GOV classification markers) are out of scope by vertical. Rule 6.2 (My Number) applies
  to GOV and to HR/payroll templates regardless of vertical; this agent is
  records-governance/legal-hold, not HR/payroll, so it is out of scope as well. Recorded
  here explicitly so a future reviewer does not have to re-derive this scoping decision.

## Performance Requirements

- Standard Cat 2 RAG + conflict-check + synthesis latency profile — reuses existing
  LLM + vector infra (proposal §10, "no new infra required"). No autonomous-loop iteration
  budget applies (this is not Cat 3).

## Design Decision Record

| Decision | Option A | Option B | Chosen | Rationale |
|----------|----------|----------|--------|-----------|
| L1 base type | AgentBaseGraph | AutonomousBaseGraph | **AgentBaseGraph** | Fixed multi-step job-to-be-done, one recommendation per request, no self-directed iteration loop — matches Cat 2, not Cat 3 (proposal §2-2 Cat judgment) |
| Composition pattern | GraphNode (inner BaseGraph) | Flat single-graph (all 6 steps as outer pre_process/main/post_process) | **GraphNode + inner BaseGraph** | 6 distinct domain steps do not map onto the 3 generic outer slots without collapsing meaningfully distinct responsibilities; GraphNode composition keeps the outer backbone framework-standard while giving the domain pipeline its own named nodes and linear topology |
| Inner graph parent | BaseGraph (fully custom topology) | AgentBaseGraph (5-node pipeline) | **BaseGraph** | The 6 domain steps have custom names (request_normalize, policy_metadata_retrieve, ...) that don't correspond to pre_process/main/post_process; a fully custom linear topology is the natural fit |
| Disposal-safety enforcement point | Inner graph conditional routing | S-3 `_extra_security_gate_output()` hard check | **S-3 gate** | Routing is reserved for `AgentStatus`-based control flow; the "never recommend disposal with an unresolved hold" rule is a security-boundary property (proposal Risk #1), best enforced as a non-bypassable output gate rather than a data-dependent graph edge |
| HITL | Enabled (interrupt before disposal recommendation) | Disabled (human reviews after the fact) | **Disabled** | Proposal explicitly scopes the agent as advisory-only: "the accountable governance reviewer retains decision authority" *after* receiving the decision brief, not as an in-loop approval step; no `config.yaml` `hitl.enabled` needed |
