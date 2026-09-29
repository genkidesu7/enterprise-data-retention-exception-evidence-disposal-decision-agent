# CMN-C2-672 — Unit Tests: RetentionPolicyService (permanently-mocked boundary)

import pytest

from src.services.retention_policy_service import RetentionPolicyService


@pytest.mark.asyncio
async def test_retrieve_returns_policy_metadata_with_stale_flag():
    service = RetentionPolicyService()
    result = await service.retrieve({"record_type": "customer_records"})
    assert "stale" in result
    assert "retention_schedule" in result


@pytest.mark.asyncio
async def test_retrieve_returns_mock_data_even_without_use_mock_set(monkeypatch):
    """Rule #2 (agenticstar-deploy skill): only the LLM call is ever real —
    this service never round-trips to a real retention-schedule store,
    regardless of USE_MOCK/STG_MOCK_MODE."""
    monkeypatch.delenv("USE_MOCK", raising=False)
    monkeypatch.delenv("STG_MOCK_MODE", raising=False)
    service = RetentionPolicyService()
    result = await service.retrieve({"record_type": "customer_records"})
    assert "stale" in result
    assert "retention_schedule" in result
