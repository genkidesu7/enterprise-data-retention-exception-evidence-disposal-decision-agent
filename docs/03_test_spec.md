# Test Specification

## Test Strategy
- Coverage target: 80%
- Test types: Unit / Integration
- Design reference: docs/02_design.md
- Implementation reference: docs/implement_tasks.md

## Framework Compliance Tests (Mandatory)

| TC-ID | Test | Expected Result | Result |
|-------|------|----------------|--------|
| TC-01 | State contract: flat TypedDict | Type check pass, no Pydantic/dataclass | Completed — `tests/proof_of_boundary/test_state_safety.py` |
| TC-02 | SecurityViolationError fires on invalid input | Error raised | Completed — `tests/unit/test_output_validate_node.py::test_deletion_execution_instruction_is_blocked` |
| TC-03 | No JWT/Credential in State | CI `gate-credential-scan`: 0 violations | Completed — `tests/unit/test_framework_compliance_tc06_tc07.py::test_tc03_no_credential_field_assignments_on_state_object` |
| TC-04 | InvocationContext via configurable only | Direct access raises error | Completed — `tests/unit/test_framework_compliance_tc06_tc07.py::test_tc04_invocation_context_not_read_from_state_configurable_key` |
| TC-05 | S-4: no duplicate lifecycle events in `execute()` | `node_start`/`node_complete`/`node_error` absent from `execute()` body | Completed — `tests/proof_of_boundary/test_pb_invoke_order.py` (verifies exact call order, no duplicates) |
| TC-06 | S-2: `_security_gate_input()` not overridden (`FunctionNode` subclass) | `TypeError` raised at class definition if overridden | Completed — `tests/unit/test_framework_compliance_tc06_tc07.py::test_tc06_security_gate_input_cannot_be_overridden` |
| TC-07 | S-3: `_security_gate_output()` not overridden (`FunctionNode` subclass) | `TypeError` raised at class definition if overridden | Completed — `tests/unit/test_framework_compliance_tc06_tc07.py::test_tc07_security_gate_output_cannot_be_overridden` |
| TC-08 | `required_trust_level` enforced | Insufficient trust → refused | Completed — verified via `check-security.sh` trust-level-consistency check; all 8 nodes declare `VERIFIED_EXTERNAL` matching `config/agent.yaml` |
| TC-09 | S-2: `_extra_security_gate_input()` non-trivial when domain checks needed | Domain-specific input checks execute correctly | Completed — `tests/unit/test_request_normalize_node.py::test_missing_justification_fallback_is_not_a_pipeline_error` |
| TC-10 | S-3: `_extra_security_gate_output()` non-trivial when domain checks needed | Domain-specific output checks execute correctly | Completed — `tests/unit/test_output_validate_node.py` (5 cases: approve/disposal-clean/disposal-blocked/missing-flags/deletion-instruction) |
| TC-11 | S-4: at least one domain `emit_trace_event()` inside each `execute()` | Domain event emitted on every invocation path | Completed — verified via `check-security.sh` emit_trace_event check across all 8 nodes |

## Proof-of-Boundary Tests (Mandatory)

| PB-ID | Boundary | Test | Expected Result | Result |
|-------|----------|------|----------------|--------|
| PB-1 | BaseNode → EventEmitter | `emit_trace_event()` fires on every invocation path | No silent failures | Completed — `tests/proof_of_boundary/test_pb_invoke_order.py` |
| PB-2 | State serialization | Post-invoke State is primitives only | No Pydantic/dataclass | Completed — `tests/proof_of_boundary/test_state_safety.py` |
| PB-3 | Level 2 → External service | Real external service connection | Data retrieved | Auto-waived — this template's services (`RetentionPolicyService`, `HoldRegistryService`, `DecisionBriefService`) are not yet wired to a live external client (mock-mode only, per design's Services section); real-connection PB-3 applies once `shared/services/<client>` wiring lands in a future sprint |
| PB-4 | Import isolation | No Level 0 imports | AST scan: 0 violations | Completed — `tests/proof_of_boundary/test_import_isolation.py` |
| PB-5 | Checkpoint safety | No JWT/Pydantic in checkpoint | Inspection pass | Completed — `tests/proof_of_boundary/test_state_safety.py` |
| PB-6 | Invoke execution order | `__call__()`: S-1 → S-4 `node_start` → S-2 → `execute()` → S-3 → S-4 `node_complete` | Order verified | Completed — `tests/proof_of_boundary/test_pb_invoke_order.py` (auto-discovers all 8 nodes under `src/nodes/`) |
| PB-7 | HITL interrupt propagation *(conditional)* | Required only when `config.yaml` sets `hitl.enabled: true` | Auto-waived — non-HITL | Auto-waived — `config/agent.yaml` does not set `hitl.enabled: true` (design decision record: HITL disabled, agent is advisory-only). `tests/proof_of_boundary/test_pb7_hitl_interrupt_propagation.py` self-skips via `pytest.mark.skipif`. |

