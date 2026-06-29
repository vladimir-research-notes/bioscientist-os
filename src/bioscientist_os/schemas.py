"""Typed data schemas for bioscientist-os, with provenance as a first-class field.

These ``pydantic`` v2 models encode the evidence chain and force every *derived*
object to point back at its source::

    paper -> extracted claim -> biological entities -> database links
          -> support / conflict / uncertainty -> evidence table

Two disciplines are baked into the type system rather than left to convention:

* **data source.** Anything that crosses the boundary from "outside the program"
  carries :class:`DataSource` ∈ {``fixture``, ``cache``, ``live``} and a
  ``synthetic`` flag, so a reader can always tell whether a record is committed,
  cached, freshly fetched, and whether it was fabricated for illustration.
* **epistemic level.** Every *derived* object (an entity mention, a claim, an
  evidence cell) carries a :class:`Provenance` block whose
  :class:`EpistemicLevel` says what *kind* of statement it is — directly observed
  metadata, an extracted claim, an inferred relation, or an unsupported
  hypothesis. The project never silently collapses these four levels
  (see ``docs/SAFETY.md`` and the package-level ``EPISTEMIC_LEVELS`` constant).

The schema set is intentionally minimal — it is not a biomedical ontology.
Entity typing is coarse and dictionary-driven (Milestone 4); ``db_xrefs`` are
only as complete as the fixtures/connectors provide. See ``docs/DATA_MODEL.md``.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from bioscientist_os import EPISTEMIC_LEVELS

# ---------------------------------------------------------------------------
# Controlled vocabularies
# ---------------------------------------------------------------------------


class DataSource(StrEnum):
    """Where a record physically came from, for provenance display.

    ``fixture`` — a small, committed file in ``data/fixtures/`` (the default and
    only source on the offline path); ``cache`` — written under ``data/cache/``
    by a connector (Milestone 6, gitignored); ``live`` — fetched from a remote
    service in an explicitly opted-in run.
    """

    fixture = "fixture"
    cache = "cache"
    live = "live"


class EpistemicLevel(StrEnum):
    """The four levels the project never collapses (see ``docs/PLAN.md``).

    The string values are stable, machine-friendly slugs; :pyattr:`display`
    gives the human label used by ``biosci info`` and the package constant
    :data:`bioscientist_os.EPISTEMIC_LEVELS`.
    """

    observed_metadata = "observed_metadata"
    extracted_claim = "extracted_claim"
    inferred_relation = "inferred_relation"
    unsupported_hypothesis = "unsupported_hypothesis"

    @property
    def display(self) -> str:
        return self.value.replace("_", " ")


# Sanity check at import time: the enum and the package-level tuple must agree on
# both membership and order. If they ever drift, fail loudly here rather than let
# the CLI and the schemas describe different "four levels".
_PACKAGE_LEVELS = tuple(name for name, _ in EPISTEMIC_LEVELS)
assert tuple(level.display for level in EpistemicLevel) == _PACKAGE_LEVELS, (
    "EpistemicLevel enum has drifted from bioscientist_os.EPISTEMIC_LEVELS"
)


class EntityType(StrEnum):
    """Coarse, dictionary-driven entity typing (Milestone 4).

    Deliberately blunt: this is not an ontology. ``other`` is the honest bucket
    for mentions the dictionaries cannot confidently type.
    """

    gene = "gene"
    protein = "protein"
    disease = "disease"
    process = "process"
    pathway = "pathway"
    cell_type = "cell_type"
    chemical = "chemical"
    other = "other"


class SupportLabel(StrEnum):
    """A heuristic *textual* signal for an evidence row — not a biological verdict.

    ``support`` / ``conflict`` describe how a paper's text reads relative to a
    research question; ``unknown`` is the default and the honest answer when the
    text does not clearly do either. This is never a claim about biological truth
    (see ``docs/SAFETY.md``).
    """

    support = "support"
    conflict = "conflict"
    unknown = "unknown"


# ---------------------------------------------------------------------------
# Provenance — attached to every derived object
# ---------------------------------------------------------------------------


class Provenance(BaseModel):
    """Where a derived statement came from, and what kind of statement it is.

    Carried by :class:`BiomedicalEntity`, :class:`Claim`, and
    :class:`EvidenceItem`. A derived object without provenance is, by project
    policy, incomplete and should fail review.
    """

    model_config = ConfigDict(extra="forbid")

    paper_id: str | None = Field(
        None, description="local Paper.paper_id this statement was derived from, if any"
    )
    source_snippet: str | None = Field(
        None, description="the exact text span the statement was read from, verbatim"
    )
    char_span: tuple[int, int] | None = Field(
        None,
        description="[start, end) character offsets of source_snippet within the source text",
    )
    extraction_method: str = Field(
        ...,
        min_length=1,
        description="named method that produced this object, e.g. 'fixture:load', "
        "'dict:entity', 'rule:svo'",
    )
    data_source: DataSource = DataSource.fixture
    epistemic_level: EpistemicLevel

    @model_validator(mode="after")
    def _check_span(self) -> Provenance:
        if self.char_span is not None:
            start, end = self.char_span
            if start < 0 or end < 0:
                raise ValueError("char_span offsets must be non-negative")
            if start > end:
                raise ValueError("char_span start must be <= end")
        return self


# ---------------------------------------------------------------------------
# Observed-metadata objects (they *are* the source: data_source + synthetic)
# ---------------------------------------------------------------------------


class Author(BaseModel):
    """An author of a paper. Public metadata only (no private personal data)."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(..., min_length=1)
    orcid: str | None = None
    affiliation: str | None = None


