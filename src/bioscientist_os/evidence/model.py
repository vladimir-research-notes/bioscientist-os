"""Result objects for entity / claim extraction (Milestone 4).

The recognized *entities* and *claims* are the typed
:class:`bioscientist_os.schemas.BiomedicalEntity` and
:class:`bioscientist_os.schemas.Claim` pydantic models — they carry provenance and
enter the four-level epistemic vocabulary, so they belong in the schema layer. The
objects here are the plain, frozen *containers* that group those per paper and over
the corpus (parallel to :mod:`bioscientist_os.search.model`): a raw recognizer
:class:`EntityMention`, a per-paper :class:`PaperExtraction`, and a corpus-level
:class:`ExtractionReport` with ``to_dict`` / CSV helpers used by
``biosci extract --json`` and ``scripts/03_extract_claims.py``.

Floats are rounded only in the ``to_dict`` / CSV output (to display precision),
never on the stored objects, so in-memory values stay exact and JSON/CSV are stable.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import ClassVar

from bioscientist_os.schemas import BiomedicalEntity, Claim

# Confidence rounding applied only in JSON/CSV output.
_NDIGITS = 4


@dataclass(frozen=True)
class EntityMention:
    """One dictionary match: a canonical entity recognized at an exact span.

    The raw output of :meth:`bioscientist_os.evidence.dictionary.EntityDictionary.find`,
    before mentions are grouped into per-paper :class:`BiomedicalEntity` objects.
    ``surface`` is the verbatim matched text (``abstract[start:end]``); ``entity_type``
    is the :class:`bioscientist_os.schemas.EntityType` value as a string.
    """

    entity_id: str
    canonical_name: str
    entity_type: str
    surface: str
    start: int
    end: int

    def to_dict(self) -> dict:
        return {
            "entity_id": self.entity_id,
            "canonical_name": self.canonical_name,
            "entity_type": self.entity_type,
            "surface": self.surface,
            "char_span": [self.start, self.end],
        }


@dataclass(frozen=True)
class PaperExtraction:
    """All entities and claims extracted from one paper's abstract."""

    paper_id: str
    title: str
    entities: list[BiomedicalEntity] = field(default_factory=list)
    claims: list[Claim] = field(default_factory=list)

    @property
    def num_relations(self) -> int:
        """Claims for which a subject–relation–object triple was filled."""
        return sum(1 for c in self.claims if c.relation is not None)

    def to_dict(self) -> dict:
        return {
            "paper_id": self.paper_id,
            "title": self.title,
            "num_entities": len(self.entities),
            "num_claims": len(self.claims),
            "num_relations": self.num_relations,
            "entities": [_entity_dict(e) for e in self.entities],
            "claims": [_claim_dict(c) for c in self.claims],
        }


@dataclass(frozen=True)
class ExtractionReport:
    """The entities and claims extracted across the whole corpus, with parameters."""

    method: str
    params: dict[str, object]
    data_source: str
    total_papers: int
    papers: list[PaperExtraction] = field(default_factory=list)

    @property
    def all_entities(self) -> list[BiomedicalEntity]:
        return [e for p in self.papers for e in p.entities]

    @property
    def all_claims(self) -> list[Claim]:
        return [c for p in self.papers for c in p.claims]

    @property
    def num_entities(self) -> int:
        return sum(len(p.entities) for p in self.papers)

    @property
    def num_claims(self) -> int:
        return sum(len(p.claims) for p in self.papers)

    @property
    def num_relations(self) -> int:
        return sum(p.num_relations for p in self.papers)

    def entity_name_by_id(self) -> dict[str, str]:
        """Map canonical ``entity_id`` -> canonical name (stable across papers)."""
        names: dict[str, str] = {}
        for e in self.all_entities:
            names.setdefault(e.entity_id, e.name)
        return names

    def to_dict(self) -> dict:
        return {
            "method": self.method,
            "params": self.params,
            "data_source": self.data_source,
            "total_papers": self.total_papers,
            "num_entities": self.num_entities,
            "num_claims": self.num_claims,
            "num_relations": self.num_relations,
            "papers": [p.to_dict() for p in self.papers],
        }

    # -- flat CSV views (the headline artifacts written by the M4 script) -----

    ENTITY_COLUMNS: ClassVar[tuple[str, ...]] = (
        "entity_id", "name", "entity_type", "paper_id", "synonyms", "db_xrefs",
        "confidence", "extraction_method", "source_snippet", "char_start", "char_end",
        "data_source", "epistemic_level",
    )
    CLAIM_COLUMNS: ClassVar[tuple[str, ...]] = (
        "claim_id", "paper_id", "claim_text", "subject", "relation", "object",
        "entity_ids", "entity_names", "confidence", "extraction_method",
        "source_snippet", "char_start", "char_end", "data_source", "epistemic_level",
    )

    def entity_rows(self) -> list[dict[str, object]]:
        """One row per recognized entity (flattened across papers), CSV-friendly."""
        rows: list[dict[str, object]] = []
        for e in self.all_entities:
            p = e.provenance
            span = p.char_span or (None, None)
            rows.append({
                "entity_id": e.entity_id,
                "name": e.name,
                "entity_type": e.entity_type.value,
                "paper_id": p.paper_id,
                "synonyms": "|".join(e.synonyms),
                "db_xrefs": ";".join(f"{k}={v}" for k, v in sorted(e.db_xrefs.items())),
                "confidence": round(e.confidence, _NDIGITS),
                "extraction_method": p.extraction_method,
                "source_snippet": p.source_snippet,
                "char_start": span[0],
                "char_end": span[1],
                "data_source": p.data_source.value,
                "epistemic_level": p.epistemic_level.value,
            })
        return rows

    def claim_rows(self) -> list[dict[str, object]]:
        """One row per extracted claim (flattened across papers), CSV-friendly."""
        names = self.entity_name_by_id()
        rows: list[dict[str, object]] = []
        for c in self.all_claims:
            p = c.provenance
            span = p.char_span or (None, None)
            rows.append({
                "claim_id": c.claim_id,
                "paper_id": c.paper_id,
                "claim_text": c.claim_text,
                "subject": c.subject,
                "relation": c.relation,
                "object": c.object,
                "entity_ids": "|".join(c.entity_ids),
                "entity_names": "|".join(names.get(i, i) for i in c.entity_ids),
                "confidence": round(c.confidence, _NDIGITS),
                "extraction_method": p.extraction_method,
                "source_snippet": p.source_snippet,
                "char_start": span[0],
                "char_end": span[1],
                "data_source": p.data_source.value,
                "epistemic_level": p.epistemic_level.value,
            })
        return rows


def _entity_dict(e: BiomedicalEntity) -> dict:
    d = e.model_dump(mode="json")
    d["confidence"] = round(e.confidence, _NDIGITS)
    return d


def _claim_dict(c: Claim) -> dict:
    d = c.model_dump(mode="json")
    d["confidence"] = round(c.confidence, _NDIGITS)
    return d


__all__ = ["EntityMention", "PaperExtraction", "ExtractionReport"]
