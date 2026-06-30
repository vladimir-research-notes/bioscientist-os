"""Self-evaluation harness with committed gold labels (Milestone 8).

A small but rigorous evaluation of the **workbench itself** (not of biological
truth): ingestion correctness, BM25F search recall on labeled queries, dictionary
entity precision/recall against gold sets, claim-extraction sanity, evidence-table
completeness, and provenance coverage. Every rate is a
:class:`~bioscientist_os.evals.metrics.Proportion` that carries its denominator and
a 95% Wilson interval; small N is stated honestly and heterogeneous tasks are never
collapsed into one headline number.

Layout:

* :mod:`bioscientist_os.evals.metrics` — the proportion/Wilson-interval core;
* :mod:`bioscientist_os.evals.gold` — typed loaders for the committed gold labels
  under ``data/fixtures/gold/``;
* :mod:`bioscientist_os.evals.harness` — the per-task evaluators, the
  :class:`~bioscientist_os.evals.harness.EvalReport` container, and the
  database-backed :func:`~bioscientist_os.evals.harness.run_eval`.

The evaluators are pure, deterministic, and fully offline; ``biosci eval`` and
``scripts/06_run_eval.py`` are thin wrappers over :func:`run_eval`.
"""

from __future__ import annotations

from bioscientist_os.evals.gold import (
    GoldEntity,
    GoldEntityLabel,
    GoldError,
    GoldLabels,
    GoldQuery,
    load_entity_labels,
    load_gold,
    load_search_queries,
)
from bioscientist_os.evals.harness import (
    DEFAULT_RECALL_K,
    EVAL_METHOD,
    ClaimEval,
    EntityEval,
    EvalReport,
    EvidenceEval,
    IngestionEval,
    SearchEval,
    evaluate_claims,
    evaluate_entities,
    evaluate_evidence,
    evaluate_ingestion,
    evaluate_search_recall,
    run_eval,
)
from bioscientist_os.evals.metrics import (
    DEFAULT_CONFIDENCE,
    Proportion,
    f1_score,
    wilson_interval,
    z_for_confidence,
)

__all__ = [
    # metrics
    "DEFAULT_CONFIDENCE",
    "Proportion",
    "wilson_interval",
    "z_for_confidence",
    "f1_score",
    # gold labels
    "GoldError",
    "GoldQuery",
    "GoldEntity",
    "GoldEntityLabel",
    "GoldLabels",
    "load_gold",
    "load_search_queries",
    "load_entity_labels",
    # harness
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
