"""AgentCore Platform v1.0"""

# Mock stub functions for local/CI mock-mode runs. Never touches a real
# credential_handle — mock mode must succeed with zero secrets bound.

from __future__ import annotations

from typing import Any


async def stub_retention_policy_lookup(normalized_request: dict[str, Any]) -> dict[str, Any]:
    """Stubbed retention-schedule / classification / SoR metadata lookup."""
    return {
        "retention_schedule": {
            "record_type": normalized_request.get("record_type", "unknown"),
            "retention_years": 5,
        },
        "data_classification": "internal",
        "system_of_record_metadata": {"source": "mock-sor", "last_updated": "2026-01-01"},
        "stale": False,
    }


async def stub_hold_registry_lookup(normalized_request: dict[str, Any]) -> dict[str, Any]:
    """Stubbed legal-hold notice registry lookup."""
    return {"hold_status": "clean", "active_holds": []}


async def stub_decision_brief_synthesis(
    normalized_request: dict[str, Any],
    policy_metadata: dict[str, Any],
    conflict_flags: list[dict[str, Any]],
    evidence_gaps: list[str],
) -> dict[str, Any]:
    """Stubbed cited-recommendation synthesis."""
    if conflict_flags or evidence_gaps:
        recommendation = "route_for_review"
    else:
        recommendation = (
            "approve_exception" if normalized_request.get("request_type") == "exception" else "proceed_to_disposal"
        )
    return {
        "recommendation": recommendation,
        "citations": ["mock-retention-schedule", "mock-hold-registry"],
        "routing": "records_management_reviewer",
        "conflict_flags": conflict_flags,
    }
