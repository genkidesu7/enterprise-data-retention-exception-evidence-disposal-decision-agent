"""AgentCore Platform v1.0"""

# Inner domain-workflow node (Cat 2). Retrieves retention schedule, data
# classification, and system-of-record metadata via RetentionPolicyService.

from __future__ import annotations

import asyncio
from typing import Any, ClassVar

from framework.nodes.function_node import FunctionNode
from framework.schemas.agent_status import AgentStatus
from framework.schemas.trust_level import TrustLevel
from shared.utils.audit_logger import emit_trace_event

from src.services.retention_policy_service import RetentionPolicyService


class PolicyMetadataRetrieveNode(FunctionNode):
    """RAG retrieval of retention schedule / classification / SoR metadata.

    Reads: normalized_request.
    Writes: policy_metadata, status.
    """

    required_trust_level: ClassVar[TrustLevel] = TrustLevel.VERIFIED_EXTERNAL

    def execute(self, state: dict[str, Any]) -> dict[str, Any]:
        normalized_request = state.get("normalized_request", {})

        # RetentionPolicyService is a permanently-mocked boundary (agenticstar-deploy
        # skill hard rule #2 — only the LLM call is ever real), so no credential is
        # ever required here.
        service = RetentionPolicyService()
        try:
            policy_metadata = asyncio.run(service.retrieve(normalized_request))
        except Exception as exc:  # noqa: BLE001 — transient retrieval failure
            return {
                "status": AgentStatus.RETRY.value,
                "error": str(exc),
                "error_log": [f"[RETRY] PolicyMetadataRetrieveNode: {exc}"],
            }

        emit_trace_event(
            "policy_metadata_retrieved",
            {"stale": policy_metadata.get("stale", False)},
            state,
        )

        return {
            "policy_metadata": policy_metadata,
            "status": AgentStatus.SUCCESS.value,
        }
