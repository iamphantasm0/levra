"""Tests for deployment configuration.

Two properties matter here: a missing variable produces a clear ConfigError
rather than a KeyError, and chain logging is all-or-nothing so it can never be
half-configured into per-request failure.
"""

import pytest

from levra.config import (
    DEFAULT_X402_NETWORK,
    XLAYER_MAINNET_CHAIN_ID,
    XLAYER_TESTNET_CHAIN_ID,
    chain_config,
    chain_logging_is_configured,
    llm_api_key,
    llm_is_configured,
    x402_network,
    x402_pay_to,
    x402_price,
)
from levra.errors import ConfigError, LevraError

CHAIN_VARS = ("XLAYER_RPC_URL", "LEVRA_LOG_ADDRESS", "CHAIN_LOGGER_PRIVATE_KEY")


@pytest.fixture(autouse=True)
def _clear_env(monkeypatch):
    for var in (
        "OPENROUTER_API_KEY",
        "XLAYER_CHAIN_ID",
        "X402_NETWORK",
        "X402_PRICE",
        "X402_DENOMINATION",
        "X402_PAY_TO_ADDRESS",
        *CHAIN_VARS,
    ):
        monkeypatch.delenv(var, raising=False)


class TestLlmKey:
    def test_missing_key_raises_config_error_not_key_error(self):
        with pytest.raises(ConfigError, match="OPENROUTER_API_KEY"):
            llm_api_key()

    def test_config_error_is_a_levra_error_so_the_handler_catches_it(self):
        # This is what maps the failure to a 503 instead of an unhandled 500.
        assert issubclass(ConfigError, LevraError)

    def test_error_message_names_the_gateway_not_anthropic(self, monkeypatch):
        with pytest.raises(ConfigError) as excinfo:
            llm_api_key()
        assert "OpenRouter" in str(excinfo.value)
        assert "ANTHROPIC_API_KEY" not in str(excinfo.value)

    def test_whitespace_only_counts_as_absent(self, monkeypatch):
        monkeypatch.setenv("OPENROUTER_API_KEY", "   ")
        assert not llm_is_configured()
        with pytest.raises(ConfigError):
            llm_api_key()

    def test_present_key_is_returned_stripped(self, monkeypatch):
        monkeypatch.setenv("OPENROUTER_API_KEY", "  sk-or-abc123  ")
        assert llm_api_key() == "sk-or-abc123"
        assert llm_is_configured()


class TestChainConfig:
    def test_unconfigured_returns_none(self):
        assert chain_config() is None
        assert not chain_logging_is_configured()

    @pytest.mark.parametrize("present", CHAIN_VARS)
    def test_partial_configuration_returns_none(self, monkeypatch, present):
        # All-or-nothing: one variable is not enough to switch logging on.
        monkeypatch.setenv(present, "0xabc")
        assert chain_config() is None

    def test_fully_configured_returns_config(self, monkeypatch):
        monkeypatch.setenv("XLAYER_RPC_URL", "https://rpc.xlayer.tech")
        monkeypatch.setenv("LEVRA_LOG_ADDRESS", "0x" + "11" * 20)
        monkeypatch.setenv("CHAIN_LOGGER_PRIVATE_KEY", "0x" + "22" * 32)

        cfg = chain_config()
        assert cfg is not None
        assert cfg.rpc_url == "https://rpc.xlayer.tech"
        assert cfg.chain_id == XLAYER_MAINNET_CHAIN_ID

    def test_chain_id_is_overridable_for_testnet(self, monkeypatch):
        monkeypatch.setenv("XLAYER_RPC_URL", "https://testrpc.xlayer.tech/terigon")
        monkeypatch.setenv("LEVRA_LOG_ADDRESS", "0x" + "11" * 20)
        monkeypatch.setenv("CHAIN_LOGGER_PRIVATE_KEY", "0x" + "22" * 32)
        monkeypatch.setenv("XLAYER_CHAIN_ID", str(XLAYER_TESTNET_CHAIN_ID))

        cfg = chain_config()
        assert cfg is not None
        assert cfg.chain_id == 1952

    def test_private_key_gets_hex_prefix_when_missing(self, monkeypatch):
        monkeypatch.setenv("XLAYER_RPC_URL", "https://rpc.xlayer.tech")
        monkeypatch.setenv("LEVRA_LOG_ADDRESS", "0x" + "11" * 20)
        monkeypatch.setenv("CHAIN_LOGGER_PRIVATE_KEY", "22" * 32)

        cfg = chain_config()
        assert cfg is not None
        assert cfg.private_key == "0x" + "22" * 32

    def test_non_integer_chain_id_raises_config_error(self, monkeypatch):
        monkeypatch.setenv("XLAYER_RPC_URL", "https://rpc.xlayer.tech")
        monkeypatch.setenv("LEVRA_LOG_ADDRESS", "0x" + "11" * 20)
        monkeypatch.setenv("CHAIN_LOGGER_PRIVATE_KEY", "0x" + "22" * 32)
        monkeypatch.setenv("XLAYER_CHAIN_ID", "not-a-number")

        with pytest.raises(ConfigError, match="XLAYER_CHAIN_ID"):
            chain_config()

    def test_config_is_frozen(self, monkeypatch):
        monkeypatch.setenv("XLAYER_RPC_URL", "https://rpc.xlayer.tech")
        monkeypatch.setenv("LEVRA_LOG_ADDRESS", "0x" + "11" * 20)
        monkeypatch.setenv("CHAIN_LOGGER_PRIVATE_KEY", "0x" + "22" * 32)

        cfg = chain_config()
        assert cfg is not None
        with pytest.raises(Exception):  # noqa: B017 - FrozenInstanceError
            cfg.rpc_url = "https://evil.example"  # type: ignore[misc]


class TestX402Config:
    def test_default_network_is_x_layer_not_base(self):
        # Regression: this defaulted to eip155:8453 (Base) while the project
        # deploys on X Layer.
        assert x402_network() == DEFAULT_X402_NETWORK
        assert x402_network() == f"eip155:{XLAYER_MAINNET_CHAIN_ID}"
        assert "8453" not in x402_network()

    def test_network_is_overridable(self, monkeypatch):
        monkeypatch.setenv("X402_NETWORK", f"eip155:{XLAYER_TESTNET_CHAIN_ID}")
        assert x402_network() == "eip155:1952"

    def test_pay_to_has_no_default(self):
        # Regression: a zero-address default would advertise a burn address.
        assert x402_pay_to() is None

    def test_pay_to_is_never_the_zero_address_by_default(self):
        assert x402_pay_to() != "0x" + "00" * 20

    def test_pay_to_is_returned_when_set(self, monkeypatch):
        monkeypatch.setenv("X402_PAY_TO_ADDRESS", "0x" + "ab" * 20)
        assert x402_pay_to() == "0x" + "ab" * 20

    def test_price_default(self):
        assert x402_price() == "1.00"
