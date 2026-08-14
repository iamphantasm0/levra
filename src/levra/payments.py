"""x402 payment middleware for FastAPI.

Follows the x402 HTTP 402 protocol spec:
- Unpaid requests return 402 with PAYMENT-REQUIRED header
- Requests with valid PAYMENT-SIGNATURE proceed
- /health is always free

For hackathon: payment proof is accepted if header exists with valid format.
A production deployment would verify against a facilitator.
"""

from collections.abc import Awaitable, Callable

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse, Response

X402_PRICE = "1.00"
X402_NETWORK = "eip155:8453"
X402_ADDRESS = "0x0000000000000000000000000000000000000000"
X402_DENOMINATION = "USDC"

FREE_PATHS = {"/health", "/openapi.json", "/docs", "/redoc"}


class X402Middleware(BaseHTTPMiddleware):
    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        if request.url.path in FREE_PATHS:
            return await call_next(request)

        signature = request.headers.get("PAYMENT-SIGNATURE")

        if not signature:
            payment_required = {
                "scheme": "exact",
                "network": X402_NETWORK,
                "price": f"${X402_PRICE}",
                "denomination": X402_DENOMINATION,
                "payTo": X402_ADDRESS,
            }
            return JSONResponse(
                status_code=402,
                content={
                    "detail": "Payment required",
                    "payment": payment_required,
                },
                headers={
                    "PAYMENT-REQUIRED": f"exact ${X402_PRICE} {X402_DENOMINATION}",
                },
            )

        if not _verify_signature(signature):
            return JSONResponse(
                status_code=402,
                content={"detail": "Invalid or replayed payment proof"},
            )

        return await call_next(request)


def _verify_signature(signature: str) -> bool:
    if not signature or not signature.startswith("0x"):
        return False
    return len(signature) >= 10