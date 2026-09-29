"""AgentCore Platform v1.0"""

# Service layer: LLM-backed synthesis of a cited retention/disposal
# recommendation from policy metadata, conflict flags, and evidence gaps.
# Must NOT contain business logic, routing, or credentials.
# Nodes call this; this calls shared/services/ for external integrations.
#
# This is the one service in this agent whose real (non-mock) path is ever
# real (agenticstar-deploy skill hard rule #2) — RetentionPolicyService and
# HoldRegistryService are permanently-mocked boundaries; only this LLM call
# round-trips to a real provider when mock mode is off.

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

from src.services.mock_mode import mock_mode_enabled

if TYPE_CHECKING:
    from framework.secrets.base import SecretProvider

_ALLOWED_RECOMMENDATIONS = ("approve_exception", "proceed_to_disposal")


class DecisionBriefService:
    """Synthesizes a cited recommendation for a retention/disposal request.

    Usage from a node::

        service = DecisionBriefService()
        brief = await service.draft(
            normalized_request, policy_metadata, conflict_flags, evidence_gaps, credential_handle
        )
    """

    async def draft(
        self,
        normalized_request: dict[str, Any],
        policy_metadata: dict[str, Any],
        conflict_flags: list[dict[str, Any]],
        evidence_gaps: list[str],
        credential_handle: "SecretProvider",
    ) -> dict[str, Any]:
        """Draft a cited recommendation.

        Args:
            normalized_request: Parsed request.
            policy_metadata: Retention schedule / classification / SoR metadata.
            conflict_flags: Legal-hold conflicts identified for this request.
            evidence_gaps: Missing evidence / unresolved obligations.
            credential_handle: `InvocationContext.secrets` `SecretProvider`. Only read
                (via `.require(...)`) on the real (non-mock) path — never logged/stored.

        Returns:
            Dict with `recommendation` (one of "approve_exception",
            "route_for_review", "proceed_to_disposal"), `citations`, `routing`,
            and `conflict_flags`.
        """
        if conflict_flags or evidence_gaps:
            # Deterministic — never the LLM's call. Active conflicts/gaps always
            # route for review, mock or real, with no LLM round trip needed.
            return {
                "recommendation": "route_for_review",
                "citations": ["retention-schedule", "hold-registry"],
                "routing": "records_management_reviewer",
                "conflict_flags": conflict_flags,
            }

        if mock_mode_enabled():
            from src.services.mock_data import stub_decision_brief_synthesis

            return await stub_decision_brief_synthesis(
                normalized_request, policy_metadata, conflict_flags, evidence_gaps
            )

        recommendation = call_llm_recommendation(normalized_request, policy_metadata, credential_handle)
        return {
            "recommendation": recommendation,
            "citations": ["retention-schedule", "hold-registry"],
            "routing": "records_management_reviewer",
            "conflict_flags": conflict_flags,
        }


def _build_recommendation_prompt(normalized_request: dict[str, Any], policy_metadata: dict[str, Any]) -> str:
    """Compose the LLM prompt for the approve/dispose decision.

    Only reachable with no active hold conflicts and no evidence gaps —
    `route_for_review` is always decided deterministically before this is called.
    """
    return (
        "You are assisting a records-governance reviewer with a retention-exception or "
        "disposal request. There are no active legal-hold conflicts and no evidence gaps. "
        "Decide whether to approve a time-bound retention exception or proceed to disposal, "
        "based on the request and retention policy metadata below.\n\n"
        f"Request: {json.dumps(normalized_request)}\n\n"
        f"Retention policy metadata: {json.dumps(policy_metadata)}\n\n"
        'Respond with ONLY a JSON object of the exact shape {"recommendation": '
        '"approve_exception"} or {"recommendation": "proceed_to_disposal"} — no other text.'
    )


def call_llm_recommendation(
    normalized_request: dict[str, Any],
    policy_metadata: dict[str, Any],
    credential_handle: "SecretProvider",
) -> str:
    """The one place `AzureOpenAIClient` is constructed (agenticstar-deploy skill).

    `credential_handle` is the `InvocationContext.secrets` `SecretProvider` —
    credentials are always resolved via `.require(...)`, never `os.environ`.
    Raises on a malformed/unrecognized LLM response so the caller's RETRY
    handling applies, the same as any other transient synthesis failure.
    """
    from shared.services.llm.azure_openai_client import AzureOpenAIClient

    api_key = credential_handle.require("AZURE_OPENAI_API_KEY")
    azure_endpoint = credential_handle.require("AZURE_OPENAI_ENDPOINT")
    azure_deployment = credential_handle.require("AZURE_OPENAI_DEPLOYMENT")

    client = AzureOpenAIClient(
        config={
            "api_key": api_key,
            "azure_endpoint": azure_endpoint,
            "azure_deployment": azure_deployment,
        }
    )
    prompt = _build_recommendation_prompt(normalized_request, policy_metadata)
    content = str(client.complete([{"role": "user", "content": prompt}])["content"])

    parsed = json.loads(content)
    recommendation = parsed["recommendation"]
    if recommendation not in _ALLOWED_RECOMMENDATIONS:
        raise ValueError(f"LLM returned an unrecognized recommendation: {recommendation!r}")
    return str(recommendation)
