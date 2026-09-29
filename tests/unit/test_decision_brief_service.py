# CMN-C2-672 — Unit Tests: DecisionBriefService (mock mode + real LLM boundary)

import os

import pytest
from framework.secrets.base import MissingSecret, NullProvider
from shared.secrets.inmemory_provider import InMemoryProvider

from src.services.decision_brief_service import DecisionBriefService


@pytest.fixture(autouse=True)
def _mock_mode():
    os.environ["USE_MOCK"] = "true"
    yield
    os.environ.pop("USE_MOCK", None)


@pytest.mark.asyncio
async def test_draft_returns_recommendation_and_citations():
    service = DecisionBriefService()
    result = await service.draft(
        {"record_type": "customer_records", "request_type": "exception"},
        {"stale": False},
        [],
        [],
        NullProvider(),
    )
    assert result["recommendation"] in ("approve_exception", "route_for_review", "proceed_to_disposal")
    assert len(result["citations"]) > 0


@pytest.mark.asyncio
async def test_conflicts_route_for_review_without_any_llm_call(monkeypatch):
    """Active conflicts/evidence gaps are decided deterministically — never the
    LLM's call — so this must short-circuit even with no credential and mock
    mode off (a real LLM round trip would otherwise require one)."""
    monkeypatch.delenv("USE_MOCK", raising=False)
    monkeypatch.delenv("STG_MOCK_MODE", raising=False)
    service = DecisionBriefService()
    result = await service.draft(
        {"record_type": "customer_records", "request_type": "disposal"},
        {"stale": False},
        [{"hold_status": "conflict"}],
        [],
        NullProvider(),
    )
    assert result["recommendation"] == "route_for_review"


@pytest.mark.asyncio
async def test_real_mode_without_secret_is_a_genuine_boundary(monkeypatch):
    """PB-3: the real (non-mock), no-conflict path must genuinely attempt the
    AzureOpenAIClient call and fail only for lack of a resolvable credential
    (MissingSecret), never a NotImplementedError stand-in."""
    monkeypatch.delenv("USE_MOCK", raising=False)
    monkeypatch.delenv("STG_MOCK_MODE", raising=False)
    service = DecisionBriefService()
    with pytest.raises(MissingSecret):
        await service.draft(
            {"record_type": "customer_records", "request_type": "exception"},
            {"stale": False},
            [],
            [],
            NullProvider(),
        )


@pytest.mark.asyncio
async def test_real_mode_calls_azure_openai_client(monkeypatch):
    """Real path actually constructs and calls AzureOpenAIClient (the
    agenticstar-deploy skill's REQUIRED LLM client) when credentials resolve —
    not a raw openai/langchain client, no hardcoded HTTP call."""
    monkeypatch.delenv("USE_MOCK", raising=False)
    monkeypatch.delenv("STG_MOCK_MODE", raising=False)

    captured = {}

    class _FakeAzureOpenAIClient:
        def __init__(self, config):
            captured["config"] = config

        def complete(self, messages):
            captured["messages"] = messages
            return {"content": '{"recommendation": "approve_exception"}'}

    import shared.services.llm.azure_openai_client as azure_openai_client_module

    monkeypatch.setattr(azure_openai_client_module, "AzureOpenAIClient", _FakeAzureOpenAIClient)

    credential_handle = InMemoryProvider(
        {
            "AZURE_OPENAI_API_KEY": "test-key",
            "AZURE_OPENAI_ENDPOINT": "https://example.openai.azure.com",
            "AZURE_OPENAI_DEPLOYMENT": "gpt-4o",
        }
    )
    service = DecisionBriefService()
    result = await service.draft(
        {"record_type": "customer_records", "request_type": "exception"},
        {"stale": False},
        [],
        [],
        credential_handle,
    )
    assert result["recommendation"] == "approve_exception"
    assert captured["config"]["api_key"] == "test-key"
    assert captured["config"]["azure_endpoint"] == "https://example.openai.azure.com"
    assert captured["config"]["azure_deployment"] == "gpt-4o"


@pytest.mark.asyncio
async def test_real_mode_rejects_unrecognized_llm_recommendation(monkeypatch):
    """An LLM response outside the allowed enum must raise (→ RETRY at the
    node level), never be passed through as a fabricated recommendation."""
    monkeypatch.delenv("USE_MOCK", raising=False)
    monkeypatch.delenv("STG_MOCK_MODE", raising=False)

    class _FakeAzureOpenAIClient:
        def __init__(self, config):
            pass

        def complete(self, messages):
            return {"content": '{"recommendation": "delete_everything"}'}

    import shared.services.llm.azure_openai_client as azure_openai_client_module

    monkeypatch.setattr(azure_openai_client_module, "AzureOpenAIClient", _FakeAzureOpenAIClient)

    credential_handle = InMemoryProvider(
        {
            "AZURE_OPENAI_API_KEY": "test-key",
            "AZURE_OPENAI_ENDPOINT": "https://example.openai.azure.com",
            "AZURE_OPENAI_DEPLOYMENT": "gpt-4o",
        }
    )
    service = DecisionBriefService()
    with pytest.raises(ValueError):
        await service.draft(
            {"record_type": "customer_records", "request_type": "exception"},
            {"stale": False},
            [],
            [],
            credential_handle,
        )
