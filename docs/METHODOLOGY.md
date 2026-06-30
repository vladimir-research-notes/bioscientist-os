# Methodology

## TL;DR

`bioscientist-os` turns a small paper corpus into an **inspectable evidence
chain**: `paper -> extracted claim -> biological entities -> database links ->
support/conflict/uncertainty -> visual report`. Every step records provenance and
is produced by a *named, transparent method* (rule-based / lexical first), so a
scientist can audit rather than trust.

## Short explanation

The system is a pipeline of small, individually testable stages:

1. **Ingest** small fixture corpora and normalize fields (Milestone 2).
2. **Search / cluster** with lexical + TF-IDF baselines (Milestone 3).
3. **Extract** entities and claim sentences from abstracts with dictionaries and
   templates (Milestone 4, done).
4. **Link** claims to biological entities and database records via connectors
   (Milestone 5 assembles the links from fixtures; the connector layer is M6).
5. **Assemble** evidence tables tagged with support / conflict / unknown and full
   provenance (Milestone 5, done).
6. **Visualize** timeline, clusters, evidence matrix, and link graph (Milestone 7).
7. **Evaluate** against tiny gold labels with explicit denominators (Milestone 8).
8. **Report** a structured, non-clinical research memo (Milestone 9, done).

## Longer explanation

### Epistemic levels

Every output is labeled with one of four levels, and the labels are never
collapsed:

1. **Observed metadata** — title, authors, journal, year, IDs. Copied, not inferred.
2. **Extracted claim** — a sentence/relation pulled from text by a named method,
   with the exact source snippet recorded.
3. **Inferred relation** — an assertion produced by combining records (e.g. two
   claims sharing an entity), with the inference basis recorded.
4. **Unsupported hypothesis** — a suggestion (e.g. a "next experiment"),
   explicitly marked as *not* evidence.

### Provenance fields

Each claim / link / evidence cell records: `paper_id`, `source_snippet`
(span where available), `extraction_method` (the named method that produced it —
e.g. `dict:exact` for a recognized entity, `rule:svo` / `rule:assoc` /
`rule:claim-sentence` for a claim), `confidence`, and `data_source`
(`fixture` / `cache` / `live`).
**Provenance coverage** (the fraction of cells with complete provenance) is itself
an evaluated metric (Milestone 8).

### Evidence-table assembly (Milestone 5)

An evidence table is built for one research question. The question's text and its
`entities_of_interest` are run through the same fixture entity dictionary, so a
curated fixture question or a free-text question both resolve to recognized entity
ids (terms with no fixture record are reported as *unmatched*, never silently
dropped). A claim is kept iff it mentions ≥1 of those entities — a transparent,
grounded relevance filter. Each kept claim becomes one `EvidenceItem` row that
keeps the four levels separate:

- the **source snippet** (the claim sentence, with its exact span) is an *extracted
  claim* — the row's provenance is anchored here, so provenance coverage is 100% by
  construction;
- **entity names** are *observed metadata* (recognized mentions);
- **database links** — UniProt/HGNC cross-references for the claim's entities plus
  any Open Targets-style association records naming their gene — are *inferred
  relations*, labeled as such (the human-readable association descriptor is written
  into the row's `notes`);
- **support / conflict / unknown** is a heuristic *textual* signal
  (`rule:support-cues`), not a level of the chain and never a biological verdict.

The support heuristic is a small, fully-listed cue rule, in precedence order: a
strong **negation** cue (e.g. *not associated*, *no significant*) → `conflict`
(it overrides any co-occurring relation verb); otherwise an **asserted
relationship** — a relation triple from M4, or an affirmative cue reusing the M4
association/directed-verb vocabulary — → `support`; a weak **contrast** cue
(*however*, *without*) → `conflict` only when nothing affirms a relationship;
otherwise → `unknown` (the honest default). The cue that fired is recorded in
`notes`, so the label can always be reconstructed from the sentence. Rows are
sorted by `(-confidence, paper_id, claim_id)` for a deterministic, strongest-first
ordering.

### Why transparent baselines first

Rule-based and lexical methods are auditable: a reviewer can read the dictionary,
the template, and the matched span. An optional LLM adapter (Milestone 10) is
disabled by default and, when used, must still emit the same provenance fields so
its outputs remain inspectable rather than opaque.

## Exact commands

These are populated as milestones land; see `docs/REPRODUCIBILITY.md` for the
current runnable subset. Target end-to-end flow:

```bash
python3 scripts/01_ingest_fixtures.py
python3 scripts/02_build_index.py
python3 scripts/03_extract_claims.py
python3 scripts/04_build_evidence_table.py
python3 scripts/05_generate_visualizations.py
python3 scripts/06_run_eval.py
```

## Limitations

- The corpus is tiny and partly synthetic; metrics are illustrative, not
  population estimates.
- Rule-based extraction has limited recall and will miss paraphrase and complex
  syntax. This is by design (auditability over coverage) and is reported, not hidden.
- "Support / conflict" labels are heuristic signals about *textual* agreement, not
  adjudications of biological truth. The label reads one sentence's phrasing; it
  does not detect when two papers conflict only in *direction* (both directional
  claims read as `support` per row). Cross-paper conflict detection is future work.
