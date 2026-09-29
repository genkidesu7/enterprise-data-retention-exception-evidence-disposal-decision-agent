"""AgentCore Platform v1.0"""

# ADR-005: State must be a flat TypedDict (see ADR-005 for the prohibited
# alternatives). LangGraph checkpoints use msgpack serialization, so only
# plain serializable fields are allowed. Do NOT add credentials or secrets.

from typing import Any

from framework.schemas.agent_state import AgentState


class State(AgentState):
    """Agent state.

    Add only fields specific to this agent below.
    All shared fields (user_input, status, session_id, node_history,
    error_log, hitl_*, etc.) are inherited from AgentState.
    """

    normalized_request: dict[str, Any]
    policy_metadata: dict[str, Any]
    conflict_flags: list[dict[str, Any]]
    evidence_gaps: list[str]
    decision_brief: dict[str, Any]
    result: dict[str, Any]
    formatted_output: dict[str, Any]
