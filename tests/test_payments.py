"""Tests for x402 payment middleware."""

import json
from unittest.mock import AsyncMock

import httpx
import pytest

from levra.api import app


@pytest.mark.asyncio
async def test_unpaid_post_spec_returns_402(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        resp = await c.post("/spec", json={"thesis": "Long ETH 30d moderate $2000"})
    assert resp.status_code == 402
    body = resp.json()
    assert "payment" in body


@pytest.mark.asyncio
async def test_valid_payment_proof_proceeds_to_handler(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")

    import respx

    def _tool_call_block(name: str, arguments: dict):
        block = AsyncMock()
        block.function = AsyncMock()
        block.function.name = name
        block.function.arguments = json.dumps(arguments)
        return block

    mock_llm = AsyncMock()
    idx = [0]
    responses = [
        {
            "asset": "ETH",
            "direction": "LONG",
            "horizon_days": 30,
            "conviction": "MODERATE",
            "capital_usd": 2000,
        },
        {"bull": "a", "base": "b", "bear": "c"},
    ]

    async def create(*args, **kwargs):
        choice = AsyncMock()
        choice.message = AsyncMock()
        name = "extract_thesis" if idx[0] == 0 else "narrate_scenarios"
        choice.message.tool_calls = [_tool_call_block(name, responses[idx[0]])]
        idx[0] += 1
        resp = AsyncMock()
        resp.choices = [choice]
        return resp

    mock_llm.chat.completions.create = create
    monkeypatch.setattr("levra.api.build_llm_client", lambda: mock_llm)

    base_ts = 1756656000
    data = []
    for i in range(30):
        ts = base_ts + (29 - i) * 14400
        low = "3190" if i == 7 else ("3150" if i == 13 else "3300")
        data.append([str(ts * 1000), "3420", "3420", low, "3310", "100", "330000", "330000", "1"])

    with respx.mock(base_url="https://www.okx.com", assert_all_called=False) as rx:
        rx.get("/api/v5/market/candles").respond(json={"code": "0", "data": data})
        rx.get("/api/v5/market/ticker").respond(json={"code": "0", "data": [{"last": "3300"}]})
        rx.get("/api/v5/public/funding-rate").respond(
            json={"code": "0", "data": [{"fundingRate": "0.0001"}]}
        )
        rx.get("/api/v5/public/position-tiers").respond(
            json={"code": "0", "data": [{"mmr": "0.005"}]}
        )

        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
            resp = await c.post(
                "/spec",
                json={"thesis": "Long ETH 30d moderate $2000"},
                headers={"PAYMENT-SIGNATURE": "0x" + "aa" * 32},
            )
        rx.stop()

    assert resp.status_code == 200
    body = resp.json()
    assert body["asset"] == "ETH"


@pytest.mark.asyncio
async def test_invalid_payment_proof_returns_402(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        resp = await c.post(
            "/spec",
            json={"thesis": "Long ETH"},
            headers={"PAYMENT-SIGNATURE": "bad"},
        )
    assert resp.status_code == 402


@pytest.mark.asyncio
async def test_health_stays_free(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        resp = await c.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


@pytest.mark.asyncio
async def test_health_stays_free_without_payment_header(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        resp = await c.get("/health")
    assert resp.status_code == 200