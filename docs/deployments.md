# Deployments

## Network information — verified

Confirmed by `eth_chainId` against each endpoint on **2026-08-14**, not taken
from documentation.

| Network | Chain ID | Hex | RPC |
|---|---|---|---|
| X Layer mainnet | **196** | `0xc4` | `https://rpc.xlayer.tech` (alt: `https://xlayerrpc.okx.com`) |
| X Layer testnet | **1952** | `0x7a0` | `https://testrpc.xlayer.tech/terigon` (alt: `https://xlayertestrpc.okx.com/terigon`) |

> **The testnet chain ID is 1952, not 195.** Several OKX documentation pages
> still publish `195` with a bare `https://testrpc.xlayer.tech` URL. That is the
> retired Polygon CDK zkEVM testnet; X Layer has since migrated to the OP Stack.
> All three live testnet endpoints — including the bare one — now answer `0x7a0`.
> Deploying against `195` targets a chain that no longer accepts transactions.

Native gas token on both networks is **OKB**.

Explorers:
- mainnet — <https://www.okx.com/web3/explorer/xlayer>
- testnet — <https://www.okx.com/web3/explorer/xlayer-test>

## Contract status

`contracts/LevraLog.sol` compiles under Solc 0.8.28 and its Foundry suite passes
(8 tests, including a 256-run fuzz over the hash round-trip). Bytecode is
identical between testnet and mainnet — `evm_version` is pinned to `cancun` in
`foundry.toml` so this stays true.

### X Layer Testnet

| Field | Value |
|-------|-------|
| Contract | `LevraLog` |
| Chain ID | 1952 |
| RPC | `https://testrpc.xlayer.tech/terigon` |
| Address | Pending deploy |
| Deploy TX | Pending deploy |
| Deploy date | Pending |

### X Layer Mainnet

| Field | Value |
|-------|-------|
| Contract | `LevraLog` (same bytecode as testnet) |
| Chain ID | 196 |
| RPC | `https://rpc.xlayer.tech` |
| Address | Pending deploy |
| Deploy TX | Pending deploy |
| Deploy date | Pending |

## Prerequisites

1. **Foundry.** `curl -L https://foundry.paradigm.xyz | bash && foundryup`
2. **forge-std**, fetched at a pinned tag (not vendored):
   ```bash
   git clone --depth 1 --branch v1.16.2 \
     https://github.com/foundry-rs/forge-std lib/forge-std
   ```
   `lib/` is gitignored. If you would rather track it as a submodule, run
   `forge install foundry-rs/forge-std` instead and drop the ignore rule.
3. **A funded deployer key.** Needs OKB for gas on the target network. Use a
   dedicated key, not a treasury key.

## Deploy commands (Foundry)

```bash
export XLAYER_TESTNET_RPC=https://testrpc.xlayer.tech/terigon
export XLAYER_MAINNET_RPC=https://rpc.xlayer.tech
export LEVRA_DEPLOYER_KEY=0x...

# Sanity check: confirm the chain you are about to deploy to.
cast chain-id --rpc-url $XLAYER_TESTNET_RPC   # expect 1952
cast chain-id --rpc-url $XLAYER_MAINNET_RPC   # expect 196

# Confirm the deployer has gas.
cast balance $(cast wallet address --private-key $LEVRA_DEPLOYER_KEY) \
  --rpc-url $XLAYER_TESTNET_RPC

# Testnet
forge create contracts/LevraLog.sol:LevraLog \
  --rpc-url $XLAYER_TESTNET_RPC \
  --private-key $LEVRA_DEPLOYER_KEY \
  --broadcast \
  --legacy

# Mainnet (only after the testnet address is recorded above)
forge create contracts/LevraLog.sol:LevraLog \
  --rpc-url $XLAYER_MAINNET_RPC \
  --private-key $LEVRA_DEPLOYER_KEY \
  --broadcast \
  --legacy
```

## Verifying a deploy

```bash
export ADDR=<deployed address>
export RPC=$XLAYER_TESTNET_RPC

# Fresh contract reads zero.
cast call $ADDR "count()(uint256)" --rpc-url $RPC

# Write a hash.
cast send $ADDR "log(bytes32)" 0x$(printf 'levra' | cast keccak | cut -c3-) \
  --rpc-url $RPC --private-key $LEVRA_DEPLOYER_KEY

# Read it back.
cast call $ADDR "count()(uint256)" --rpc-url $RPC
cast call $ADDR "getEntry(uint256)(bytes32,uint256)" 0 --rpc-url $RPC
```

## Wiring the app to the deployed contract

Set these on Railway once an address exists. All three are required together —
`chain_config()` is all-or-nothing, so a partial set leaves logging off rather
than failing per request.

| Variable | Value |
|---|---|
| `XLAYER_RPC_URL` | the RPC for the network you deployed to |
| `XLAYER_CHAIN_ID` | `196` (mainnet) or `1952` (testnet) |
| `LEVRA_LOG_ADDRESS` | the deployed contract address |
| `CHAIN_LOGGER_PRIVATE_KEY` | gas-paying hot key, funded with OKB |

Confirm it took effect: generate a spec, then check `count()` incremented.
