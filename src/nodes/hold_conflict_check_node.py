"""AgentCore Platform v1.0"""

# Inner domain-workflow node (Cat 2). Checks the request against active
# legal-hold notices via HoldRegistryService.

from __future__ import annotations

import asyncio
from typing import Any, ClassVar

from framework.nodes.function_node import FunctionNode
from framework.schemas.agent_status import AgentStatus
from framework.schemas.trust_level import TrustLevel
from shared.utils.audit_logger import emit_trace_event

from src.services.hold_registry_service import HoldRegistryService


class HoldConflictCheckNode(FunctionNode):
    """Check the request against active legal-hold notices.

    Reads: normalized_request.
    Writes: conflict_flags, status.
    """

    required_trust_level: ClassVar[TrustLevel] = TrustLevel.VERIFIED_EXTERNAL

    def execute(self, state: dict[str, Any]) -> dict[str, Any]:
        normalized_request = state.get("normalized_request", {})

        # HoldRegistryService is a permanently-mocked boundary (agenticstar-deploy
        # skill hard rule #2 — only the LLM call is ever real), so no credential is
        # ever required here.
        service = HoldRegistryService()
        try:
            hold_result = asyncio.run(service.check(normalized_request))
        except Exception as exc:  # noqa: BLE001 — transient registry failure
            return {
                "status": AgentStatus.RETRY.value,
                "error": str(exc),
                "error_log": [f"[RETRY] HoldConflictCheckNode: {exc}"],
            }

        hold_status = hold_result.get("hold_status", "ambiguous")
        conflict_flags = [{"hold_status": hold_status, **hold} for hold in hold_result.get("active_holds", [])]
        if hold_status != "clean" and not conflict_flags:
            # Ambiguous/conflict status with no itemized hold still counts as a
            # flag — never silently treated as clean (proposal Risk #1).
            conflict_flags = [{"hold_status": hold_status}]

        emit_trace_event(
            "hold_conflict_checked",
            {"hold_status": hold_status, "conflict_count": len(conflict_flags)},
            state,
        )

        return {
            "conflict_flags": conflict_flags,
            "status": AgentStatus.SUCCESS.value,
        }
