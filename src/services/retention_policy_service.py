"""AgentCore Platform v1.0"""

# Service layer: RAG retrieval against the retention-schedule store, data
# classification registry, and system-of-record metadata.
# Must NOT contain business logic, routing, or credentials.
# Nodes call this; this calls shared/services/ for external integrations.

from __future__ import annotations

from typing import Any


class RetentionPolicyService:
    """Retrieves retention schedule, data classification, and SoR metadata.

    Per agenticstar-deploy skill hard rule #2 ("every service other than the
    LLM call defaults to mock, including in real/non-mock mode — only the LLM
    call is ever real"), this is a permanently-mocked boundary: it never
    round-trips to a real retention-schedule store, regardless of USE_MOCK.
    Wiring an actual retention-schedule/classification/SoR source is future
    work tracked separately from this agent's LLM synthesis path.

    Usage from a node::

        service = RetentionPolicyService()
        metadata = await service.retrieve(normalized_request)
    """

    async def retrieve(self, normalized_request: dict[str, Any]) -> dict[str, Any]:
        """Retrieve applicable policy and metadata for a normalized request.

        Args:
            normalized_request: Parsed request (record type, request type, justification).

        Returns:
            Policy/metadata dict including a `stale` freshness flag.
        """
        from src.services.mock_data import stub_retention_policy_lookup

        return await stub_retention_policy_lookup(normalized_request)
