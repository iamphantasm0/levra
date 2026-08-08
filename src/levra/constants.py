"""Fixed product rules. Nothing here is configurable at runtime."""

from decimal import Decimal
from typing import Final

# The risk rule. Declared once, here. Never passed as a parameter, never read
# from config or env, never overridden — including by a user's thesis.
MAX_RISK_PCT: Final[Decimal] = Decimal("0.02")

SUPPORTED_ASSETS: Final[tuple[str, ...]] = ("BTC", "ETH")

SWING_TIMEFRAME: Final[str] = "4H"
SWING_LOOKBACK_CANDLES: Final[int] = 20
PIVOT_STRENGTH: Final[int] = 2

# Entry zone spans from the mark price toward the stop by this fraction of the
# mark-to-stop distance.
ENTRY_ZONE_STOP_DISTANCE_FRACTION: Final[Decimal] = Decimal("0.25")

MAX_LEVERAGE: Final[Decimal] = Decimal("10")

# Fallback only, used when the OKX position-tier lookup fails (Task 8). The live
# value is preferred; this exists so a tier-endpoint outage degrades the
# liquidation estimate instead of taking the endpoint down.
DEFAULT_MAINTENANCE_MARGIN_RATE: Final[Decimal] = Decimal("0.005")

RISK_RULE_DISCLOSURE: Final[str] = (
    "Risk: 2% of stated capital, structural stop only — non-negotiable"
)
FUNDING_ASSUMPTION_DISCLOSURE: Final[str] = (
    "Assumes current funding rate holds flat over horizon; "
    "actual cost will vary with market conditions."
)
