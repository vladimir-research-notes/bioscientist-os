"""Rule-based entity and claim extraction over paper abstracts (Milestone 4).

A transparent, **non-LLM** baseline that turns an ingested corpus into recognized
entities and extracted claims, each with a confidence and full provenance:

1. **Entities.** :func:`extract_entities` runs the fixture-built
   :class:`bioscientist_os.evidence.dictionary.EntityDictionary` over a paper's
   abstract and groups the recognized mentions into one
   :class:`bioscientist_os.schemas.BiomedicalEntity` per distinct entity. Each
   carries the verbatim first-mention surface and its exact ``char_span``, the
   surface forms seen, the entity's ``db_xrefs``, and
   ``extraction_method = "dict:exact"`` at epistemic level *observed metadata* (a
   recognized mention is read from the text, not inferred).

2. **Claims.** :func:`extract_claims` splits the abstract into sentences and emits a
   :class:`bioscientist_os.schemas.Claim` for every sentence that contains at least
   one recognized entity — a deliberately high-precision / limited-recall rule that
   keeps each claim grounded in known entities. The claim stores the verbatim
   sentence and its exact span; its ``entity_ids`` are the entities mentioned in the
   sentence; epistemic level is *extracted claim*.

3. **Relation templates (optional).** When a sentence contains a relation cue and a
   recognized entity on each side of it, a naive subject–verb–object triple is
   filled (``extraction_method = "rule:svo"`` for directed verbs, ``"rule:assoc"``
   for association cues). This is proximity-based and syntax-free: it picks the
   nearest recognized entity before/after the cue. It misses paraphrase and complex
   syntax by construction; the triple is part of the *extracted claim* (read from
   the sentence), never an inferred relation — inferring relations by combining
   records is Milestone 5.

Confidence is a transparent, additive **salience heuristic** — not a probability.
See :func:`_claim_confidence`. Extraction is deterministic: papers are processed in
``paper_id`` order and results stay in document order.

Scope note: extraction reads the **abstract** only, so every span indexes one
well-defined field and ``abstract[start:end]`` reproduces the snippet exactly.
Entities that appear only in a title are not recognized — a documented limitation.
"""

from __future__ import annotations

from pathlib import Path

from bioscientist_os.evidence.dictionary import EntityDictionary, build_dictionary
from bioscientist_os.evidence.model import EntityMention, ExtractionReport, PaperExtraction
from bioscientist_os.evidence.text import sentence_spans
from bioscientist_os.schemas import (
    BiomedicalEntity,
    Claim,
    EntityType,
    EpistemicLevel,
    Paper,
    Provenance,
)

ENTITY_METHOD = "dict:exact"

# Directed relation cues mapped to a normalized relation. Matched as lower-cased
# substrings (no word-boundary or morphology analysis — a baseline), so a stem such
# as "reduc" deliberately covers reduce/reduced/reduces/reduction. Order does not
# affect correctness; the leftmost valid cue in the sentence is chosen.
DIRECTED_CUES: tuple[tuple[str, str], ...] = (
    ("secrete", "secretes"),
    ("secretion of", "secretes"),
    ("promote", "promotes"),
    ("restrain", "restrains"),
    ("drive", "drives"),
    ("induce", "induces"),
    ("inhibit", "inhibits"),
    ("activat", "activates"),
    ("accelerat", "accelerates"),
    ("reduc", "reduces"),
    ("lower", "reduces"),
    ("attenuat", "reduces"),
    ("increase", "increases"),
    ("upregulation", "increases"),
    ("require", "required_for"),
    ("extend", "extends"),
    ("delay", "delays"),
    ("improve", "improves"),
)

# Symmetric association cues -> a single "associated_with" relation.
ASSOCIATION_CUES: tuple[str, ...] = (
    "associated with",
    "association with",
    "linked to",
    "correlated with",
    "co-occur",
    "tracks",
    "consistent with",
)

# Reporting/assertion cues that nudge claim salience up by a small amount.
REPORTING_CUES: tuple[str, ...] = (
    "observed", "found", "report", "shows", "show", "showed", "demonstrat",
    "reveal", "indicat", "conclude", "suggest", "support", "results",
)


