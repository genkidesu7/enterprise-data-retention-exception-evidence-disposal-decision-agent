# CMN-C2-672 — Unit Tests: RetentionDecisionWorkflowGraph checkpoint routing

import pytest

from framework.schemas.invocation_context import InvocationContext
from framework.schemas.trust_level import TrustLevel
from framework.secrets.base import NullProvider
from framework.secrets.context import bound_secrets
from src.graph.domain_workflow_graph import RetentionDecisionWorkflowGraph


@pytest.fixture(autouse=True)
def _mock_mode(monkeypatch):
    monkeypatch.setenv("USE_MOCK", "true")


def test_mock_mode_reaches_output_validate():
    graph = RetentionDecisionWorkflowGraph(config={})
    graph.compile()
    with bound_secrets(NullProvider()):
        ctx = InvocationContext(caller_trust_level=TrustLevel.VERIFIED_EXTERNAL)
        result = graph.invoke(
            "Request to retain customer records past the default schedule pending litigation",
            ctx=ctx,
        )
    assert result["status"] == "success"
    assert "OutputValidateNode" in result["node_history"]


def test_llm_failure_short_circuits_before_output_validate(monkeypatch):
    """A RETRY from decision_brief_draft must stop the pipeline immediately —
    output_validate must never run on a failed upstream state and report a
    fabricated success with an empty decision brief."""
    monkeypatch.delenv("USE_MOCK", raising=False)
    monkeypatch.delenv("STG_MOCK_MODE", raising=False)

    graph = RetentionDecisionWorkflowGraph(config={})
    graph.compile()
    with bound_secrets(NullProvider()):
        ctx = InvocationContext(caller_trust_level=TrustLevel.VERIFIED_EXTERNAL)
        result = graph.invoke(
            "Request to retain customer records past the default schedule pending litigation",
            ctx=ctx,
        )
    assert result["status"] == "retry"
    assert "OutputValidateNode" not in result["node_history"]
    assert result["node_history"][-1] == "DecisionBriefDraftNode"
