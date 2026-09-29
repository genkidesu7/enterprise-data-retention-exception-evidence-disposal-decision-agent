"""AgentCore Platform v1.0"""

# Inner domain-workflow node (Cat 2). Drafts a cited recommendation via
# DecisionBriefService.

from __future__ import annotations

import asyncio
from typing import Any, ClassVar

from framework.nodes.function_node import FunctionNode
from framework.schemas.agent_status import AgentStatus
from framework.schemas.invocation_context import InvocationContext
from framework.schemas.trust_level import TrustLevel
from framework.secrets.base import NullProvider, SecretProvider
from shared.utils.audit_logger import emit_trace_event

from src.services.decision_brief_service import DecisionBriefService
from src.services.mock_mode import mock_mode_enabled


class DecisionBriefDraftNode(FunctionNode):
    """Draft a cited recommendation with approval routing.

    Reads: normalized_request, policy_metadata, conflict_flags, evidence_gaps.
    Writes: decision_brief, status.
    """

    required_trust_level: ClassVar[TrustLevel] = TrustLevel.VERIFIED_EXTERNAL

    def execute(self, state: dict[str, Any]) -> dict[str, Any]:
        normalized_request = state.get("normalized_request", {})
        policy_metadata = state.get("policy_metadata", {})
        conflict_flags = state.get("conflict_flags", [])
        evidence_gaps = state.get("evidence_gaps", [])

        # Mock mode short-circuits before any credential is required — building
        # InvocationContext from state also requires state's tracing fields
        # (correlation_id, etc.), which a mock unit test may not supply.
        credential_handle: SecretProvider
        if mock_mode_enabled():
            credential_handle = NullProvider()
        else:
            credential_handle = InvocationContext.from_state(state).secrets

        service = DecisionBriefService()
        try:
            decision_brief = asyncio.run(
                service.draft(normalized_request, policy_metadata, conflict_flags, evidence_gaps, credential_handle)
            )
        except Exception as exc:  # noqa: BLE001 — transient LLM synthesis failure
            return {
                "status": AgentStatus.RETRY.value,
                "error": str(exc),
                "error_log": [f"[RETRY] DecisionBriefDraftNode: {exc}"],
            }

        emit_trace_event(
            "decision_brief_drafted",
            {"recommendation": decision_brief.get("recommendation")},
            state,
        )

        return {
            "decision_brief": decision_brief,
            "status": AgentStatus.SUCCESS.value,
        }