def extract_entities(paper: Paper, dictionary: EntityDictionary) -> list[BiomedicalEntity]:
    """Recognize dictionary entities in ``paper``'s abstract as :class:`BiomedicalEntity`.

    One entity per distinct canonical id, with the verbatim first-mention surface
    and span as provenance and all observed surface forms as ``synonyms``.
    """
    mentions = dictionary.find(paper.abstract)
    return _entities_from_mentions(paper, dictionary, mentions)


def extract_claims(paper: Paper, dictionary: EntityDictionary) -> list[Claim]:
    """Extract entity-grounded claim sentences (with optional relation triples)."""
    mentions = dictionary.find(paper.abstract)
    return _claims_from_mentions(paper, mentions)


def extract_paper(paper: Paper, dictionary: EntityDictionary) -> PaperExtraction:
    """Extract both entities and claims for one paper (recognized once)."""
    mentions = dictionary.find(paper.abstract)
    return PaperExtraction(
        paper_id=paper.paper_id,
        title=paper.title,
        entities=_entities_from_mentions(paper, dictionary, mentions),
        claims=_claims_from_mentions(paper, mentions),
    )


def extract_corpus(papers: list[Paper], dictionary: EntityDictionary) -> ExtractionReport:
    """Extract entities and claims for the whole corpus, deterministically."""
    ordered = sorted(papers, key=lambda p: p.paper_id)
    paper_extractions = [extract_paper(p, dictionary) for p in ordered]
    sources = {p.data_source.value for p in ordered}
    data_source = next(iter(sources)) if len(sources) == 1 else ("mixed" if sources else "fixture")
    return ExtractionReport(
        method="dict:exact entities + rule:claim-sentence/svo claims",
        params={
            "dictionary_entities": len(dictionary),
            "dictionary_surfaces": dictionary.num_surfaces(),
            "claim_rule": "abstract sentence containing >= 1 recognized entity",
            "entity_method": ENTITY_METHOD,
        },
        data_source=data_source,
        total_papers=len(ordered),
        papers=paper_extractions,
    )


# -- internals -------------------------------------------------------------


def _entities_from_mentions(
    paper: Paper, dictionary: EntityDictionary, mentions: list[EntityMention]
) -> list[BiomedicalEntity]:
    first: dict[str, EntityMention] = {}
    surfaces: dict[str, list[str]] = {}
    order: list[str] = []
    for m in mentions:
        if m.entity_id not in first:
            first[m.entity_id] = m
            surfaces[m.entity_id] = []
            order.append(m.entity_id)
        if m.surface not in surfaces[m.entity_id]:
            surfaces[m.entity_id].append(m.surface)

    out: list[BiomedicalEntity] = []
    for entity_id in order:
        m = first[entity_id]
        canonical = dictionary.entities.get(entity_id)
        out.append(
            BiomedicalEntity(
                entity_id=entity_id,
                name=m.canonical_name,
                entity_type=EntityType(m.entity_type),
                synonyms=sorted(surfaces[entity_id]),
                db_xrefs=dict(canonical.db_xrefs) if canonical else {},
                confidence=1.0,
                provenance=Provenance(
                    paper_id=paper.paper_id,
                    source_snippet=m.surface,
                    char_span=(m.start, m.end),
                    extraction_method=ENTITY_METHOD,
                    data_source=paper.data_source,
                    epistemic_level=EpistemicLevel.observed_metadata,
                ),
            )
        )
    return out


def _claims_from_mentions(paper: Paper, mentions: list[EntityMention]) -> list[Claim]:
    claims: list[Claim] = []
    n = 0
    for start, end in sentence_spans(paper.abstract):
        in_sentence = [m for m in mentions if m.start >= start and m.end <= end]
        if not in_sentence:
            continue
        n += 1
        entity_ids: list[str] = []
        for m in in_sentence:
            if m.entity_id not in entity_ids:
                entity_ids.append(m.entity_id)

        sentence = paper.abstract[start:end]
        relation = _extract_relation(sentence, start, in_sentence)
        subject = obj = rel = None
        method = "rule:claim-sentence"
        if relation is not None:
            subject, rel, obj, method = relation

        confidence = _claim_confidence(
            num_entities=len(entity_ids), has_triple=relation is not None, text=sentence
        )
        claims.append(
            Claim(
                claim_id=f"{paper.paper_id}-c{n}",
                claim_text=sentence,
                paper_id=paper.paper_id,
                subject=subject,
                relation=rel,
                object=obj,
                entity_ids=entity_ids,
                confidence=confidence,
                provenance=Provenance(
                    paper_id=paper.paper_id,
                    source_snippet=sentence,
                    char_span=(start, end),
                    extraction_method=method,
                    data_source=paper.data_source,
                    epistemic_level=EpistemicLevel.extracted_claim,
                ),
            )
        )
    return claims


