import json
from decimal import Decimal
from unittest.mock import AsyncMock

import httpx
import pytest
import respx

from levra.api import app
from levra.constants import FUNDING_ASSUMPTION_DISCLOSURE, RISK_RULE_DISCLOSURE

OKX_BASE = "https://www.okx.com"


def _make_candle_data():
    base_ts = 1756656000
    data = []
    for i in range(30):
        ts = base_ts + (29 - i) * 14400
        low = "3190" if i == 7 else ("3150" if i == 13 else "3300")
        data.append([str(ts * 1000), "3420", "3420", low, "3310", "100", "330000", "330000", "1"])
    return data


CANDLE_DATA = _make_candle_data()


def _tool_call_block(name: str, arguments: dict):
    block = AsyncMock()
    block.function = AsyncMock()
    block.function.name = name
    block.function.arguments = json.dumps(arguments)
    return block


def _make_llm_mock(responses):
    client = AsyncMock()
    idx = [0]

    async def create(*args, **kwargs):
        choice = AsyncMock()
        choice.message = AsyncMock()
        if idx[0] < len(responses):
            choice.message.tool_calls = [
                _tool_call_block(
                    "extract_thesis" if idx[0] == 0 else "narrate_scenarios",
                    responses[idx[0]],
                )
            ]
            idx[0] += 1
        else:
            choice.message.tool_calls = None
        resp = AsyncMock()
        resp.choices = [choice]
        return resp

    client.chat.completions.create = create
    return client


PARSER_INPUT = {
    "asset": "ETH",
    "direction": "LONG",
    "horizon_days": 30,
    "conviction": "MODERATE",
    "capital_usd": 2000,
}

NARRATOR_INPUT = {
    "bull": "Price runs to $4,000 as momentum builds.",
    "base": "Gradual climb into September, funding costs manageable.",
    "bear": "Swing low at $3,190 breaks, stop triggered at a small loss.",
}


def _mock_okx_respx(assert_all_called=True):
    rx = respx.mock(base_url=OKX_BASE, assert_all_called=assert_all_called)
    rx.get("/api/v5/market/candles").respond(
        json={"code": "0", "data": CANDLE_DATA}
    )
    rx.get("/api/v5/market/ticker").respond(
        json={"code": "0", "data": [{"last": "3300"}]}
    )
    rx.get("/api/v5/public/funding-rate").respond(
        json={"code": "0", "data": [{"fundingRate": "0.0001"}]}
    )
    rx.get("/api/v5/public/position-tiers").respond(
        json={"code": "0", "data": [{"mmr": "0.005"}]}
    )
    return rx


@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")


PAYMENT_HEADER = {"PAYMENT-SIGNATURE": "0x" + "aa" * 32}
_THESIS = {"thesis": "Long ETH 30d moderate $2000"}


def _client_with_mocks(monkeypatch, llm_responses):
    mock_llm = _make_llm_mock(llm_responses)
    monkeypatch.setattr("levra.api.build_llm_client", lambda: mock_llm)
    return mock_llm


@pytest.mark.asyncio
async def test_post_spec_returns_200_and_every_field(monkeypatch):
    with _mock_okx_respx():
        _client_with_mocks(monkeypatch, [PARSER_INPUT, NARRATOR_INPUT])
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
            resp = await c.post("/spec", json=_THESIS, headers=PAYMENT_HEADER)
    assert resp.status_code == 200
    body = resp.json()
    assert body["asset"] == "ETH"
    assert body["direction"] == "long"
    assert "entry_zone" in body
    assert "stop" in body
    assert "stop_rationale" in body
    assert "position_size" in body
    assert "notional" in body
    assert "risk_amount" in body
    assert "leverage" in body
    assert "liquidation_price" in body
    assert "liquidation_buffer_ratio" in body
    assert "funding_cost" in body
    assert "scenarios" in body


@pytest.mark.asyncio
async def test_numeric_fields_are_strings(monkeypatch):
    with _mock_okx_respx():
        _client_with_mocks(monkeypatch, [PARSER_INPUT, NARRATOR_INPUT])
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
            resp = await c.post("/spec", json=_THESIS, headers=PAYMENT_HEADER)
    body = resp.json()
    for field in [
        "position_size", "notional", "risk_amount", "leverage",
        "liquidation_price", "liquidation_buffer_ratio",
        "funding_cost", "funding_rate", "stop",
    ]:
        assert isinstance(body[field], str), f"{field} is not a string, got {type(body[field])}"
        Decimal(body[field])


@pytest.mark.asyncio
async def test_disclosures_are_verbatim(monkeypatch):
    with _mock_okx_respx():
        _client_with_mocks(monkeypatch, [PARSER_INPUT, NARRATOR_INPUT])
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
            resp = await c.post("/spec", json=_THESIS, headers=PAYMENT_HEADER)
    body = resp.json()
    assert body["risk_rule"] == RISK_RULE_DISCLOSURE
    assert body["funding_assumption"] == FUNDING_ASSUMPTION_DISCLOSURE


@pytest.mark.asyncio
async def test_stop_rationale_mentions_lookback(monkeypatch):
    with _mock_okx_respx():
        _client_with_mocks(monkeypatch, [PARSER_INPUT, NARRATOR_INPUT])
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
            resp = await c.post("/spec", json=_THESIS, headers=PAYMENT_HEADER)
    body = resp.json()
    assert "4H candles" in body["stop_rationale"]


@pytest.mark.asyncio
async def test_unsupported_asset_returns_422(monkeypatch):
    with _mock_okx_respx(assert_all_called=False):
        _client_with_mocks(monkeypatch, [dict(PARSER_INPUT, asset="SOL"), NARRATOR_INPUT])
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
            resp = await c.post("/spec", json={"thesis": "Long SOL"}, headers=PAYMENT_HEADER)
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_okx_outage_returns_502(monkeypatch):
    with respx.mock(base_url=OKX_BASE) as rx:
        rx.get("/api/v5/market/candles").respond(503)
        rx.get("/api/v5/market/ticker").respond(503)
        rx.get("/api/v5/public/funding-rate").respond(503)
        rx.get("/api/v5/public/position-tiers").respond(503)
        _client_with_mocks(monkeypatch, [PARSER_INPUT, NARRATOR_INPUT])
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
            resp = await c.post("/spec", json=_THESIS, headers=PAYMENT_HEADER)
    assert resp.status_code == 502


@pytest.mark.asyncio
async def test_empty_thesis_returns_422(monkeypatch):
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        resp = await c.post("/spec", json={"thesis": ""}, headers=PAYMENT_HEADER)
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_health_returns_200():
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        resp = await c.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}
