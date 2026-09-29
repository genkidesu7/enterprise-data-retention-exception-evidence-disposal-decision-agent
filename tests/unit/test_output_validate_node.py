# CMN-C2-672 — Unit Tests: OutputValidateNode (S-3 disposal-safety hard gate)

from framework.schemas.agent_status import AgentStatus
from src.nodes.output_validate_node import OutputValidateNode


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


class TestOutputValidateNode:
    def setup_method(self):
        self.node = OutputValidateNode()

    def test_approve_exception_passes(self):
        state = _base_state(
            decision_brief={"recommendation": "approve_exception", "conflict_flags": []},
        )
        result = self.node(state)
        assert result["status"] == AgentStatus.SUCCESS.value

    def test_proceed_to_disposal_with_clean_conflict_flags_passes(self):
        state = _base_state(
            decision_brief={"recommendation": "proceed_to_disposal", "conflict_flags": []},
        )
        result = self.node(state)
        assert result["status"] == AgentStatus.SUCCESS.value

    def test_proceed_to_disposal_with_active_conflict_is_blocked(self):
        """Proposal Risk #1: hard S-3 gate blocks disposal when a hold conflict exists."""
        state = _base_state(
            decision_brief={
                "recommendation": "proceed_to_disposal",
                "conflict_flags": [{"hold_status": "conflict"}],
            },
        )
        result = self.node(state)
        assert result["status"] == AgentStatus.ERROR.value

    def test_proceed_to_disposal_with_no_conflict_flag_result_is_blocked(self):
        """Absence of a conflict-flag result must never be treated as implicitly clean."""
        state = _base_state(
            decision_brief={"recommendation": "proceed_to_disposal"},
        )
        result = self.node(state)
        assert result["status"] == AgentStatus.ERROR.value

    def test_deletion_execution_instruction_is_blocked(self):
        state = _base_state(
            decision_brief={
                "recommendation": "approve_exception",
                "conflict_flags": [],
                "action": "execute_deletion",
            },
        )
        result = self.node(state)
        assert result["status"] == AgentStatus.ERROR.value
