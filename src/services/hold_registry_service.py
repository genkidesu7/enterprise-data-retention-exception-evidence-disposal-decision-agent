"""AgentCore Platform v1.0"""

# Service layer: queries the legal-hold notice registry for active holds
# matching a normalized request.
# Must NOT contain business logic, routing, or credentials.
# Nodes call this; this calls shared/services/ for external integrations.

from __future__ import annotations

from typing import Any


class HoldRegistryService:
    """Checks a normalized request against active legal-hold notices.

    Per agenticstar-deploy skill hard rule #2 ("every service other than the
    LLM call defaults to mock, including in real/non-mock mode — only the LLM
    call is ever real"), this is a permanently-mocked boundary: it never
    round-trips to a real hold-registry, regardless of USE_MOCK. Wiring an
    actual hold-registry source is future work tracked separately from this
    agent's LLM synthesis path.

    Usage from a node::

        service = HoldRegistryService()
        conflicts = await service.check(normalized_request)
    """

    async def check(self, normalized_request: dict[str, Any]) -> dict[str, Any]:
        """Check the request against the legal-hold notice registry.

        Args:
            normalized_request: Parsed request (record type, request type, justification).

        Returns:
            Dict with `hold_status` ("clean" | "conflict" | "ambiguous") and
            `active_holds` list. Never silently defaults ambiguous data to "clean".
        """
        from src.services.mock_data import stub_hold_registry_lookup

        return await stub_hold_registry_lookup(normalized_request)
