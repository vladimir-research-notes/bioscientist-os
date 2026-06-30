# Commit note: Milestone 4 — Add rule-based entity and claim extraction baseline

## Intent
Turn the ingested corpus into recognized entities and extracted claims with a
transparent, **non-LLM** baseline, on CPU and offline, with auditability as the
first-class output: a reviewer can print the whole dictionary and verify every
recognized span and every claim sentence against the source abstract. Each result
carries its provenance (paper, exact snippet span, named method, confidence, data
source). No support/conflict judgement and no biological assertion is made here —
that is Milestone 5, and even then it is a heuristic textual signal.

## What the commit contains
- `src/bioscientist_os/evidence/text.py`: span-aware `token_spans` (offsets so
  `text[start:end]` is the verbatim surface), `surface_key`, and a naive but
  span-exact `sentence_spans`. Shares the search tokenizer's conventions.
- `src/bioscientist_os/evidence/dictionary.py`: `EntityDictionary` (longest-match
  recognition) + `build_dictionary` — UniProt protein records (real
  accession/HGNC `db_xrefs`), Open Targets `target_symbol` surface synonyms, and a
  short, fully-listed curated process/phenotype seed (`CURATED_TERMS`). 26 entities
  / 61 surfaces on the fixtures.
- `src/bioscientist_os/evidence/extract.py`: `extract_entities` (→ `BiomedicalEntity`,
  `dict:exact`, observed metadata), `extract_claims` (entity-grounded abstract
  sentences → `Claim`, extracted claim), proximity SVO/association relation templates
  (`rule:svo` / `rule:assoc`), additive transparent confidence, `extract_corpus`, and
  `load_dictionary` / `load_extraction` database loaders.
- `src/bioscientist_os/evidence/model.py`: frozen `EntityMention`, `PaperExtraction`,
  `ExtractionReport` with `to_dict()` and flat CSV-row views.
- `src/bioscientist_os/cli.py`: `biosci extract --db <path> [--paper ID]
  [--min-confidence X] [--json]`; `info` updated to Milestones 0–4.
- `scripts/03_extract_claims.py`: install-free wrapper; prints a summary and sample
  triples, writes `results/processed/claims.{json,csv}` and `entities.csv`
  (gitignored, regenerable, deterministic).
- `tests/test_extract.py` (24): text helpers, dictionary build, longest-match, span
  round-trips against the abstract, claim selection, relation templates, transparent
  confidence, determinism, and the CLI. 119 total, all offline.
- Docs + website: milestone/commit/review notes; `RESULTS.md`, `ARCHITECTURE.md`,
  `REPRODUCIBILITY.md`, `METHODOLOGY.md`, `DATA_MODEL.md`; `site/` (new
  `extraction.html`, nav link on every page, `milestones`/`index`/`architecture`/
  `results`/`evidence`/`search` updated to M4 → Done).

## Why it is safe to commit
CPU-only, offline, no network or paid API, no GPU. The only generated artifacts are
under `results/` (the SQLite database, `claims.{json,csv}`, `entities.csv`), which
is gitignored and regenerable from the committed fixtures; they are **not** staged.
No secrets, caches, virtualenvs, weights, or large data are staged. Extraction
produces no clinical content and no biological verdict; entities are observed
metadata, claims are extracted claims, and any relation triple is part of the claim
(read from the sentence), not an inferred relation. Every result carries its
provenance, and all spans round-trip against the source abstract. Working tree is
clean after commit.
