"""Evidence-table assembly grouped by a research question (Milestone 5).

This is the milestone that turns the M4 extraction into the project's headline
artifact: an **evidence table** in which every row (cell) carries explicit
provenance and never collapses the four epistemic levels.

Pipeline, end to end::

    research question ─▶ question entities (dict-recognized in the question text
                          and its entities_of_interest)
    extracted claims  ─▶ keep claims grounded in ≥1 question entity
    each kept claim   ─▶ one EvidenceItem row:
        • claim_text + source_snippet + span   (extracted claim — verbatim)
        • entity_names                         (observed metadata — recognized)
        • database_links (xrefs + associations) (inferred relation — combined)
        • support / conflict / unknown          (heuristic textual signal)

Three disciplines, all inherited from the rest of the package:

* **Provenance on every cell.** Each :class:`~bioscientist_os.schemas.EvidenceItem`
  carries a :class:`~bioscientist_os.schemas.Provenance` block pointing at the
  paper, the verbatim snippet, its exact ``char_span``, the claim's extraction
  method, and the data source. ``EvidenceTable.provenance_coverage`` is 1.0 by
  construction here (a row is only emitted from a claim that has both).
* **Levels are never collapsed.** A row's provenance is anchored to the
  *extracted claim* (its snippet). The other facets live in their own fields and
  are labeled for what they are: ``entity_names`` (observed), ``database_links``
  (inferred relation), and ``support_conflict_unknown`` (a heuristic textual
  signal — see :func:`classify_support` and :class:`SupportLabel`).
* **No biological or clinical verdict.** ``support`` / ``conflict`` describe how a
  sentence's *phrasing* reads (asserts vs. negates/contrasts a relationship), not
  whether a hypothesis is biologically true. This is a research-assistance tool,
  not medical advice (see ``docs/SAFETY.md``).

The support classifier reuses the M4 cue vocabulary
(:data:`~bioscientist_os.evidence.extract.ASSOCIATION_CUES` and the
:data:`~bioscientist_os.evidence.extract.DIRECTED_CUES` stems) so the workbench
has one transparent set of relation cues, plus a small, explicit list of negation
and contrast cues defined here. Everything is deterministic: claims are processed
in corpus order and rows are sorted by ``(-confidence, paper_id, claim_id)``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import ClassVar

from bioscientist_os.evidence.dictionary import EntityDictionary, build_dictionary
from bioscientist_os.evidence.extract import (
    ASSOCIATION_CUES,
    DIRECTED_CUES,
    extract_corpus,
)
from bioscientist_os.evidence.model import ExtractionReport
from bioscientist_os.schemas import (
    Claim,
    DatabaseRecord,
    EpistemicLevel,
    EvidenceItem,
    EvidenceTable,
    Provenance,
    ResearchQuestion,
    SupportLabel,
)

# The named method that produces the support/conflict/unknown label. Recorded in
# every row's notes and in the table's ``generated_by`` so the heuristic is
# auditable, never silent.
SUPPORT_METHOD = "rule:support-cues"

# The named method that assembles a row from a claim. Used for the table's
# ``generated_by``; each row's ``provenance.extraction_method`` keeps the *claim's*
# method (e.g. "rule:svo") so the snippet stays traceable to how it was extracted.
BUILDER_METHOD = "evidence-table-builder"

# Confidence rounding applied only in JSON/CSV output (mirrors search/extract).
_NDIGITS = 4

# Strong negation cues: the sentence explicitly negates a relationship. Matched as
# lower-cased substrings (a baseline; no syntax). These win over any relation triple
# or support cue — "X did not increase Y" is conflict even though "increase" occurs.
NEGATION_CUES: tuple[str, ...] = (
    "no association",
    "not associated",
    "no significant",
    "no detectable",
    "no effect",
    "no difference",
    "no change",
    "no evidence",
    "did not",
    "does not",
    "do not",
    "was not",
    "were not",
    "is not",
    "are not",
    "fail to",
    "fails to",
    "failed to",
    "not required",
    "independent of",
    "contrary to",
    "neither",
)

# Weak contrast cues: they hedge or contrast. They mark conflict only when the
# sentence does *not* also assert a relationship (no relation triple). So
# "SIRT1 reduced IL-6 without affecting proliferation" stays support (a triple is
# present), while a bare "however, levels were stable" reads as conflict.
CONTRAST_CUES: tuple[str, ...] = (
    "however",
    "in contrast",
    "whereas",
    "but not",
    "rather than",
    "without",
    "absence of",
)

# Affirmative relationship cues, used to label support when no triple was extracted.
# Reuses the M4 vocabulary: association cues plus the directed-verb stems (e.g.
# "promote", "reduc", "increase") so a single cue set drives both extraction and
# the support label.
_SUPPORT_CUES: tuple[str, ...] = ASSOCIATION_CUES + tuple(cue for cue, _ in DIRECTED_CUES)


def classify_support(text: str, *, has_relation: bool) -> tuple[SupportLabel, str]:
    """Label a claim's *phrasing* as support / conflict / unknown, with a reason.

    A transparent textual heuristic — **not** a biological verdict (see
    ``docs/SAFETY.md``). The rule, in precedence order:

    1. a strong :data:`NEGATION_CUES` cue  → ``conflict`` (wins over everything);
    2. an asserted relationship (a relation triple, or a :data:`_SUPPORT_CUES`
       cue) with no overriding contrast → ``support``;
    3. a weak :data:`CONTRAST_CUES` cue, when nothing stronger affirms a
       relationship → ``conflict``;
    4. otherwise → ``unknown`` (the honest default).

    Returns ``(label, reason)`` where ``reason`` names the cue(s) that fired, so
    the label can always be reconstructed from the sentence.
    """
    low = text.lower()
    neg = next((c for c in NEGATION_CUES if c in low), None)
    if neg is not None:
        return SupportLabel.conflict, f"negation cue '{neg}'"

    contrast = next((c for c in CONTRAST_CUES if c in low), None)
    support_cue = next((c for c in _SUPPORT_CUES if c in low), None)
    affirms = has_relation or support_cue is not None

    if affirms:
        if contrast is not None and not has_relation:
            # A bare cue hedged by a contrast word reads as conflict.
            return SupportLabel.conflict, f"contrast cue '{contrast}' (no relation triple)"
        basis = "relation triple" if has_relation else f"support cue '{support_cue}'"
        if has_relation and support_cue is not None:
            basis = f"relation triple + support cue '{support_cue}'"
        if contrast is not None:
            basis += f" (despite contrast '{contrast}')"
        return SupportLabel.support, basis

    if contrast is not None:
        return SupportLabel.conflict, f"contrast cue '{contrast}'"

    return SupportLabel.unknown, "no affirming or negating cue"


def resolve_question_entities(
    question: ResearchQuestion, dictionary: EntityDictionary
) -> tuple[list[str], list[str]]:
    """Recognize the question's entities of interest with the entity dictionary.

    Looks for dictionary entities in the question text *and* its
    ``entities_of_interest`` list (so both a curated fixture question and a
    free-text question work). Returns ``(entity_ids, unmatched_terms)``:
    ``entity_ids`` is the ordered, de-duplicated list of recognized entity ids;
    ``unmatched_terms`` are the ``entities_of_interest`` whose own surface the
    dictionary does not recognize (surfaced for honesty — they contribute nothing).
    """
    text = question.text + " " + " ".join(question.entities_of_interest)
    entity_ids: list[str] = []
    for m in dictionary.find(text):
        if m.entity_id not in entity_ids:
            entity_ids.append(m.entity_id)

    matched = set(entity_ids)
    unmatched = [
        term
        for term in question.entities_of_interest
        if not any(m.entity_id in matched for m in dictionary.find(term))
    ]
    return entity_ids, unmatched


@dataclass(frozen=True)
class EvidenceReport:
    """An :class:`EvidenceTable` plus the parameters and counts that produced it.

    A plain frozen container (like :class:`ExtractionReport`) wrapping the typed
    :class:`EvidenceTable`. It carries the resolved question, the dictionary-matched
    question entities, corpus totals (the honest denominators), and CSV/JSON views
    used by ``biosci evidence`` and ``scripts/04_build_evidence_table.py``.
    """

    question: ResearchQuestion
    table: EvidenceTable
    method: str
    params: dict[str, object]
    data_source: str
    total_papers: int
    total_claims: int
    question_entity_ids: list[str]
    question_entity_names: list[str]
    unmatched_terms: list[str] = field(default_factory=list)

    EVIDENCE_COLUMNS: ClassVar[tuple[str, ...]] = (
        "claim_id",
        "paper_id",
        "claim_text",
        "entity_names",
        "support_conflict_unknown",
        "confidence",
        "extraction_method",
        "source_snippet",
        "char_start",
        "char_end",
        "database_links",
        "notes",
        "data_source",
        "epistemic_level",
    )

    @property
    def rows(self) -> list[EvidenceItem]:
        return self.table.rows

    @property
    def num_rows(self) -> int:
        return len(self.table.rows)

    @property
    def provenance_coverage(self) -> float:
        return self.table.provenance_coverage

    def support_counts(self) -> dict[str, int]:
        """Count of rows per :class:`SupportLabel` value (all three keys present)."""
        counts = {label.value: 0 for label in SupportLabel}
        for r in self.table.rows:
            counts[r.support_conflict_unknown.value] += 1
        return counts

    def to_dict(self) -> dict:
        return {
            "question": {
                "question_id": self.question.question_id,
                "text": self.question.text,
                "entities_of_interest": list(self.question.entities_of_interest),
            },
            "method": self.method,
            "params": self.params,
            "data_source": self.data_source,
            "total_papers": self.total_papers,
            "total_claims": self.total_claims,
            "question_entity_ids": self.question_entity_ids,
            "question_entity_names": self.question_entity_names,
            "unmatched_terms": self.unmatched_terms,
            "table_id": self.table.table_id,
            "research_question_id": self.table.research_question_id,
            "generated_by": self.table.generated_by,
            "num_rows": self.num_rows,
            "support_counts": self.support_counts(),
            "provenance_coverage": round(self.provenance_coverage, _NDIGITS),
            "rows": [self._row_dict(r) for r in self.table.rows],
        }

    def evidence_rows(self) -> list[dict[str, object]]:
        """One flat, CSV-friendly dict per evidence row (columns = EVIDENCE_COLUMNS)."""
        rows: list[dict[str, object]] = []
        for r in self.table.rows:
            p = r.provenance
            span = p.char_span or (None, None)
            rows.append(
                {
                    "claim_id": r.claim_id,
                    "paper_id": r.paper_id,
                    "claim_text": r.claim_text,
                    "entity_names": "|".join(r.entity_names),
                    "support_conflict_unknown": r.support_conflict_unknown.value,
                    "confidence": round(r.confidence, _NDIGITS),
                    "extraction_method": p.extraction_method,
                    "source_snippet": p.source_snippet,
                    "char_start": span[0],
                    "char_end": span[1],
                    "database_links": "|".join(r.database_links),
                    "notes": r.notes,
                    "data_source": p.data_source.value,
                    "epistemic_level": p.epistemic_level.value,
                }
            )
        return rows

    @staticmethod
    def _row_dict(r: EvidenceItem) -> dict:
        d = r.model_dump(mode="json")
        d["confidence"] = round(r.confidence, _NDIGITS)
        return d


# -- assembly --------------------------------------------------------------


def _associations_by_entity(
    records: list[DatabaseRecord], dictionary: EntityDictionary
) -> dict[str, list[DatabaseRecord]]:
    """Map each protein entity id to the association records naming its gene.

    Combines records (a UniProt-anchored entity ↔ an Open Targets-style
    association) — an *inferred relation*. The gene key is the entity's HGNC
    cross-reference (every fixture protein carries one).
    """
    gene_to_eid: dict[str, str] = {}
    for eid, ent in dictionary.entities.items():
        gene = ent.db_xrefs.get("HGNC")
        if gene:
            gene_to_eid.setdefault(gene, eid)

    by_eid: dict[str, list[DatabaseRecord]] = {}
    for r in records:
        if r.record_type != "association":
            continue
        gene = r.fields.get("target_gene")
        eid = gene_to_eid.get(gene) if isinstance(gene, str) else None
        if eid is not None:
            by_eid.setdefault(eid, []).append(r)
    return by_eid


def _assoc_descriptor(r: DatabaseRecord) -> str:
    """A short human descriptor of an association record, for the notes field."""
    f = r.fields
    symbol = f.get("target_symbol") or f.get("target_gene") or r.record_id
    disease = f.get("disease_label", "?")
    score = f.get("association_score")
    score_str = f"; score={score}" if score is not None else ""
    return f"{r.source}:{r.record_id} ({symbol}→{disease}{score_str})"


def _row_links_and_notes(
    claim: Claim,
    overlap_ids: list[str],
    dictionary: EntityDictionary,
    assoc_by_eid: dict[str, list[DatabaseRecord]],
    support_reason: SupportLabel,
    reason_text: str,
) -> tuple[list[str], str]:
    """Build a row's ``database_links`` (ids) and ``notes`` (human provenance)."""
    links: set[str] = set()
    assoc_descriptors: list[str] = []
    for eid in claim.entity_ids:
        ent = dictionary.entities.get(eid)
        if ent is not None:
            for db, acc in ent.db_xrefs.items():
                links.add(f"{db}:{acc}")
        for rec in assoc_by_eid.get(eid, []):
            links.add(f"{rec.source}:{rec.record_id}")
            assoc_descriptors.append(_assoc_descriptor(rec))

    matched_names = [
        dictionary.entities[eid].canonical_name
        for eid in overlap_ids
        if eid in dictionary.entities
    ]
    note = f"{SUPPORT_METHOD} -> {support_reason.value} ({reason_text})"
    if matched_names:
        note += "; question entities matched: " + ", ".join(matched_names)
    if assoc_descriptors:
        note += "; associations: " + "; ".join(sorted(set(assoc_descriptors)))
    return sorted(links), note


