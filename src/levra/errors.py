class LevraError(Exception):
    """Base class for all Levra domain errors."""


class UnsupportedAsset(LevraError):
    """Thesis names an asset outside BTC/ETH."""


class NoValidStructuralStop(LevraError):
    """No confirmed higher-low (long) or lower-high (short) in the lookback window."""


class InvalidZone(LevraError):
    """Entry zone is degenerate — zero width, or on the wrong side of the stop."""


class StopTooTight(LevraError):
    """Stop distance implies leverage above the ceiling on the stated capital."""


class ThesisIncomplete(LevraError):
    """The parser could not extract all required fields from the thesis text."""


class NarrationFailed(LevraError):
    """The narrator could not produce a valid scenario set."""


class MarketDataError(LevraError):
    """OKX returned an error envelope, a bad status, or an unusable payload."""


class ConfigError(LevraError):
    """A required deployment variable is missing or malformed.

    Distinct from the domain errors above: this is an operator problem, not a
    caller problem, and maps to 503 rather than 4xx.
    """
