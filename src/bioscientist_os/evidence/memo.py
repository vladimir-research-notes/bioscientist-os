"""End-to-end research-memo generation (Milestone 9).

The memo is the workbench's *narrative capstone*: it assembles the existing,
transparent pipeline outputs for one research question into a single structured
document — and it does so without introducing any new, unaudited computation.
Every part of the memo is a re-presentation of a layer that already exists, with
its provenance and its epistemic level kept intact:

================ ================================================= ====================
memo section     built from                                        epistemic level
================ ================================================= ====================
research question the question + dictionary-recognized entities     observed metadata
key papers        BM25F retrieval (M3) + evidence contribution      observed metadata
evidence table    the M5 evidence-table builder                     extracted claim (rows)
database links    UniProt/HGNC xrefs + Open Targets associations    inferred relation
conflicts/uncert. textual-conflict rows + candidate disagreements   extracted claim / uncertainty
next experiments  generated mechanically from the evidence          unsupported hypothesis
================ ================================================= ====================

Three disciplines, inherited from the rest of the package and enforced here:

* **The four epistemic levels are never collapsed.** Each memo section is tagged
  with the level it belongs to (see :data:`bioscientist_os.EPISTEMIC_LEVELS`), and
  the "suggested next experiments" are emitted *only* as
  :class:`Hypothesis` objects explicitly marked ``unsupported`` — never as
  findings, recommendations, or protocols.
* **Provenance on every claim.** Every evidence row carries its paper, verbatim
  snippet, exact span, method, and data source (provenance coverage is 1.0 by
  construction, inherited from M5).
* **No medical advice.** The memo opens and closes with the non-clinical
  statement; the support/conflict label is a heuristic *textual* signal, the
  database links are *inferred relations*, and the hypotheses are *unsupported*.
  Anything that could read as clinical advice is a defect (see ``docs/SAFETY.md``).

Everything is deterministic and offline: papers, rows, links, disagreements, and
hypotheses are all sorted before they enter the memo, so the Markdown and JSON a
run produces are byte-identical across runs. The database-backed :func:`load_memo`
mirrors :func:`bioscientist_os.evidence.load_evidence` /
:func:`bioscientist_os.visualization.load_visualizations`.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import ClassVar

from bioscientist_os import __version__
from bioscientist_os.evidence.dictionary import EntityDictionary, build_dictionary
from bioscientist_os.evidence.extract import extract_corpus
from bioscientist_os.evidence.model import ExtractionReport
from bioscientist_os.evidence.table import (
    BUILDER_METHOD,
    SUPPORT_METHOD,
    EvidenceReport,
    build_evidence_report,
    resolve_question,
)
from bioscientist_os.schemas import (
    Claim,
    DatabaseRecord,
    EvidenceItem,
    Paper,
    ResearchQuestion,
    SupportLabel,
)
from bioscientist_os.search import SearchIndex

# The named method that assembles the memo (recorded in ``generated_by``). The
# memo introduces no new computation — it composes M3 retrieval, the M5 evidence
# table, db-xref/association links, and a mechanical hypothesis generator.
MEMO_METHOD = "memo-generator"

# Open Targets-style association source name (matches the fixtures / connectors).
_ASSOCIATION_SOURCE = "OpenTargets"

# Confidence rounding applied only in JSON output (mirrors the rest of the package).
_NDIGITS = 4

# Readable phrasing for the M4 normalized relation verbs, used when a hypothesis is
# rendered from a relation triple. Falls back to the relation with underscores
# turned into spaces, so an unmapped verb still reads sensibly.
_RELATION_PHRASE: dict[str, str] = {
    "secretes": "secretes",
    "promotes": "promotes",
    "restrains": "restrains",
    "drives": "drives",
    "induces": "induces",
    "inhibits": "inhibits",
    "activates": "activates",
    "accelerates": "accelerates",
    "reduces": "reduces",
    "increases": "increases",
    "required_for": "is required for",
    "extends": "extends",
    "delays": "delays",
    "improves": "improves",
    "associated_with": "is associated with",
}


def _relation_phrase(relation: str) -> str:
    return _RELATION_PHRASE.get(relation, relation.replace("_", " "))


# ---------------------------------------------------------------------------
# Section result containers
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class KeyPaper:
    """A paper that contributes evidence to the question, with its retrieval signal.

    ``num_evidence_rows`` / ``support_counts`` describe this paper's contribution to
    the evidence table; ``bm25f_rank`` / ``bm25f_score`` / ``matched_terms`` are the
    independent M3 BM25F retrieval signal against the question text (shown for
    reference, not used to rank). All fields are *observed metadata*.
    """

    paper_id: str
    title: str
    year: int | None
    journal: str | None
    external_ids: dict[str, str]
    num_evidence_rows: int
    support_counts: dict[str, int]
    summed_confidence: float
    bm25f_rank: int | None
    bm25f_score: float
    matched_terms: list[str]

    def to_dict(self) -> dict:
        return {
            "paper_id": self.paper_id,
            "title": self.title,
            "year": self.year,
            "journal": self.journal,
            "external_ids": dict(sorted(self.external_ids.items())),
            "num_evidence_rows": self.num_evidence_rows,
            "support_counts": self.support_counts,
            "summed_confidence": round(self.summed_confidence, _NDIGITS),
            "bm25f_rank": self.bm25f_rank,
            "bm25f_score": round(self.bm25f_score, _NDIGITS),
            "matched_terms": list(self.matched_terms),
        }


@dataclass(frozen=True)
class EntityLinks:
    """The database links for one entity — an *inferred relation* (combined records)."""

    entity_id: str
    entity_name: str
    xrefs: dict[str, str]
    associations: list[str]

    def to_dict(self) -> dict:
        return {
            "entity_id": self.entity_id,
            "entity_name": self.entity_name,
            "xrefs": dict(sorted(self.xrefs.items())),
            "associations": list(self.associations),
        }


@dataclass(frozen=True)
class DirectionalDisagreement:
    """Two+ papers asserting different relation verbs on the same entity pair.

    A **candidate** disagreement surfaced for a human to verify — NOT an asserted
    biological conflict. The per-sentence support label does not detect this (a
    documented M5 limitation); the memo flags it as an *uncertainty*.
    """

    entity_a: str
    entity_b: str
    relations: list[str]
    claims: list[dict]

    def to_dict(self) -> dict:
        return {
            "entity_a": self.entity_a,
            "entity_b": self.entity_b,
            "relations": list(self.relations),
            "claims": list(self.claims),
        }


@dataclass(frozen=True)
class Hypothesis:
    """A suggested next question, generated mechanically and explicitly unsupported.

    A hypothesis for a human researcher to evaluate — never evidence, a finding, a
    recommendation, a protocol, or clinical advice (see ``docs/SAFETY.md``).
    ``status`` is always ``"unsupported"``.
    """

    text: str
    basis: str
    status: str = "unsupported"

    def to_dict(self) -> dict:
        return {"text": self.text, "basis": self.basis, "status": self.status}


# ---------------------------------------------------------------------------
# The memo report
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class MemoReport:
    """A structured research memo assembled from the pipeline for one question.

    Holds the resolved question, the M5 :class:`EvidenceReport` it is built on, and
    the derived memo sections (key papers, database links, conflicts/uncertainties,
    unsupported hypotheses). Renders to Markdown (:meth:`to_markdown`) and to a
    deterministic JSON dict (:meth:`to_dict`).
    """

    question: ResearchQuestion
    evidence: EvidenceReport
    key_papers: list[KeyPaper]
    total_contributing_papers: int
    database_links: list[str]
    link_details: list[EntityLinks]
    conflict_rows: list[EvidenceItem]
    directional_disagreements: list[DirectionalDisagreement]
    hypotheses: list[Hypothesis]
    retrieved_without_evidence: list[dict]
    method: str
    data_source: str
    params: dict[str, object]
    version: str = __version__

    # The four-level legend, in canonical order. Surfaced in the memo so a reader
    # always sees the vocabulary the memo is tagged with.
    EPISTEMIC_LEGEND: ClassVar[tuple[tuple[str, str], ...]] = (
        ("observed metadata", "directly read from a record (titles, ids, years)"),
        ("extracted claim", "a sentence pulled from an abstract by a named method, with its span"),
        ("inferred relation", "a link asserted by combining records (xrefs, associations)"),
        ("unsupported hypothesis", "a suggestion for a human to evaluate; explicitly not evidence"),
    )

    # ---- convenience views ------------------------------------------------

    @property
    def support_counts(self) -> dict[str, int]:
        return self.evidence.support_counts()

    @property
    def num_rows(self) -> int:
        return self.evidence.num_rows

    # ---- JSON view --------------------------------------------------------

    def to_dict(self) -> dict:
        return {
            "method": self.method,
            "version": self.version,
            "data_source": self.data_source,
            "params": self.params,
            "question": {
                "question_id": self.question.question_id,
                "text": self.question.text,
                "entities_of_interest": list(self.question.entities_of_interest),
            },
            "question_entity_names": list(self.evidence.question_entity_names),
            "unmatched_terms": list(self.evidence.unmatched_terms),
            "corpus": {
                "total_papers": self.evidence.total_papers,
                "total_claims": self.evidence.total_claims,
                "relevant_rows": self.num_rows,
                "support_counts": self.support_counts,
                "provenance_coverage": round(self.evidence.provenance_coverage, _NDIGITS),
            },
            "key_papers": [k.to_dict() for k in self.key_papers],
            "total_contributing_papers": self.total_contributing_papers,
            "evidence_rows": self.evidence.evidence_rows(),
            "database_links": list(self.database_links),
            "link_details": [d.to_dict() for d in self.link_details],
            "conflicts": {
                "textual_conflict_rows": [self._row_brief(r) for r in self.conflict_rows],
                "directional_disagreements": [
                    d.to_dict() for d in self.directional_disagreements
                ],
            },
            "uncertainties": {
                "unknown_rows": self.support_counts["unknown"],
                "unmatched_terms": list(self.evidence.unmatched_terms),
                "retrieved_without_evidence": list(self.retrieved_without_evidence),
            },
            "hypotheses": [h.to_dict() for h in self.hypotheses],
        }

    @staticmethod
    def _row_brief(r: EvidenceItem) -> dict:
        span = r.provenance.char_span or (None, None)
        return {
            "claim_id": r.claim_id,
            "paper_id": r.paper_id,
            "claim_text": r.claim_text,
            "support_conflict_unknown": r.support_conflict_unknown.value,
            "char_start": span[0],
            "char_end": span[1],
            "notes": r.notes,
        }

    # ---- Markdown view ----------------------------------------------------

    def to_markdown(self) -> str:
        """Render the memo as GitHub-flavored Markdown (deterministic)."""
        ev = self.evidence
        lines: list[str] = []

        # -- header + non-clinical banner -----------------------------------
        lines += [
            f"# Research memo: {self.question.text}",
            "",
            "> **Not medical advice.** bioscientist-os is a research-assistance tool, "
            "**not** a medical-advice, diagnostic, or treatment-recommendation tool. "
            "Nothing in this memo is a clinical recommendation. Every section is tagged "
            "with one of four epistemic levels and these are never collapsed "
            "(see docs/SAFETY.md).",
            "",
            f"- question_id: `{self.question.question_id}` · "
            f"data_source: `{self.data_source}` · "
            f"generated_by: `{self.method}` · bioscientist-os v{self.version}",
            "- Assembled deterministically from the committed corpus by transparent, "
            "non-LLM baselines (BM25F retrieval, dictionary entity recognition, "
            "rule-based claim extraction, the evidence-table builder, and a mechanical "
            "hypothesis generator). No language model wrote this memo.",
            "",
            "## Epistemic levels used in this memo",
        ]
        for i, (level, gloss) in enumerate(self.EPISTEMIC_LEGEND, start=1):
            lines.append(f"{i}. **{level}** — {gloss}.")
        lines.append("")

        # -- 1. research question -------------------------------------------
        lines += [
            "## 1. Research question  _[observed metadata]_",
            "",
            f"- **Question:** {self.question.text}",
            "- **Recognized entities of interest:** "
            + (", ".join(ev.question_entity_names) or "_(none recognized)_"),
        ]
        if ev.unmatched_terms:
            lines.append(
                "- **Unmatched terms (no fixture record — honest coverage gap):** "
                + ", ".join(ev.unmatched_terms)
            )
        lines.append("")

        # -- 2. corpus + method ---------------------------------------------
        sc = self.support_counts
        lines += [
            "## 2. Corpus and method  _[observed metadata]_",
            "",
            f"- Corpus: {ev.total_papers} papers, {ev.total_claims} extracted claims "
            f"(data_source={self.data_source}).",
            f"- Relevant claims for this question: **{self.num_rows}** of {ev.total_claims} "
            "(a claim is kept iff it mentions ≥ 1 recognized question entity).",
            f"- Support label breakdown: support {sc['support']} · conflict {sc['conflict']} "
            f"· unknown {sc['unknown']}.",
            "- Methods: retrieval = BM25F; entities = `dict:exact`; claims = "
            "`rule:claim-sentence`/`rule:svo`; support = `rule:support-cues`; "
            "links = db-xrefs + associations.",
            "",
        ]

        # -- 3. key papers ---------------------------------------------------
        lines += [
            "## 3. Key papers  _[observed metadata]_",
            "",
            f"Papers contributing evidence to this question ({len(self.key_papers)} of "
            f"{self.total_contributing_papers} shown), ranked by evidence contribution; "
            "the BM25F retrieval rank against the question text is shown for reference.",
            "",
        ]
        if not self.key_papers:
            lines.append("_(no paper contributed an evidence row for this question)_")
        for k in self.key_papers:
            year = k.year if k.year is not None else "----"
            journal = f", *{k.journal}*" if k.journal else ""
            ids = ", ".join(f"{db}={acc}" for db, acc in sorted(k.external_ids.items())) or "—"
            rank = f"#{k.bm25f_rank}" if k.bm25f_rank is not None else "—"
            matched = ", ".join(k.matched_terms) or "—"
            lines += [
                f"- **{k.paper_id}** ({year}{journal}) — {k.num_evidence_rows} evidence "
                f"row(s) [{k.support_counts['support']} support / "
                f"{k.support_counts['conflict']} conflict / {k.support_counts['unknown']} "
                f"unknown]; BM25F rank {rank} (score {k.bm25f_score:.3f}); ids: {ids}",
                f"  - {k.title}",
                f"  - matched query terms: {matched}",
            ]
        lines.append("")

        # -- 4. evidence table ----------------------------------------------
        lines += [
            "## 4. Evidence table",
            "",
            "Per row: the snippet is an _extracted claim_, `entity_names` are "
            "_observed metadata_, `database_links` are _inferred relations_, and the "
            "support/conflict/unknown label is a heuristic _textual_ signal — never a "
            "biological or clinical verdict.",
            "",
            f"Provenance coverage: **{ev.provenance_coverage:.0%}** "
            f"({self.num_rows}/{self.num_rows} rows name a paper and a source snippet).",
            "",
        ]
        if not ev.rows:
            lines += ["_(no claim mentions a recognized question entity)_", ""]
        else:
            for label in (SupportLabel.support, SupportLabel.conflict, SupportLabel.unknown):
                group = [r for r in ev.rows if r.support_conflict_unknown is label]
                lines.append(f"### {label.value.capitalize()} ({len(group)})")
                if not group:
                    lines += ["", "_(none)_", ""]
                    continue
                lines.append("")
                for r in group:
                    lines += self._render_evidence_row(r)
                lines.append("")

        # -- 5. database links ----------------------------------------------
        lines += [
            "## 5. Database links  _[inferred relation]_",
            "",
            "Links are asserted by **combining records** (a UniProt-anchored entity ↔ its "
            "cross-references and Open Targets-style associations); they are not stated "
            "outright in any single paper.",
            "",
        ]
        if not self.link_details:
            lines.append(
                "_(no database links for the entities in this question's evidence)_"
            )
        for d in self.link_details:
            xrefs = ", ".join(f"{db}:{acc}" for db, acc in sorted(d.xrefs.items())) or "—"
            line = f"- **{d.entity_name}** (`{d.entity_id}`): {xrefs}"
            if d.associations:
                line += "; associations: " + "; ".join(d.associations)
            lines.append(line)
        lines.append("")

        # -- 6. conflicts + uncertainties -----------------------------------
        lines += [
            "## 6. Conflicts and uncertainties",
            "",
            "This section asserts **no** biological conflict; it surfaces _textual_ "
            "signals and _candidate_ disagreements for a human to verify.",
            "",
            "### Textual-conflict rows  _[extracted claim · heuristic textual signal]_",
            "",
            "Sentences whose phrasing negates or contrasts a relationship "
            "(per-sentence, not cross-paper):",
            "",
        ]
        if not self.conflict_rows:
            lines.append("_(no row's phrasing negates or contrasts a relationship)_")
        for r in self.conflict_rows:
            lines.append(
                f"- `{r.claim_id}` ({r.paper_id}): \"{r.claim_text}\" — {r.notes}"
            )
        lines += [
            "",
            "### Candidate directional disagreements (verify by hand)  _[uncertainty]_",
            "",
            "Different relation verbs asserted on the same entity pair across papers. "
            "This is a **candidate** disagreement to read and verify — the per-sentence "
            "support label does **not** detect it (a documented limitation), and it is "
            "not asserted here as a real biological conflict.",
            "",
        ]
        if not self.directional_disagreements:
            lines.append(
                "_(no two papers assert different relation verbs on the same entity pair)_"
            )
        for d in self.directional_disagreements:
            lines.append(
                f"- **{d.entity_a} ↔ {d.entity_b}**: papers assert "
                f"{{{', '.join(d.relations)}}}"
            )
            for c in d.claims:
                lines.append(
                    f"  - {c['paper_id']} ({c['relation']}): \"{c['claim_text']}\""
                )
        lines += ["", "### Other uncertainties  _[observed metadata]_", ""]
        lines.append(
            f"- Unknown-label rows: {sc['unknown']} of {self.num_rows} "
            "(phrasing neither affirms nor negates a relationship)."
        )
        if ev.unmatched_terms:
            lines.append(
                "- Unmatched question terms (no fixture record → not covered): "
                + ", ".join(ev.unmatched_terms) + "."
            )
        if self.retrieved_without_evidence:
            pretty = ", ".join(
                f"{r['paper_id']} (BM25F #{r['bm25f_rank']})"
                for r in self.retrieved_without_evidence
            )
            lines.append(
                "- Retrieved but contributed no extractable claim (recall gap): "
                + pretty + "."
            )
        lines.append("")

        # -- 7. suggested next experiments (UNSUPPORTED) --------------------
        lines += [
            "## 7. Suggested next experiments — UNSUPPORTED HYPOTHESES  "
            "_[unsupported hypothesis]_",
            "",
            "These are research questions for a human to evaluate. They are **not "
            "evidence, not findings, not recommendations, and not clinical or treatment "
            "advice.** Each is generated mechanically from the evidence above and is "
            "explicitly **UNTESTED**.",
            "",
        ]
        if not self.hypotheses:
            lines.append("_(insufficient structured evidence to propose a hypothesis)_")
        for i, h in enumerate(self.hypotheses, start=1):
            lines.append(
                f"{i}. **Hypothesis (UNSUPPORTED):** {h.text} _Basis: {h.basis}. "
                "Status: UNTESTED._"
            )
        lines.append("")

        # -- 8. limitations -------------------------------------------------
        lines += [
            "## 8. Limitations  _[observed metadata about this tool]_",
            "",
            "- Tiny, partly-synthetic, theme-focused corpus; counts illustrate pipeline "
            "behavior, **not** biological truth or population performance.",
            "- Extraction is a rule-based baseline (dictionary + proximity templates): "
            "limited recall, abstract-only, no coreference or syntax.",
            "- The support/conflict/unknown label reads one sentence's phrasing; it is "
            "not a biological or clinical verdict and does not, by itself, detect "
            "cross-paper conflict.",
            "- Database links are inferred by combining records; they are not asserted "
            "by any single paper.",
            "- Hypotheses are unsupported suggestions for humans, not findings.",
            "",
        ]

        # -- 9. provenance --------------------------------------------------
        lines += [
            "## 9. Provenance  _[observed metadata]_",
            "",
            "- Every evidence row carries `paper_id`, the verbatim source snippet, its "
            "exact character span, the extraction method, and `data_source` "
            f"(here: {self.data_source}).",
            f"- Provenance coverage: {ev.provenance_coverage:.0%} "
            f"({self.num_rows}/{self.num_rows}).",
            "- Reproduce (deterministic): `biosci memo --question \""
            f"{self.question.text}\" --db results/raw/bioscientist.db "
            "--out results/processed/memo.md`",
            "",
            "---",
            "",
            "bioscientist-os — research-assistance tool, **not** a medical-advice or "
            "diagnostic tool. Outputs organize literature and database metadata for human "
            "researchers; they are not clinical guidance (docs/SAFETY.md).",
        ]
        return "\n".join(lines) + "\n"

    @staticmethod
    def _render_evidence_row(r: EvidenceItem) -> list[str]:
        prov = r.provenance
        span = prov.char_span or (None, None)
        links = ", ".join(r.database_links) or "—"
        return [
            f"- `{r.claim_id}` — {r.paper_id}, conf={r.confidence:.2f}, "
            f"method=`{prov.extraction_method}`  _[extracted claim]_",
            f"  > \"{r.claim_text}\"",
            f"  - entities _[observed metadata]_: {', '.join(r.entity_names) or '—'}",
            f"  - database links _[inferred relation]_: {links}",
            f"  - support _[heuristic textual signal]_: "
            f"{r.support_conflict_unknown.value} — {r.notes}",
            f"  - provenance: {prov.paper_id}, abstract chars [{span[0]}:{span[1]}]",
        ]


# ---------------------------------------------------------------------------
# Assembly
# ---------------------------------------------------------------------------


def _gene_to_entity(dictionary: EntityDictionary) -> dict[str, str]:
    """Map an HGNC gene symbol to its entity id (first wins) — mirrors the M5 builder."""
    gene_to_eid: dict[str, str] = {}
    for eid, ent in dictionary.entities.items():
        gene = ent.db_xrefs.get("HGNC")
        if gene:
            gene_to_eid.setdefault(gene, eid)
    return gene_to_eid


def _associations_by_entity(
    records: list[DatabaseRecord], dictionary: EntityDictionary
) -> dict[str, list[DatabaseRecord]]:
    """Map each protein entity id to the association records naming its gene.

    Mirrors :func:`bioscientist_os.evidence.table._associations_by_entity` (the
    canonical M5 link assembly) so the memo's links never disagree with the table.
    """
    gene_to_eid = _gene_to_entity(dictionary)
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
    """A short human descriptor of an association record (mirrors the M5 builder)."""
    f = r.fields
    symbol = f.get("target_symbol") or f.get("target_gene") or r.record_id
    disease = f.get("disease_label", "?")
    score = f.get("association_score")
    score_str = f"; score={score}" if score is not None else ""
    return f"{r.source}:{r.record_id} ({symbol}→{disease}{score_str})"


def _build_key_papers(
    evidence: EvidenceReport,
    papers: list[Paper],
    index: SearchIndex,
    *,
    max_papers: int,
) -> tuple[list[KeyPaper], int, list[dict]]:
    """Build the ranked key-paper list plus the retrieved-but-no-evidence recall gap.

    Key papers are the papers that contributed ≥ 1 evidence row, ranked by
    ``(-num_rows, -summed_confidence, -bm25f_score, paper_id)``. The BM25F ranking
    over the *full* corpus supplies each paper's retrieval rank/score/matched terms,
    and the top retrieved papers that contributed no row are returned as an honest
    recall gap.
    """
    papers_by_id = {p.paper_id: p for p in papers}

    # Per-paper evidence contribution.
    by_paper: dict[str, list[EvidenceItem]] = {}
    for r in evidence.rows:
        by_paper.setdefault(r.paper_id, []).append(r)

    # Full-corpus BM25F ranking of the question text (rank/score/matched terms).
    response = index.search(evidence.question.text, limit=len(papers) or 1)
    rank_of = {h.paper_id: h.rank for h in response.hits}
    score_of = {h.paper_id: h.score for h in response.hits}
    terms_of = {h.paper_id: h.matched_terms for h in response.hits}

    def _counts(rows: list[EvidenceItem]) -> dict[str, int]:
        c = {label.value: 0 for label in SupportLabel}
        for row in rows:
            c[row.support_conflict_unknown.value] += 1
        return c

    contributors: list[KeyPaper] = []
    for pid, rows in by_paper.items():
        paper = papers_by_id.get(pid)
        contributors.append(
            KeyPaper(
                paper_id=pid,
                title=paper.title if paper else pid,
                year=paper.year if paper else None,
                journal=paper.journal if paper else None,
                external_ids=dict(paper.external_ids) if paper else {},
                num_evidence_rows=len(rows),
                support_counts=_counts(rows),
                summed_confidence=sum(r.confidence for r in rows),
                bm25f_rank=rank_of.get(pid),
                bm25f_score=score_of.get(pid, 0.0),
                matched_terms=list(terms_of.get(pid, [])),
            )
        )
    contributors.sort(
        key=lambda k: (-k.num_evidence_rows, -k.summed_confidence, -k.bm25f_score, k.paper_id)
    )
    total = len(contributors)

    # Recall gap: the top BM25F hits that contributed no evidence row.
    retrieved_gap = [
        {"paper_id": h.paper_id, "bm25f_rank": h.rank}
        for h in response.hits
        if h.paper_id not in by_paper and h.score > 0.0
    ][:3]

    return contributors[:max_papers], total, retrieved_gap


def _build_link_details(
    evidence: EvidenceReport,
    claims_by_id: dict[str, Claim],
    dictionary: EntityDictionary,
    records: list[DatabaseRecord],
) -> tuple[list[str], list[EntityLinks]]:
    """Aggregate distinct database links + per-entity link detail over the evidence rows."""
    assoc_by_eid = _associations_by_entity(records, dictionary)

    # Entity ids that appear in this question's evidence rows, in first-seen order.
    entity_ids: list[str] = []
    for r in evidence.rows:
        claim = claims_by_id.get(r.claim_id)
        if claim is None:
            continue
        for eid in claim.entity_ids:
            if eid not in entity_ids:
                entity_ids.append(eid)

    details: list[EntityLinks] = []
    for eid in entity_ids:
        ent = dictionary.entities.get(eid)
        if ent is None:
            continue
        assoc = sorted(_assoc_descriptor(rec) for rec in assoc_by_eid.get(eid, []))
        if not ent.db_xrefs and not assoc:
            continue  # an entity with no database link is not a "database link"
        details.append(
            EntityLinks(
                entity_id=eid,
                entity_name=ent.canonical_name,
                xrefs=dict(ent.db_xrefs),
                associations=assoc,
            )
        )
    details.sort(key=lambda d: d.entity_name)

    distinct_links = sorted({link for r in evidence.rows for link in r.database_links})
    return distinct_links, details


def _build_disagreements(
    evidence: EvidenceReport, claims_by_id: dict[str, Claim]
) -> list[DirectionalDisagreement]:
    """Find candidate cross-paper directional disagreements among the evidence rows.

    Groups the relation triples of this question's evidence-row claims by the
    unordered ``{subject, object}`` entity pair; a group is flagged when ≥ 2 distinct
    relation verbs are asserted by ≥ 2 distinct papers. This is a *candidate*
    disagreement for human review, not an asserted biological conflict.
    """
    # pair -> {relations}, {papers}, [claim dicts]
    by_pair: dict[tuple[str, str], dict] = {}
    for r in evidence.rows:
        claim = claims_by_id.get(r.claim_id)
        if claim is None or claim.relation is None:
            continue
        if not claim.subject or not claim.object:
            continue
        pair = tuple(sorted((claim.subject, claim.object)))
        bucket = by_pair.setdefault(
            pair, {"relations": set(), "papers": set(), "claims": []}
        )
        bucket["relations"].add(claim.relation)
        bucket["papers"].add(claim.paper_id)
        bucket["claims"].append(
            {
                "paper_id": claim.paper_id,
                "claim_id": claim.claim_id,
                "relation": claim.relation,
                "claim_text": claim.claim_text,
                "char_span": list(claim.provenance.char_span)
                if claim.provenance.char_span
                else None,
            }
        )

    out: list[DirectionalDisagreement] = []
    for (a, b), bucket in sorted(by_pair.items()):
        if len(bucket["relations"]) >= 2 and len(bucket["papers"]) >= 2:
            out.append(
                DirectionalDisagreement(
                    entity_a=a,
                    entity_b=b,
                    relations=sorted(bucket["relations"]),
                    claims=sorted(
                        bucket["claims"], key=lambda c: (c["paper_id"], c["claim_id"])
                    ),
                )
            )
    return out


def _build_hypotheses(
    evidence: EvidenceReport,
    claims_by_id: dict[str, Claim],
    disagreements: list[DirectionalDisagreement],
    *,
    max_hypotheses: int,
) -> list[Hypothesis]:
    """Generate unsupported hypotheses, deterministically, from the evidence.

    Priority order: (1) candidate directional disagreements (resolve the direction);
    (2) affirmed relation triples from support rows (test the asserted relationship);
    (3) unmatched question terms (a coverage gap to fill). Every hypothesis is framed
    as a research question and explicitly marked unsupported — never a recommendation,
    protocol, or clinical advice (see ``docs/SAFETY.md``).
    """
    out: list[Hypothesis] = []

    # (1) directional disagreements.
    for d in disagreements:
        verbs = " or ".join(_relation_phrase(rel) for rel in d.relations)
        papers = ", ".join(sorted({c["paper_id"] for c in d.claims}))
        out.append(
            Hypothesis(
                text=f"Whether {d.entity_a} {verbs} {d.entity_b}.",
                basis=f"candidate directional disagreement across papers {papers}",
            )
        )

    # (2) affirmed relation triples from support rows (dedup by triple).
    triples: list[tuple[float, str, str, str, str, str]] = []
    for r in evidence.rows:
        if r.support_conflict_unknown is not SupportLabel.support:
            continue
        claim = claims_by_id.get(r.claim_id)
        if claim is None or claim.relation is None or not claim.subject or not claim.object:
            continue
        triples.append(
            (r.confidence, r.claim_id, claim.subject, claim.relation, claim.object, r.paper_id)
        )
    triples.sort(key=lambda t: (-t[0], t[1]))
    seen: set[tuple[str, str, str]] = set()
    for _conf, _cid, subject, relation, obj, paper_id in triples:
        key = (subject, relation, obj)
        if key in seen:
            continue
        seen.add(key)
        out.append(
            Hypothesis(
                text=f"Whether {subject} {_relation_phrase(relation)} {obj}.",
                basis=f"relation triple reported by {paper_id}",
            )
        )

    # (3) unmatched question terms (coverage gaps).
    for term in evidence.unmatched_terms:
        out.append(
            Hypothesis(
                text=f"Whether {term} is relevant to this question, "
                "which the current corpus cannot address.",
                basis=f"coverage gap (no fixture record for {term})",
            )
        )

    return out[:max_hypotheses]


def build_memo_report(
    question: ResearchQuestion,
    papers: list[Paper],
    extraction: ExtractionReport,
    dictionary: EntityDictionary,
    records: list[DatabaseRecord],
    *,
    index: SearchIndex | None = None,
    max_papers: int = 8,
    max_hypotheses: int = 6,
    min_confidence: float = 0.0,
    limit: int | None = None,
) -> MemoReport:
    """Assemble the research memo for ``question`` from an extracted corpus.

    Builds the M5 evidence table (the spine of the memo), then derives the key
    papers (M3 BM25F + evidence contribution), the database-link detail, the
    textual-conflict rows, candidate directional disagreements, and the unsupported
    hypotheses. Deterministic and offline; introduces no new computation beyond the
    transparent baselines it composes.
    """
    evidence = build_evidence_report(
        question, extraction, dictionary, records,
        min_confidence=min_confidence, limit=limit,
    )
    claims_by_id = {c.claim_id: c for c in extraction.all_claims}
    if index is None:
        index = SearchIndex.from_papers(papers)

    key_papers, total_contributing, retrieved_gap = _build_key_papers(
        evidence, papers, index, max_papers=max_papers
    )
    distinct_links, link_details = _build_link_details(
        evidence, claims_by_id, dictionary, records
    )
    conflict_rows = [
        r for r in evidence.rows if r.support_conflict_unknown is SupportLabel.conflict
    ]
    disagreements = _build_disagreements(evidence, claims_by_id)
    hypotheses = _build_hypotheses(
        evidence, claims_by_id, disagreements, max_hypotheses=max_hypotheses
    )

    return MemoReport(
        question=question,
        evidence=evidence,
        key_papers=key_papers,
        total_contributing_papers=total_contributing,
        database_links=distinct_links,
        link_details=link_details,
        conflict_rows=conflict_rows,
        directional_disagreements=disagreements,
        hypotheses=hypotheses,
        retrieved_without_evidence=retrieved_gap,
        method=(
            f"{MEMO_METHOD}: M3 BM25F key papers + {BUILDER_METHOD} evidence table; "
            f"support via {SUPPORT_METHOD}; links from db-xrefs + associations; "
            "hypotheses are mechanically generated and unsupported"
        ),
        data_source=evidence.data_source,
        params={
            "max_papers": max_papers,
            "max_hypotheses": max_hypotheses,
            "min_confidence": min_confidence,
            "limit": limit,
            "association_source": _ASSOCIATION_SOURCE,
            "relevance_rule": "claim mentions >= 1 recognized question entity",
        },
    )


def load_memo(
    db_path: str | Path,
    *,
    question_text: str | None = None,
    question_id: str | None = None,
    max_papers: int = 8,
    max_hypotheses: int = 6,
    min_confidence: float = 0.0,
    limit: int | None = None,
) -> MemoReport:
    """Open an ingested database and assemble the research memo for a question.

    Builds the dictionary, extracts the corpus, resolves the question, and assembles
    the memo — all offline and deterministic. Raises :class:`ValueError` if the file
    is not a bioscientist-os database and :class:`KeyError` if ``question_id`` names
    no stored question, mirroring the other database-backed entry points.
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
    return build_memo_report(
        question, papers, extraction, dictionary, records,
        max_papers=max_papers, max_hypotheses=max_hypotheses,
        min_confidence=min_confidence, limit=limit,
    )


__all__ = [
    "MEMO_METHOD",
    "KeyPaper",
    "EntityLinks",
    "DirectionalDisagreement",
    "Hypothesis",
    "MemoReport",
    "build_memo_report",
    "load_memo",
]