def build_evidence_report(
    question: ResearchQuestion,
    extraction: ExtractionReport,
    dictionary: EntityDictionary,
    records: list[DatabaseRecord],
    *,
    min_confidence: float = 0.0,
    limit: int | None = None,
) -> EvidenceReport:
    """Assemble the evidence table for ``question`` from an extracted corpus.

    Keeps every extracted claim that mentions at least one of the question's
    recognized entities (and meets ``min_confidence``), turning each into one
    :class:`EvidenceItem` with full provenance, a support/conflict/unknown label,
    and database links. Rows are sorted by ``(-confidence, paper_id, claim_id)``
    so the strongest, most-grounded claims surface first; ``limit`` (if given)
    keeps the top rows after sorting.
    """
    question_entity_ids, unmatched = resolve_question_entities(question, dictionary)
    question_set = set(question_entity_ids)
    assoc_by_eid = _associations_by_entity(records, dictionary)
    names = {eid: ent.canonical_name for eid, ent in dictionary.entities.items()}

    items: list[EvidenceItem] = []
    for claim in extraction.all_claims:
        overlap = [eid for eid in claim.entity_ids if eid in question_set]
        if not overlap:
            continue
        if claim.confidence < min_confidence:
            continue

        label, reason_text = classify_support(
            claim.claim_text, has_relation=claim.relation is not None
        )
        links, note = _row_links_and_notes(
            claim, overlap, dictionary, assoc_by_eid, label, reason_text
        )
        items.append(
            EvidenceItem(
                claim_id=claim.claim_id,
                claim_text=claim.claim_text,
                entity_names=[names.get(eid, eid) for eid in claim.entity_ids],
                paper_id=claim.paper_id,
                support_conflict_unknown=label,
                database_links=links,
                confidence=claim.confidence,
                notes=note,
                provenance=Provenance(
                    paper_id=claim.paper_id,
                    source_snippet=claim.claim_text,
                    char_span=claim.provenance.char_span,
                    extraction_method=claim.provenance.extraction_method,
                    data_source=claim.provenance.data_source,
                    epistemic_level=EpistemicLevel.extracted_claim,
                ),
            )
        )

    items.sort(key=lambda r: (-r.confidence, r.paper_id, r.claim_id))
    if limit is not None:
        items = items[:limit]

    table = EvidenceTable(
        table_id=f"evtbl-{question.question_id}",
        research_question_id=question.question_id,
        research_question_text=question.text,
        rows=items,
        generated_by=(
            f"{BUILDER_METHOD}: claims grounded in question entities; "
            f"support via {SUPPORT_METHOD}; links from db-xrefs + associations"
        ),
        data_source=extraction.data_source if extraction.data_source != "mixed" else "fixture",
    )
    return EvidenceReport(
        question=question,
        table=table,
        method=table.generated_by,
        params={
            "relevance_rule": "claim mentions >= 1 recognized question entity",
            "support_method": SUPPORT_METHOD,
            "min_confidence": min_confidence,
            "limit": limit,
            "sort": "(-confidence, paper_id, claim_id)",
        },
        data_source=table.data_source,
        total_papers=extraction.total_papers,
        total_claims=extraction.num_claims,
        question_entity_ids=question_entity_ids,
        question_entity_names=[names.get(eid, eid) for eid in question_entity_ids],
        unmatched_terms=unmatched,
    )


