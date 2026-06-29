"""Load the committed fixtures into typed schemas.

This module does exactly one thing: parse the small JSON files under
``data/fixtures/`` into the :mod:`bioscientist_os.schemas` models, validating
each record and stamping ``data_source = fixture`` so downstream provenance is
explicit. It is deliberately thin and dependency-light (stdlib ``json`` plus the
schemas):

* it does **not** open a database, normalize, deduplicate, or index — that is the
  job of the ingestion + storage layer in Milestone 2, which builds on top of
  this loader;
* it raises a readable :class:`FixtureError` (naming the file and record index)
  when a fixture is malformed, so a broken corpus fails loudly rather than
  silently producing partial data.

The fixtures themselves are tiny, theme-focused (cellular senescence / longevity
/ autophagy), and labeled ``synthetic`` per record — see
``data/fixtures/README.md``.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from bioscientist_os.schemas import (
    DatabaseRecord,
    DataSource,
    Paper,
    ResearchQuestion,
)

# Fixture file locations, resolved relative to the repository root so the loader
# works from a source checkout without an install. The default root is computed
# from this file's path: src/bioscientist_os/fixtures.py -> repo root is parents[2].
_REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_FIXTURES_DIR = _REPO_ROOT / "data" / "fixtures"

PAPERS_FILE = Path("papers") / "papers.json"
UNIPROT_FILE = Path("uniprot") / "proteins.json"
OPENTARGETS_FILE = Path("opentargets") / "associations.json"
QUESTIONS_FILE = Path("questions.json")


class FixtureError(ValueError):
    """Raised when a fixture file is missing or contains an invalid record."""


@dataclass(frozen=True)
class FixtureBundle:
    """Everything the committed fixtures contain, parsed and validated."""

    papers: list[Paper]
    proteins: list[DatabaseRecord]
    associations: list[DatabaseRecord]
    questions: list[ResearchQuestion]

    def summary(self) -> dict[str, int]:
        """Record counts, for ``biosci`` status output and tests."""
        return {
            "papers": len(self.papers),
            "proteins": len(self.proteins),
            "associations": len(self.associations),
            "questions": len(self.questions),
        }


def fixtures_dir(root: Path | str | None = None) -> Path:
    """Resolve the fixtures directory (defaults to ``data/fixtures/`` in the repo)."""
    return Path(root) if root is not None else DEFAULT_FIXTURES_DIR


def _read_json_array(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        raise FixtureError(f"fixture file not found: {path}")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:  # pragma: no cover - exercised via tests
        raise FixtureError(f"{path}: invalid JSON ({exc})") from exc
    if not isinstance(data, list):
        raise FixtureError(f"{path}: expected a JSON array of records, got {type(data).__name__}")
    return data


def _parse_records(path: Path, model: type, *, stamp: dict[str, Any]) -> list[Any]:
    """Validate every record in ``path`` against ``model``, injecting ``stamp``.

    ``stamp`` carries fields the loader sets rather than the fixture (e.g.
    ``data_source``). A fixture that also specifies a stamped field is a conflict
    and is reported, so the loader stays the single authority on provenance source.
    """
    out: list[Any] = []
    for i, raw in enumerate(_read_json_array(path)):
        if not isinstance(raw, dict):
            raise FixtureError(f"{path}[{i}]: expected an object, got {type(raw).__name__}")
        clash = stamp.keys() & raw.keys()
        if clash:
            raise FixtureError(
                f"{path}[{i}]: fixture must not set loader-stamped field(s) {sorted(clash)}"
            )
        try:
            out.append(model(**raw, **stamp))
        except ValidationError as exc:
            raise FixtureError(f"{path}[{i}]: {exc}") from exc
    return out


def load_papers(root: Path | str | None = None) -> list[Paper]:
    """Load paper records, stamping ``data_source = fixture``."""
    return _parse_records(
        fixtures_dir(root) / PAPERS_FILE, Paper, stamp={"data_source": DataSource.fixture}
    )


def load_protein_records(root: Path | str | None = None) -> list[DatabaseRecord]:
    """Load UniProt-style protein records as :class:`DatabaseRecord`."""
    return _parse_records(
        fixtures_dir(root) / UNIPROT_FILE, DatabaseRecord, stamp={"data_source": DataSource.fixture}
    )


def load_association_records(root: Path | str | None = None) -> list[DatabaseRecord]:
    """Load Open Targets-style association records as :class:`DatabaseRecord`."""
    return _parse_records(
        fixtures_dir(root) / OPENTARGETS_FILE,
        DatabaseRecord,
        stamp={"data_source": DataSource.fixture},
    )


def load_research_questions(root: Path | str | None = None) -> list[ResearchQuestion]:
    """Load the seed research questions used by evidence tables and memos."""
    return _parse_records(fixtures_dir(root) / QUESTIONS_FILE, ResearchQuestion, stamp={})


def load_all(root: Path | str | None = None) -> FixtureBundle:
    """Load and validate the entire committed fixture corpus."""
    return FixtureBundle(
        papers=load_papers(root),
        proteins=load_protein_records(root),
        associations=load_association_records(root),
        questions=load_research_questions(root),
    )


__all__ = [
    "FixtureError",
    "FixtureBundle",
    "fixtures_dir",
    "DEFAULT_FIXTURES_DIR",
    "load_papers",
    "load_protein_records",
    "load_association_records",
    "load_research_questions",
    "load_all",
]
