"""On-chain spec logging.

Produces a deterministic keccak256 hash of a PositionSpec, then (in production)
writes it to the LevraLog contract on X Layer. The hash is derived from a
canonical JSON serialisation so a spec produces the same hash every time.
"""

import json
from decimal import Decimal
from typing import Any

from Crypto.Hash import keccak

from levra.models import PositionSpec


def _json_default(obj: Any) -> Any:
    if isinstance(obj, Decimal):
        return str(obj)
    raise TypeError(f"Object of type {type(obj)} is not JSON serialisable")


def hash_spec(spec: PositionSpec) -> bytes:
    canonical: dict[str, Any] = {
        "asset": spec.asset,
        "direction": spec.direction.value,
        "entry_zone": {
            "low": spec.entry_zone.low,
            "high": spec.entry_zone.high,
            "sizing_edge": spec.entry_zone.sizing_edge,
        },
        "stop": spec.stop,
        "stop_rationale": spec.stop_rationale,
        "position_size": spec.position_size,
        "notional": spec.notional,
        "risk_amount": spec.risk_amount,
        "leverage": spec.leverage,
        "liquidation_price": spec.liquidation_price,
        "liquidation_buffer_ratio": spec.liquidation_buffer_ratio,
        "funding_cost": spec.funding_cost,
        "funding_rate": spec.funding_rate,
        "funding_intervals": spec.funding_intervals,
        "horizon_days": spec.horizon_days,
        "conviction": spec.conviction.value,
        "generated_at": spec.generated_at.isoformat(),
    }
    json_bytes = json.dumps(
        canonical, default=_json_default, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    k = keccak.new(digest_bits=256)
    k.update(json_bytes)
    return k.digest()


def hash_spec_hex(spec: PositionSpec) -> str:
    return "0x" + hash_spec(spec).hex()


async def log_to_chain(spec: PositionSpec, rpc_url: str | None = None) -> None:
    """Fire-and-forget: logs the spec hash to the LevraLog contract.

    Currently computes the hash only. The actual on-chain transaction is wired
    post-X Layer testnet deploy (Task 15). A chain-write failure must not fail
    the API response.
    """
    _ = hash_spec_hex(spec)
    if rpc_url is None:
        return