# CMN-C2-672 — Unit Tests: PolicyMetadataRetrieveNode

import os

from framework.schemas.agent_status import AgentStatus
from src.nodes.policy_metadata_retrieve_node import PolicyMetadataRetrieveNode


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
    }
    state.update(overrides)
    return state


class TestPolicyMetadataRetrieveNode:
    def setup_method(self, monkeypatch=None):
        os.environ["USE_MOCK"] = "true"
        self.node = PolicyMetadataRetrieveNode()

    def teardown_method(self):
        os.environ.pop("USE_MOCK", None)

    def test_retrieves_policy_metadata_in_mock_mode_with_no_secret_bound(self):
        """Mock mode must succeed with zero secrets bound (no ANTHROPIC_API_KEY etc.)."""
        state = _base_state()
        result = self.node(state)
        assert result["status"] == AgentStatus.SUCCESS.value
        assert "policy_metadata" in result
        assert "stale" in result["policy_metadata"]
