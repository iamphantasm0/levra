"""FastAPI application — x402-payable endpoint."""


import httpx
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from levra.engine.build import build_spec
from levra.errors import (
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

OKX_BASE_URL = "https://www.okx.com"

app = FastAPI(title="Levra", version="0.1.0")
app.add_middleware(X402Middleware)


@app.exception_handler(LevraError)
async def levra_exception_handler(request: Request, exc: LevraError) -> JSONResponse:
    status = _status_for(exc)
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

    import asyncio

    from levra.chain import log_to_chain
    asyncio.create_task(log_to_chain(spec))

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
