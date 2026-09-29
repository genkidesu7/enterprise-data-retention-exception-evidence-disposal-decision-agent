# CMN-C2-672 — Unit Tests: EvidenceCompletenessAssessNode

from framework.schemas.agent_status import AgentStatus
from src.nodes.evidence_completeness_assess_node import EvidenceCompletenessAssessNode


def _base_state(**overrides) -> dict:
    state = {
        "caller_trust_level": "VERIFIED_EXTERNAL",
        "correlation_id": "test-correlation",
        "session_id": "test-session",
        "thread_id": "test-thread",
        "trace_id": "test-trace",
        "node_history": [],
        "error_log": [],
        "policy_metadata": {"stale": False, "retention_schedule": {"retention_years": 5}},
        "conflict_flags": [],
    }
    state.update(overrides)
    return state


class TestEvidenceCompletenessAssessNode:
    def setup_method(self):
        self.node = EvidenceCompletenessAssessNode()

    def test_no_gaps_when_metadata_complete_and_fresh(self):
        state = _base_state()
        result = self.node(state)
        assert result["status"] == AgentStatus.SUCCESS.value
        assert result["evidence_gaps"] == []

    def test_flags_stale_metadata(self):
        state = _base_state(policy_metadata={"stale": True, "retention_schedule": {"retention_years": 5}})
        result = self.node(state)
        assert "stale_policy_metadata" in result["evidence_gaps"]

    def test_flags_ambiguous_hold_status(self):
        state = _base_state(conflict_flags=[{"hold_status": "ambiguous"}])
        result = self.node(state)
        assert "ambiguous_hold_status" in result["evidence_gaps"]
