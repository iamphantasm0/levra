"""Deployment wiring, read from the environment.

Nothing in this module may influence a number in a position spec. Every product
rule — the 2% risk cap, the swing lookback, the entry-zone fraction — lives in
``constants.py`` and is deliberately not configurable. This module carries only
the things that legitimately differ between machines: credentials, RPC
endpoints, contract and payout addresses.

Reads happen inside functions, never at import time, so importing the package
never depends on a populated environment and tests can set variables freely.
"""

import os
from dataclasses import dataclass

from levra.errors import ConfigError

# The LLM is reached through OpenRouter using the OpenAI-compatible SDK. The
# key names the *gateway*, not the model — the model itself is pinned in
# llm/client.py.
LLM_API_KEY_VAR = "OPENROUTER_API_KEY"

# X Layer network identifiers, confirmed against eth_chainId on 2026-08-14.
XLAYER_MAINNET_CHAIN_ID = 196
XLAYER_TESTNET_CHAIN_ID = 1952

# x402 settlement defaults. CAIP-2 network id; X Layer mainnet.
DEFAULT_X402_NETWORK = f"eip155:{XLAYER_MAINNET_CHAIN_ID}"
DEFAULT_X402_PRICE = "1.00"
DEFAULT_X402_DENOMINATION = "USDC"


def _clean(name: str) -> str:
    """Read an env var, treating whitespace-only as absent."""
    return os.environ.get(name, "").strip()


def llm_api_key() -> str:
    """The OpenRouter API key.

    Raises ConfigError — not KeyError — so a missing key surfaces as a clear,
    actionable 503 rather than an opaque 500 halfway through a request.
    """
    key = _clean(LLM_API_KEY_VAR)
    if not key:
        raise ConfigError(
            f"{LLM_API_KEY_VAR} is not set. Levra reaches Claude through "
            "OpenRouter; set this variable in the deployment environment "
            "(Railway → Variables) before calling /spec."
        )
    return key


def llm_is_configured() -> bool:
    """Whether the LLM key is present. Used for startup diagnostics only."""
    return bool(_clean(LLM_API_KEY_VAR))


@dataclass(frozen=True)
class ChainConfig:
    """Everything needed to write a spec hash to LevraLog."""

    rpc_url: str
    contract_address: str
    private_key: str
    chain_id: int


def chain_config() -> ChainConfig | None:
    """Chain-logging config, or None when logging is not configured.

    All-or-nothing on purpose: a partially configured chain writer is worse
    than a disabled one, because it fails per-request instead of at boot. When
    this returns None, ``log_to_chain`` is a documented no-op.
    """
    rpc_url = _clean("XLAYER_RPC_URL")
    address = _clean("LEVRA_LOG_ADDRESS")
    key = _clean("CHAIN_LOGGER_PRIVATE_KEY")

    if not (rpc_url and address and key):
        return None

    raw_chain_id = _clean("XLAYER_CHAIN_ID")
    try:
        chain_id = int(raw_chain_id) if raw_chain_id else XLAYER_MAINNET_CHAIN_ID
    except ValueError as err:
        raise ConfigError(f"XLAYER_CHAIN_ID must be an integer, got {raw_chain_id!r}") from err

    if not key.startswith("0x"):
        key = "0x" + key

    return ChainConfig(
        rpc_url=rpc_url,
        contract_address=address,
        private_key=key,
        chain_id=chain_id,
    )


def chain_logging_is_configured() -> bool:
    """Whether on-chain logging will actually write. Startup diagnostics only."""
    return chain_config() is not None


def x402_network() -> str:
    """CAIP-2 network id for payment settlement. Defaults to X Layer mainnet."""
    return _clean("X402_NETWORK") or DEFAULT_X402_NETWORK


def x402_price() -> str:
    return _clean("X402_PRICE") or DEFAULT_X402_PRICE


def x402_denomination() -> str:
    return _clean("X402_DENOMINATION") or DEFAULT_X402_DENOMINATION


def x402_pay_to() -> str | None:
    """The settlement address, or None when unset.

    There is deliberately no default. The previous zero-address fallback would
    have advertised 0x000…0 as the payee, and any caller who honoured it would
    have burned real funds.
    """
    return _clean("X402_PAY_TO_ADDRESS") or None
