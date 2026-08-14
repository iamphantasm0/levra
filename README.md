# Levra

AI agent that converts a plain-English trading thesis into a structured,
risk-managed perpetual futures position spec.

**Input:** "I think ETH grinds up into September, moderate conviction, $2,000 risk capital."

**Output:** Entry zone, structural stop, position size, funding cost projection,
liquidation buffer, and bull/base/bear scenarios — every number computed by a
deterministic engine, every word written by an LLM that cannot touch the numbers.

## Stack

- **API:** FastAPI (Python 3.12+)
- **Market data:** OKX public API
- **LLM:** Claude (Sonnet) via **OpenRouter**, using the OpenAI-compatible SDK — thesis parsing + scenario narration only
- **Payments:** x402 (HTTP 402 + stablecoin settlement)
- **On-chain logging:** X Layer (`LevraLog.sol`) — mainnet chain id 196, testnet 1952
- **Deploy:** Railway

## Quickstart

```bash
# Install dependencies
uv sync --all-groups

# Set the LLM gateway key. Note: OPENROUTER_API_KEY, not ANTHROPIC_API_KEY —
# Claude is reached through OpenRouter. Get one at https://openrouter.ai/keys
export OPENROUTER_API_KEY=sk-or-...

# Run the dev server
uv run uvicorn levra.api:app --reload --port 8000
```

`/spec` sits behind x402, so a request needs a payment proof header. `/health` is
free.

```bash
# Health — no payment
curl -s localhost:8000/health

# Unpaid /spec returns 402 plus a payment challenge
curl -s -X POST localhost:8000/spec \
  -H 'content-type: application/json' \
  -d '{"thesis":"ETH grinds up into September, moderate conviction, $2,000"}' | jq

# With a payment proof
curl -s -X POST localhost:8000/spec \
  -H 'content-type: application/json' \
  -H "PAYMENT-SIGNATURE: 0x$(openssl rand -hex 32)" \
  -d '{"thesis":"ETH grinds up into September, moderate conviction, $2,000"}' | jq
```

See `.env.example` for every variable, including the on-chain logging and x402
settlement settings.

## Deploying to Railway

1. Install and authenticate the [Railway CLI](https://docs.railway.com/cli/install)
2. Link the project: `railway link`
3. Set the LLM key: `railway variables --set OPENROUTER_API_KEY=sk-or-...`
4. Deploy: `railway up`

Railway auto-detects the Python project (Railpack, uv) and uses the start command
in `railway.json`. The public domain must target the same port as `$PORT`
(8080) — a mismatch surfaces as a 502.

If `/health` returns `{"status":"error","code":404,"message":"Application not
found"}` with an `x-railway-fallback: true` header, no service is bound to the
domain: re-attach it in the service's Settings → Networking.

## Running tests

```bash
uv run pytest -q          # 227 tests
uv run mypy               # strict
uv run ruff check .

git clone --depth 1 --branch v1.16.2 \
  https://github.com/foundry-rs/forge-std lib/forge-std
forge test -vvv           # 8 contract tests
```

CI runs all five on every push and pull request.

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