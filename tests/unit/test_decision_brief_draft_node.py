# CMN-C2-672 — Unit Tests: DecisionBriefDraftNode

import os

from framework.schemas.agent_status import AgentStatus
from src.nodes.decision_brief_draft_node import DecisionBriefDraftNode


def _base_state(**overrides) -> dict:
    state = {
        "caller_trust_level": "VERIFIED_EXTERNAL",
        "correlation_id": "test-correlation",
        "session_id": "test-session",
        "thread_id": "test-thread",
        "trace_id": "test-trace",
        "node_history": [],
        "error_log": [],
        "normalized_request": {"record_type": "customer_records", "request_type": "exception"},
        "policy_metadata": {"stale": False},
        "conflict_flags": [],
        "evidence_gaps": [],
    }
    state.update(overrides)
    return state


class TestDecisionBriefDraftNode:
    def setup_method(self):
        os.environ["USE_MOCK"] = "true"
        self.node = DecisionBriefDraftNode()

    def teardown_method(self):
        os.environ.pop("USE_MOCK", None)

    def test_recommendation_is_one_of_defined_values(self):
        state = _base_state()
        result = self.node(state)
        assert result["status"] == AgentStatus.SUCCESS.value
        assert result["decision_brief"]["recommendation"] in (
            "approve_exception",
            "route_for_review",
            "proceed_to_disposal",
        )

    def test_conflicts_force_route_for_review(self):
        state = _base_state(conflict_flags=[{"hold_status": "conflict"}])
        result = self.node(state)
        assert result["decision_brief"]["recommendation"] == "route_for_review"

    def test_citations_present(self):
        state = _base_state()
        result = self.node(state)
        assert len(result["decision_brief"]["citations"]) > 0
