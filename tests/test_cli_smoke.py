"""Smoke tests for the ``biosci`` CLI (Milestone 0).

Uses Typer's in-process ``CliRunner`` so no subprocess or install is required.
These confirm the three Milestone-0 subcommands are wired and that ``info``
surfaces the safety stance and the four epistemic levels.
"""

from __future__ import annotations

import json

from typer.testing import CliRunner

import bioscientist_os
from bioscientist_os.cli import app

runner = CliRunner()


def test_help_lists_subcommands() -> None:
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    for sub in ("info", "version", "env-check"):
        assert sub in result.output


def test_version_prints_package_version() -> None:
    result = runner.invoke(app, ["version"])
    assert result.exit_code == 0
    assert bioscientist_os.__version__ in result.output


def test_info_shows_safety_and_epistemic_levels() -> None:
    result = runner.invoke(app, ["info"])
    assert result.exit_code == 0
    out = result.output
    assert bioscientist_os.PACKAGE_NAME in out
    # Non-clinical disclaimer must be visible.
    assert "NOT a medical" in out
    # All four epistemic levels are named.
    for level, _ in bioscientist_os.EPISTEMIC_LEVELS:
        assert level in out


def test_env_check_text_runs() -> None:
    result = runner.invoke(app, ["env-check"])
    # The supported test environment has the core deps, so the hard check passes.
    assert result.exit_code == 0
    assert "environment report" in result.output
    assert "RESULT:" in result.output


def test_env_check_json_is_parseable() -> None:
    result = runner.invoke(app, ["env-check", "--json"])
    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["hard_ok"] is True
    assert any(c["name"] == "required:import bioscientist_os" for c in payload["checks"])
