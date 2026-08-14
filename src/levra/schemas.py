"""Pydantic models for the API layer.

Numbers serialise as strings to avoid JSON float precision loss.
Domain types stay in frozen dataclasses; the API layer converts at the edge.
"""

from decimal import Decimal
from typing import Annotated

from pydantic import BaseModel, Field, PlainSerializer, SerializationInfo


def _decimal_to_str(v: Decimal, _info: SerializationInfo) -> str:
    return str(v)


DecimalStr = Annotated[Decimal, PlainSerializer(_decimal_to_str, return_type=str)]


class SpecRequest(BaseModel):
    thesis: str = Field(min_length=1, max_length=1000)


class EntryZoneResponse(BaseModel):
    low: DecimalStr
    high: DecimalStr
    sizing_edge: DecimalStr


class ScenariosResponse(BaseModel):
    bull: str
    base: str
    bear: str


class SpecResponse(BaseModel):
    asset: str
    direction: str
    entry_zone: EntryZoneResponse
    stop: DecimalStr
    stop_rationale: str
    position_size: DecimalStr
    notional: DecimalStr
    risk_amount: DecimalStr
    leverage: DecimalStr
    liquidation_price: DecimalStr
    liquidation_buffer_ratio: DecimalStr
    funding_cost: DecimalStr
    funding_rate: DecimalStr
    funding_intervals: int
    horizon_days: int
    conviction: str
    risk_rule: str
    funding_assumption: str
    generated_at: str
    scenarios: ScenariosResponse


class ErrorResponse(BaseModel):
    detail: str
