# CMN-C2-672 — Integration test: /invoke over a real ASGI transport (async route boundary)
#
# Regression test: agent.invoke() is sync and its nodes call asyncio.run() internally.
# Calling it directly from an async route (without to_thread) raises "asyncio.run()
# cannot be called from a running event loop" inside the node, which the node's
# except-Exception silently turns into status: "error" — a 200 response with no
# visible crash. An in-process sync call to agent.invoke() never exercises this path;
# only driving the ASGI app on a real event loop reproduces it.

import os
import secrets

import pytest
from httpx import ASGITransport, AsyncClient


@pytest.fixture(autouse=True)
def _mock_and_auth_env():
    os.environ["USE_MOCK"] = "true"
    token = secrets.token_urlsafe(32)
    os.environ["INVOKE_AUTH_TOKEN"] = token
    yield token
    os.environ.pop("USE_MOCK", None)
    os.environ.pop("INVOKE_AUTH_TOKEN", None)


@pytest.mark.asyncio
async def test_invoke_endpoint_succeeds_over_http(_mock_and_auth_env):
    token = _mock_and_auth_env
    from src.api.server import app

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/invoke",
            json={"input": "Request to retain customer records past schedule pending litigation"},
            headers={"Authorization": f"Bearer {token}"},
        )

    assert resp.status_code == 200
    assert resp.json()["status"] == "success"


@pytest.mark.asyncio
async def test_health_endpoint_over_http():
    from src.api.server import app

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/health")

    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"
