# CMN-C2-672 — Unit Tests: RequestNormalizeNode

from framework.schemas.agent_status import AgentStatus
from src.nodes.request_normalize_node import RequestNormalizeNode


def _base_state(**overrides) -> dict:
    state = {
        "caller_trust_level": "VERIFIED_EXTERNAL",
        "correlation_id": "test-correlation",
        "session_id": "test-session",
        "thread_id": "test-thread",
        "trace_id": "test-trace",
        "node_history": [],
        "error_log": [],
    }
    state.update(overrides)
    return state


class TestRequestNormalizeNode:
    def setup_method(self):
        self.node = RequestNormalizeNode()

    def test_parses_exception_request(self):
        state = _base_state(validated_input="Request to retain records past schedule")
        result = self.node(state)
        assert result["status"] == AgentStatus.SUCCESS.value
        assert result["normalized_request"]["request_type"] == "exception"

    def test_parses_disposal_request(self):
        state = _base_state(validated_input="Request to dispose of these records")
        result = self.node(state)
        assert result["status"] == AgentStatus.SUCCESS.value
        assert result["normalized_request"]["request_type"] == "disposal"

    def test_falls_back_to_user_input_when_validated_input_absent(self):
        """Inner graph's initial_state only carries user_input."""
        state = _base_state(user_input="Request to retain records past schedule")
        result = self.node(state)
        assert result["status"] == AgentStatus.SUCCESS.value

    def test_missing_justification_fallback_is_not_a_pipeline_error(self):
        """Proposal Risk #3: missing justification routes to clarification, not error."""
        state = _base_state(validated_input="", user_input="")
        result = self.node(state)
        assert result["status"] == AgentStatus.SUCCESS.value
