"""FastAPI application — x402-payable endpoint."""

import asyncio
import logging
from collections.abc import AsyncIterator, Coroutine
from contextlib import asynccontextmanager
from typing import Any

import httpx
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from levra.chain import log_to_chain
from levra.config import (
    LLM_API_KEY_VAR,
    chain_logging_is_configured,
    llm_is_configured,
    x402_pay_to,
)
from levra.engine.build import build_spec
from levra.errors import (
    ConfigError,
    InvalidZone,
    LevraError,
    MarketDataError,
    NarrationFailed,
    NoValidStructuralStop,
    StopTooTight,
    ThesisIncomplete,
    UnsupportedAsset,
)
from levra.llm.client import build_client as build_llm_client
from levra.llm.narrator import narrate
from levra.llm.parser import parse_thesis
from levra.market.okx import OKXClient
from levra.market.snapshot import build_snapshot
from levra.payments import X402Middleware
from levra.schemas import (
    EntryZoneResponse,
    ScenariosResponse,
    SpecRequest,
    SpecResponse,
)

logger = logging.getLogger(__name__)

OKX_BASE_URL = "https://www.okx.com"

# Strong references to in-flight background tasks. asyncio only holds a weak
# reference to a bare create_task, so a fire-and-forget task can be garbage
# collected mid-flight — silently losing the chain write it was created for.
_background_tasks: set[asyncio.Task[Any]] = set()


def _spawn_background(coro: Coroutine[Any, Any, Any]) -> None:
    task = asyncio.create_task(coro)
    _background_tasks.add(task)
    task.add_done_callback(_background_tasks.discard)


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    """Report configuration state at boot.

    Deliberately does not abort startup on missing configuration: /health is the
    platform healthcheck, and keeping it up is what makes a misconfigured deploy
    diagnosable rather than merely dead. Each specific failure is logged loudly
    here, and /spec returns 503 while the key is absent.
    """
    if not llm_is_configured():
        logger.critical(
            "%s is not set - POST /spec will return 503 until it is configured.",
            LLM_API_KEY_VAR,
        )
    if not chain_logging_is_configured():
        logger.warning(
            "chain logging is disabled - set XLAYER_RPC_URL, LEVRA_LOG_ADDRESS and "
            "CHAIN_LOGGER_PRIVATE_KEY to write spec hashes to X Layer."
        )
    if not x402_pay_to():
        logger.error("X402_PAY_TO_ADDRESS is not set - payment challenges name no payee.")
    yield


app = FastAPI(title="Levra", version="0.1.0", lifespan=lifespan)
app.add_middleware(X402Middleware)


@app.exception_handler(LevraError)
async def levra_exception_handler(request: Request, exc: LevraError) -> JSONResponse:
    status = _status_for(exc)
    if status >= 500:
        logger.error("request failed with %d: %s", status, exc)
    return JSONResponse(
        status_code=status,
        content={"detail": str(exc)},
    )


def _status_for(exc: LevraError) -> int:
    mapping = {
        UnsupportedAsset: 422,
        ThesisIncomplete: 422,
        NoValidStructuralStop: 422,
        StopTooTight: 422,
        InvalidZone: 422,
        MarketDataError: 502,
        NarrationFailed: 502,
        # An operator problem, not a caller problem.
        ConfigError: 503,
    }
    for exc_type, status in mapping.items():
        if isinstance(exc, exc_type):
            return status
    return 500


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/spec", response_model=SpecResponse)
async def generate_spec(req: SpecRequest) -> SpecResponse:
    llm = build_llm_client()

    thesis = await parse_thesis(req.thesis, llm)

    async with httpx.AsyncClient(base_url=OKX_BASE_URL) as http:
        okx = OKXClient(http)
        snapshot = await build_snapshot(okx, thesis.asset)

    spec = build_spec(thesis, snapshot)
    scenarios = await narrate(spec, llm)

    # Corroboration, not part of the product path — never awaited, never fatal.
    _spawn_background(log_to_chain(spec))

    return SpecResponse(
        asset=spec.asset,
        direction=spec.direction.value,
        entry_zone=EntryZoneResponse(
            low=spec.entry_zone.low,
            high=spec.entry_zone.high,
            sizing_edge=spec.entry_zone.sizing_edge,
        ),
        stop=spec.stop,
        stop_rationale=spec.stop_rationale,
        position_size=spec.position_size,
        notional=spec.notional,
        risk_amount=spec.risk_amount,
        leverage=spec.leverage,
        liquidation_price=spec.liquidation_price,
        liquidation_buffer_ratio=spec.liquidation_buffer_ratio,
        funding_cost=spec.funding_cost,
        funding_rate=spec.funding_rate,
        funding_intervals=spec.funding_intervals,
        horizon_days=spec.horizon_days,
        conviction=spec.conviction.value,
        risk_rule=spec.risk_rule,
        funding_assumption=spec.funding_assumption,
        generated_at=spec.generated_at.isoformat(),
        scenarios=ScenariosResponse(
            bull=scenarios.bull,
            base=scenarios.base,
            bear=scenarios.bear,
        ),
    )