def _extract_relation(
    sentence: str, base: int, mentions: list[EntityMention]
) -> tuple[str, str, str, str] | None:
    """Fill a naive subject–relation–object triple from a relation cue, or return None.

    Picks the leftmost cue in the sentence that has a recognized entity on each side
    (nearest before = subject, nearest after = object). Directed verbs yield their
    normalized relation (``rule:svo``); association cues yield ``associated_with``
    (``rule:assoc``). Subject and object must be different entities.
    """
    low = sentence.lower()
    ordered = sorted(mentions, key=lambda m: m.start)
    candidates: list[tuple[int, str, str, str, str]] = []

    def add_candidates(cue: str, relation: str, method: str) -> None:
        pos = low.find(cue)
        while pos != -1:
            cue_start = base + pos
            cue_end = cue_start + len(cue)
            subject = None
            for m in ordered:
                if m.end <= cue_start:
                    subject = m
                else:
                    break
            obj = next((m for m in ordered if m.start >= cue_end), None)
            if subject and obj and subject.entity_id != obj.entity_id:
                candidates.append(
                    (pos, relation, subject.canonical_name, obj.canonical_name, method)
                )
            pos = low.find(cue, pos + 1)

    for cue, relation in DIRECTED_CUES:
        add_candidates(cue, relation, "rule:svo")
    for cue in ASSOCIATION_CUES:
        add_candidates(cue, "associated_with", "rule:assoc")

    if not candidates:
        return None
    # Leftmost cue wins; ties broken by relation name for determinism.
    candidates.sort(key=lambda c: (c[0], c[1]))
    _, relation, subject_name, object_name, method = candidates[0]
    return subject_name, relation, object_name, method


def _claim_confidence(*, num_entities: int, has_triple: bool, text: str) -> float:
    """A transparent additive salience score in [0, 1] (not a probability).

    * 0.35 base — the sentence is grounded in at least one recognized entity;
    * +0.25 — it mentions two or more distinct entities (relational potential);
    * +0.30 — a subject–relation–object triple was extracted;
    * +0.10 — it contains a reporting/assertion cue (``observed``, ``found``, …).

    The components are independent and named so a reader can reconstruct any score.
    """
    low = text.lower()
    confidence = 0.35
    if num_entities >= 2:
        confidence += 0.25
    if has_triple:
        confidence += 0.30
    if any(cue in low for cue in REPORTING_CUES):
        confidence += 0.10
    return min(confidence, 1.0)


# -- database-backed convenience -------------------------------------------


def load_dictionary(db_path: str | Path) -> EntityDictionary:
    """Build the entity dictionary from an ingested database's records."""
    from bioscientist_os.storage import SQLiteStore

    with SQLiteStore(db_path) as store:
        if not store.is_initialized():
            raise ValueError(f"{db_path} is not a bioscientist-os database (no ingested tables)")
        return build_dictionary(list(store.iter_database_records()))


def load_extraction(db_path: str | Path) -> ExtractionReport:
    """Open an ingested database, build the dictionary, and extract the whole corpus.

    Raises :class:`ValueError` if the file is not a bioscientist-os database (no
    ingested tables), mirroring the guard used by ``biosci stats`` / ``search``.
    """
    from bioscientist_os.storage import SQLiteStore

    with SQLiteStore(db_path) as store:
        if not store.is_initialized():
            raise ValueError(f"{db_path} is not a bioscientist-os database (no ingested tables)")
        dictionary = build_dictionary(list(store.iter_database_records()))
        papers = list(store.iter_papers())
    return extract_corpus(papers, dictionary)


__all__ = [
    "ENTITY_METHOD",
    "DIRECTED_CUES",
    "ASSOCIATION_CUES",
    "REPORTING_CUES",
    "extract_entities",
    "extract_claims",
    "extract_paper",
    "extract_corpus",
    "load_dictionary",
    "load_extraction",
]
