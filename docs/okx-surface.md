# OKX Public API Surface — Verified Aug 8, 2026

## Candles

- **URL**: `GET https://www.okx.com/api/v5/market/candles?instId=BTC-USDT-SWAP&bar=4H&limit=3`
- **HTTP**: 200
- **Envelope**: `{"code":"0","msg":"","data":[...]}`
- **Order**: **Newest-first**. Must reverse to oldest-first before engine use.
- **Fields** (per element): `[ts, o, h, l, c, vol, volCcy, volCcyQuote, confirm]`
  - `ts`: Unix ms string (e.g. `"1786147200000"`)
  - `o`, `h`, `l`, `c`: price strings (USD)
  - `vol`: string
  - `volCcy`: string
  - `volCcyQuote`: string
  - `confirm`: `"0"` (unconfirmed/forming) or `"1"` (confirmed)
- **Confirmed filter**: Only candles where `confirm == "1"` are eligible for pivot detection.
- **Conversion**: All price strings go `str → Decimal`, never via `float`.

## Funding Rate

- **URL**: `GET https://www.okx.com/api/v5/public/funding-rate?instId=BTC-USDT-SWAP`
- **HTTP**: 200
- **Envelope**: `{"code":"0","msg":"","data":[...]}`
- **Key fields**:
  - `fundingRate`: string (e.g. `"-0.0000003453401540"`)
  - `fundingTime`: Unix ms string
  - `nextFundingTime`: Unix ms string
  - `prevFundingTime`: Unix ms string
- **Interval**: 8 hours (28800000 ms between funding events), consistent with OKX documentation.

## Ticker (Mark Price)

- **URL**: `GET https://www.okx.com/api/v5/market/ticker?instId=BTC-USDT-SWAP`
- **HTTP**: 200
- **Envelope**: `{"code":"0","msg":"","data":[...]}`
- **Key fields**:
  - `last`: latest price (use as mark price proxy)
  - `askPx`, `bidPx`: best bid/ask
  - `high24h`, `low24h`: 24h range

## Position Tiers (Maintenance Margin)

- **URL**: `GET https://www.okx.com/api/v5/public/position-tiers?instType=SWAP&tdMode=isolated&instFamily=BTC-USDT`
- **HTTP**: 200
- **Envelope**: `{"code":"0","msg":"","data":[...]}`
- **Key fields**:
  - `tier`: tier number string
  - `minSz`, `maxSz`: position size range strings
  - `mmr`: maintenance margin rate string (e.g. `"0.004"`, `"0.005"`)
  - `imr`: initial margin rate string
  - `maxLever`: max leverage string
- **Default tier**: Tier 1 `mmr == "0.004"` (BTC). Fallback: `DEFAULT_MAINTENANCE_MARGIN_RATE = Decimal("0.005")`.

## Instrument ID Convention

- BTC perps: `BTC-USDT-SWAP`
- ETH perps: `ETH-USDT-SWAP`
- Instrument family for tiers: `BTC-USDT`, `ETH-USDT`
