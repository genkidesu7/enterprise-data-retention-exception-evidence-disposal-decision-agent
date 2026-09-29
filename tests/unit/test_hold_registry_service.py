# CMN-C2-672 — Unit Tests: HoldRegistryService (permanently-mocked boundary)

import pytest

from src.services.hold_registry_service import HoldRegistryService


@pytest.mark.asyncio
async def test_check_returns_conclusive_hold_status():
    service = HoldRegistryService()
    result = await service.check({"record_type": "customer_records"})
    assert result["hold_status"] in ("clean", "conflict", "ambiguous")


@pytest.mark.asyncio
async def test_check_returns_mock_data_even_without_use_mock_set(monkeypatch):
    """Rule #2 (agenticstar-deploy skill): only the LLM call is ever real —
    this service never round-trips to a real hold registry, regardless of
    USE_MOCK/STG_MOCK_MODE."""
    monkeypatch.delenv("USE_MOCK", raising=False)
    monkeypatch.delenv("STG_MOCK_MODE", raising=False)
    service = HoldRegistryService()
    result = await service.check({"record_type": "customer_records"})
    assert result["hold_status"] in ("clean", "conflict", "ambiguous")
