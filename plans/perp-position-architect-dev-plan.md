# Levra — Development Lifecycle Plan
*(f.k.a. "Perp Position Architect" — working name locked to **Levra**)*
**AI Season Hackathon (X Layer) — Aug 7–21, 2026**

---

## 1. What It Is

**Levra** is an AI agent that converts a plain-English trading thesis into a fully structured, risk-managed **perpetual futures position** — not commentary, a tradeable spec.

**Input example:**
> "I think ETH grinds up into September. Moderate conviction. $2,000 risk capital."

**Output:**
- Entry zone
- Structural stop-loss (placed at real market structure — swing low/high, not an arbitrary %)
- Position size (derived from a fixed risk rule, not a guess)
- Funding cost projected across the stated horizon
- Liquidation buffer / distance to liquidation
- Bull / base / bear scenario table

**Core design principle (borrowed as a pattern, not a copy):** the LLM never invents a number. It parses intent and narrates scenarios. A deterministic engine — plain code — pulls live market data and computes every price, size, and risk figure. This is the same "code for facts, model for language" architecture LEAPSY used for options; here it's applied to a structurally different instrument (perps: funding + liquidation risk, no expiry) rather than listed options (defined risk, time decay). That distinction is your answer if anyone calls it derivative.

---

## 2. Why This, Why Now

- **Gap confirmed by research:** OKX's own Skills Marketplace has a funding-rate scanner and a bare position-size calculator (entry/stop/funds → size + liquidation price). Neither *designs* a position from a thesis. Nothing on OKX.ai currently does thesis-to-structure for perps.
- **Funding-carry scanning (the other idea considered) is saturated** — OKX ships it natively, and third-party x402 agents already do it. Correctly dropped.
- **Authenticity edge:** this encodes a risk framework (2% rule, structural stops, no chasing) you actually trade by. A live demo where you can defend *why* the stop is where it is, from experience, is hard for other teams to fake.
- **On-chain differentiator:** logging every generated position spec to X Layer with a timestamp gives the agent an auditable, tamper-proof track record — proof you're not cherry-picking good calls after the fact. LEAPSY doesn't have this. This is your strongest judge-facing wedge.

---

## 3. MVP Scope (what to actually build in 13 days)

Keep this ruthless. Cut anything not needed for a 3-minute live demo + working ASP listing.

