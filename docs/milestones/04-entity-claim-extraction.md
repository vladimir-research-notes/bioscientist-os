# Milestone 4 — Entity and claim extraction baseline

## Summary

The ingested corpus now yields recognized **entities** and extracted **claims**
through a transparent, **non-LLM** baseline, entirely on CPU and offline.
`bioscientist-os` gains a fixture-built `EntityDictionary` with longest-match
recognition, span-exact tokenization and sentence splitting, rule-based
claim-sentence extraction with optional subject–verb–object relation templates, a
transparent additive confidence on every claim, the `biosci extract` CLI command,
and a `scripts/03_extract_claims.py` wrapper that writes CSV/JSON artifacts.

Every result is auditable: recognized entities are *observed metadata*
(`dict:exact`), extracted claims are *extracted claims* (`rule:claim-sentence` /
`rule:svo` / `rule:assoc`), and each carries the paper, the **exact** source
snippet, its character span, the named method, a confidence, and the data source. A
relation triple, when filled, is part of the claim — it is **not** an inferred
relation (combining records to infer relations is Milestone 5). No
support/conflict judgement and no biological assertion is made here.

## Deliverables

- **`src/bioscientist_os/evidence/text.py`** — span-aware helpers sharing the search
  tokenizer's conventions: `token_spans` (lower-cased tokens with `[start, end)`
  offsets so `text[start:end]` is the verbatim surface), `surface_key` (tokenize a
  dictionary surface into its match key), and `sentence_spans` (a naive but
  span-exact sentence splitter; no abbreviation handling, documented).
- **`src/bioscientist_os/evidence/dictionary.py`** — `DictionaryEntity`,
  `EntityDictionary` (longest-match `find`), and `build_dictionary`:
  - UniProt protein records → one entity each (surfaces: gene, common name, protein
    name, accession; `db_xrefs` = real UniProt accession + HGNC symbol);
  - Open Targets associations → extra surface synonyms on the named protein (e.g.
    `IL-6` for IL6, a form UniProt does not list but abstracts use);
  - a short, fully-listed curated seed (`CURATED_TERMS`, 16 process/phenotype/
    chemical terms) for concepts with no protein record.
  - On the committed fixtures: **26** entities (10 protein, 9 process, 6 other, 1
    chemical) over **61** surface forms. Surface-key collisions resolve to the
    first-inserted entity (UniProt anchors win over the curated seed).
- **`src/bioscientist_os/evidence/extract.py`** — the extractors:
  - `extract_entities` groups recognized mentions into one `BiomedicalEntity` per
    distinct entity, with the verbatim first-mention span, observed surface forms as
    `synonyms`, `db_xrefs`, `confidence = 1.0`, and `extraction_method = "dict:exact"`
    at level *observed metadata*;
  - `extract_claims` emits a `Claim` for every abstract sentence that mentions ≥1
    recognized entity (high-precision, limited-recall, documented), with the verbatim
    sentence span and `entity_ids`, at level *extracted claim*;
  - relation templates: proximity-based, syntax-free SVO — the nearest recognized
    entity before/after a relation cue becomes subject/object (`rule:svo` for
    directed verbs, `rule:assoc` for association cues);
  - `extract_corpus`, plus `load_dictionary(db)` / `load_extraction(db)` that build
    the dictionary from a database's records and extract the whole corpus.
- **`src/bioscientist_os/evidence/model.py`** — frozen containers (`EntityMention`,
  `PaperExtraction`, `ExtractionReport`) with `to_dict()` and flat CSV-row views.
- **CLI** (`cli.py`): `biosci extract --db <path> [--paper ID] [--min-confidence X]
  [--json]`; `info` status updated to Milestones 0–4.
- **`scripts/03_extract_claims.py`** — install-free wrapper: prints a summary and
  sample triples, writes `results/processed/claims.json`, `claims.csv`,
  `entities.csv` (gitignored, regenerable, deterministic).
- **Tests**: `tests/test_extract.py` (24) — 119 total, all offline.

## Design notes / decisions

- **Dictionary, not a model.** Recognition is a printable dictionary + longest
  match. A reviewer can read every surface form and verify every span against the
  source. The dictionary is built from the fixtures (UniProt anchors + Open Targets
  surface synonyms) plus a small, explicit curated seed for theme concepts with no
  protein record.
- **Abstract-only, span-exact.** Extraction reads the abstract so every span indexes
  one well-defined field and `abstract[start:end]` reproduces the stored snippet
  exactly (a tested invariant: **0 of 105** round-trips fail). Title-only entities
  are not recognized — a documented limitation, not a hidden one.
- **Entity-grounded claims.** A sentence is a claim only if it mentions a recognized
  entity. This favors precision over recall and keeps every claim tied to known
  entities; the recall cost is stated, not hidden.
- **Naive SVO, named for what it is.** Relation templates pick the nearest
  recognized entity on each side of a relation cue. They miss paraphrase and complex
  syntax by construction; the triple is part of the *extracted claim* (read from the
  sentence), never an inferred relation.
- **Transparent confidence.** Confidence is an additive salience score in [0, 1],
  not a probability: 0.35 base (entity-grounded), +0.25 (≥2 entities), +0.30 (a
  triple), +0.10 (a reporting cue). The components are named so any score
  reconstructs. Exact dictionary matches have confidence 1.0 (no disambiguation).
- **Epistemic discipline preserved.** Entities = observed metadata; claims =
  extracted claims; no support/conflict or biological verdict is produced (that is
  M5 and is a heuristic *textual* signal even then — see `docs/SAFETY.md`).

## Validation

```bash
python3 -m pytest -q                                  # 119 passed (offline)
python3 scripts/01_ingest_fixtures.py --reset         # -> results/raw/bioscientist.db
python3 scripts/03_extract_claims.py                  # dictionary + extraction summary + artifacts
biosci extract --db results/raw/bioscientist.db --paper biosci-paper-006
biosci extract --db results/raw/bioscientist.db --json | head
ruff check src/bioscientist_os/evidence src/bioscientist_os/cli.py \
           scripts/03_extract_claims.py tests/test_extract.py        # clean
```

Measured on the committed fixtures (18 abstracts): **26** dictionary entities / 61
surfaces → **63** entity mentions, **42** claims, **15** with a relation triple; all
**105** entity+claim spans round-trip against the source abstract. Claim-confidence
distribution: 0.35×9, 0.45×5, 0.60×8, 0.70×5, 0.90×11, 1.00×4. The designed conflict
pair surfaces: paper-006 `autophagy --promotes--> cellular senescence` vs paper-007
`autophagy --restrains--> cellular senescence`. Extraction is deterministic
(`claims.json` byte-identical across runs). These are extraction *counts and
behavior*, not quality metrics; precision/recall against gold labels (with
denominators and Wilson intervals) is Milestone 8. All offline; no network, no paid
API, no GPU.

## Status

**Complete.** Next: **Milestone 5 — Evidence table builder** (group extracted
claims by a research question into an evidence table with `support_conflict_unknown`,
`database_links`, and full per-cell provenance; assert provenance coverage and
column completeness).
