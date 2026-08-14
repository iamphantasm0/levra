# Deployments

## X Layer Testnet

| Field | Value |
|-------|-------|
| Contract | `LevraLog` |
| File | `contracts/LevraLog.sol` |
| Chain ID | Pending verification |
| RPC | Pending verification |
| Address | Pending deploy |
| Deploy TX | Pending deploy |
| Deploy date | Pending |

## X Layer Mainnet

| Field | Value |
|-------|-------|
| Contract | `LevraLog` (same bytecode as testnet) |
| Chain ID | Pending verification |
| RPC | Pending verification |
| Address | Pending deploy |
| Deploy TX | Pending deploy |
| Deploy date | Pending |

## Deploy commands (Foundry)

```bash
# Testnet
forge create contracts/LevraLog.sol:LevraLog \
  --rpc-url $XLAYER_TESTNET_RPC \
  --private-key $LEVRA_DEPLOYER_KEY \
  --legacy

# Mainnet (after testnet verified)
forge create contracts/LevraLog.sol:LevraLog \
  --rpc-url $XLAYER_MAINNET_RPC \
  --private-key $LEVRA_DEPLOYER_KEY \
  --legacy
```

## Verification

```bash
# Cast the log function
cast send <CONTRACT_ADDRESS> "log(bytes32)" <SPEC_HASH> \
  --rpc-url $XLAYER_RPC \
  --private-key $LEVRA_DEPLOYER_KEY

# Read back
cast call <CONTRACT_ADDRESS> "count()(uint256)"
cast call <CONTRACT_ADDRESS> "getEntry(uint256)(bytes32,uint256)" 0
```