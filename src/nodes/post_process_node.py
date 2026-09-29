"""AgentCore Platform v1.0"""

from typing import Any, ClassVar

from framework.nodes.function_node import FunctionNode
from framework.schemas.agent_status import AgentStatus
from framework.schemas.trust_level import TrustLevel
from shared.utils.audit_logger import emit_trace_event


class PostProcessNode(FunctionNode):
    """Format and finalize the decision-brief output."""

    required_trust_level: ClassVar[TrustLevel] = TrustLevel.VERIFIED_EXTERNAL

    def execute(self, state: dict[str, Any]) -> dict[str, Any]:
        result = state.get("result", {})

        emit_trace_event("output_formatted", {"recommendation": result.get("recommendation")}, state)

        return {
            "formatted_output": result,
            "status": AgentStatus.SUCCESS.value,
        }

    def _extra_security_gate_output(self, result: dict[str, Any]) -> dict[str, Any]:
        """S-3 domain extension: the inner graph's own output_validate node already
        applied the hard disposal-safety gate — no additional checks needed here
        beyond the default credential scan."""
        return result
