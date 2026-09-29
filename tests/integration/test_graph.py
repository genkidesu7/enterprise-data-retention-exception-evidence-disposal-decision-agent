# CMN-C2-672 — Integration test: full outer→inner pipeline, mock mode

import os

import pytest

from framework.schemas.invocation_context import InvocationContext
from framework.schemas.trust_level import TrustLevel
from framework.secrets.base import NullProvider
from framework.secrets.context import bound_secrets


@pytest.fixture(autouse=True)
def _mock_mode():
    os.environ["USE_MOCK"] = "true"
    yield
    os.environ.pop("USE_MOCK", None)


def test_full_pipeline_invoke_succeeds():
    from src.graph.graph import RetentionExceptionDisposalAgent

    agent = RetentionExceptionDisposalAgent(config={"max_retry": 1})
    agent.compile()
    ctx = InvocationContext(caller_trust_level=TrustLevel.VERIFIED_EXTERNAL)

    result = agent.invoke(
        "Request to retain customer records past the default schedule pending litigation",
        ctx=ctx,
    )

    assert result["status"] == "success"
    assert result["output"]["recommendation"] in (
        "approve_exception",
        "route_for_review",
        "proceed_to_disposal",
    )
    assert "PreProcessNode" in result["node_history"]
    assert "RetentionDecisionWorkflowGraphNode" in result["node_history"]
    assert "PostProcessNode" in result["node_history"]


def test_real_mode_llm_failure_is_bounded_and_never_reported_as_success(monkeypatch):
    """Regression test for two bugs found wiring the real (non-mock) LLM path:

    1. The inner domain workflow graph was fully linear with no RETRY/ERROR
       checkpoint — a failed `decision_brief_draft` still let `output_validate`
       run next, which unconditionally reports SUCCESS with whatever (empty)
       `decision_brief` it was handed. A real LLM/credential failure must
       never be silently reported as a successful, empty decision.
    2. Nothing incremented `retry_count` on the outer RETRY→pre_process loop,
       so a genuine failure looped until LangGraph's recursion limit instead
       of respecting `config/config.yaml`'s `max_retry`.
    """
    monkeypatch.delenv("USE_MOCK", raising=False)
    monkeypatch.delenv("STG_MOCK_MODE", raising=False)

    from src.graph.graph import RetentionExceptionDisposalAgent

    agent = RetentionExceptionDisposalAgent(config={"max_retry": 2})
    agent.compile()
    agent.provision_secrets(NullProvider())

    with bound_secrets(NullProvider()):
        ctx = InvocationContext(caller_trust_level=TrustLevel.VERIFIED_EXTERNAL)
        result = agent.invoke(
            "Request to retain customer records past the default schedule pending litigation",
            ctx=ctx,
        )

    # Never a fabricated success — the missing AZURE_OPENAI_* credential must
    # surface as a non-success terminal status, not "success" with output={}.
    assert result["status"] != "success"
    assert "PostProcessNode" not in result["node_history"]
    # Bounded: with max_retry=2, pre_process runs at most 1 (initial) + 2 (retries).
    assert result["node_history"].count("PreProcessNode") <= 3