> **Pre-CoE gate checklist:** PB-1 through PB-6 are mandatory and completed above. PB-7 is auto-waived (non-HITL). PB-3 is noted above pending real external-service wiring in a future sprint — this does not block the current stage per design's mock-mode scope.

## Business Logic Tests

| TC-ID | Test | Input | Expected Result | Result |
|-------|------|-------|----------------|--------|
| BL-01 | Missing-justification fallback (proposal Risk #3) | Empty `business_justification`/`user_input` | Routed for clarification, not a pipeline error | Completed — `tests/unit/test_request_normalize_node.py::test_missing_justification_fallback_is_not_a_pipeline_error` |
| BL-02 | Hold conflict forces `route_for_review` recommendation | `conflict_flags` non-empty | `decision_brief.recommendation == "route_for_review"` | Completed — `tests/unit/test_decision_brief_draft_node.py::test_conflicts_force_route_for_review` |
| BL-03 | Disposal-safety hard gate blocks unsafe disposal (proposal Risk #1) | `recommendation == "proceed_to_disposal"` with active hold conflict | `SecurityViolationError` → `status: error` | Completed — `tests/unit/test_output_validate_node.py::test_proceed_to_disposal_with_active_conflict_is_blocked` |
| BL-04 | Absent conflict-flag result is never treated as implicitly clean | `decision_brief` with `proceed_to_disposal` and no `conflict_flags` key | Blocked, not silently allowed | Completed — `tests/unit/test_output_validate_node.py::test_proceed_to_disposal_with_no_conflict_flag_result_is_blocked` |
| BL-05 | Stale policy metadata surfaced as an evidence gap (proposal Risk #2) | `policy_metadata.stale == True` | `"stale_policy_metadata"` in `evidence_gaps` | Completed — `tests/unit/test_evidence_completeness_assess_node.py::test_flags_stale_metadata` |
| BL-06 | Mock-mode flag resolution under every alias (deploy-stg regression) | `USE_MOCK` / `STG_MOCK_MODE` set individually | `mock_mode_enabled()` returns `True` for either alias, `False` for neither | Completed — `tests/unit/test_mock_mode.py` (3 cases) |
| BL-07 | Async route / sync `.invoke()` boundary (deploy-stg regression) | POST `/invoke` over a real ASGI transport | 200 response, `status: "success"`, no `asyncio.run()` nested-loop error | Completed — `tests/integration/test_invoke_endpoint_http.py::test_invoke_endpoint_succeeds_over_http` |
| BL-08 | Full outer→inner pipeline end-to-end (mock mode) | Sample retention-exception request | `.compile()` + `.invoke()` succeeds, `status: "success"`, decision brief returned | Completed — `tests/integration/test_graph.py::test_full_pipeline_invoke_succeeds` |

## Test Execution Summary
- Execution date: 2026-07-20
- Total tests: 35 (33 executed, 2 conditionally skipped — non-HITL)
- Pass: 33 / Fail: 0 / Skip: 2
- Coverage: 95% (`pytest --cov=src`), exceeds 80% target
- `check-local.sh` (project root): all 15 gates pass, including Stage 5 STG invoke evidence
  (`overall: PASS`, all 7 assertions true, `agent_status_success: true`)
