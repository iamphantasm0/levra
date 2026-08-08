"""Frozen domain types. Every numeric field is Decimal."""

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import Literal


class Direction(StrEnum):
    LONG = "long"
    SHORT = "short"


class Conviction(StrEnum):
    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"


@dataclass(frozen=True, slots=True)
class Thesis:
    """Parsed user intent. The only thing the inbound LLM call may produce."""

    asset: str
    direction: Direction
    horizon_days: int
    conviction: Conviction
    capital: Decimal
    raw_text: str


@dataclass(frozen=True, slots=True)
class Candle:
    ts: datetime
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    confirmed: bool


@dataclass(frozen=True, slots=True)
class MarketSnapshot:
    asset: str
    mark_price: Decimal
    candles: tuple[Candle, ...]  # oldest-first, confirmed only
    funding_rate: Decimal  # per interval, e.g. Decimal("0.0001")
    funding_interval_hours: int
    maintenance_margin_rate: Decimal
    fetched_at: datetime


@dataclass(frozen=True, slots=True)
class Swing:
    price: Decimal
    ts: datetime
    kind: Literal["higher_low", "lower_high"]


@dataclass(frozen=True, slots=True)
class EntryZone:
    """`sizing_edge` is the edge furthest from the stop — sizing from it means a
    fill anywhere in the zone risks no more than the budget."""

    low: Decimal
    high: Decimal
    sizing_edge: Decimal


@dataclass(frozen=True, slots=True)
class Scenarios:
    """The narrator's entire output surface. Strings only, by construction."""

    bull: str
    base: str
    bear: str


@dataclass(frozen=True, slots=True)
class PositionSpec:
    asset: str
    direction: Direction
    entry_zone: EntryZone
    stop: Decimal
    stop_rationale: str
    position_size: Decimal  # units of base asset
    notional: Decimal
    risk_amount: Decimal
    leverage: Decimal
    liquidation_price: Decimal
    liquidation_buffer_ratio: Decimal  # |liq-entry| / |entry-stop|
    funding_cost: Decimal  # signed; negative means the position earns funding
    funding_rate: Decimal
    funding_intervals: int
    horizon_days: int
    conviction: Conviction
    risk_rule: str
    funding_assumption: str
    generated_at: datetime
