# Milestone 1 — Data schemas and small fixtures

## Summary

Implemented the typed data model and a small, clearly-labeled fixture corpus.
`bioscientist-os` now has nine `pydantic` v2 schemas with provenance as a
first-class field, four controlled vocabularies, a thin fixture loader, and a
theme-focused (cellular senescence / longevity / autophagy) set of committed
fixtures that load and validate offline. No storage or pipeline logic yet — that
begins at Milestone 2.

## Deliverables

- **`src/bioscientist_os/schemas.py`** — the data model:
  - Schemas: `Author`, `Paper`, `DatabaseRecord`, `BiomedicalEntity`, `Claim`,
    `EvidenceItem`, `ResearchQuestion`, `EvidenceTable`, `WorkbenchRun`.
  - Shared `Provenance` submodel: `paper_id`, `source_snippet`, `char_span`,
    `extraction_method`, `data_source`, `epistemic_level`.
  - Controlled vocabularies: `DataSource` (`fixture`/`cache`/`live`),
    `EpistemicLevel` (the four levels), `EntityType` (coarse), `SupportLabel`
    (`support`/`conflict`/`unknown`).
- **`src/bioscientist_os/fixtures.py`** — a dependency-light loader that parses
  the committed JSON fixtures into the schemas, stamps `data_source = fixture`,
  and raises a readable `FixtureError` (file + record index) on malformed input.
  It does **no** storage, normalization, or deduplication (that is M2).
- **Fixtures** under `data/fixtures/` (theme: senescence / longevity / autophagy):
  - `papers/papers.json` — 18 paper records (`synthetic: true`; fabricated
    abstracts, `10.0000/` test-prefix DOIs).
  - `uniprot/proteins.json` — 10 UniProt-style protein records
    (`synthetic: false`; real accessions/gene symbols, condensed function text).
  - `opentargets/associations.json` — 9 association records (`synthetic: true`;
    real gene symbols, fabricated scores, `SYN-DIS-*` disease ids).
  - `questions.json` — 3 `ResearchQuestion` seeds.
  - Updated `data/fixtures/README.md` to document exactly what is synthetic.
- **Tests**: `tests/test_schemas.py` (round-trips + enforced validation/provenance
  rules) and `tests/test_fixtures.py` (loads-and-validates, labeling, determinism,
  loud failure on malformed input).
- Updated `docs/DATA_MODEL.md`, `docs/RESULTS.md`, and the website
  (`data-model.html`, `milestones.html`, `index.html`, `architecture.html`).

## Design notes / decisions

- **Two object families.** Observed-metadata objects (`Paper`, `DatabaseRecord`)
  carry `data_source` + `synthetic` directly and have no `Provenance`. Derived
  objects (`BiomedicalEntity`, `Claim`, `EvidenceItem`) carry a **required**
  `Provenance` block — the provenance discipline is enforced by the type system,
  not by convention.
- **`extra="forbid"` everywhere.** A typo'd or stray fixture key fails loudly
  rather than being silently dropped. The loader additionally refuses fixtures
  that hard-code a loader-stamped field (e.g. `data_source`).
- **Honest synthetic labeling.** Papers and association scores are fabricated and
  flagged `synthetic: true`; protein records are modeled on real public UniProt
  accessions and flagged `synthetic: false`, with paraphrased/condensed function
  text (no bulk redistribution). The corpus is built to exercise the pipeline,
  including a deliberate support/conflict tension between papers 006 and 007.
- **Loader, not ingestion.** The M1 loader parses + validates only; SQLite
  storage and normalization are deliberately deferred to M2 so milestone
  boundaries stay clean.
- **Enum/CLI single source of truth.** `EpistemicLevel` is asserted at import
  time to match `bioscientist_os.EPISTEMIC_LEVELS`, so the schemas and the CLI
  cannot describe different "four levels".

## Validation

```bash
python3 -m pytest -q                       # 50 passed (offline)
python3 -c "from bioscientist_os.fixtures import load_all; print(load_all().summary())"
# -> {'papers': 18, 'proteins': 10, 'associations': 9, 'questions': 3}
python3 -c "from bioscientist_os.schemas import Paper; print(Paper.model_json_schema()['title'])"
ruff check src/bioscientist_os/schemas.py src/bioscientist_os/fixtures.py \
           tests/test_schemas.py tests/test_fixtures.py     # clean
```

All offline; no network, no paid API, no GPU. No database file is produced.

## Status

**Complete.** Next: **Milestone 2 — Ingestion and local storage** (ingest the
fixtures into SQLite via a storage layer, with idempotent re-ingest and
deterministic database creation).
