# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repository status

This repo is **pre-implementation**. It currently contains only `plans/perp-position-architect-dev-plan.md` — the full product and delivery plan. There is no source tree, no git repository, and no build tooling yet.

Read the plan before writing code. When scaffolding happens, replace the Commands section below with the real commands.

## Commands

Not yet established. Planned stack is FastAPI (Python) deployed on Railway. Once scaffolded, document here: dev server, test runner, single-test invocation, lint, and deploy.

## What Levra is

An AI agent that turns a plain-English trading thesis ("I think ETH grinds up into September, moderate conviction, $2,000 risk capital") into a structured, risk-managed **perpetual futures position spec** — entry zone, structural stop, position size, projected funding cost, liquidation buffer, and bull/base/bear scenarios.

It produces a *spec*, never an executed trade.

## Architecture — the one thing that matters

```
thesis (+ x402 payment)
   → LLM: thesis parser        → {asset, direction, horizon, conviction, capital}
   → Deterministic engine      → every price, size, and risk number (pure code)
   → LLM: scenario writer      → prose narration over already-fixed numbers
   → response + spec hash logged on X Layer
```

**The LLM boundary is drawn around language, not arithmetic.** This is the central design decision of the project and the thing it is pitched on.

- The LLM appears at exactly two sites: parsing intent on the way in, narrating scenarios on the way out.
- The deterministic engine — plain code pulling live market data — computes every numeric field. Prices, stop levels, position sizes, funding projections, liquidation distances.
- The scenario writer receives numbers that are already final. It must not be able to alter any numeric field. Guardrail tests for this are part of the deliverable, not optional.

If a change would let model output influence a number, it is wrong regardless of how well it works.

## Deterministic engine — fixed rules

These are product decisions, not implementation details. Do not "improve" them without an explicit decision to.

**Swing detection is mechanical and boring on purpose.** Last confirmed higher-low (longs) or lower-high (shorts) over a fixed lookback — 20 candles on the 4H timeframe. No fitted or ML-based detection. The rule must be verifiable by eye on a chart and explainable in one sentence during live Q&A.

**Every response carries a "why this stop" field.** Plain English, traceable: `"Stop placed at $3,142 — last confirmed swing low over the past 20 4H candles (Aug 3, 14:00 UTC)."` Reasoning is the product; the arithmetic is table stakes.

**Position size** derives from a fixed **2%** risk rule: `size = (capital × 0.02) / |entry − stop|`.

Hardcode this in the sizing engine as a named constant — `MAX_RISK_PCT = 0.02`. Not a config key, not a default argument, not an env var. Nothing in the call path may override it, including the thesis parser: if a user's thesis asks for more size or more risk, the engine ignores it.

Every output states the rule verbatim — `"Risk: 2% of stated capital, structural stop only — non-negotiable"`. That claim has to be true in code, not just in prose. A "non-negotiable" rule that turns out to be a configurable default is worse than never having claimed it.

**Funding cost assumes the current rate holds flat** across the stated horizon, and the output says so: `"Assumes current funding rate holds flat over horizon; actual cost will vary with market conditions."` Disclose the assumption inline rather than modelling something more fragile.

## Scope guardrails

In scope: BTC and ETH only. Spec generation only.

Out of scope — do not build these without an explicit decision: additional assets, trade auto-execution (spec-only limits liability and scope), portfolio-level position management, polished mobile/web UI.

Liquidation-cluster data is the hardest data source and is explicitly a stretch. Ship with funding rate + swing structure alone rather than letting it block anything.

## Stack

| Layer | Choice |
|---|---|
| API | FastAPI |
| Deploy | Railway |
| Market data | OKX public market API (candles, funding, OI) — no auth |
| LLM | Claude API — parsing and narration only |
| Payments | x402 (HTTP 402 + stablecoin settlement) |
| On-chain | Minimal Solidity contract on X Layer (`LevraLog.sol`) storing spec hash + timestamp |
| Listing | Registered as an ASP on OKX.ai |

On-chain logging exists to give the agent an auditable, tamper-proof track record — proof that results aren't cherry-picked after the fact. It is a differentiator, not incidental plumbing.

## Hard constraints

Built for the AI Season Hackathon on X Layer. **Submission deadline: Aug 21, 2026, 23:59 UTC.**

Two deploys are required inside the contest window, in order: X Layer **Testnet** first, then **Mainnet**. Both must land before submission.

## Knowledge base

Per the user's global convention, durable reasoning lives in Obsidian, not this repo:

```
/home/iamphantasm0/zeros, obsidian/Levra/
```

Repo holds code, API docs, setup, schemas, ADRs. The vault holds why decisions were made, research, strategy, and per-session logs (`logs/YYYY-MM-DD.md`). Update `STATUS.md` and append to `progress.md` at the end of each session.
