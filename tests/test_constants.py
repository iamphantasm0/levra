from decimal import Decimal

from levra import constants


def test_max_risk_pct_is_exactly_two_percent():
    assert Decimal("0.02") == constants.MAX_RISK_PCT


def test_max_risk_pct_is_decimal_not_float():
    assert isinstance(constants.MAX_RISK_PCT, Decimal)


def test_risk_disclosure_is_verbatim():
    assert (
        constants.RISK_RULE_DISCLOSURE
        == "Risk: 2% of stated capital, structural stop only — non-negotiable"
    )


def test_funding_disclosure_is_verbatim():
    assert constants.FUNDING_ASSUMPTION_DISCLOSURE == (
        "Assumes current funding rate holds flat over horizon; "
        "actual cost will vary with market conditions."
    )
