# Levra

AI agent that converts a plain-English trading thesis into a structured,
risk-managed perpetual futures position spec.

**Input:** "I think ETH grinds up into September, moderate conviction, $2,000 risk capital."

**Output:** Entry zone, structural stop, position size, funding cost projection,
liquidation buffer, and bull/base/bear scenarios — every number computed by a
deterministic engine, every word written by an LLM that cannot touch the numbers.

## Stack

- **API:** FastAPI (Python 3.12)
- **Market data:** OKX public API
- **LLM:** Claude (Anthropic API) — thesis parsing + scenario narration only
- **Payments:** x402 (HTTP 402 + stablecoin settlement)
- **On-chain logging:** X Layer (`LevraLog.sol`)
- **Deploy:** Railway

## Quickstart

```bash
# Install dependencies
uv sync

# Set your Anthropic API key
export ANTHROPIC_API_KEY=sk-...

# Run the dev server
uv run uvicorn levra.api:app --reload
```

```bash
# Test the endpoint
curl -s localhost:8000/spec \
  -H 'content-type: application/json' \
  -d '{"thesis":"I think ETH grinds up into September, moderate conviction, $2,000 risk capital"}' | jq
```

## Deploying to Railway

1. Install and authenticate the [Railway CLI](https://docs.railway.com/cli/install)
2. Link the project: `railway link`
3. Set the Anthropic API key: `railway variables set ANTHROPIC_API_KEY=sk-...`
4. Deploy: `railway up`

Railway auto-detects the Python project and uses the start command in `railway.json`.

## Running tests

```bash
uv run pytest -v
uv run mypy src
uv run ruff check .
```

## Architecture

The LLM boundary is drawn around language, not arithmetic:

```
thesis → LLM parser → {asset, direction, horizon, conviction, capital}
       → Deterministic engine → every price, size, and risk number
       → LLM narrator → bull/base/bear prose over already-fixed numbers
       → response + on-chain spec hash
```

The parser's entire output surface is an enum + Decimal type. The narrator's
entire output surface is three `str` fields. The engine never calls a model.
Guardrail tests in `tests/guardrails/` prove each of these boundaries structurally.

## Guardrails

See `docs/guardrails.md` for the structural proofs that the LLM cannot produce
or alter any numeric field on the position spec.