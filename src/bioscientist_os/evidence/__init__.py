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

Recognized entities are *observed metadata* (read from the text); extracted claims
are *extracted claims*; any subject–relation–object triple is part of the claim,
not an inferred relation. See :mod:`bioscientist_os.evidence.extract`.
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
]
