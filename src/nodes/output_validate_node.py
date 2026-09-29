"""AgentCore Platform v1.0"""

# Inner domain-workflow node (Cat 2). Hard S-3 gate: confirms no deletion
# execution or retention-setting change is ever authorized, and blocks any
# "proceed to disposal" recommendation unless the hold-registry check
# returned an unambiguous clean result (proposal Risk #1).

from __future__ import annotations

from typing import Any, ClassVar

from framework.errors import SecurityViolationError
from framework.nodes.function_node import FunctionNode
from framework.schemas.agent_status import AgentStatus
from framework.schemas.trust_level import TrustLevel
from shared.utils.audit_logger import emit_trace_event

_FORBIDDEN_INSTRUCTION_MARKERS = ("delete_record", "execute_deletion", "change_retention_setting")


class OutputValidateNode(FunctionNode):
    """Final S-3 gate: never authorize deletion or a retention-setting change.

    Reads: decision_brief, conflict_flags.
    Writes: result, status.
    """

    required_trust_level: ClassVar[TrustLevel] = TrustLevel.VERIFIED_EXTERNAL

    def execute(self, state: dict[str, Any]) -> dict[str, Any]:
        decision_brief = state.get("decision_brief", {})
        recommendation = decision_brief.get("recommendation")

        emit_trace_event(
            "output_validated",
            {"recommendation": recommendation},
            state,
        )

        return {
            "result": decision_brief,
            "status": AgentStatus.SUCCESS.value,
        }

    def _extra_security_gate_output(self, result: dict[str, Any]) -> dict[str, Any]:
        """S-3 hard gate — non-bypassable disposal-safety check (proposal Risk #1)."""
        decision_brief = result.get("result", {}) or {}
        recommendation = decision_brief.get("recommendation")

        for key, value in decision_brief.items():
            if isinstance(value, str) and any(marker in value for marker in _FORBIDDEN_INSTRUCTION_MARKERS):
                raise SecurityViolationError(
                    f"S-3: decision brief field {key!r} contains a deletion-execution or "
                    "retention-setting-change instruction — never permitted from this agent"
                )

        if recommendation == "proceed_to_disposal":
            # conflict_flags must be present in the brief itself (embedded by
            # decision_brief_draft/DecisionBriefService) — its absence is
            # treated as unresolved, never as an implicit "clean" pass,
            # per proposal Risk #1.
            if "conflict_flags" not in decision_brief:
                raise SecurityViolationError(
                    "S-3: proceed_to_disposal recommendation lacks a conflict-flag "
                    "result — cannot confirm the hold-registry check was clean"
                )
            if decision_brief["conflict_flags"]:
                raise SecurityViolationError(
                    "S-3: proceed_to_disposal recommendation blocked — active hold "
                    "conflicts present; must route for legal/privacy review instead"
                )

        return result
