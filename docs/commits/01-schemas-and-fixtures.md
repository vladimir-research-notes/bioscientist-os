# Commit note: Milestone 1 — Add typed schemas and labeled biomedical fixtures

## Intent
Give `bioscientist-os` its typed data model with provenance as a first-class
field, plus a small, clearly-labeled fixture corpus that loads and validates
offline — the foundation every later milestone (ingestion, search, extraction,
evidence tables) builds on. No storage or pipeline logic in this commit.

## What the commit contains
- `src/bioscientist_os/schemas.py`: nine pydantic v2 schemas (`Author`, `Paper`,
  `DatabaseRecord`, `BiomedicalEntity`, `Claim`, `EvidenceItem`,
  `ResearchQuestion`, `EvidenceTable`, `WorkbenchRun`), a shared `Provenance`
  submodel, and four controlled vocabularies (`DataSource`, `EpistemicLevel`,
  `EntityType`, `SupportLabel`). Derived objects require provenance;
  `extra="forbid"` and field constraints are enforced at construction.
- `src/bioscientist_os/fixtures.py`: a dependency-light loader that parses the
  committed fixtures into the schemas, stamps `data_source = fixture`, and fails
  loudly (`FixtureError` with file + index) on malformed input. Parse + validate
  only; storage/normalization are Milestone 2.
- `data/fixtures/`: `papers/papers.json` (18, synthetic), `uniprot/proteins.json`
  (10, modeled on real accessions), `opentargets/associations.json` (9, synthetic
  scores), `questions.json` (3). Updated `data/fixtures/README.md` with the exact
  synthetic-vs-real labeling.
- `tests/test_schemas.py` and `tests/test_fixtures.py` (30 new tests; 50 total,
  all offline).
- Docs + website: `docs/DATA_MODEL.md`, `docs/RESULTS.md`, and
  `site/{data-model,milestones,index,architecture}.html` updated to reflect the
  implemented state (M1 → Done).

## Why it is safe to commit
CPU-only, offline, no network or paid API. Fixtures are tiny, human-readable
JSON; paper abstracts and association scores are fabricated and flagged
`synthetic: true`, protein records are modeled on real public UniProt accessions
and flagged `synthetic: false`, and DOIs use the non-resolving `10.0000/` test
prefix. No secrets, caches, virtualenvs, weights, or large data are staged
(`.venv/`, `*.egg-info/`, `__pycache__/`, `results/` remain gitignored). Working
tree is clean after commit.
