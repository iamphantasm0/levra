"""Tests for the on-chain logging path.

Two guarantees are load-bearing and both are tested here:

1. logging is a no-op when unconfigured, and
2. a chain failure never propagates to the caller.

Plus the hash contract: the canonical bytes are what a third party would need to
reproduce a hash, so their shape is part of the deliverable.
"""

import json
from datetime import UTC, datetime
from decimal import Decimal

import pytest

from levra.chain import canonical_bytes, hash_spec, hash_spec_hex, log_to_chain
from levra.engine.build import build_spec
from levra.models import Candle, Conviction, Direction, MarketSnapshot, Thesis

CHAIN_VARS = ("XLAYER_RPC_URL", "LEVRA_LOG_ADDRESS", "CHAIN_LOGGER_PRIVATE_KEY")


@pytest.fixture(autouse=True)
def _no_chain_env(monkeypatch):
    for var in (*CHAIN_VARS, "XLAYER_CHAIN_ID"):
        monkeypatch.delenv(var, raising=False)


@pytest.fixture
def spec():
    start = datetime(2026, 8, 1, tzinfo=UTC)
    lows = ["3200", "3180", "3150", "3180", "3205", "3210", "3190", "3205", "3215"]
    candles = tuple(
        Candle(
            ts=start.replace(hour=(i * 4) % 24, day=1 + (i * 4) // 24),
            open=Decimal(low),
            high=Decimal(low) + Decimal("120"),
            low=Decimal(low),
            close=Decimal(low) + Decimal("60"),
            confirmed=True,
        )
        for i, low in enumerate(lows)
    )
    snapshot = MarketSnapshot(
        asset="ETH",
        mark_price=Decimal("3300"),
        candles=candles,
        funding_rate=Decimal("0.0001"),
        funding_interval_hours=8,
        maintenance_margin_rate=Decimal("0.005"),
        fetched_at=start,
    )
    thesis = Thesis(
        asset="ETH",
        direction=Direction.LONG,
        horizon_days=30,
        conviction=Conviction.MODERATE,
        capital=Decimal("2000"),
        raw_text="Long ETH 30d",
    )
    return build_spec(thesis, snapshot)


class TestCanonicalBytes:
    def test_is_deterministic(self, spec):
        assert canonical_bytes(spec) == canonical_bytes(spec)

    def test_keys_are_sorted_and_compact(self, spec):
        raw = canonical_bytes(spec).decode()
        parsed = json.loads(raw)
        assert list(parsed) == sorted(parsed)
        # Re-serialising with the canonical settings must reproduce the bytes
        # exactly — that is what makes the hash reproducible elsewhere.
        assert json.dumps(parsed, sort_keys=True, separators=(",", ":")) == raw

    def test_decimals_serialise_as_strings_not_floats(self, spec):
        parsed = json.loads(canonical_bytes(spec))
        # A float here would make the hash platform-dependent.
        assert isinstance(parsed["stop"], str)
        assert isinstance(parsed["position_size"], str)
        assert isinstance(parsed["entry_zone"]["low"], str)

    def test_hash_matches_keccak_of_canonical_bytes(self, spec):
        from Crypto.Hash import keccak

        k = keccak.new(digest_bits=256)
        k.update(canonical_bytes(spec))
        assert hash_spec(spec) == k.digest()

    def test_hex_form_is_32_bytes_prefixed(self, spec):
        assert hash_spec_hex(spec).startswith("0x")
        assert len(hash_spec_hex(spec)) == 66


class TestLogToChainDisabled:
    async def test_returns_none_when_unconfigured(self, spec):
        assert await log_to_chain(spec) is None

    async def test_does_not_raise_when_unconfigured(self, spec):
        await log_to_chain(spec)

    async def test_makes_no_network_call_when_unconfigured(self, spec, monkeypatch):
        def explode(*_args, **_kwargs):
            raise AssertionError("no transaction may be attempted when disabled")

        monkeypatch.setattr("levra.chain._send_log_tx", explode)
        assert await log_to_chain(spec) is None


class TestLogToChainFailureIsNonFatal:
    async def test_transaction_failure_returns_none_and_does_not_raise(
        self, spec, monkeypatch
    ):
        monkeypatch.setenv("XLAYER_RPC_URL", "https://rpc.invalid.example")
        monkeypatch.setenv("LEVRA_LOG_ADDRESS", "0x" + "11" * 20)
        monkeypatch.setenv("CHAIN_LOGGER_PRIVATE_KEY", "0x" + "22" * 32)

        def explode(*_args, **_kwargs):
            raise RuntimeError("RPC unreachable")

        monkeypatch.setattr("levra.chain._send_log_tx", explode)

        # The whole point: the caller's response must survive this.
        assert await log_to_chain(spec) is None

    async def test_failure_is_logged_as_a_warning(self, spec, monkeypatch, caplog):
        monkeypatch.setenv("XLAYER_RPC_URL", "https://rpc.invalid.example")
        monkeypatch.setenv("LEVRA_LOG_ADDRESS", "0x" + "11" * 20)
        monkeypatch.setenv("CHAIN_LOGGER_PRIVATE_KEY", "0x" + "22" * 32)
        monkeypatch.setattr(
            "levra.chain._send_log_tx",
            lambda *_a, **_k: (_ for _ in ()).throw(RuntimeError("boom")),
        )

        with caplog.at_level("WARNING"):
            await log_to_chain(spec)

        assert any("chain log failed" in r.message for r in caplog.records)

    async def test_success_returns_the_transaction_hash(self, spec, monkeypatch):
        monkeypatch.setenv("XLAYER_RPC_URL", "https://rpc.xlayer.tech")
        monkeypatch.setenv("LEVRA_LOG_ADDRESS", "0x" + "11" * 20)
        monkeypatch.setenv("CHAIN_LOGGER_PRIVATE_KEY", "0x" + "22" * 32)
        monkeypatch.setattr("levra.chain._send_log_tx", lambda *_a, **_k: "0xdeadbeef")

        assert await log_to_chain(spec) == "0xdeadbeef"

    async def test_hash_passed_to_the_transaction_is_the_spec_hash(
        self, spec, monkeypatch
    ):
        monkeypatch.setenv("XLAYER_RPC_URL", "https://rpc.xlayer.tech")
        monkeypatch.setenv("LEVRA_LOG_ADDRESS", "0x" + "11" * 20)
        monkeypatch.setenv("CHAIN_LOGGER_PRIVATE_KEY", "0x" + "22" * 32)

        captured = {}

        def capture(spec_hash, cfg):
            captured["hash"] = spec_hash
            captured["chain_id"] = cfg.chain_id
            return "0xabc"

        monkeypatch.setattr("levra.chain._send_log_tx", capture)
        await log_to_chain(spec)

        assert captured["hash"] == hash_spec(spec)
        assert captured["chain_id"] == 196