**In scope:**
1. Thesis parser (LLM → structured params: asset, direction, horizon, conviction, capital)
2. Deterministic data layer: live price, recent swing structure, funding rate, open interest, liquidation cluster proximity (start with BTC + ETH only)
3. Deterministic sizing/stop engine (risk-rule based, no LLM involved in the math)
4. Scenario narration layer (LLM writes bull/base/bear prose off the computed numbers)
5. x402-payable API endpoint (HTTP 402 + stablecoin settlement)
6. On-chain position logging — a minimal X Layer contract that timestamps a hash of each generated spec
7. Simple front end or CLI demo (doesn't need to be polished — OKX.ai listing + a clean terminal/API demo is enough)

**Explicitly out of scope for hackathon MVP:**
- More than 2 assets
- Auto-execution of trades (spec-only, not an execution bot — reduces liability and scope)
- Portfolio-level position management
- Mobile app / polished UI

---

## 4. Architecture

```
User / Agent Caller
      │  (plain-English thesis + x402 payment)
      ▼
┌─────────────────────┐
│  API Gateway (FastAPI)│  ← x402 middleware for pay-per-call
└─────────┬────────────┘
          ▼
┌─────────────────────┐
│  LLM: Thesis Parser  │  → {asset, direction, horizon, conviction, capital}
└─────────┬────────────┘
          ▼
┌──────────────────────────────┐
│  Deterministic Engine (pure code) │
│  - Live price feed            │
│  - Swing structure detection  │  → stop level
│  - Funding rate pull          │  → cost projection
│  - OI / liquidation clusters  │  → liquidation buffer
│  - Position sizing formula    │  → size = risk$ / (entry − stop)
└─────────┬─────────────────────┘
          ▼
┌─────────────────────┐
│  LLM: Scenario Writer │  → bull/base/bear narrative (numbers already fixed)
└─────────┬────────────┘
          ▼
┌─────────────────────┐
│  Response + On-chain Log │ → hash of spec written to X Layer contract
└──────────────────────────┘
```

**Why this shape matters for judging:** the LLM boundary is drawn explicitly around language, not arithmetic. That's the single most defensible design decision in the whole project — call it out in the pitch.

---

## 5. Tech Stack (aligned to what you already run)

| Layer | Choice | Why |
|---|---|---|
| API framework | FastAPI | Your default stack, fast to ship |
| Async/queueing | Redis (if needed for rate-limiting x402 calls) | Already know it from Cypra |
| Deployment | Railway | Your existing deploy pipeline, fast iteration |
| Market data | OKX public market API (funding, OI, candles) — no auth needed | Free tier, live, matches judging ecosystem |
| Liquidation clusters | CoinGlass API or equivalent, if budget/time allows; otherwise derive from OI + leverage distribution proxy | Keep as stretch — don't block MVP on it |
| LLM | Claude (via API) — thesis parsing + scenario writing only | Matches "AI element" requirement cleanly; also mirrors the "built with Claude" narrative that worked for LEAPSY's creator |
| Payments | x402 (HTTP 402 + stablecoin) | Required for agent-native distribution, matches OKX Agent Payments Protocol |
| On-chain logging | Minimal Solidity contract on X Layer — stores hash + timestamp per generated spec | Satisfies deployment requirement AND gives you the audit-trail differentiator |
| Agent listing | Register as ASP on OKX.ai | Discoverability by other agents, matches LEAPSY's distribution model |

---

## 6. Development Timeline (13 days: Aug 8 → Aug 21, 23:59 UTC)

Aggressive but doable given your FastAPI/Railway fluency. Build in public daily on the @Levra (or closest available handle) X account (also satisfies the "keep it active" rule for free).

**Phase 1 — Foundation (Aug 8–10)**
- Scaffold `levra` FastAPI project, Railway deploy pipeline
- Build deterministic data layer: price, funding rate, OI pulls from OKX public API for BTC + ETH
- Write and unit-test the sizing/stop formula in isolation (no LLM yet) — this is the credibility core, get it right first

**Phase 2 — AI Layer (Aug 11–13)**
- Thesis parser prompt + structured output (Claude API, JSON mode)
- Scenario writer prompt, fed only the already-computed numbers
- Guardrail tests: confirm the LLM cannot alter any numeric field, only narrate

**Phase 3 — X Layer Integration (Aug 14–16)**
- Write minimal logging contract `LevraLog.sol` (spec hash + timestamp)
- Deploy to **X Layer Testnet**
- Wire x402 payment middleware into the API
- End-to-end test: thesis in → paid call → structured response out → hash logged on testnet

**Phase 4 — Polish + Demo Prep (Aug 17–18)**
- Clean up API responses / minimal demo interface (CLI or simple web form is enough)
- Record demo video / prepare live-demo script
- Stress-test edge cases (garbage thesis input, extreme conviction values, illiquid horizon)

**Phase 5 — Mainnet + ASP Listing (Aug 19–20)**
- Deploy logging contract to **X Layer Mainnet**
- Register agent as an ASP on OKX.ai
- Final x402 payment flow test against mainnet settlement
- Publish official project X account post tagging **@XLayerOfficial**

**Phase 6 — Submission (Aug 21, before 23:59 UTC)**
- Final Google Form submission
- Confirm X post is live and tagged
- Sanity-check all four participation requirements (checklist below) one last time

Build buffer: don't let liquidation-cluster data (the hardest data source) block anything — ship with funding rate + swing structure alone if needed, add liquidation buffer as a stretch enhancement.

---

## 7. Tournament Rules — Explicit Compliance Mapping

| Rule | How this project satisfies it | Status owner |
|---|---|---|
| **AI elements in product design, deployed on X Layer** | AI does real work in the pipeline (thesis parsing + scenario narration, not a bolt-on chatbot). Deployment = the logging contract + x402 settlement layer live on X Layer. | Phase 3 & 5 |
| **Deployed on X Layer Testnet during Hackathon, then launched on Mainnet** | Testnet deploy in Phase 3 (Aug 14–16), Mainnet deploy in Phase 5 (Aug 19–20) — both inside the Aug 7–21 window | Phase 3 & 5 |
| **Dedicated, active X account for project lifetime** | Create account **Day 1** (Aug 8). Post daily build-in-public updates through submission and beyond — this is free marketing AND compliance | Start immediately |
| **Official X account posts submission + tags @XLayerOfficial** | Scheduled for Phase 5, after mainnet deploy is confirmed live | Phase 5 |
| **Submit via Google Form by Aug 21, 23:59 UTC** | Phase 6, with a same-day buffer — do not submit at the literal deadline | Phase 6 |

**Do not skip:** identity/KYC verification will be required before any prize payout, and prize wallets must be self-custodial — have a wallet ready that isn't tied to an exchange custodial balance.

---

## 8. Positioning Note for Judges (have this ready verbally)

> "This is inspired by the LEAPSY pattern — deterministic data, AI for language only, agent-native payments — applied to a fundamentally different instrument. LEAPSY structures long-dated listed options against Deribit's chain: defined risk, time decay, no liquidation. We structure perpetual futures against live funding, open interest, and liquidation data: undefined time horizon, funding bleed, real liquidation risk. The risk-management problem is different, so the deterministic engine is different. What we borrowed is the architecture, not the product — and we extended it with on-chain position logging, which gives the agent something LEAPSY doesn't have: a verifiable, tamper-proof track record."

Have this ready before anyone asks — get ahead of the comparison instead of reacting to it.

---

## 8a. Hardening Pass — Post-Review Revisions

Applied after external review (8.4/10 — strongest flagged risks were swing detection reliability, funding-assumption transparency, and live-demo fragility).

**Swing structure detection — keep it boring and explainable**
Do not use a fitted or ML-based swing detector. Use a fixed, mechanical rule: last confirmed higher-low (for longs) or lower-high (for shorts) over a fixed lookback window (e.g. last 20 candles on the 4H timeframe). The stop level must be traceable to one plain-English sentence a judge can verify by eye on a chart. Clever detection that can't be explained in one sentence is a liability in a live Q&A, not a feature.

**"Why this stop" field — add to every response**
Every generated spec must include a short explanation output field, e.g.:
> "Stop placed at $3,142 — last confirmed swing low over the past 20 4H candles (Aug 3, 14:00 UTC)."
This is the single cheapest addition with the highest credibility payoff. It turns "here's a number" into "here's reasoning," which is the actual product, not the arithmetic.

**Funding cost projection — disclose the assumption, don't hide it**
State the methodology inline in the output: funding cost is projected assuming the *current* funding rate holds flat across the stated horizon. Add one caveat line to the response: "Assumes current funding rate holds flat over horizon; actual cost will vary with market conditions." An honest, simple assumption beats a fragile, "smarter" one a judge can poke a hole in.

**Canned demo theses — de-risk the live pitch**
Pre-run and cache 3–4 high-quality theses spanning different assets/conviction/horizon combinations before the demo (e.g. BTC high-conviction short horizon, ETH moderate-conviction long horizon, a low-conviction/small-size case, a short-side case). Use these as the primary demo path — live API calls underneath are fine, but never let a live infra hiccup be the thing that sinks the pitch. If live data lags or errors during Q&A, fall back to a cached run without missing a beat.

**Explicit, non-negotiable risk rule**
Keep the risk-per-trade rule fixed and stated plainly in every output (e.g. "Risk: 2% of stated capital, structural stop only — non-negotiable"). Judges respond well to visibly disciplined frameworks over flexible/configurable ones that look improvised.

---

## 9. Immediate Next Actions (today)

1. Create the project X account and post a "building in public, day 1" tweet
2. Scaffold the `levra` FastAPI repo on Railway
3. Pull OKX public funding-rate and OI endpoints and confirm live data access before writing any AI code