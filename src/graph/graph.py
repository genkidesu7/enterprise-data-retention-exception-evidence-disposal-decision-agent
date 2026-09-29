"""AgentCore Platform v1.0"""

# Cat 2 — AgentBaseGraph (outer) + GraphNode wrapping an inner BaseGraph.
#
# Outer backbone (fixed, framework-owned):
#   START → initialize → pre_process → main → {route} → post_process → finalize → END
#                                          ↓ (RETRY, max 3)
#                                       pre_process
#
# Domain complexity (evidence assembly + cited recommendation) lives entirely
# inside the `main` slot via RetentionDecisionWorkflowGraphNode, which wraps
# the inner graph at src/graph/domain_workflow_graph.py.

from typing import TYPE_CHECKING, Any, ClassVar

from framework.graph.agent_base_graph import AgentBaseGraph
from framework.nodes.graph_node import GraphNode
from framework.schemas.agent_state import AgentState
from src.nodes.post_process_node import PostProcessNode
from src.nodes.pre_process_node import PreProcessNode
from src.schemas.state import State

if TYPE_CHECKING:
    from src.graph.domain_workflow_graph import RetentionDecisionWorkflowGraph


class RetentionDecisionWorkflowGraphNode(GraphNode):
    """Wraps the inner retention-decision workflow graph; assigned to `main`."""

    error_strategy: ClassVar[str] = "propagate"
    propagate_hitl: ClassVar[bool] = False

    def get_subgraph(self) -> "RetentionDecisionWorkflowGraph":
        """Instantiate and return the inner domain workflow graph."""
        from src.graph.domain_workflow_graph import RetentionDecisionWorkflowGraph

        return RetentionDecisionWorkflowGraph(config=self._parent_config())

    def extract_input(self, state: AgentState) -> str:
        """Return the string user_input to pass into inner_graph.invoke()."""
        return str(state.get("validated_input", state.get("user_input", "")))

    def merge_output(self, state: AgentState, sub_result: dict[str, Any]) -> dict[str, Any]:
        """Map inner graph sub_result fields back into the outer state.

        Returns only the keys this node changes — never the full state.
        """
        return {
            "result": sub_result.get("output"),
            "status": sub_result.get("status"),
        }

    def _parent_config(self) -> dict[str, Any]:
        """No config keys need forwarding to the inner graph currently."""
        return {}


class RetentionExceptionDisposalAgent(AgentBaseGraph):
    """Enterprise Data Retention Exception Evidence & Disposal Decision Agent.

    Cat 2 outer graph. Domain logic is encapsulated in
    RetentionDecisionWorkflowGraphNode (`main` slot).
    Backbone: initialize → pre_process → main → post_process → finalize (fixed).
    """

    @property
    def name(self) -> str:
        return "retention_exception_disposal_agent"

    @property
    def state_schema(self) -> type:
        return State

    def register_nodes(self) -> None:
        super().register_nodes()  # injects InitializeNode + FinalizeNode
        self._nodes["pre_process"] = PreProcessNode()
        self._nodes["main"] = RetentionDecisionWorkflowGraphNode()
        self._nodes["post_process"] = PostProcessNode()

    # add_edges() is NOT overridden — backbone wiring belongs to the framework.
