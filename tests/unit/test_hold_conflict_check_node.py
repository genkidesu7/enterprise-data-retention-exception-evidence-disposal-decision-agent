# CMN-C2-672 — Unit Tests: HoldConflictCheckNode

import os

from framework.schemas.agent_status import AgentStatus
from src.nodes.hold_conflict_check_node import HoldConflictCheckNode


def _base_state(**overrides) -> dict:
    state = {
        "caller_trust_level": "VERIFIED_EXTERNAL",
        "correlation_id": "test-correlation",
        "session_id": "test-session",
        "thread_id": "test-thread",
        "trace_id": "test-trace",
        "node_history": [],
        "error_log": [],
        "normalized_request": {"record_type": "customer_records", "request_type": "disposal"},
    }
    state.update(overrides)
    return state


class TestHoldConflictCheckNode:
    def setup_method(self):
        os.environ["USE_MOCK"] = "true"
        self.node = HoldConflictCheckNode()

    def teardown_method(self):
        os.environ.pop("USE_MOCK", None)

    def test_clean_hold_status_returns_no_conflicts(self):
        state = _base_state()
        result = self.node(state)
        assert result["status"] == AgentStatus.SUCCESS.value
        assert result["conflict_flags"] == []
