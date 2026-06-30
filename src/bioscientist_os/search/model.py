"""Result objects for search and topic grouping (Milestone 3).

These are plain frozen dataclasses (like :class:`bioscientist_os.ingest.IngestReport`),
not pydantic schemas: search and topic grouping produce *rankings and groupings of
papers*, not derived claims, so they do not enter the four-level epistemic
vocabulary. They are honest, inspectable provenance objects all the same — every
hit names the paper, the query terms that matched, the fields they matched in, the
per-term score breakdown, the scoring ``method``, and the row's ``data_source``.

The :meth:`to_dict` methods give the exact shape emitted by ``biosci search --json``
and ``biosci topics --json`` and written by ``scripts/02_build_index.py``. Floats
are rounded there (not on the dataclasses) so JSON is stable to display precision
while in-memory math stays exact.
"""

from __future__ import annotations

from dataclasses import dataclass, field

# Score rounding applied only in JSON/text output, never to the stored floats.
_NDIGITS = 4


@dataclass(frozen=True)
class TermMatch:
    """How one query term scored against one paper under BM25F — fully inspectable.

    ``field_tf`` is the raw term frequency per field (only fields where it occurs),
    ``weighted_tf`` is the BM25F field-weighted, length-normalized frequency, and
    ``contribution`` is exactly this term's additive share of the paper's score.
    For a query term absent from the paper, ``matched`` is ``False`` and
    ``contribution`` is ``0.0`` (the term is still listed, so "did not match" is
    visible rather than silent).
    """

    term: str
    matched: bool
    idf: float
    field_tf: dict[str, int]
    weighted_tf: float
    contribution: float

    def to_dict(self) -> dict:
        return {
            "term": self.term,
            "matched": self.matched,
            "idf": round(self.idf, _NDIGITS),
            "field_tf": dict(sorted(self.field_tf.items())),
            "weighted_tf": round(self.weighted_tf, _NDIGITS),
            "contribution": round(self.contribution, _NDIGITS),
        }


@dataclass(frozen=True)
class SearchHit:
    """One ranked paper, with the full reason it ranked where it did.

    ``score`` is the sum of the ``contribution`` of every entry in
    ``term_matches`` (the explanation reconstructs the score exactly).
    ``matched_fields`` is the sorted union of fields any query term matched in.
    """

    rank: int
    paper_id: str
    title: str
    year: int | None
    score: float
    term_matches: list[TermMatch]

    @property
    def matched_terms(self) -> list[str]:
        """Query terms that occurred in this paper, in query order."""
        return [m.term for m in self.term_matches if m.matched]

    @property
    def matched_fields(self) -> list[str]:
        """Sorted union of fields any matched query term occurred in."""
        fields: set[str] = set()
        for m in self.term_matches:
            fields.update(m.field_tf)
        return sorted(fields)

    def why(self) -> str:
        """A compact one-line explanation, e.g. ``senescence[title,abstract] il-6[abstract]``."""
        parts = []
        for m in self.term_matches:
            if m.matched:
                fields = ",".join(sorted(m.field_tf))
                parts.append(f"{m.term}[{fields}]")
        return " ".join(parts) if parts else "(no query term matched)"

    def to_dict(self) -> dict:
        return {
            "rank": self.rank,
            "paper_id": self.paper_id,
            "title": self.title,
            "year": self.year,
            "score": round(self.score, _NDIGITS),
            "matched_terms": self.matched_terms,
            "matched_fields": self.matched_fields,
            "term_matches": [m.to_dict() for m in self.term_matches],
        }


@dataclass(frozen=True)
class SearchResponse:
    """The full result of one query: the ranking plus the parameters that produced it."""

    query: str
    query_terms: list[str]
    method: str
    params: dict[str, float]
    total_papers: int
    data_source: str
    hits: list[SearchHit] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "query": self.query,
            "query_terms": self.query_terms,
            "method": self.method,
            "params": self.params,
            "total_papers": self.total_papers,
            "data_source": self.data_source,
            "num_hits": len(self.hits),
            "hits": [h.to_dict() for h in self.hits],
        }


@dataclass(frozen=True)
class TopicGroup:
    """A cluster of papers and the distinctive terms that label it.

    ``label_terms`` are the highest-TF-IDF-mass terms across the group's members
    (a description, not a name the corpus asserts). ``paper_ids`` are sorted.
    """

    topic_id: str
    label_terms: list[str]
    paper_ids: list[str]

    @property
    def size(self) -> int:
        return len(self.paper_ids)

    def to_dict(self) -> dict:
        return {
            "topic_id": self.topic_id,
            "label_terms": self.label_terms,
            "size": self.size,
            "paper_ids": self.paper_ids,
        }


@dataclass(frozen=True)
class TopicReport:
    """The grouping of the whole corpus into topics for one threshold."""

    method: str
    threshold: float
    params: dict[str, float]
    total_papers: int
    data_source: str
    groups: list[TopicGroup] = field(default_factory=list)

    @property
    def num_groups(self) -> int:
        return len(self.groups)

    @property
    def num_singletons(self) -> int:
        """Groups of exactly one paper (papers similar to no other above threshold)."""
        return sum(1 for g in self.groups if g.size == 1)

    def to_dict(self) -> dict:
        return {
            "method": self.method,
            "threshold": self.threshold,
            "params": self.params,
            "total_papers": self.total_papers,
            "data_source": self.data_source,
            "num_groups": self.num_groups,
            "num_singletons": self.num_singletons,
            "groups": [g.to_dict() for g in self.groups],
        }


__all__ = [
    "TermMatch",
    "SearchHit",
    "SearchResponse",
    "TopicGroup",
    "TopicReport",
]
