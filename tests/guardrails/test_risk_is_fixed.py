import ast
import inspect
from decimal import Decimal
from pathlib import Path

import pytest

from levra import constants
from levra.engine import build, entry, funding, liquidation, sizing, swings

SRC = Path(__file__).resolve().parents[2] / "src" / "levra"
ENGINE_MODULES = [build, entry, funding, liquidation, sizing, swings]
FORBIDDEN = ("risk_pct", "risk_percent", "max_risk", "risk_fraction", "risk_override")


def test_max_risk_pct_is_two_percent_and_a_decimal():
    assert Decimal("0.02") == constants.MAX_RISK_PCT
    assert isinstance(constants.MAX_RISK_PCT, Decimal)


def test_max_risk_pct_is_assigned_in_exactly_one_place():
    assignments = 0
    for path in SRC.rglob("*.py"):
        tree = ast.parse(path.read_text())
        for node in ast.walk(tree):
            targets = (
                [node.target]
                if isinstance(node, ast.AnnAssign)
                else node.targets
                if isinstance(node, ast.Assign)
                else []
            )
            for t in targets:
                if isinstance(t, ast.Name) and t.id == "MAX_RISK_PCT":
                    assignments += 1
                    assert path.name == "constants.py", (
                        f"MAX_RISK_PCT assigned outside constants.py: {path}"
                    )
    assert assignments == 1


@pytest.mark.parametrize("module", ENGINE_MODULES, ids=lambda m: m.__name__)
def test_no_engine_function_accepts_a_risk_parameter(module):
    for name, fn in inspect.getmembers(module, inspect.isfunction):
        if fn.__module__ != module.__name__:
            continue
        for param in inspect.signature(fn).parameters:
            lowered = param.lower()
            assert not any(f in lowered for f in FORBIDDEN), (
                f"{module.__name__}.{name} exposes risk parameter {param!r}"
            )


def test_no_environment_variable_can_change_the_risk_rule():
    source = (SRC / "constants.py").read_text()
    assert "getenv" not in source
    assert "environ" not in source