class Paper(BaseModel):
    """Normalized paper metadata plus abstract — level: observed metadata.

    Identifiers in ``external_ids`` (e.g. ``PMID``, ``DOI``) are kept as a plain
    mapping so heterogeneous fixtures and connectors agree on shape without a
    rigid per-source model.
    """

    model_config = ConfigDict(extra="forbid")

    paper_id: str = Field(..., min_length=1, description="stable local id, e.g. 'biosci-paper-001'")
    title: str = Field(..., min_length=1)
    authors: list[Author] = Field(default_factory=list)
    journal: str | None = None
    year: int | None = Field(None, ge=1500, le=2100)
    abstract: str = Field("", description="abstract text; paraphrased/synthetic where flagged")
    keywords: list[str] = Field(default_factory=list)
    url: str | None = None
    external_ids: dict[str, str] = Field(
        default_factory=dict, description="e.g. {'PMID': '...', 'DOI': '...'}"
    )
    data_source: DataSource = DataSource.fixture
    synthetic: bool = Field(
        ..., description="True if fabricated for illustration; never present synthetic data as real"
    )


class DatabaseRecord(BaseModel):
    """A record from a database connector (UniProt-style, Open Targets-style, ...).

    Level: observed metadata. The envelope (``record_id``, ``source``,
    ``record_type``, ``data_source``, ``synthetic``) is typed; the payload lives
    in ``fields`` as a free-form mapping so one model covers heterogeneous
    sources. Typed connectors (Milestone 6) build on this.
    """

    model_config = ConfigDict(extra="forbid")

    record_id: str = Field(..., min_length=1, description="id within the source, e.g. 'P05231'")
    source: str = Field(..., min_length=1, description="originating database, e.g. 'UniProt'")
    record_type: str = Field(
        ..., min_length=1, description="kind of record, e.g. 'protein', 'association'"
    )
    fields: dict[str, Any] = Field(default_factory=dict, description="source-specific payload")
    data_source: DataSource = DataSource.fixture
    synthetic: bool = Field(..., description="True if fabricated for illustration")


# ---------------------------------------------------------------------------
# Derived objects (carry Provenance)
# ---------------------------------------------------------------------------


class BiomedicalEntity(BaseModel):
    """A gene/protein/disease/process mention linked to database cross-references.

    Produced by dictionary matching (Milestone 4); ``provenance`` records the
    paper, snippet, and method. Level: observed metadata (a recognized mention)
    or inferred relation when ``db_xrefs`` come from combining records.
    """

    model_config = ConfigDict(extra="forbid")

    entity_id: str = Field(..., min_length=1, description="stable local id, e.g. 'ent-IL6'")
    name: str = Field(..., min_length=1, description="canonical or surface name")
    entity_type: EntityType
    synonyms: list[str] = Field(default_factory=list)
    db_xrefs: dict[str, str] = Field(
        default_factory=dict, description="e.g. {'UniProt': 'P05231', 'HGNC': 'IL6'}"
    )
    confidence: float = Field(1.0, ge=0.0, le=1.0)
    provenance: Provenance


