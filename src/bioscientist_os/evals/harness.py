"""The self-evaluation harness (Milestone 8).

A small but rigorous evaluation of the **workbench itself** — not of biological
truth. It measures whether the pipeline does what it claims on a fixed, committed
fixture set with hand-authored gold labels:

============================ ============================================ ====================
metric                       what it checks                               denominator
============================ ============================================ ====================
ingestion correctness        every fixture row lands in the db intact     # fixture records
search recall@k              labeled-relevant papers retrieved by BM25F   # relevant pairs
entity precision / recall    dictionary hits vs. gold entity sets         # predicted / # gold
claim sanity                 claims are well-formed and span-traceable    # extracted claims
evidence completeness        required columns populated                   # evidence rows
provenance coverage          rows with full provenance                    # evidence rows
============================ ============================================ ====================

Every rate is a :class:`bioscientist_os.evals.metrics.Proportion` carrying its
denominator and a 95% Wilson interval (see :mod:`bioscientist_os.evals.metrics`);
no metric is reported without its denominator, and heterogeneous tasks are never
folded into one headline number. Known failure modes (the rule-based recall misses)
are surfaced, not averaged away.

Everything is deterministic and offline: the evaluators are pure functions over the
ingested corpus, the dictionary/extraction, and the committed gold labels. The
database-backed :func:`run_eval` mirrors the other ``load_*`` entry points — it
opens an ingested SQLite database, rebuilds the dictionary/extraction/index once,
and runs every evaluator.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from bioscientist_os import __version__
from bioscientist_os.evals.gold import GoldEntityLabel, GoldLabels, GoldQuery, load_gold
from bioscientist_os.evals.metrics import DEFAULT_CONFIDENCE, Proportion, f1_score
from bioscientist_os.evidence.dictionary import EntityDictionary, build_dictionary
from bioscientist_os.evidence.extract import extract_corpus, extract_entities
from bioscientist_os.evidence.model import ExtractionReport
from bioscientist_os.evidence.table import build_evidence_report
from bioscientist_os.schemas import (
    DatabaseRecord,
    EpistemicLevel,
    Paper,
    ResearchQuestion,
)
from bioscientist_os.search import SearchIndex

EVAL_METHOD = (
    "self-eval: ingestion / search-recall / entity-PR / claim-sanity / evidence-completeness"
)

# Default retrieval cut-offs for recall@k.
DEFAULT_RECALL_K: tuple[int, ...] = (3, 5)

_NDIGITS = 4


def _data_source(papers: list[Paper]) -> str:
    sources = {p.data_source.value for p in papers}
    if not sources:
        return "fixture"
    return next(iter(sources)) if len(sources) == 1 else "mixed"


# ---------------------------------------------------------------------------
# 1. Ingestion correctness
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class IngestionEval:
    """Whether every committed fixture record round-trips through the database."""

    papers: Proportion
    database_records: Proportion
    research_questions: Proportion
    overall: Proportion
    extra_in_db: dict[str, int]
    mismatched_ids: dict[str, list[str]]

    def to_dict(self) -> dict:
        return {
            "papers": self.papers.to_dict(),
            "database_records": self.database_records.to_dict(),
            "research_questions": self.research_questions.to_dict(),
            "overall": self.overall.to_dict(),
            "extra_in_db": self.extra_in_db,
            "mismatched_ids": self.mismatched_ids,
        }


def evaluate_ingestion(
    fixtures_bundle,
    db_papers: list[Paper],
    db_records: list[DatabaseRecord],
    db_questions: list[ResearchQuestion],
    *,
    level: float = DEFAULT_CONFIDENCE,
) -> IngestionEval:
    """Compare the committed fixtures to what the database holds, record by record.

    A fixture record "matches" when a database row with the same id exists and is
    *equal* (full pydantic-model equality). Reports a proportion per table plus an
    overall proportion, the count of any db rows not present in the fixtures, and
    the ids that exist on both sides but differ.
    """
    fx_papers = {p.paper_id: p for p in fixtures_bundle.papers}
    fx_records = {
        (r.source, r.record_id): r
        for r in fixtures_bundle.proteins + fixtures_bundle.associations
    }
    fx_questions = {q.question_id: q for q in fixtures_bundle.questions}

    have_papers = {p.paper_id: p for p in db_papers}
    have_records = {(r.source, r.record_id): r for r in db_records}
    have_questions = {q.question_id: q for q in db_questions}

    def _match(fx: dict, have: dict, mismatched: list[str]) -> int:
        ok = 0
        for key, value in fx.items():
            if key in have:
                if have[key] == value:
                    ok += 1
                else:
                    mismatched.append(str(key))
        return ok

    mism: dict[str, list[str]] = {"papers": [], "database_records": [], "research_questions": []}
    p_ok = _match(fx_papers, have_papers, mism["papers"])
    r_ok = _match(fx_records, have_records, mism["database_records"])
    q_ok = _match(fx_questions, have_questions, mism["research_questions"])

    papers = Proportion("ingestion: papers", p_ok, len(fx_papers), level)
    records = Proportion("ingestion: database_records", r_ok, len(fx_records), level)
    questions = Proportion("ingestion: research_questions", q_ok, len(fx_questions), level)
    overall = Proportion(
        "ingestion: all fixture records",
        p_ok + r_ok + q_ok,
        len(fx_papers) + len(fx_records) + len(fx_questions),
        level,
    )
    extra = {
        "papers": max(0, len(have_papers) - len(fx_papers)),
        "database_records": max(0, len(have_records) - len(fx_records)),
        "research_questions": max(0, len(have_questions) - len(fx_questions)),
    }
    return IngestionEval(
        papers=papers,
        database_records=records,
        research_questions=questions,
        overall=overall,
        extra_in_db=extra,
        mismatched_ids={k: sorted(v) for k, v in mism.items()},
    )


# ---------------------------------------------------------------------------
# 2. Search recall on labeled queries
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SearchEval:
    """Retrieval recall on the labeled queries, micro (pooled) and macro (per-query mean)."""

    recall_micro: list[Proportion]
    recall_macro: dict[int, float]
    per_query: list[dict]
    recall_k: tuple[int, ...]
    num_queries: int

    def to_dict(self) -> dict:
        return {
            "recall_k": list(self.recall_k),
            "num_queries": self.num_queries,
            "recall_micro": [p.to_dict() for p in self.recall_micro],
            "recall_macro": {str(k): round(v, _NDIGITS) for k, v in self.recall_macro.items()},
            "per_query": self.per_query,
        }


def evaluate_search_recall(
    index: SearchIndex,
    queries: list[GoldQuery],
    *,
    recall_k: tuple[int, ...] = DEFAULT_RECALL_K,
    level: float = DEFAULT_CONFIDENCE,
) -> SearchEval:
    """Measure recall@k of the BM25F ranker against the labeled relevant sets.

    *Micro* recall@k pools relevant items across queries (numerator = relevant
    papers retrieved in the top k, denominator = total relevant pairs); *macro*
    recall@k averages the per-query recall. Each query's detail records the rank at
    which every relevant paper was retrieved (or ``null`` if outside the top k),
    so a low recall is auditable. Raises :class:`ValueError` if a gold relevant id
    is not in the corpus.
    """
    recall_k = tuple(sorted(set(recall_k)))
    max_k = max(recall_k) if recall_k else 0
    corpus_ids = {p.paper_id for p in index.papers}

    micro_num = dict.fromkeys(recall_k, 0)
    micro_den = 0
    macro_acc = dict.fromkeys(recall_k, 0.0)
    per_query: list[dict] = []

    for q in sorted(queries, key=lambda x: x.query_id):
        missing = [pid for pid in q.relevant_paper_ids if pid not in corpus_ids]
        if missing:
            raise ValueError(
                f"gold query {q.query_id!r} names paper(s) not in the corpus: {missing}"
            )
        response = index.search(q.query, limit=max_k)
        ranked = [h.paper_id for h in response.hits]
        rank_of = {pid: i + 1 for i, pid in enumerate(ranked)}
        relevant = set(q.relevant_paper_ids)
        micro_den += len(relevant)

        recalls: dict[int, float] = {}
        for k in recall_k:
            topk = set(ranked[:k])
            hit = len(relevant & topk)
            micro_num[k] += hit
            recalls[k] = hit / len(relevant)
            macro_acc[k] += recalls[k]
        per_query.append(
            {
                "query_id": q.query_id,
                "query": q.query,
                "num_relevant": len(relevant),
                "relevant_ranks": {
                    pid: rank_of.get(pid) for pid in sorted(q.relevant_paper_ids)
                },
                "recall_at_k": {str(k): round(recalls[k], _NDIGITS) for k in recall_k},
            }
        )

    n = len(queries)
    recall_micro = [Proportion(f"recall@{k}", micro_num[k], micro_den, level) for k in recall_k]
    recall_macro = {k: (macro_acc[k] / n if n else 0.0) for k in recall_k}
    return SearchEval(
        recall_micro=recall_micro,
        recall_macro=recall_macro,
        per_query=per_query,
        recall_k=recall_k,
        num_queries=n,
    )


# ---------------------------------------------------------------------------
# 3. Entity precision / recall on gold sets
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class EntityEval:
    """Distinct-entity precision/recall of the dictionary recognizer vs. gold sets."""

    precision: Proportion
    recall: Proportion
    f1: float | None
    true_positives: int
    false_positives: int
    false_negatives: int
    per_abstract: list[dict]

    def to_dict(self) -> dict:
        return {
            "precision": self.precision.to_dict(),
            "recall": self.recall.to_dict(),
            "f1": None if self.f1 is None else round(self.f1, _NDIGITS),
            "true_positives": self.true_positives,
            "false_positives": self.false_positives,
            "false_negatives": self.false_negatives,
            "per_abstract": self.per_abstract,
        }


def evaluate_entities(
    papers_by_id: dict[str, Paper],
    dictionary: EntityDictionary,
    entity_labels: list[GoldEntityLabel],
    *,
    level: float = DEFAULT_CONFIDENCE,
) -> EntityEval:
    """Micro precision/recall of dictionary recognition over the labeled abstracts.

    Granularity is *distinct entity per abstract* (what the recognizer emits). A
    true positive is a gold entity id the recognizer reports; a false positive is a
    reported id not in gold; a false negative is a gold id not reported (the recall
    misses). Raises :class:`KeyError` if a labeled paper is absent from the corpus.
    """
    tp = fp = fn = 0
    per_abstract: list[dict] = []
    for label in sorted(entity_labels, key=lambda x: x.paper_id):
        paper = papers_by_id[label.paper_id]
        recognized = {e.entity_id for e in extract_entities(paper, dictionary)}
        gold = label.entity_ids
        hits = recognized & gold
        extra = recognized - gold
        missed = gold - recognized
        tp += len(hits)
        fp += len(extra)
        fn += len(missed)
        per_abstract.append(
            {
                "paper_id": label.paper_id,
                "gold": sorted(gold),
                "recognized": sorted(recognized),
                "true_positives": sorted(hits),
                "false_positives": sorted(extra),
                "false_negatives": sorted(missed),
            }
        )

    precision = Proportion("entity precision", tp, tp + fp, level)
    recall = Proportion("entity recall", tp, tp + fn, level)
    return EntityEval(
        precision=precision,
        recall=recall,
        f1=f1_score(precision.point, recall.point),
        true_positives=tp,
        false_positives=fp,
        false_negatives=fn,
        per_abstract=per_abstract,
    )


# ---------------------------------------------------------------------------
# 4. Claim-extraction sanity
# ---------------------------------------------------------------------------

# The per-claim checks. Each is a named predicate so the report can show which
# property a claim would fail (all are expected to pass — this is a regression
# floor, not a quality score).
_CLAIM_CHECKS: tuple[str, ...] = (
    "text_nonempty",
    "span_round_trips",
    "paper_known",
    "grounded_in_entities",
    "confidence_in_range",
    "level_is_extracted_claim",
    "method_recorded",
)


@dataclass(frozen=True)
class ClaimEval:
    """Whether every extracted claim is well-formed and traceable to its source span."""

    overall: Proportion
    per_check: dict[str, Proportion]
    num_claims: int
    num_relations: int

    def to_dict(self) -> dict:
        return {
            "overall_well_formed_and_traceable": self.overall.to_dict(),
            "per_check": {name: p.to_dict() for name, p in self.per_check.items()},
            "num_claims": self.num_claims,
            "num_relations": self.num_relations,
        }


def evaluate_claims(
    extraction: ExtractionReport,
    papers_by_id: dict[str, Paper],
    dictionary: EntityDictionary,
    *,
    level: float = DEFAULT_CONFIDENCE,
) -> ClaimEval:
    """Sanity-check every extracted claim: well-formed, grounded, and span-traceable.

    For each claim, evaluate the :data:`_CLAIM_CHECKS` predicates — non-empty text,
    a ``char_span`` that reproduces the claim verbatim from the source abstract, a
    known paper, grounding in at least one recognized entity, an in-range
    confidence, the ``extracted_claim`` epistemic level, and a recorded method. The
    headline proportion is the fraction passing *all* checks (a regression floor,
    expected to be 1.0); each check also reports its own proportion.
    """
    claims = extraction.all_claims
    passed = dict.fromkeys(_CLAIM_CHECKS, 0)
    all_pass = 0
    for c in claims:
        prov = c.provenance
        paper = papers_by_id.get(c.paper_id)
        span = prov.char_span
        span_ok = (
            paper is not None
            and span is not None
            and paper.abstract[span[0] : span[1]] == c.claim_text
        )
        checks = {
            "text_nonempty": bool(c.claim_text.strip()),
            "span_round_trips": span_ok,
            "paper_known": paper is not None,
            "grounded_in_entities": (
                len(c.entity_ids) >= 1
                and all(eid in dictionary.entities for eid in c.entity_ids)
            ),
            "confidence_in_range": 0.0 <= c.confidence <= 1.0,
            "level_is_extracted_claim": prov.epistemic_level is EpistemicLevel.extracted_claim,
            "method_recorded": bool(prov.extraction_method),
        }
        for name, ok in checks.items():
            if ok:
                passed[name] += 1
        if all(checks.values()):
            all_pass += 1

    n = len(claims)
    return ClaimEval(
        overall=Proportion("claim well-formed & traceable", all_pass, n, level),
        per_check={
            name: Proportion(f"claim:{name}", passed[name], n, level) for name in _CLAIM_CHECKS
        },
        num_claims=n,
        num_relations=extraction.num_relations,
    )


# ---------------------------------------------------------------------------
# 5. Evidence-table completeness + provenance coverage
# ---------------------------------------------------------------------------

# Evidence-row fields that must be populated for the row to count as "complete".
# database_links is intentionally excluded: a curated-only entity legitimately has
# no database link, so requiring it would penalize an honest empty cell.
_REQUIRED_EVIDENCE_FIELDS: tuple[str, ...] = (
    "claim_id",
    "claim_text",
    "paper_id",
    "entity_names",
    "source_snippet",
    "extraction_method",
    "notes",
)


@dataclass(frozen=True)
class EvidenceEval:
    """Evidence-table completeness and full-provenance coverage across all questions."""

    completeness: Proportion
    provenance_coverage: Proportion
    total_rows: int
    per_question: list[dict]

    def to_dict(self) -> dict:
        return {
            "completeness": self.completeness.to_dict(),
            "provenance_coverage": self.provenance_coverage.to_dict(),
            "total_rows": self.total_rows,
            "per_question": self.per_question,
        }


def _row_is_complete(item) -> bool:
    prov = item.provenance
    values = {
        "claim_id": item.claim_id,
        "claim_text": item.claim_text,
        "paper_id": item.paper_id,
        "entity_names": item.entity_names,
        "source_snippet": prov.source_snippet,
        "extraction_method": prov.extraction_method,
        "notes": item.notes,
    }
    for fieldname in _REQUIRED_EVIDENCE_FIELDS:
        v = values[fieldname]
        if v is None or (isinstance(v, (str, list)) and len(v) == 0):
            return False
    return 0.0 <= item.confidence <= 1.0


def _row_has_full_provenance(item) -> bool:
    prov = item.provenance
    return bool(
        prov.paper_id
        and prov.source_snippet
        and prov.char_span is not None
        and prov.extraction_method
        and prov.epistemic_level is not None
    )


def evaluate_evidence(
    questions: list[ResearchQuestion],
    extraction: ExtractionReport,
    dictionary: EntityDictionary,
    records: list[DatabaseRecord],
    *,
    level: float = DEFAULT_CONFIDENCE,
) -> EvidenceEval:
    """Build the evidence table per stored question; score completeness + provenance.

    A row is *complete* when every required column (see
    :data:`_REQUIRED_EVIDENCE_FIELDS`) is populated and its confidence is in range;
    it has *full provenance* when its provenance names a paper, a verbatim snippet,
    an exact span, a method, and an epistemic level. Both proportions pool rows over
    all stored questions (denominator = total evidence rows).
    """
    complete = full_prov = total = 0
    per_question: list[dict] = []
    for q in sorted(questions, key=lambda x: x.question_id):
        report = build_evidence_report(q, extraction, dictionary, records)
        q_complete = sum(1 for r in report.rows if _row_is_complete(r))
        q_prov = sum(1 for r in report.rows if _row_has_full_provenance(r))
        complete += q_complete
        full_prov += q_prov
        total += report.num_rows
        per_question.append(
            {
                "question_id": q.question_id,
                "num_rows": report.num_rows,
                "complete_rows": q_complete,
                "full_provenance_rows": q_prov,
                "support_counts": report.support_counts(),
            }
        )
    return EvidenceEval(
        completeness=Proportion("evidence completeness", complete, total, level),
        provenance_coverage=Proportion("provenance coverage", full_prov, total, level),
        total_rows=total,
        per_question=per_question,
    )


# ---------------------------------------------------------------------------
# Report container + database-backed entry point
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class EvalReport:
    """The full self-evaluation: every section plus the run parameters that produced it."""

    ingestion: IngestionEval
    search: SearchEval
    entities: EntityEval
    claims: ClaimEval
    evidence: EvidenceEval
    data_source: str
    confidence_level: float
    params: dict[str, object]
    gold_summary: dict[str, int]

    method: str = EVAL_METHOD
    version: str = __version__

    def headline(self) -> list[Proportion]:
        """The key proportions, in report order (for the text summary)."""
        return [
            self.ingestion.overall,
            *self.search.recall_micro,
            self.entities.precision,
            self.entities.recall,
            self.claims.overall,
            self.evidence.completeness,
            self.evidence.provenance_coverage,
        ]

    def to_dict(self) -> dict:
        return {
            "method": self.method,
            "version": self.version,
            "data_source": self.data_source,
            "confidence_level": self.confidence_level,
            "params": self.params,
            "gold_summary": self.gold_summary,
            "ingestion": self.ingestion.to_dict(),
            "search": self.search.to_dict(),
            "entities": self.entities.to_dict(),
            "claims": self.claims.to_dict(),
            "evidence": self.evidence.to_dict(),
        }

    def format_text(self) -> str:
        """A readable, denominator-first multi-section summary."""
        lines = [
            f"Self-evaluation  (method={self.method})",
            f"  data_source={self.data_source}  confidence={int(self.confidence_level * 100)}%  "
            f"version={self.version}",
            f"  gold: {self.gold_summary['queries']} queries / "
            f"{self.gold_summary['relevant_pairs']} relevant pairs, "
            f"{self.gold_summary['entity_labeled_abstracts']} labeled abstracts / "
            f"{self.gold_summary['gold_entity_mentions']} gold entities",
            "",
            "1. Ingestion correctness (fixture rows that round-trip through the db)",
            "     " + self.ingestion.overall.format_line(),
            f"       papers={self.ingestion.papers.numerator}/{self.ingestion.papers.denominator}  "
            f"records={self.ingestion.database_records.numerator}/"
            f"{self.ingestion.database_records.denominator}  "
            f"questions={self.ingestion.research_questions.numerator}/"
            f"{self.ingestion.research_questions.denominator}  "
            f"extra_in_db={self.ingestion.extra_in_db}",
            "",
            "2. Search recall on labeled queries (BM25F)",
        ]
        for p in self.search.recall_micro:
            k = int(p.label.split("@")[1])
            macro = self.search.recall_macro.get(k)
            lines.append(f"     micro {p.format_line()}   macro mean={macro:.3f}")
        lines += [
            "",
            "3. Entity recognition vs. gold sets (distinct entity per abstract)",
            "     " + self.entities.precision.format_line(),
            "     " + self.entities.recall.format_line(),
            f"     F1={self.entities.f1:.3f}  (TP={self.entities.true_positives} "
            f"FP={self.entities.false_positives} FN={self.entities.false_negatives})"
            if self.entities.f1 is not None
            else "     F1=undefined",
            "",
            "4. Claim-extraction sanity (well-formed + span-traceable)",
            "     " + self.claims.overall.format_line(),
            f"       over {self.claims.num_claims} claims "
            f"({self.claims.num_relations} with a relation triple)",
            "",
            "5. Evidence-table completeness + provenance coverage",
            "     " + self.evidence.completeness.format_line(),
            "     " + self.evidence.provenance_coverage.format_line(),
            f"       over {self.evidence.total_rows} evidence rows "
            f"across {len(self.evidence.per_question)} questions",
            "",
            "This evaluates the PIPELINE on a tiny, partly-synthetic fixture corpus — not",
            "biological truth. N is small by construction; Wilson intervals are wide and",
            "convey uncertainty, they do not certify performance (see docs/SAFETY.md).",
        ]
        return "\n".join(lines)


def run_eval(
    db_path: str | Path,
    *,
    gold: GoldLabels | None = None,
    gold_root: Path | str | None = None,
    fixtures_root: Path | str | None = None,
    confidence: float = DEFAULT_CONFIDENCE,
    recall_k: tuple[int, ...] = DEFAULT_RECALL_K,
) -> EvalReport:
    """Open an ingested database and run the full self-evaluation, offline.

    Reads the corpus from the database, the committed gold labels (via ``gold`` or
    ``gold_root``), and the committed fixtures (for the ingestion-correctness
    comparison, via ``fixtures_root``). Raises :class:`ValueError` if the file is
    not a bioscientist-os database (no ingested tables), mirroring the other
    database-backed entry points.
    """
    from bioscientist_os import fixtures as fixtures_mod
    from bioscientist_os.storage import SQLiteStore

    with SQLiteStore(db_path) as store:
        if not store.is_initialized():
            raise ValueError(f"{db_path} is not a bioscientist-os database (no ingested tables)")
        papers = list(store.iter_papers())
        records = list(store.iter_database_records())
        questions = list(store.iter_research_questions())

    if gold is None:
        gold = load_gold(gold_root)
    fixtures_bundle = fixtures_mod.load_all(fixtures_root)

    dictionary = build_dictionary(records)
    extraction = extract_corpus(papers, dictionary)
    index = SearchIndex.from_papers(papers)
    papers_by_id = {p.paper_id: p for p in papers}

    ingestion = evaluate_ingestion(fixtures_bundle, papers, records, questions, level=confidence)
    search = evaluate_search_recall(index, list(gold.queries), recall_k=recall_k, level=confidence)
    entities = evaluate_entities(
        papers_by_id, dictionary, list(gold.entity_labels), level=confidence
    )
    claims = evaluate_claims(extraction, papers_by_id, dictionary, level=confidence)
    evidence = evaluate_evidence(questions, extraction, dictionary, records, level=confidence)

    return EvalReport(
        ingestion=ingestion,
        search=search,
        entities=entities,
        claims=claims,
        evidence=evidence,
        data_source=_data_source(papers),
        confidence_level=confidence,
        params={
            "recall_k": list(search.recall_k),
            "num_papers": len(papers),
            "num_database_records": len(records),
            "num_questions": len(questions),
            "dictionary_entities": len(dictionary),
        },
        gold_summary=gold.summary(),
    )


__all__ = [
    "EVAL_METHOD",
    "DEFAULT_RECALL_K",
    "IngestionEval",
    "SearchEval",
    "EntityEval",
    "ClaimEval",
    "EvidenceEval",
    "EvalReport",
    "evaluate_ingestion",
    "evaluate_search_recall",
    "evaluate_entities",
    "evaluate_claims",
    "evaluate_evidence",
    "run_eval",
]
