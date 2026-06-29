"""Repository-contract tests.

These are dependency-free (stdlib + pytest only) so the suite is green from the
very first commit, before any package dependency is installed. They assert that
the project's *contract* — plan, docs, website, permission policy, runner — is
present and self-consistent. Milestones add functional tests alongside these.
"""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

SITE_PAGES = [
    "index.html",
    "architecture.html",
    "data-model.html",
    "ingestion.html",
    "evidence.html",
    "databases.html",
    "visualizations.html",
    "evaluation.html",
    "results.html",
    "milestones.html",
    "reproducibility.html",
    "limitations.html",
    "safety.html",
    "roadmap.html",
]

DOCS = [
    "PLAN.md",
    "METHODOLOGY.md",
    "ARCHITECTURE.md",
    "DATA_MODEL.md",
    "DATABASES.md",
    "EVALUATION.md",
    "RESULTS.md",
    "LIMITATIONS.md",
    "REPRODUCIBILITY.md",
    "SAFETY.md",
    "ROADMAP.md",
    "WEBSITE_NOTES.md",
]


def test_top_level_files_exist() -> None:
    for name in (
        "README.md",
        "CLAUDE.md",
        "pyproject.toml",
        "requirements.txt",
        "LICENSE",
        ".gitignore",
        "conftest.py",
    ):
        assert (ROOT / name).is_file(), f"missing {name}"


def test_docs_skeleton_exists() -> None:
    for name in DOCS:
        assert (ROOT / "docs" / name).is_file(), f"missing docs/{name}"
    for sub in ("prompts", "milestones", "review_notes", "commits"):
        assert (ROOT / "docs" / sub).is_dir(), f"missing docs/{sub}/"


def test_package_and_data_dirs_exist() -> None:
    assert (ROOT / "src" / "bioscientist_os").is_dir()
    for sub in ("papers", "uniprot", "opentargets"):
        assert (ROOT / "data" / "fixtures" / sub).is_dir(), f"missing data/fixtures/{sub}"
    for sub in ("raw", "processed", "figures"):
        assert (ROOT / "results" / sub).is_dir(), f"missing results/{sub}"


def test_scripts_present_and_runner_executable() -> None:
    runner = ROOT / "scripts" / "run_all_milestones_with_claude.sh"
    env_check = ROOT / "scripts" / "00_check_environment.py"
    assert runner.is_file(), "missing milestone runner"
    assert env_check.is_file(), "missing environment-check script"
    # Runner must be executable so `./scripts/run_all_milestones_with_claude.sh` works.
    assert runner.stat().st_mode & 0o111, "runner is not executable (chmod +x)"


def test_all_site_pages_and_css_exist() -> None:
    for page in SITE_PAGES:
        p = ROOT / "site" / page
        assert p.is_file(), f"missing site/{page}"
        text = p.read_text(encoding="utf-8")
        assert "style.css" in text, f"site/{page} does not link the stylesheet"
        # Every page shares the nav, so it should link the safety page.
        assert "safety.html" in text, f"site/{page} missing nav link to safety"
    assert (ROOT / "site" / "style.css").is_file(), "missing site/style.css"


def test_permission_policy_is_safe() -> None:
    settings = json.loads((ROOT / ".claude" / "settings.json").read_text(encoding="utf-8"))
    perms = settings["permissions"]
    assert perms.get("defaultMode") == "acceptEdits"
    deny = perms.get("deny", [])
    # The autonomous runner must never push or read common secret locations.
    assert any("git push" in d for d in deny), "policy must deny git push"
    assert any(".env" in d for d in deny), "policy must deny reading .env"
    assert any("settings.local.json" in d for d in deny), "policy must deny local settings read"


def test_safety_statement_is_non_clinical() -> None:
    safety_md = (ROOT / "docs" / "SAFETY.md").read_text(encoding="utf-8").lower()
    safety_html = (ROOT / "site" / "safety.html").read_text(encoding="utf-8").lower()
    for blob, label in ((safety_md, "SAFETY.md"), (safety_html, "safety.html")):
        assert "not" in blob and "medical" in blob, f"{label} missing non-medical disclaimer"
        assert "diagnos" in blob, f"{label} should disclaim diagnosis"


def test_gitignore_protects_artifacts_and_secrets() -> None:
    gi = (ROOT / ".gitignore").read_text(encoding="utf-8")
    for needle in (".env", ".venv/", "data/cache/", "results/", "*.safetensors", "settings.local.json"):
        assert needle in gi, f".gitignore should mention {needle}"