class Claim(BaseModel):
    """A claim extracted from a paper's text — level: extracted claim.

    The optional ``subject``/``relation``/``object`` triple is filled by simple
    relation templates (Milestone 4) where they apply; ``claim_text`` and the
    snippet in ``provenance`` are always present so the extraction is auditable.
    """

    model_config = ConfigDict(extra="forbid")

    claim_id: str = Field(..., min_length=1)
    claim_text: str = Field(..., min_length=1, description="the extracted claim sentence/clause")
    paper_id: str = Field(..., min_length=1)
    subject: str | None = None
    relation: str | None = None
    object: str | None = None
    entity_ids: list[str] = Field(default_factory=list)
    confidence: float = Field(..., ge=0.0, le=1.0)
    provenance: Provenance

    @model_validator(mode="after")
    def _claim_points_at_its_paper(self) -> Claim:
        # A claim's provenance must reference the same paper it is attributed to.
        if self.provenance.paper_id not in (None, self.paper_id):
            raise ValueError(
                f"claim {self.claim_id}: provenance.paper_id "
                f"({self.provenance.paper_id!r}) != paper_id ({self.paper_id!r})"
            )
        return self


class EvidenceItem(BaseModel):
    """One row of an evidence table: claim ↔ paper ↔ entities ↔ database links.

    ``support_conflict_unknown`` is a heuristic textual signal (see
    :class:`SupportLabel`), not a biological verdict. ``database_links`` are
    record ids or cross-reference strings; ``provenance`` ties the row back to
    its claim and snippet.
    """

    model_config = ConfigDict(extra="forbid")

    claim_id: str = Field(..., min_length=1)
    claim_text: str = Field(..., min_length=1)
    entity_names: list[str] = Field(default_factory=list)
    paper_id: str = Field(..., min_length=1)
    support_conflict_unknown: SupportLabel = SupportLabel.unknown
    database_links: list[str] = Field(default_factory=list)
    confidence: float = Field(..., ge=0.0, le=1.0)
    notes: str | None = None
    provenance: Provenance


class ResearchQuestion(BaseModel):
    """The question driving an evidence table or memo."""

    model_config = ConfigDict(extra="forbid")

    question_id: str = Field(..., min_length=1)
    text: str = Field(..., min_length=1)
    entities_of_interest: list[str] = Field(default_factory=list)


class EvidenceTable(BaseModel):
    """A set of :class:`EvidenceItem` rows assembled for one research question."""

    model_config = ConfigDict(extra="forbid")

    table_id: str = Field(..., min_length=1)
    research_question_id: str = Field(..., min_length=1)
    research_question_text: str = Field(..., min_length=1)
    rows: list[EvidenceItem] = Field(default_factory=list)
    generated_by: str = Field(
        ..., min_length=1, description="run id or method that produced the table"
    )
    data_source: DataSource = DataSource.fixture

    @property
    def provenance_coverage(self) -> float:
        """Fraction of rows whose provenance names a paper and a source snippet.

        A simple, honest completeness signal surfaced by the evaluation harness
        (Milestone 8). Returns 1.0 for an empty table (vacuously complete).
        """
        if not self.rows:
            return 1.0
        complete = sum(
            1
            for r in self.rows
            if r.provenance.paper_id and r.provenance.source_snippet
        )
        return complete / len(self.rows)


class WorkbenchRun(BaseModel):
    """A reproducible record of one workbench run (inputs, versions, timing).

    Timestamps are stored as ISO-8601 *strings* supplied by the caller rather
    than captured implicitly, so a run record can be reconstructed
    deterministically in tests and reproductions.
    """

    model_config = ConfigDict(extra="forbid")

    run_id: str = Field(..., min_length=1)
    inputs: dict[str, Any] = Field(default_factory=dict)
    versions: dict[str, str] = Field(
        default_factory=dict, description="tool/package versions, e.g. {'bioscientist_os': '0.0.0'}"
    )
    started_at: str | None = Field(None, description="ISO-8601 timestamp, caller-supplied")
    finished_at: str | None = None
    notes: str | None = None

    @field_validator("versions", mode="before")
    @classmethod
    def _stringify_versions(cls, v: Any) -> Any:
        # Versions are commonly read as non-strings (ints, tuples); normalize so a
        # run record round-trips cleanly to JSON.
        if isinstance(v, dict):
            return {str(k): str(val) for k, val in v.items()}
        return v


__all__ = [
    "DataSource",
    "EpistemicLevel",
    "EntityType",
    "SupportLabel",
    "Provenance",
    "Author",
    "Paper",
    "DatabaseRecord",
    "BiomedicalEntity",
    "Claim",
    "EvidenceItem",
    "ResearchQuestion",
    "EvidenceTable",
    "WorkbenchRun",
]
