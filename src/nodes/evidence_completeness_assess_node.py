"""AgentCore Platform v1.0"""

# Inner domain-workflow node (Cat 2). Identifies missing evidence and
# conflicting obligations relative to policy. Pure logic, no external calls.

from __future__ import annotations

from typing import Any, ClassVar

from framework.nodes.function_node import FunctionNode
from framework.schemas.agent_status import AgentStatus
from framework.schemas.trust_level import TrustLevel
from shared.utils.audit_logger import emit_trace_event


class EvidenceCompletenessAssessNode(FunctionNode):
    """Identify missing evidence / conflicting obligations relative to policy.

    Reads: policy_metadata, conflict_flags.
    Writes: evidence_gaps, status.
    """

    required_trust_level: ClassVar[TrustLevel] = TrustLevel.VERIFIED_EXTERNAL

    def execute(self, state: dict[str, Any]) -> dict[str, Any]:
        policy_metadata = state.get("policy_metadata", {})
        conflict_flags = state.get("conflict_flags", [])
        # Preserve gaps flagged upstream (e.g. missing_business_justification
        # from request_normalize's S-2 extension) rather than discarding them.
        evidence_gaps = list(state.get("evidence_gaps", []))

        if policy_metadata.get("stale"):
            evidence_gaps.append("stale_policy_metadata")
        if not policy_metadata.get("retention_schedule"):
            evidence_gaps.append("missing_retention_schedule")
        if any(flag.get("hold_status") == "ambiguous" for flag in conflict_flags):
            evidence_gaps.append("ambiguous_hold_status")

        emit_trace_event(
            "evidence_gaps_identified",
            {"gap_count": len(evidence_gaps)},
            state,
        )

        return {
            "evidence_gaps": evidence_gaps,
            "status": AgentStatus.SUCCESS.value,
        }