# -- question resolution + database-backed convenience ---------------------


def _norm(text: str) -> str:
    return " ".join(text.lower().split())


def resolve_question(
    stored: list[ResearchQuestion],
    dictionary: EntityDictionary,
    *,
    question_text: str | None = None,
    question_id: str | None = None,
) -> ResearchQuestion:
    """Resolve the CLI's ``--question`` / ``--question-id`` to a :class:`ResearchQuestion`.

    * ``question_id`` given → the matching stored question (``KeyError`` if none).
    * ``question_text`` matching a stored question's id or normalized text → that
      stored question (so the curated ``entities_of_interest`` are used).
    * otherwise → a synthesized question whose ``entities_of_interest`` are left
      empty and resolved from the text alone, with a slug id.
    """
    by_id = {q.question_id: q for q in stored}
    if question_id is not None:
        if question_id not in by_id:
            raise KeyError(question_id)
        return by_id[question_id]

    if question_text is None:
        raise ValueError("either question_text or question_id must be provided")

    if question_text in by_id:
        return by_id[question_text]
    norm = _norm(question_text)
    for q in stored:
        if _norm(q.text) == norm:
            return q

    slug = "".join(c if c.isalnum() else "-" for c in norm).strip("-")[:48] or "adhoc"
    return ResearchQuestion(question_id=f"rq-adhoc-{slug}", text=question_text)


