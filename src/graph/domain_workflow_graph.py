"""AgentCore Platform v1.0"""

# Inner graph for the Cat 2 domain workflow (evidence assembly + cited
# recommendation for a retention-exception/disposal request).
# Instantiated by RetentionDecisionWorkflowGraphNode.get_subgraph() in graph.py.
#
# Directory rule: src/graph/domain_workflow_graph.py is the ONLY accepted path.

from collections.abc import Callable
from typing import Any

from langgraph.graph import END, START

from framework.graph.base_graph import BaseGraph
from framework.schemas.agent_status import AgentStatus
from src.nodes.decision_brief_draft_node import DecisionBriefDraftNode
from src.nodes.evidence_completeness_assess_node import EvidenceCompletenessAssessNode
from src.nodes.hold_conflict_check_node import HoldConflictCheckNode
from src.nodes.output_validate_node import OutputValidateNode
from src.nodes.policy_metadata_retrieve_node import PolicyMetadataRetrieveNode
from src.nodes.request_normalize_node import RequestNormalizeNode
from src.schemas.state import State


class RetentionDecisionWorkflowGraph(BaseGraph):
    """Inner graph: assembles evidence and drafts a cited recommendation.

    Inherits BaseGraph directly — the 6 domain steps have custom names that
    don't correspond to the outer pre_process/main/post_process slots.

    Pipeline (linear, per docs/02_design.md Data Flow):
        START → request_normalize → policy_metadata_retrieve → hold_conflict_check
              → evidence_completeness_assess → decision_brief_draft → output_validate → END
    """

    @property
    def name(self) -> str:
        return "retention_decision_workflow"

    @property
    def state_schema(self) -> type:
        return State

    def _validate_config(self) -> None:
        """No mandatory config for this inner graph."""

    def register_nodes(self) -> None:
        """No super() call — BaseGraph.register_nodes() is abstract.

        Do NOT register initialize/finalize — outer backbone concern.
        """
        self._nodes["request_normalize"] = RequestNormalizeNode()
        self._nodes["policy_metadata_retrieve"] = PolicyMetadataRetrieveNode()
        self._nodes["hold_conflict_check"] = HoldConflictCheckNode()
        self._nodes["evidence_completeness_assess"] = EvidenceCompletenessAssessNode()
        self._nodes["decision_brief_draft"] = DecisionBriefDraftNode()
        self._nodes["output_validate"] = OutputValidateNode()

    def add_edges(self) -> None:
        """Wire the linear domain topology with a RETRY/ERROR checkpoint after
        every node (see `_checkpoint`) — a plain `add_edge` chain would let a
        downstream node run on a failed upstream state and, since each node
        only reports its OWN outcome, unconditionally overwrite the failure
        with its own SUCCESS (e.g. `output_validate` blindly reporting
        success with an empty decision brief after `decision_brief_draft`
        failed). Never reachable in mock mode — every mock stub always
        succeeds — but a real (non-mock) LLM/service failure must not be
        silently papered over.
        """
        self._sg.add_edge(START, "request_normalize")
        self._sg.add_conditional_edges("request_normalize", self._checkpoint("policy_metadata_retrieve"))
        self._sg.add_conditional_edges("policy_metadata_retrieve", self._checkpoint("hold_conflict_check"))
        self._sg.add_conditional_edges("hold_conflict_check", self._checkpoint("evidence_completeness_assess"))
        self._sg.add_conditional_edges("evidence_completeness_assess", self._checkpoint("decision_brief_draft"))
        self._sg.add_conditional_edges("decision_brief_draft", self._checkpoint("output_validate"))
        self._sg.add_edge("output_validate", END)

    @staticmethod
    def _checkpoint(next_node: str) -> Callable[["State"], str]:
        """Route to `next_node`, or straight to END if status is RETRY/ERROR.

        One checkpoint per edge (bound to that edge's own `next_node`) rather
        than a single shared `route()` — each edge needs a different
        "continue to" target, which a single-signature `route(state) -> str`
        cannot express.
        """

        def _route(state: State) -> str:
            if state.get("status") in (AgentStatus.RETRY.value, AgentStatus.ERROR.value):
                return END
            return next_node

        return _route

    def route(self, state: State) -> str:
        """Required by BaseGraph ABC. Not used for edge wiring — every edge
        here has its own `_checkpoint(next_node)` — kept as an exhaustive,
        generically-correct implementation of the ABC contract.
        """
        return END if state.get("status") in (AgentStatus.RETRY.value, AgentStatus.ERROR.value) else "output_validate"

    def get_output(self, state: State) -> dict[str, Any]:
        """Shape the sub_result dict returned to the outer GraphNode.

        Designed together with RetentionDecisionWorkflowGraphNode.merge_output()
        in graph.py. Annotated with State, not AgentState (same rule as route()).
        """
        return {
            "output": state.get("result"),
            "status": state.get("status"),
            "trace_id": state.get("trace_id"),
            "correlation_id": state.get("correlation_id"),
            "node_history": state.get("node_history", []),
        }
