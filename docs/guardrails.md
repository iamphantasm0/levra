# Guardrails

These are structural proofs — not guidelines — that the LLM boundary stays intact.

## No floats in the numeric path

`tests/guardrails/test_no_floats.py` walks the AST of every file in the engine, models, and constants directories. It fails on any `float` literal, `float()` call, or `float` type annotation. The entire numeric surface is `Decimal` only.

**What breakage it catches:** A contributor adding a `float` price or calculation that silently introduces floating-point error into position sizing, funding, or liquidation estimates.

## The 2% risk rule is fixed

`tests/guardrails/test_risk_is_fixed.py` proves three things:

1. `MAX_RISK_PCT == Decimal("0.02")` and it is a `Decimal`, not a float.
2. `MAX_RISK_PCT` is assigned in exactly one file (constants.py) and exactly once.
3. No function in any engine module exposes a parameter whose name contains `risk_pct`, `risk_percent`, `max_risk`, `risk_fraction`, or `risk_override`.
4. The constants.py source contains no `getenv` or `environ` call.

**What breakage it catches:** Someone making the 2% rule configurable via an env var, a function parameter, or a second assignment elsewhere — all of which would mean the output's claim that the rule is "non-negotiable" is false.

## The LLM cannot produce numbers

`tests/guardrails/test_llm_cannot_touch_numbers.py` proves:

1. `Scenarios` has exactly three fields, all `str`. The narrator's entire output surface is prose.
2. `narrate()` returns `Scenarios` and nothing else (via `inspect.signature`).
3. `Thesis` has exactly six fields, none of which is a price, size, or leverage field. The parser cannot inject a numeric trading parameter.
4. `PositionSpec` is a frozen dataclass — once built, no field can be mutated.
5. Five adversarial theses (demanding 25% risk, 50x leverage, a $1 stop, 100% risk tolerance, etc.) all produce the same risk amount (2%), the same structural stop, and the same risk disclosure — because the engine ignores everything that isn't in the Thesis type, and the Thesis type has nowhere for those demands to land.

**What breakage it catches:** A future change that lets model output influence any numeric field on the spec — the exact boundary the project is pitched on.
