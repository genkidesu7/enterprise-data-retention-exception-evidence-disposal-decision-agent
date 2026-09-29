"""AgentCore Platform v1.0"""

# Node contract (agents_layer_design.md §1):
#  - Extend FunctionNode; implement execute(state) -> dict
#  - Return ONLY the fields this node changes (never full state)
#  - Return AgentStatus enum constants — never plain strings [A1]
#  - Read input_context via state.get("input_context", {}) — read-only [C1]
#  - Never import from mediator/, api/, or other agents

from typing import Any, ClassVar

from framework.nodes.function_node import FunctionNode
from framework.schemas.agent_status import AgentStatus
from framework.schemas.trust_level import TrustLevel
from shared.utils.audit_logger import emit_trace_event


class PreProcessNode(FunctionNode):
    """Validate and enrich incoming retention-exception/disposal request input."""

    required_trust_level: ClassVar[TrustLevel] = TrustLevel.VERIFIED_EXTERNAL

    def execute(self, state: dict[str, Any]) -> dict[str, Any]:
        user_input = state.get("user_input", "")
        input_context = state.get("input_context", {})  # read-only [C1]

        # pre_process is the outer backbone's RETRY re-entry point
        # (AgentBaseGraph.route(): status=RETRY + retry_count<max_retry loops
        # back here). Nothing else in the framework increments retry_count —
        # skipping this turns any genuine main-node RETRY into an infinite
        # pre_process<->main loop (bounded only by LangGraph's recursion
        # limit, not by config/config.yaml's max_retry).
        retry_count = state.get("retry_count", 0) + 1

        if not user_input or not user_input.strip():
            return {
                "status": AgentStatus.ERROR.value,
                "error_log": ["PreProcessNode: user_input is empty or missing"],
                "retry_count": retry_count,
            }

        emit_trace_event("input_validated", {"input_length": len(user_input)}, state)

        return {
            "validated_input": user_input.strip(),
            "enriched_context": {
                "source": "retention_exception_disposal_agent",
                "channel": input_context.get("channel", "unknown"),
            },
            "status": AgentStatus.SUCCESS.value,
            "retry_count": retry_count,
        }

    def _extra_security_gate_input(self, state: dict[str, Any]) -> dict[str, Any]:
        """S-2 domain extension: no additional checks beyond the default PII scan."""
        return state
