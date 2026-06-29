"""Package-import tests for the Milestone 0 skeleton.

These assert the package is importable, its metadata is coherent, and every
planned subpackage exists and imports cleanly. They depend only on the package
itself (no third-party imports beyond what the package already requires).
"""

from __future__ import annotations

import importlib
import tomllib
from pathlib import Path

import bioscientist_os

ROOT = Path(__file__).resolve().parents[1]


def test_version_is_nonempty_string() -> None:
    assert isinstance(bioscientist_os.__version__, str)
    assert bioscientist_os.__version__.strip(), "version must not be blank"


def test_version_matches_pyproject() -> None:
    """The in-code version must match the packaging metadata (single source of truth)."""
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    assert bioscientist_os.__version__ == pyproject["project"]["version"]


def test_package_exposes_identity_and_safety() -> None:
    assert bioscientist_os.PACKAGE_NAME == "bioscientist-os"
    assert bioscientist_os.DESCRIPTION.strip()
    note = bioscientist_os.SAFETY_NOTE.lower()
    # The non-clinical stance is part of the package's public surface.
    assert "not a medical" in note
    assert "diagnos" in note


def test_four_epistemic_levels_in_order() -> None:
    levels = bioscientist_os.EPISTEMIC_LEVELS
    assert [name for name, _ in levels] == [
        "observed metadata",
        "extracted claim",
        "inferred relation",
        "unsupported hypothesis",
    ]
    # Each level carries a non-empty gloss.
    assert all(gloss.strip() for _, gloss in levels)


def test_all_subpackages_import() -> None:
    for name in bioscientist_os.SUBPACKAGES:
        mod = importlib.import_module(f"bioscientist_os.{name}")
        assert mod.__doc__, f"subpackage {name} should document its role"


def test_subpackages_match_plan_layout() -> None:
    """The skeleton on disk matches the declared subpackage list."""
    pkg_dir = ROOT / "src" / "bioscientist_os"
    for name in bioscientist_os.SUBPACKAGES:
        assert (pkg_dir / name / "__init__.py").is_file(), f"missing subpackage {name}/"


def test_environment_module_runs_offline() -> None:
    """The shared env-check logic produces a coherent report without network access."""
    from bioscientist_os import environment

    rep = environment.run_checks()
    assert any(c.name == "required:python>=3.12" for c in rep.checks)
    assert any(c.name == "required:import bioscientist_os" for c in rep.checks)
    # report_payload is JSON-serializable and exposes the hard_ok verdict.
    payload = environment.report_payload(rep)
    assert "hard_ok" in payload
    assert isinstance(payload["checks"], list)
