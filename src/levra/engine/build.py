"""The deterministic engine, end to end.

Thesis + MarketSnapshot -> PositionSpec. Pure: no I/O, no clock beyond the
injected one, no model calls. Every numeric field on the returned spec is
final by the time this function returns.
"""

from datetime import UTC, datetime

from levra.constants import (
    FUNDING_ASSUMPTION_DISCLOSURE,
    RISK_RULE_DISCLOSURE,
    SUPPORTED_ASSETS,
)
from levra.engine.entry import build_entry_zone
from levra.engine.funding import project_funding
from levra.engine.liquidation import project_liquidation
from levra.engine.sizing import size_position
from levra.engine.swings import find_structural_stop, stop_rationale
from levra.errors import UnsupportedAsset
from levra.models import MarketSnapshot, PositionSpec, Thesis


def build_spec(
    thesis: Thesis, snapshot: MarketSnapshot, now: datetime | None = None
) -> PositionSpec:
    if thesis.asset not in SUPPORTED_ASSETS:
        raise UnsupportedAsset(
            f"{thesis.asset} is not supported. Supported: {', '.join(SUPPORTED_ASSETS)}."
        )

    swing = find_structural_stop(snapshot.candles, thesis.direction)
    zone = build_entry_zone(snapshot.mark_price, swing.price, thesis.direction)
    sizing = size_position(thesis.capital, zone.sizing_edge, swing.price)

    funding = project_funding(
        notional=sizing.notional,
        rate=snapshot.funding_rate,
        interval_hours=snapshot.funding_interval_hours,
        horizon_days=thesis.horizon_days,
        direction=thesis.direction,
    )
    liquidation = project_liquidation(
        entry=zone.sizing_edge,
        stop=swing.price,
        leverage=sizing.leverage,
        maintenance_margin_rate=snapshot.maintenance_margin_rate,
        direction=thesis.direction,
    )

    return PositionSpec(
        asset=thesis.asset,
        direction=thesis.direction,
        entry_zone=zone,
        stop=swing.price,
        stop_rationale=stop_rationale(swing),
        position_size=sizing.size,
        notional=sizing.notional,
        risk_amount=sizing.risk_amount,
        leverage=sizing.leverage,
        liquidation_price=liquidation.price,
        liquidation_buffer_ratio=liquidation.buffer_ratio,
        funding_cost=funding.cost,
        funding_rate=funding.rate,
        funding_intervals=funding.intervals,
        horizon_days=thesis.horizon_days,
        conviction=thesis.conviction,
        risk_rule=RISK_RULE_DISCLOSURE,
        funding_assumption=FUNDING_ASSUMPTION_DISCLOSURE,
        generated_at=now or datetime.now(UTC),
    )
