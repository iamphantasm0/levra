"""Scenario narrator — the only outbound LLM call site.

Receives a finished PositionSpec whose numbers are already final and returns
Scenarios with three str fields. The narrator must not compute, adjust, or
restate any number beyond what is in the spec block.

Uses OpenRouter (OpenAI-compatible API) to reach Claude.
"""

import json

from openai import AsyncOpenAI

from levra.errors import NarrationFailed
from levra.llm.client import NARRATOR_MODEL
from levra.models import PositionSpec, Scenarios

MAX_SCENARIO_CHARS = 1500

NARRATE_SCENARIOS_FUNCTION = {
    "name": "narrate_scenarios",
    "description": "Write bull, base, and bear scenario narratives for a position spec.",
    "parameters": {
        "type": "object",
        "properties": {
            "bull": {
                "type": "string",
                "description": "The bull-case narrative for this position.",
            },
            "base": {
                "type": "string",
                "description": "The base-case narrative for this position.",
            },
            "bear": {
                "type": "string",
                "description": "The bear-case narrative for this position.",
            },
        },
        "required": ["bull", "base", "bear"],
    },
}


def _format_spec_for_narrator(spec: PositionSpec) -> str:
    return (
        f"Asset: {spec.asset}\n"
        f"Direction: {spec.direction.value}\n"
        f"Entry zone: ${spec.entry_zone.sizing_edge:,.2f}\n"
        f"Stop: ${spec.stop:,.2f}\n"
        f"Stop rationale: {spec.stop_rationale}\n"
        f"Position size: {spec.position_size} {spec.asset}\n"
        f"Notional: ${spec.notional:,.2f}\n"
        f"Leverage: {spec.leverage}x\n"
        f"Liquidation price: ${spec.liquidation_price:,.2f}\n"
        f"Liquidation buffer (relative to stop distance): {spec.liquidation_buffer_ratio}x\n"
        f"Funding cost ({spec.funding_intervals} intervals): ${spec.funding_cost}\n"
        f"Horizon: {spec.horizon_days} days\n"
        f"Conviction: {spec.conviction.value}\n"
        f"Risk rule: {spec.risk_rule}\n"
        f"Funding assumption: {spec.funding_assumption}"
    )


async def narrate(spec: PositionSpec, client: AsyncOpenAI) -> Scenarios:
    spec_block = _format_spec_for_narrator(spec)
    user_text = (
        "Below is a pre-computed perpetual futures position spec for a "
        f"{spec.asset} {spec.direction.value}. "
        "Narrate what happens to this position in three scenarios: bull, base, "
        "and bear. Every number you need is given. Do not compute, adjust, or "
        "restate any number that is not in the spec block above.\n\n"
        f"--- SPEC ---\n{spec_block}\n--- END SPEC ---"
    )
    response = await client.chat.completions.create(  # type: ignore[call-overload]
        model=NARRATOR_MODEL,
        max_tokens=1200,
        messages=[{"role": "user", "content": user_text}],
        tools=[{"type": "function", "function": NARRATE_SCENARIOS_FUNCTION}],
        tool_choice={
            "type": "function",
            "function": {"name": "narrate_scenarios"},
        },
    )

    choice = response.choices[0]
    if not choice.message.tool_calls:
        raise NarrationFailed("Model did not call the narrate_scenarios function")

    tc = choice.message.tool_calls[0]
    if tc.function.name != "narrate_scenarios":
        raise NarrationFailed(f"Unexpected function called: {tc.function.name}")

    try:
        inp = json.loads(tc.function.arguments)
    except json.JSONDecodeError:
        raise NarrationFailed("Model returned invalid JSON arguments")

    bull = inp.get("bull")
    base = inp.get("base")
    bear = inp.get("bear")

    if not bull or not base or not bear:
        missing = [
            k for k, v in {"bull": bull, "base": base, "bear": bear}.items() if not v
        ]
        raise NarrationFailed(f"Missing scenarios: {', '.join(missing)}")

    if any(len(s) > MAX_SCENARIO_CHARS for s in (bull, base, bear)):
        raise NarrationFailed(
            f"Scenario text exceeds {MAX_SCENARIO_CHARS} character limit"
        )

    return Scenarios(bull=str(bull), base=str(base), bear=str(bear))