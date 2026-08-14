"""Shared test setup.

The x402 replay guard is process-wide by design, so it has to be reset between
tests — otherwise a payment proof spent by one test makes an unrelated test fail
for the right reason at the wrong time.
"""

import pytest

from levra.payments import default_replay_cache


@pytest.fixture(autouse=True)
def _reset_replay_cache():
    default_replay_cache.clear()
    yield
    default_replay_cache.clear()