def load_evidence(
    db_path: str | Path,
    *,
    question_text: str | None = None,
    question_id: str | None = None,
    min_confidence: float = 0.0,
    limit: int | None = None,
) -> EvidenceReport:
    """Open an ingested database and build the evidence table for a question.

    Builds the fixture dictionary, extracts the corpus, resolves the question, and
    assembles the table — all offline and deterministic. Raises :class:`ValueError`
    if the file is not a bioscientist-os database, mirroring the other subcommands.
    """
    from bioscientist_os.storage import SQLiteStore

    with SQLiteStore(db_path) as store:
        if not store.is_initialized():
            raise ValueError(f"{db_path} is not a bioscientist-os database (no ingested tables)")
        records = list(store.iter_database_records())
        papers = list(store.iter_papers())
        stored_questions = list(store.iter_research_questions())

    dictionary = build_dictionary(records)
    extraction = extract_corpus(papers, dictionary)
    question = resolve_question(
        stored_questions, dictionary, question_text=question_text, question_id=question_id
    )
    return build_evidence_report(
        question, extraction, dictionary, records,
        min_confidence=min_confidence, limit=limit,
    )


__all__ = [
    "SUPPORT_METHOD",
    "BUILDER_METHOD",
    "NEGATION_CUES",
    "CONTRAST_CUES",
    "classify_support",
    "resolve_question_entities",
    "resolve_question",
    "EvidenceReport",
    "build_evidence_report",
    "load_evidence",
]
