import dataclasses
import json
from decimal import Decimal
from unittest.mock import AsyncMock

import pytest

from levra.errors import ThesisIncomplete, UnsupportedAsset
from levra.llm.parser import parse_thesis
from levra.models import Conviction, Direction, Thesis


def _tool_call_block(name: str, arguments: dict) -> AsyncMock:
    block = AsyncMock()
    block.id = "call_1"
    block.type = "function"
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


_VALID_INPUT = {
    "asset": "ETH",
    "direction": "LONG",
    "horizon_days": 30,
    "conviction": "MODERATE",
    "capital_usd": 2000.0,
}


class TestParseThesis:
    async def test_well_formed_tool_call_maps_to_thesis(self):
        client = _mock_client(_mock_response([_tool_call_block("extract_thesis", _VALID_INPUT)]))
        thesis = await parse_thesis("Long ETH 30d moderate $2000", client)
        assert thesis.asset == "ETH"
        assert thesis.direction is Direction.LONG
        assert thesis.horizon_days == 30
        assert thesis.conviction is Conviction.MODERATE
        assert thesis.capital == Decimal("2000")
        assert thesis.raw_text == "Long ETH 30d moderate $2000"

    async def test_integer_capital_parses_as_decimal(self):
        client = _mock_client(
            _mock_response([_tool_call_block("extract_thesis", {**_VALID_INPUT, "capital_usd": 2000})])
        )
        thesis = await parse_thesis("x", client)
        assert thesis.capital == Decimal("2000")

    async def test_float_capital_parses_as_decimal(self):
        client = _mock_client(
            _mock_response([_tool_call_block("extract_thesis", {**_VALID_INPUT, "capital_usd": 2000.0})])
        )
        thesis = await parse_thesis("x", client)
        assert thesis.capital == Decimal("2000.0")

    async def test_unsupported_asset_raises_before_market_call(self):
        client = _mock_client(
            _mock_response([_tool_call_block("extract_thesis", {**_VALID_INPUT, "asset": "SOL"})])
        )
        with pytest.raises(UnsupportedAsset):
            await parse_thesis("Long SOL", client)

    async def test_missing_capital_raises_thesis_incomplete(self):
        client = _mock_client(
            _mock_response([_tool_call_block("extract_thesis", {**_VALID_INPUT, "capital_usd": None})])
        )
        with pytest.raises(ThesisIncomplete, match="capital"):
            await parse_thesis("x", client)

    async def test_negative_capital_raises_thesis_incomplete(self):
        client = _mock_client(
            _mock_response([_tool_call_block("extract_thesis", {**_VALID_INPUT, "capital_usd": -100})])
        )
        with pytest.raises(ThesisIncomplete):
            await parse_thesis("x", client)

    async def test_zero_capital_raises_thesis_incomplete(self):
        client = _mock_client(
            _mock_response([_tool_call_block("extract_thesis", {**_VALID_INPUT, "capital_usd": 0})])
        )
        with pytest.raises(ThesisIncomplete):
            await parse_thesis("x", client)

    async def test_horizon_clamped_to_365(self):
        client = _mock_client(
            _mock_response([_tool_call_block("extract_thesis", {**_VALID_INPUT, "horizon_days": 9999})])
        )
        thesis = await parse_thesis("x", client)
        assert thesis.horizon_days == 365

    async def test_horizon_clamped_to_1(self):
        client = _mock_client(
            _mock_response([_tool_call_block("extract_thesis", {**_VALID_INPUT, "horizon_days": -5})])
        )
        thesis = await parse_thesis("x", client)
        assert thesis.horizon_days == 1

    async def test_raw_text_preserved(self):
        client = _mock_client(_mock_response([_tool_call_block("extract_thesis", _VALID_INPUT)]))
        thesis = await parse_thesis("I think ETH grinds up into September", client)
        assert thesis.raw_text == "I think ETH grinds up into September"

    async def test_parser_never_returns_a_price(self):
        fields = {f.name for f in dataclasses.fields(Thesis)}
        assert fields == {"asset", "direction", "horizon_days", "conviction", "capital", "raw_text"}
        for banned in ("entry", "stop", "size", "leverage", "liquidation", "notional", "price"):
            assert banned not in fields

    async def test_model_returns_no_tool_calls_raises(self):
        choice = AsyncMock()
        choice.message = AsyncMock()
        choice.message.tool_calls = None
        resp = AsyncMock()
        resp.choices = [choice]
        client = _mock_client(resp)
        with pytest.raises(ThesisIncomplete):
            await parse_thesis("x", client)

    async def test_model_calls_wrong_function_raises(self):
        client = _mock_client(
            _mock_response([_tool_call_block("some_other_func", _VALID_INPUT)])
        )
        with pytest.raises(ThesisIncomplete, match="Unexpected function"):
            await parse_thesis("x", client)

    async def test_model_returns_invalid_json_raises(self):
        block = AsyncMock()
        block.function = AsyncMock()
        block.function.name = "extract_thesis"
        block.function.arguments = "not json"
        choice = AsyncMock()
        choice.message = AsyncMock()
        choice.message.tool_calls = [block]
        client = _mock_client(AsyncMock(choices=[choice]))
        with pytest.raises(ThesisIncomplete, match="JSON"):
            await parse_thesis("x", client)

    async def test_missing_direction_raises(self):
        inp = {**_VALID_INPUT, "direction": None}
        client = _mock_client(_mock_response([_tool_call_block("extract_thesis", inp)]))
        with pytest.raises(ThesisIncomplete, match="direction"):
            await parse_thesis("x", client)

    async def test_invalid_direction_raises(self):
        inp = {**_VALID_INPUT, "direction": "SIDEWAYS"}
        client = _mock_client(_mock_response([_tool_call_block("extract_thesis", inp)]))
        with pytest.raises(ThesisIncomplete, match="(?i)direction"):
            await parse_thesis("x", client)

    async def test_missing_conviction_raises(self):
        inp = {**_VALID_INPUT, "conviction": None}
        client = _mock_client(_mock_response([_tool_call_block("extract_thesis", inp)]))
        with pytest.raises(ThesisIncomplete, match="conviction"):
            await parse_thesis("x", client)

    async def test_invalid_conviction_raises(self):
        inp = {**_VALID_INPUT, "conviction": "EXTREME"}
        client = _mock_client(_mock_response([_tool_call_block("extract_thesis", inp)]))
        with pytest.raises(ThesisIncomplete, match="(?i)conviction"):
            await parse_thesis("x", client)

    async def test_missing_horizon_raises(self):
        inp = {**_VALID_INPUT, "horizon_days": None}
        client = _mock_client(_mock_response([_tool_call_block("extract_thesis", inp)]))
        with pytest.raises(ThesisIncomplete, match="horizon"):
            await parse_thesis("x", client)