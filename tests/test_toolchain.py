"""Phase A's proof that the toolchain itself works.

If this file passes, the src layout, the editable install, and the pinned Python are
all real — which is the precondition for every other test in the repo.
"""

from __future__ import annotations

import sys
import tomllib
from importlib.metadata import version
from pathlib import Path

import bakeoff

PYPROJECT = Path(__file__).resolve().parent.parent / "pyproject.toml"


def test_python_is_at_least_3_12() -> None:
    assert sys.version_info >= (3, 12)


def test_package_imports_and_declares_a_version() -> None:
    assert bakeoff.__version__


def test_installed_version_matches_pyproject() -> None:
    declared = tomllib.loads(PYPROJECT.read_text())["project"]["version"]
    assert bakeoff.__version__ == declared
    assert version("bakeoff") == declared


def test_dependency_surface_is_exactly_the_pre_registered_five() -> None:
    """SPEC.md names the dependency surface in full; drift is a spec violation."""
    declared = tomllib.loads(PYPROJECT.read_text())["project"]["dependencies"]
    names = {dep.split(">=")[0].split("[")[0].strip().lower() for dep in declared}
    assert names == {"click", "httpx", "jsonschema", "pydantic", "pyyaml"}
