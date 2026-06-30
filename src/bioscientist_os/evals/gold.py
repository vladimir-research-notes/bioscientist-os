"""Load the committed gold labels for the self-evaluation (Milestone 8).

A thin, dependency-light loader (stdlib ``json`` only) that parses the small files
under ``data/fixtures/gold/`` into typed, frozen containers and validates their
shape, raising a readable :class:`GoldError` (naming the file and record index) on
a malformed label. It is the evaluation counterpart of
:mod:`bioscientist_os.fixtures`: it reads labels, it does not score anything — that
is :mod:`bioscientist_os.evals.harness`.

The labels themselves (and the rationale for the two deliberate recall misses) are
documented in ``data/fixtures/gold/README.md``.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

# src/bioscientist_os/evals/gold.py -> repo root is parents[3].
_REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_GOLD_DIR = _REPO_ROOT / "data" / "fixtures" / "gold"

SEARCH_QUERIES_FILE = Path("search_queries.json")
ENTITY_LABELS_FILE = Path("entity_labels.json")


class GoldError(ValueError):
    """Raised when a gold-label file is missing or contains an invalid record."""


@dataclass(frozen=True)
class GoldQuery:
    """A labeled retrieval query and its human-judged relevant paper set."""

    query_id: str
    query: str
    relevant_paper_ids: tuple[str, ...]
    note: str = ""

    @property
    def num_relevant(self) -> int:
        return len(self.relevant_paper_ids)


@dataclass(frozen=True)
class GoldEntity:
    """One gold entity mention: its dictionary id, a surface, and whether it is modeled.

    ``modeled`` is documentation — whether the dictionary *could* recognize this
    concept; the eval tests cross-check it against the live dictionary, so a drift
    between the label and the dictionary is caught.
    """

    entity_id: str
    surface: str
    modeled: bool


@dataclass(frozen=True)
class GoldEntityLabel:
    """The gold set of distinct entities present in one abstract."""

    paper_id: str
    gold_entities: tuple[GoldEntity, ...]
    note: str = ""

    @property
    def entity_ids(self) -> set[str]:
        return {e.entity_id for e in self.gold_entities}


@dataclass(frozen=True)
class GoldLabels:
    """Everything the committed gold labels contain, parsed and validated."""

    queries: tuple[GoldQuery, ...]
    entity_labels: tuple[GoldEntityLabel, ...]

    def summary(self) -> dict[str, int]:
        return {
            "queries": len(self.queries),
            "relevant_pairs": sum(q.num_relevant for q in self.queries),
            "entity_labeled_abstracts": len(self.entity_labels),
            "gold_entity_mentions": sum(len(e.gold_entities) for e in self.entity_labels),
        }


def gold_dir(root: Path | str | None = None) -> Path:
    """Resolve the gold-labels directory (defaults to ``data/fixtures/gold/``)."""
    return Path(root) if root is not None else DEFAULT_GOLD_DIR


def _read_json_array(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        raise GoldError(f"gold-label file not found: {path}")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:  # pragma: no cover - exercised via tests
        raise GoldError(f"{path}: invalid JSON ({exc})") from exc
    if not isinstance(data, list):
        raise GoldError(f"{path}: expected a JSON array of records, got {type(data).__name__}")
    return data


def _require(path: Path, i: int, raw: dict, key: str, types: tuple[type, ...]) -> Any:
    if key not in raw:
        raise GoldError(f"{path}[{i}]: missing required field {key!r}")
    value = raw[key]
    if not isinstance(value, types):
        raise GoldError(
            f"{path}[{i}]: field {key!r} must be {' or '.join(t.__name__ for t in types)}, "
            f"got {type(value).__name__}"
        )
    return value


def load_search_queries(root: Path | str | None = None) -> list[GoldQuery]:
    """Load the labeled retrieval queries."""
    path = gold_dir(root) / SEARCH_QUERIES_FILE
    out: list[GoldQuery] = []
    for i, raw in enumerate(_read_json_array(path)):
        if not isinstance(raw, dict):
            raise GoldError(f"{path}[{i}]: expected an object, got {type(raw).__name__}")
        relevant = _require(path, i, raw, "relevant_paper_ids", (list,))
        if not relevant or not all(isinstance(p, str) and p for p in relevant):
            raise GoldError(f"{path}[{i}]: relevant_paper_ids must be a non-empty list of ids")
        out.append(
            GoldQuery(
                query_id=_require(path, i, raw, "query_id", (str,)),
                query=_require(path, i, raw, "query", (str,)),
                relevant_paper_ids=tuple(relevant),
                note=raw.get("note", ""),
            )
        )
    return out


def load_entity_labels(root: Path | str | None = None) -> list[GoldEntityLabel]:
    """Load the gold entity sets per abstract."""
    path = gold_dir(root) / ENTITY_LABELS_FILE
    out: list[GoldEntityLabel] = []
    for i, raw in enumerate(_read_json_array(path)):
        if not isinstance(raw, dict):
            raise GoldError(f"{path}[{i}]: expected an object, got {type(raw).__name__}")
        ents_raw = _require(path, i, raw, "gold_entities", (list,))
        entities: list[GoldEntity] = []
        for j, e in enumerate(ents_raw):
            if not isinstance(e, dict):
                raise GoldError(f"{path}[{i}].gold_entities[{j}]: expected an object")
            if "entity_id" not in e or not isinstance(e["entity_id"], str):
                raise GoldError(f"{path}[{i}].gold_entities[{j}]: missing string 'entity_id'")
            entities.append(
                GoldEntity(
                    entity_id=e["entity_id"],
                    surface=e.get("surface", ""),
                    modeled=bool(e.get("modeled", True)),
                )
            )
        if not entities:
            raise GoldError(f"{path}[{i}]: gold_entities must be non-empty")
        out.append(
            GoldEntityLabel(
                paper_id=_require(path, i, raw, "paper_id", (str,)),
                gold_entities=tuple(entities),
                note=raw.get("note", ""),
            )
        )
    return out


def load_gold(root: Path | str | None = None) -> GoldLabels:
    """Load and validate all committed gold labels."""
    return GoldLabels(
        queries=tuple(load_search_queries(root)),
        entity_labels=tuple(load_entity_labels(root)),
    )


__all__ = [
    "GoldError",
    "GoldQuery",
    "GoldEntity",
    "GoldEntityLabel",
    "GoldLabels",
    "gold_dir",
    "DEFAULT_GOLD_DIR",
    "load_search_queries",
    "load_entity_labels",
    "load_gold",
]
