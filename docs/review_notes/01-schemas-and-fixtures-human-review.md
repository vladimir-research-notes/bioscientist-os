# Human review: Milestone 1 — Data schemas and small fixtures

## TL;DR
`bioscientist-os` now has its typed data model: nine `pydantic` v2 schemas with a
shared `Provenance` submodel and four controlled vocabularies, plus a thin
fixture loader and a small, clearly-labeled corpus (18 papers, 10 proteins, 9
associations, 3 questions) on the senescence / longevity / autophagy theme.
Everything loads and validates offline; 50 tests pass. No storage or pipeline
logic yet — that is Milestone 2.

## What changed
- Added `src/bioscientist_os/schemas.py`: `Author`, `Paper`, `DatabaseRecord`,
  `BiomedicalEntity`, `Claim`, `EvidenceItem`, `ResearchQuestion`,
  `EvidenceTable`, `WorkbenchRun`; a `Provenance` submodel; and the `DataSource`,
  `EpistemicLevel`, `EntityType`, `SupportLabel` enums.
- Added `src/bioscientist_os/fixtures.py`: parse-and-validate loader for the
  committed fixtures; stamps `data_source = fixture`; raises `FixtureError` with
  file + index on bad input. No DB, no normalization.
- Added fixtures: `data/fixtures/papers/papers.json` (18),
  `data/fixtures/uniprot/proteins.json` (10),
  `data/fixtures/opentargets/associations.json` (9), `data/fixtures/questions.json` (3).
  Updated `data/fixtures/README.md` with the exact synthetic/real labeling.
- Added `tests/test_schemas.py` and `tests/test_fixtures.py` (30 new tests).
- Updated docs (`DATA_MODEL.md`, `RESULTS.md`) and website
  (`data-model.html`, `milestones.html`, `index.html`, `architecture.html`).

## Commands run
- `python3 -m pytest -q` → **50 passed** (offline).
- `python3 -c "from bioscientist_os.fixtures import load_all; print(load_all().summary())"`
  → `{'papers': 18, 'proteins': 10, 'associations': 9, 'questions': 3}`.
- `ruff check` on the four new files → clean.

## Test status
50 passed (20 prior + 30 new). The new tests assert schema JSON round-trips, the
enforced validation/provenance rules (required provenance, confidence bounds,
char-span ordering, claim/paper consistency, `extra="forbid"`), fixture loading
and labeling, determinism, and loud failure on malformed fixtures.

## Known limitations
- The committed corpus is **tiny and partly synthetic by design**. All 18 paper
  abstracts are fabricated; all 9 association scores are fabricated. They
  illustrate pipeline/provenance behavior, not biology.
- Entity typing is coarse and `db_xrefs` is a free-form mapping; there is no
  ontology and no validation that an xref id is well-formed for its namespace.
- The loader is parse-only. Ingestion into SQLite, normalization, and duplicate
  handling are Milestone 2, so re-running the loader just re-parses files.
- Protein `function` text is condensed/paraphrased; minor wording may differ from
  the canonical UniProt entry. The accession + gene symbol are the load-bearing
  fields and are modeled on real records.

## Possible misleading artifacts
- **`synthetic: false` on protein records does not mean "verified".** It means
  the record is modeled on a real public UniProt entry (accession, name, gene,
  organism). The function text is paraphrased and the cross-references are limited
  to the gene symbol; do not treat these as a curated database extract.
- **Real gene symbols + fabricated numbers.** The association records use real
  gene symbols (e.g. `IL6`, `FOXO3`) but every `association_score` is invented and
  every `disease_id` is a `SYN-DIS-*` placeholder. A reader could mistake the
  scores for Open Targets values — they are not.
- **DOIs look real but are not.** Paper DOIs use the reserved `10.0000/` test
  prefix and will not resolve; the papers are not real publications.
- **"Done" means the schema/fixtures exist**, not that any claim has been
  extracted or any evidence assembled. No entities, claims, or evidence rows are
  produced at this milestone; those schemas are defined but unpopulated.
- The deliberate 006↔007 autophagy support/conflict tension is **authored**, not
  discovered — it exists so later milestones have material to test against.

## Human feedback
<!-- Human will fill this later. -->
