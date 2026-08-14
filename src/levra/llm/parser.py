"""Thesis parser — the only inbound LLM call site.

Produces a Thesis with enum-constrained fields. The tool-use schema is the
primary guardrail; Python validation on the returned fields is the backstop.

Uses OpenRouter (OpenAI-compatible API) to reach Claude.
"""

import json
from decimal import Decimal, InvalidOperation

from openai import AsyncOpenAI

from levra.errors import ThesisIncomplete, UnsupportedAsset
from levra.llm.client import PARSER_MODEL
from levra.models import Conviction, Direction, Thesis

SUPPORTED_ASSET_LIST = ["BTC", "ETH"]
SUPPORTED_DIRECTION_LIST = ["LONG", "SHORT"]
SUPPORTED_CONVICTION_LIST = ["LOW", "MODERATE", "HIGH"]

EXTRACT_THESIS_FUNCTION = {
    "name": "extract_thesis",
    "description": "Extract structured trading-intent fields from a user's thesis.",
    "parameters": {
        "type": "object",
        "properties": {
            "asset": {
                "type": "string",
                "enum": SUPPORTED_ASSET_LIST,
                "description": "The asset the user wants to trade (BTC or ETH).",
            },
            "direction": {
                "type": "string",
                "enum": SUPPORTED_DIRECTION_LIST,
                "description": "LONG or SHORT.",
            },
            "horizon_days": {
                "type": "integer",
                "description": "The holding horizon in calendar days, 1–365.",
            },
            "conviction": {
                "type": "string",
                "enum": SUPPORTED_CONVICTION_LIST,
                "description": "LOW, MODERATE, or HIGH.",
            },
            "capital_usd": {
                "type": "number",
                "description": "The stated risk capital in USD, omit if absent.",
            },
        },
        "required": ["asset", "direction", "horizon_days", "conviction", "capital_usd"],
    },
}

SYSTEM_PROMPT = (
    "You are a trading-intent extractor. Your only job is to extract the structured "
    "fields from the user's thesis text. Extract only what the user stated. "
    "If capital is absent, omit it rather than guessing. "
    'Map vague horizons ("into September") to a day count from today. '
    "Do not infer a stop, entry, or size — those are not yours to produce. "
    "Call the extract_thesis function exactly once."
)


def _capital_from_input(value: float | int | None) -> Decimal:
    if value is None:
        raise ThesisIncomplete("Missing required field: capital")
    try:
        capital = Decimal(str(value))
    except InvalidOperation:
        raise ThesisIncomplete(f"Capital must be a positive number, got {value!r}") from None
    if capital <= 0:
        raise ThesisIncomplete("Capital must be a positive number")
    return capital


def _horizon_from_input(value: int | None) -> int:
    if value is None:
        raise ThesisIncomplete("Missing required field: horizon_days")
    return max(1, min(365, value))


def _asset_from_input(value: str | None) -> str:
    if value is None:
        raise ThesisIncomplete("Missing required field: asset")
    if value not in SUPPORTED_ASSET_LIST:
        raise UnsupportedAsset(f"{value} is not supported. Supported: BTC, ETH.")
    return value


def _direction_from_input(value: str | None) -> Direction:
    if value is None:
        raise ThesisIncomplete("Missing required field: direction")
    if value not in SUPPORTED_DIRECTION_LIST:
        raise ThesisIncomplete(f"Direction must be LONG or SHORT, got {value!r}")
    return Direction(value.lower())


def _conviction_from_input(value: str | None) -> Conviction:
    if value is None:
        raise ThesisIncomplete("Missing required field: conviction")
    if value not in SUPPORTED_CONVICTION_LIST:
        raise ThesisIncomplete(
            f"Conviction must be LOW, MODERATE, or HIGH, got {value!r}"
        )
    return Conviction(value.lower())


async def parse_thesis(text: str, client: AsyncOpenAI) -> Thesis:
    response = await client.chat.completions.create(  # type: ignore[call-overload]
        model=PARSER_MODEL,
        max_tokens=300,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": text},
        ],
        tools=[{"type": "function", "function": EXTRACT_THESIS_FUNCTION}],
        tool_choice={
            "type": "function",
            "function": {"name": "extract_thesis"},
        },
    )

    choice = response.choices[0]
    if not choice.message.tool_calls:
        raise ThesisIncomplete("Model did not call the extract_thesis function")

    tc = choice.message.tool_calls[0]
    if tc.function.name != "extract_thesis":
        raise ThesisIncomplete(f"Unexpected function called: {tc.function.name}")

    try:
        inp = json.loads(tc.function.arguments)
    except json.JSONDecodeError:
        raise ThesisIncomplete("Model returned invalid JSON arguments")

    asset = _asset_from_input(inp.get("asset"))
    direction = _direction_from_input(inp.get("direction"))
    horizon_days = _horizon_from_input(inp.get("horizon_days"))
    conviction = _conviction_from_input(inp.get("conviction"))
    capital = _capital_from_input(inp.get("capital_usd"))

    return Thesis(
        asset=asset,
        direction=direction,
        horizon_days=horizon_days,
        conviction=conviction,
        capital=capital,
        raw_text=text,
    )