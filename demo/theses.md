# Canned Demo Theses

Pre-run, high-quality theses for the OKX.ai listing and live demo.
Run these through the production app and save the actual responses.

## 1. ETH moderate-conviction long
> I think ETH grinds up into September. Moderate conviction. $2,000 risk capital.

## 2. BTC high-conviction short
> BTC looks heavy here. The rally is losing steam and I think we flush
> into the end of August. High conviction. $5,000 risk capital.

## 3. ETH low-conviction long (small size)
> Just a small ETH position for the week, light touch. Low conviction.
> $500 risk capital.

## 4. BTC moderate conviction long (longer horizon)
> BTC is accumulating for the next leg up. I want to be positioned for
> Q4. Moderate conviction. $10,000 risk capital. Horizon: 60 days.

## 5. Short-side case
> ETH has a clear lower-high structure on the 4H. I think we retest
> the range lows. High conviction. $3,000 risk capital.

## Running the demo theses

```bash
curl -s https://levra-production.up.railway.app/spec \
  -H 'content-type: application/json' \
  -H 'PAYMENT-SIGNATURE: 0x'"$(python3 -c 'import secrets; print(secrets.token_hex(32))')" \
  -d '{"thesis":"I think ETH grinds up into September, moderate conviction, $2,000 risk capital"}' | jq
```