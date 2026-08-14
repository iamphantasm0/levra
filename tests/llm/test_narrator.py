import copy
import inspect
import json
from unittest.mock import AsyncMock

import pytest

from levra.errors import NarrationFailed
from levra.llm.narrator import narrate
from levra.models import PositionSpec, Scenarios


def _tool_call_block(name: str, arguments: dict) -> AsyncMock:
    block = AsyncMock()
    block.function = AsyncMock()
    block.function.name = name
    block.function.arguments = json.dumps(arguments)
    return block


def _mock_response(tool_calls: list) -> AsyncMock:
    choice = AsyncMock()
    choice.message = AsyncMock()
    choice.message.tool_calls = tool_calls
    resp = AsyncMock()
    resp.choices = [choice]
    return resp


def _mock_client(response):
    client = AsyncMock()
    client.chat.completions.create = AsyncMock(return_value=response)
    return client


def _make_spec() -> PositionSpec:
    from datetime import UTC, datetime
    from decimal import Decimal

    from levra.engine.build import build_spec
    from levra.models import (
        Candle,
        Conviction,
        Direction,
        MarketSnapshot,
        Thesis,
    )

    start = datetime(2026, 8, 1, tzinfo=UTC)
    lows = ["3200", "3180", "3150", "3180", "3205", "3210", "3190", "3205", "3215"]
    candles = tuple(
        Candle(
            ts=start.replace(hour=(i * 4) % 24, day=1 + (i * 4) // 24),
            open=Decimal(low),
            high=Decimal(low) + Decimal("120"),
            low=Decimal(low),
            close=Decimal(low) + Decimal("60"),
            confirmed=True,
        )
        for i, low in enumerate(lows)
    )
    snapshot = MarketSnapshot(
        asset="ETH",
        mark_price=Decimal("3300"),
        candles=candles,
        funding_rate=Decimal("0.0001"),
        funding_interval_hours=8,
        maintenance_margin_rate=Decimal("0.005"),
        fetched_at=start,
    )
    thesis = Thesis(
        asset="ETH",
        direction=Direction.LONG,
        horizon_days=30,
        conviction=Conviction.MODERATE,
        capital=Decimal("2000"),
        raw_text="Long ETH 30d moderate $2000",
    )
    return build_spec(thesis, snapshot)


VALID_SCENARIOS = {
    "bull": "Price rallies strongly through resistance.",
    "base": "Price consolidates, modest grind upward.",
    "bear": "Stop triggered on a swing-low break.",
}


class TestNarrate:
    async def test_mocked_response_maps_to_scenarios(self):
        client = _mock_client(
            _mock_response([_tool_call_block("narrate_scenarios", VALID_SCENARIOS)])
        )
        spec = _make_spec()
        scenarios = await narrate(spec, client)
        assert scenarios.bull == "Price rallies strongly through resistance."
        assert scenarios.base == "Price consolidates, modest grind upward."
        assert scenarios.bear == "Stop triggered on a swing-low break."

    async def test_spec_not_mutated(self):
        client = _mock_client(
            _mock_response([_tool_call_block("narrate_scenarios", VALID_SCENARIOS)])
        )
        spec = _make_spec()
        pre_call = copy.deepcopy(spec)
        await narrate(spec, client)
        assert spec == pre_call

    async def test_returned_fields_are_all_str(self):
        client = _mock_client(
            _mock_response([_tool_call_block("narrate_scenarios", VALID_SCENARIOS)])
        )
        spec = _make_spec()
        result = await narrate(spec, client)
        assert isinstance(result.bull, str)
        assert isinstance(result.base, str)
        assert isinstance(result.bear, str)

    async def test_missing_bear_raises(self):
        inp = {"bull": "a", "base": "b"}
        client = _mock_client(
            _mock_response([_tool_call_block("narrate_scenarios", inp)])
        )
        with pytest.raises(NarrationFailed, match="bear"):
            await narrate(_make_spec(), client)

    async def test_missing_bull_raises(self):
        inp = {"base": "b", "bear": "c"}
        client = _mock_client(
            _mock_response([_tool_call_block("narrate_scenarios", inp)])
        )
        with pytest.raises(NarrationFailed, match="bull"):
            await narrate(_make_spec(), client)

    async def test_excessively_long_scenario_rejected(self):
        inp = {**VALID_SCENARIOS, "bull": "x" * 2000}
        client = _mock_client(
            _mock_response([_tool_call_block("narrate_scenarios", inp)])
        )
        with pytest.raises(NarrationFailed, match="1500"):
            await narrate(_make_spec(), client)

    async def test_return_annotation_is_scenarios(self):
        assert inspect.signature(narrate).return_annotation in (Scenarios, "Scenarios")

    async def test_model_returns_no_tool_calls_raises(self):
        choice = AsyncMock()
        choice.message = AsyncMock()
        choice.message.tool_calls = None
        resp = AsyncMock()
        resp.choices = [choice]
        client = _mock_client(resp)
        with pytest.raises(NarrationFailed):
            await narrate(_make_spec(), client)

    async def test_model_calls_wrong_function_raises(self):
        client = _mock_client(
            _mock_response([_tool_call_block("wrong_func", VALID_SCENARIOS)])
        )
        with pytest.raises(NarrationFailed, match="Unexpected function"):
            await narrate(_make_spec(), client)

    async def test_model_returns_invalid_json_raises(self):
        block = AsyncMock()
        block.function = AsyncMock()
        block.function.name = "narrate_scenarios"
        block.function.arguments = "bad json"
        choice = AsyncMock()
        choice.message = AsyncMock()
        choice.message.tool_calls = [block]
        client = _mock_client(AsyncMock(choices=[choice]))
        with pytest.raises(NarrationFailed, match="JSON"):
            await narrate(_make_spec(), client)