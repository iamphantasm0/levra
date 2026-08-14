"""x402 payment middleware for FastAPI.

Follows the x402 HTTP 402 convention:

- an unpaid request returns 402 with a PAYMENT-REQUIRED header and a challenge
  body describing how to pay;
- a request carrying a well-formed, unused PAYMENT-SIGNATURE proceeds;
- /health and the OpenAPI surface are always free.

**Scope of the current verification, stated plainly.** This middleware checks
that a payment proof is well-formed and has not been presented before in this
process. It does *not* verify a signature cryptographically and does *not*
confirm settlement on chain — that needs an x402 facilitator, which is
post-hackathon work. The replay guard is in-memory: it does not survive a
restart and does not coordinate across replicas.

Nothing stronger than the above may be claimed in an error message.
"""

import logging
from collections import deque
from collections.abc import Awaitable, Callable
from typing import Any

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse, Response

from levra.config import x402_denomination, x402_network, x402_pay_to, x402_price

logger = logging.getLogger(__name__)

FREE_PATHS = {"/health", "/openapi.json", "/docs", "/redoc"}

# A payment proof is a hex string — long enough to be a plausible signature,
# not so strict that it rejects proofs from a facilitator not yet integrated.
MIN_SIGNATURE_LENGTH = 10

# Bounded, so a stream of distinct proofs cannot push a long-running process
# into unbounded memory growth.
REPLAY_CACHE_MAX = 10_000

_HEX_DIGITS = set("0123456789abcdefABCDEF")


class ReplayCache:
    """Remembers recently seen payment proofs, with FIFO eviction.

    Deliberately simple and deliberately per-process. Durable replay protection
    belongs in a facilitator with shared state; this exists so that the
    middleware's "already used" rejection is a true statement rather than a
    decorative one.
    """

    def __init__(self, maxlen: int = REPLAY_CACHE_MAX) -> None:
        self._order: deque[str] = deque()
        self._seen: set[str] = set()
        self._maxlen = maxlen

    def seen(self, signature: str) -> bool:
        return signature in self._seen

    def remember(self, signature: str) -> None:
        if signature in self._seen:
            return
        self._seen.add(signature)
        self._order.append(signature)
        while len(self._order) > self._maxlen:
            self._seen.discard(self._order.popleft())

    def clear(self) -> None:
        self._order.clear()
        self._seen.clear()


# Process-wide default. Shared deliberately: one app instance means one view of
# which proofs have been spent. Exposed at module level so it can be inspected
# and reset (tests, and any future operational endpoint) rather than being
# trapped inside a middleware instance the app builds lazily.
default_replay_cache = ReplayCache()


def is_well_formed(signature: str) -> bool:
    """Whether a proof is shaped like a hex payment signature."""
    if not signature.startswith("0x"):
        return False
    if len(signature) < MIN_SIGNATURE_LENGTH:
        return False
    return all(c in _HEX_DIGITS for c in signature[2:])


class X402Middleware(BaseHTTPMiddleware):
    def __init__(self, app: Any, replay_cache: ReplayCache | None = None) -> None:
        super().__init__(app)
        self.replay_cache = replay_cache if replay_cache is not None else default_replay_cache

    def _challenge(self) -> dict[str, str]:
        """The payment challenge returned with a 402.

        ``payTo`` appears only when an address is actually configured. The
        previous zero-address default advertised 0x000...0 as the payee; a
        caller who honoured it would have burned real funds.
        """
        challenge = {
            "scheme": "exact",
            "network": x402_network(),
            "price": f"${x402_price()}",
            "denomination": x402_denomination(),
        }
        pay_to = x402_pay_to()
        if pay_to:
            challenge["payTo"] = pay_to
        else:
            logger.error(
                "X402_PAY_TO_ADDRESS is not set - the 402 challenge cannot name a "
                "payee, so no caller can complete payment."
            )
        return challenge

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        if request.url.path in FREE_PATHS:
            return await call_next(request)

        signature = request.headers.get("PAYMENT-SIGNATURE")

        if not signature:
            return JSONResponse(
                status_code=402,
                content={"detail": "Payment required", "payment": self._challenge()},
                headers={
                    "PAYMENT-REQUIRED": f"exact ${x402_price()} {x402_denomination()}",
                },
            )

        if not is_well_formed(signature):
            return JSONResponse(
                status_code=402,
                content={
                    "detail": "Malformed payment proof - expected a hex string.",
                    "payment": self._challenge(),
                },
            )

        if self.replay_cache.seen(signature):
            return JSONResponse(
                status_code=402,
                content={
                    "detail": "This payment proof has already been used.",
                    "payment": self._challenge(),
                },
            )

        self.replay_cache.remember(signature)
        return await call_next(request)
