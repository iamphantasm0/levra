"""Unit tests for x402 proof handling and the payment challenge.

These cover the claims the middleware makes about itself. The rule is that an
error message may not assert more than the code actually checks — so "already
used" has to be backed by a real replay guard.
"""

import httpx
import pytest
from fastapi import FastAPI

from levra.api import app
from levra.config import XLAYER_MAINNET_CHAIN_ID
from levra.payments import ReplayCache, X402Middleware, is_well_formed

VALID_SIG = "0x" + "ab" * 32


class TestIsWellFormed:
    @pytest.mark.parametrize(
        "sig",
        ["0x" + "ab" * 32, "0x" + "0" * 8, "0xABCDEF0123", "0x" + "f" * 130],
    )
    def test_accepts_hex_strings_of_sufficient_length(self, sig):
        assert is_well_formed(sig)

    @pytest.mark.parametrize(
        "sig",
        [
            "",
            "bad",
            "ab" * 32,  # no 0x prefix
            "0xshort",  # under the minimum length
            "0x" + "zz" * 32,  # non-hex characters
            "0x" + "ab" * 31 + "g!",
        ],
    )
    def test_rejects_malformed_proofs(self, sig):
        assert not is_well_formed(sig)


class TestReplayCache:
    def test_remembers_a_signature(self):
        cache = ReplayCache()
        assert not cache.seen(VALID_SIG)
        cache.remember(VALID_SIG)
        assert cache.seen(VALID_SIG)

    def test_remember_is_idempotent(self):
        cache = ReplayCache()
        cache.remember(VALID_SIG)
        cache.remember(VALID_SIG)
        assert cache.seen(VALID_SIG)

    def test_evicts_oldest_beyond_maxlen(self):
        cache = ReplayCache(maxlen=3)
        for i in range(4):
            cache.remember(f"0x{i:064x}")

        assert not cache.seen(f"0x{0:064x}")  # evicted
        assert cache.seen(f"0x{3:064x}")  # retained

    def test_never_grows_past_maxlen(self):
        cache = ReplayCache(maxlen=5)
        for i in range(50):
            cache.remember(f"0x{i:064x}")
        assert len(cache._seen) == 5  # noqa: SLF001

    def test_clear_empties_the_cache(self):
        cache = ReplayCache()
        cache.remember(VALID_SIG)
        cache.clear()
        assert not cache.seen(VALID_SIG)


class TestChallenge:
    def test_omits_pay_to_when_unset(self, monkeypatch):
        monkeypatch.delenv("X402_PAY_TO_ADDRESS", raising=False)
        challenge = X402Middleware(app)._challenge()  # noqa: SLF001
        assert "payTo" not in challenge

    def test_includes_pay_to_when_set(self, monkeypatch):
        monkeypatch.setenv("X402_PAY_TO_ADDRESS", "0x" + "cd" * 20)
        challenge = X402Middleware(app)._challenge()  # noqa: SLF001
        assert challenge["payTo"] == "0x" + "cd" * 20

    def test_network_is_x_layer(self, monkeypatch):
        monkeypatch.delenv("X402_NETWORK", raising=False)
        challenge = X402Middleware(app)._challenge()  # noqa: SLF001
        assert challenge["network"] == f"eip155:{XLAYER_MAINNET_CHAIN_ID}"


def _guarded_app() -> FastAPI:
    """A minimal app behind the middleware.

    Keeps replay behaviour independent of the real /spec handler, which would
    otherwise drag OKX and the LLM into a payment test.
    """
    inner = FastAPI()
    inner.add_middleware(X402Middleware)

    @inner.post("/spec")
    async def _spec() -> dict[str, str]:
        return {"ok": "true"}

    @inner.get("/health")
    async def _health() -> dict[str, str]:
        return {"status": "ok"}

    return inner


class TestReplayOverHttp:
    async def test_first_use_passes_and_second_use_is_rejected(self):
        """The middleware claims a proof can be 'already used' — prove it."""
        sig = "0x" + "cc" * 32
        transport = httpx.ASGITransport(app=_guarded_app())

        async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
            first = await c.post("/spec", headers={"PAYMENT-SIGNATURE": sig})
            second = await c.post("/spec", headers={"PAYMENT-SIGNATURE": sig})

        assert first.status_code == 200
        assert second.status_code == 402
        assert "already been used" in second.json()["detail"]

    async def test_distinct_proofs_both_pass(self):
        transport = httpx.ASGITransport(app=_guarded_app())
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
            first = await c.post("/spec", headers={"PAYMENT-SIGNATURE": "0x" + "01" * 32})
            second = await c.post("/spec", headers={"PAYMENT-SIGNATURE": "0x" + "02" * 32})

        assert first.status_code == 200
        assert second.status_code == 200

    async def test_health_needs_no_proof(self):
        transport = httpx.ASGITransport(app=_guarded_app())
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
            resp = await c.get("/health")
        assert resp.status_code == 200

    async def test_malformed_proof_mentions_the_format(self, monkeypatch):
        monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
            resp = await c.post(
                "/spec",
                json={"thesis": "Long ETH"},
                headers={"PAYMENT-SIGNATURE": "not-hex"},
            )
        assert resp.status_code == 402
        assert "hex" in resp.json()["detail"].lower()

    async def test_unpaid_challenge_advertises_x_layer(self, monkeypatch):
        monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
        monkeypatch.delenv("X402_NETWORK", raising=False)
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
            resp = await c.post("/spec", json={"thesis": "Long ETH"})

        payment = resp.json()["payment"]
        assert payment["network"] == f"eip155:{XLAYER_MAINNET_CHAIN_ID}"
        assert payment["network"] != "eip155:8453"
