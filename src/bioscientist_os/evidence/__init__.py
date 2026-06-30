"""Entity/claim extraction and evidence-table assembly (Milestones 4-5).

Transparent, non-LLM baselines: dictionary-based biomedical entity recognition,
claim-sentence extraction with exact source spans, and (Milestone 5) evidence
tables in which every cell carries provenance and a support/conflict/unknown label.

Milestone 4 (done) provides:

* :class:`EntityDictionary` / :func:`build_dictionary` — a fixture-built,
  fully inspectable surface-form dictionary with longest-match recognition;
* :func:`extract_entities`, :func:`extract_claims`, :func:`extract_paper`,
  :func:`extract_corpus` — the rule-based extractors;
* :func:`load_dictionary` / :func:`load_extraction` — database-backed convenience
  that builds the dictionary and extracts a whole ingested corpus;
* the result containers in :mod:`bioscientist_os.evidence.model`
  (:class:`EntityMention`, :class:`PaperExtraction`, :class:`ExtractionReport`).

Milestone 5 (done) adds evidence-table assembly in
:mod:`bioscientist_os.evidence.table`:

* :func:`build_evidence_report` / :func:`load_evidence` — group the extracted
  claims by a research question into an :class:`~bioscientist_os.schemas.EvidenceTable`
  whose every row carries provenance, database links, and a support label;
* :func:`classify_support` — the transparent textual support/conflict/unknown
  heuristic (not a biological verdict);
* :func:`resolve_question` / :func:`resolve_question_entities` — match the CLI
  question to a stored question and recognize its entities of interest;
* :class:`EvidenceReport` — the result container with CSV/JSON views.

Recognized entities are *observed metadata* (read from the text); extracted claims
are *extracted claims*; database links are *inferred relations*; the support label
is a heuristic textual signal — the evidence table keeps these levels separate.
"""

from __future__ import annotations

from bioscientist_os.evidence.dictionary import (
    CURATED_TERMS,
    DictionaryEntity,
    EntityDictionary,
    build_dictionary,
)
from bioscientist_os.evidence.extract import (
    ASSOCIATION_CUES,
    DIRECTED_CUES,
    ENTITY_METHOD,
    REPORTING_CUES,
    extract_claims,
    extract_corpus,
    extract_entities,
    extract_paper,
    load_dictionary,
    load_extraction,
)
from bioscientist_os.evidence.model import (
    EntityMention,
    ExtractionReport,
    PaperExtraction,
)
from bioscientist_os.evidence.table import (
    BUILDER_METHOD,
    CONTRAST_CUES,
    NEGATION_CUES,
    SUPPORT_METHOD,
    EvidenceReport,
    build_evidence_report,
    classify_support,
    load_evidence,
    resolve_question,
    resolve_question_entities,
)

__all__ = [
    "DictionaryEntity",
    "EntityDictionary",
    "build_dictionary",
    "CURATED_TERMS",
    "extract_entities",
    "extract_claims",
    "extract_paper",
    "extract_corpus",
    "load_dictionary",
    "load_extraction",
    "ENTITY_METHOD",
    "DIRECTED_CUES",
    "ASSOCIATION_CUES",
    "REPORTING_CUES",
    "EntityMention",
    "PaperExtraction",
    "ExtractionReport",
    # Milestone 5 — evidence table
    "build_evidence_report",
    "load_evidence",
    "classify_support",
    "resolve_question",
    "resolve_question_entities",
    "EvidenceReport",
    "SUPPORT_METHOD",
    "BUILDER_METHOD",
    "NEGATION_CUES",
    "CONTRAST_CUES",
]
