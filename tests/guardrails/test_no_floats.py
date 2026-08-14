import ast
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parents[2] / "src" / "levra"
NUMERIC_PATH = [SRC / "engine", SRC / "models.py", SRC / "constants.py"]


def _python_files() -> list[Path]:
    files: list[Path] = []
    for target in NUMERIC_PATH:
        files.extend(target.rglob("*.py") if target.is_dir() else [target])
    return files


@pytest.mark.parametrize("path", _python_files(), ids=lambda p: p.name)
def test_no_float_literals_or_calls(path: Path):
    tree = ast.parse(path.read_text())
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, float):
            pytest.fail(f"{path.name}:{node.lineno} float literal {node.value!r}")
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "float"
        ):
            pytest.fail(f"{path.name}:{node.lineno} float() call")


@pytest.mark.parametrize("path", _python_files(), ids=lambda p: p.name)
def test_no_float_annotations(path: Path):
    tree = ast.parse(path.read_text())
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.AnnAssign)
            and isinstance(node.annotation, ast.Name)
            and node.annotation.id == "float"
        ):
            pytest.fail(f"{path.name}:{node.lineno} float annotation")
        if (
            isinstance(node, ast.arg)
            and isinstance(node.annotation, ast.Name)
            and node.annotation.id == "float"
        ):
            pytest.fail(f"{path.name}:{node.lineno} float parameter")
