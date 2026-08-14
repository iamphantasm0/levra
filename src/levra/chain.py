"""On-chain spec logging.

Produces a deterministic keccak256 hash of a PositionSpec and writes it to the
LevraLog contract on X Layer. The hash is derived from a canonical JSON
serialisation, so the same spec always produces the same hash — that is what
makes a logged entry verifiable after the fact.

Two rules govern this module:

1. **A chain-write failure must never fail the API response.** The spec is the
   product; the log is corroboration. Every error is swallowed and recorded.
2. **It is a documented no-op when unconfigured.** A missing RPC URL, contract
   address, or signing key means logging is off, not broken.
"""

import asyncio
import json
import logging
from decimal import Decimal
from typing import Any

from Crypto.Hash import keccak

from levra.config import ChainConfig, chain_config
from levra.models import PositionSpec

logger = logging.getLogger(__name__)

# Minimal ABI — only the one function this module calls.
LEVRA_LOG_ABI: list[dict[str, Any]] = [
    {
        "inputs": [{"internalType": "bytes32", "name": "specHash", "type": "bytes32"}],
        "name": "log",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function",
    }
]

# log() is one array push plus an event — the Foundry suite measures ~76k gas.
# This ceiling leaves headroom without risking a badly overpriced transaction.
GAS_LIMIT_FALLBACK = 150_000


def _json_default(obj: Any) -> Any:
    if isinstance(obj, Decimal):
        return str(obj)
    raise TypeError(f"Object of type {type(obj)} is not JSON serialisable")


def canonical_bytes(spec: PositionSpec) -> bytes:
    """The exact byte string that gets hashed.

    Exposed separately so anyone holding a published spec can reproduce its
    hash without reimplementing the field ordering.
    """
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
    return json.dumps(
        canonical, default=_json_default, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")


def hash_spec(spec: PositionSpec) -> bytes:
    k = keccak.new(digest_bits=256)
    k.update(canonical_bytes(spec))
    return k.digest()


def hash_spec_hex(spec: PositionSpec) -> str:
    return "0x" + hash_spec(spec).hex()


def _send_log_tx(spec_hash: bytes, cfg: ChainConfig) -> str:
    """Sign and broadcast the log transaction. Blocking — run it in a thread.

    web3 is imported lazily: it is a heavy import, and an app with chain
    logging disabled should not pay for it at boot.
    """
    from eth_account import Account
    from web3 import Web3

    w3 = Web3(Web3.HTTPProvider(cfg.rpc_url, request_kwargs={"timeout": 20}))
    account = Account.from_key(cfg.private_key)
    contract = w3.eth.contract(
        address=Web3.to_checksum_address(cfg.contract_address),
        abi=LEVRA_LOG_ABI,
    )

    call = contract.functions.log(spec_hash)
    try:
        gas = int(call.estimate_gas({"from": account.address}) * 12 // 10)
    except Exception:  # noqa: BLE001 - estimation is best effort
        logger.debug("gas estimation failed; falling back to %d", GAS_LIMIT_FALLBACK)
        gas = GAS_LIMIT_FALLBACK

    tx = call.build_transaction(
        {
            "chainId": cfg.chain_id,
            "from": account.address,
            "nonce": w3.eth.get_transaction_count(account.address),
            "gas": gas,
            "gasPrice": w3.eth.gas_price,
        }
    )
    signed = account.sign_transaction(tx)
    return w3.eth.send_raw_transaction(signed.raw_transaction).hex()


async def log_to_chain(spec: PositionSpec, rpc_url: str | None = None) -> str | None:
    """Fire-and-forget: log the spec hash to LevraLog on X Layer.

    Returns the transaction hash, or None when logging is disabled or the write
    failed. Never raises — the caller's response must not depend on the chain.

    ``rpc_url`` overrides the configured endpoint, for testing against a local
    node without rewriting the environment.
    """
    cfg = chain_config()
    if cfg is None:
        logger.debug(
            "chain logging disabled - spec hash %s computed but not written",
            hash_spec_hex(spec),
        )
        return None

    if rpc_url is not None:
        cfg = ChainConfig(
            rpc_url=rpc_url,
            contract_address=cfg.contract_address,
            private_key=cfg.private_key,
            chain_id=cfg.chain_id,
        )

    spec_hash = hash_spec(spec)
    try:
        tx_hash = await asyncio.to_thread(_send_log_tx, spec_hash, cfg)
    except Exception:
        # Deliberately broad: nothing about logging may surface to the caller.
        logger.warning(
            "chain log failed for spec hash 0x%s - response unaffected",
            spec_hash.hex(),
            exc_info=True,
        )
        return None

    logger.info("logged spec hash 0x%s in tx %s", spec_hash.hex(), tx_hash)
    return tx_hash
