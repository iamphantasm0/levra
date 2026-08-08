import asyncio
import json

import httpx

BASE = "https://www.okx.com"
PROBES = [
    (
        "candles",
        "/api/v5/market/candles",
        {"instId": "BTC-USDT-SWAP", "bar": "4H", "limit": "3"},
    ),
    (
        "funding",
        "/api/v5/public/funding-rate",
        {"instId": "BTC-USDT-SWAP"},
    ),
    (
        "ticker",
        "/api/v5/market/ticker",
        {"instId": "BTC-USDT-SWAP"},
    ),
    (
        "tiers",
        "/api/v5/public/position-tiers",
        {"instType": "SWAP", "tdMode": "isolated", "instFamily": "BTC-USDT"},
    ),
]


async def main() -> None:
    async with httpx.AsyncClient(base_url=BASE, timeout=10.0) as client:
        for name, path, params in PROBES:
            r = await client.get(path, params=params)
            print(f"=== {name} {r.status_code} ===")
            body = r.json()
            print(json.dumps(body, indent=2)[:1200])
            print()


if __name__ == "__main__":
    asyncio.run(main())
