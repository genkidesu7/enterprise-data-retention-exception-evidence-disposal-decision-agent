"""AgentCore Platform v1.0"""

# Inner domain-workflow node (Cat 2). Parses the retention-exception/disposal
# request into a normalized shape. First node in the inner pipeline.

from __future__ import annotations

from typing import Any, ClassVar

from framework.nodes.function_node import FunctionNode
from framework.schemas.agent_status import AgentStatus
from framework.schemas.trust_level import TrustLevel
from shared.utils.audit_logger import emit_trace_event


def _parse_request_type(text: str) -> str:
    lowered = text.lower()
    if "dispos" in lowered:
        return "disposal"
    return "exception"


class RequestNormalizeNode(FunctionNode):
    """Parse record type, request type, and business justification.

    Reads: validated_input (fallback user_input).
    Writes: normalized_request, status.
    """

    required_trust_level: ClassVar[TrustLevel] = TrustLevel.VERIFIED_EXTERNAL

    def execute(self, state: dict[str, Any]) -> dict[str, Any]:
        # Inner graph's initial_state only carries user_input — the outer
        # pre_process's validated_input is never copied in by the framework.
        text = state.get("validated_input", state.get("user_input", ""))

        request_type = _parse_request_type(text)
        justification = state.get("business_justification", "") or text

        normalized_request: dict[str, Any] = {
            "record_type": state.get("record_type", "unspecified"),
            "request_type": request_type,
            "business_justification": justification,
        }

        emit_trace_event(
            "request_normalized",
            {"request_type": request_type, "has_justification": bool(justification.strip())},
            state,
        )

        return {
            "normalized_request": normalized_request,
            "status": AgentStatus.SUCCESS.value,
        }

    def _extra_security_gate_input(self, state: dict[str, Any]) -> dict[str, Any]:
        """S-2 domain extension: missing-justification fallback (proposal Risk #3).

        Does not reject the request — flags it so decision_brief_draft routes
        for clarification instead of treating it as a pipeline failure.
        """
        text = state.get("validated_input", state.get("user_input", ""))
        if not text or not text.strip():
            state["evidence_gaps"] = [*state.get("evidence_gaps", []), "missing_business_justification"]
        return state
