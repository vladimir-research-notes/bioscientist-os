# Human review: Milestone 4 — Entity and claim extraction baseline

## TL;DR
Added a transparent, offline, **non-LLM** extraction baseline over the ingested
abstracts: a fixture-built dictionary entity recognizer (longest-match, with real
UniProt/HGNC `db_xrefs`), entity-grounded claim-sentence extraction, naive
proximity subject–verb–object relation templates, and a transparent additive
confidence — each result carrying paper, exact source-snippet span, method, and
data source. New `biosci extract` command and `scripts/03_extract_claims.py`. 24
new tests (119 total), all offline. No support/conflict or biological claim is made
here (that is Milestone 5).

## What changed
- `src/bioscientist_os/evidence/`: `text.py` (span-exact tokenizer + sentence
  splitter), `dictionary.py` (`EntityDictionary`, `build_dictionary`,
  `CURATED_TERMS`), `extract.py` (entity/claim/relation extraction + `load_extraction`),
  `model.py` (result containers + CSV views), and re-exporting `__init__.py`.
- `src/bioscientist_os/cli.py`: `extract` subcommand (`--paper`, `--min-confidence`,
  `--json`); `info` status line updated to Milestones 0–4.
- `scripts/03_extract_claims.py`: install-free wrapper; writes
  `results/processed/claims.{json,csv}` and `entities.csv` (gitignored).
- `tests/test_extract.py`: text helpers, dictionary build, longest-match,
  span round-trips, claim selection, relation templates, confidence, determinism, CLI.
- Docs + website: this note, the milestone note, the commit note; `RESULTS.md`,
  `ARCHITECTURE.md`, `REPRODUCIBILITY.md`, `METHODOLOGY.md`, `DATA_MODEL.md`; and
  `site/` (new `extraction.html`, nav link on every page, and
  `milestones`/`index`/`architecture`/`results`/`evidence`/`search` updated).

## Commands run
- `python3 -m pytest -q` → 119 passed (offline).
- `ruff check` on the new/changed files → clean.
- `python3 scripts/01_ingest_fixtures.py --reset`, then
  `python3 scripts/03_extract_claims.py` (and a second run to confirm
  `claims.json` is byte-identical).
- `biosci extract --db ... --paper biosci-paper-006`, `biosci extract --db ... --json`.

## Test status
119 passed, 0 failed, offline. 24 of the tests are new (`tests/test_extract.py`).

## Known limitations
- Extraction reads **abstracts only**; entities appearing only in a title are not
  recognized.
- Recognition is exact dictionary matching with no disambiguation, so entity
  confidence is always 1.0 and ambiguous short surfaces could in principle mismatch
  (none observed on this corpus).
- Claims are only emitted for sentences containing a recognized entity — deliberately
  high precision, limited recall (misses paraphrase and entity-free assertions).
- Relation templates are proximity-based and syntax-free: subject/object are the
  nearest recognized entities around a relation cue, and cues are matched as
  lower-cased substrings (no morphology). They will produce wrong or missing triples
  on complex sentences.
- The curated process/phenotype seed is a small, theme-specific, hand-written list;
  it is fully listed in `dictionary.py` but is not derived from a database.
- Counts are on a tiny, partly-synthetic corpus and describe extraction *behavior*,
  not quality; precision/recall is Milestone 8.

## Possible misleading artifacts
- A relation triple (e.g. `cellular senescence --increases--> Interleukin-6`) reads
  like an assertion but is a **proximity** read of one sentence, not a parsed or
  verified relation. Subject/object use the canonical entity name, which can look
  more authoritative than the verbatim text warrants.
- `confidence` is a transparent salience heuristic in [0, 1], **not** a probability
  of correctness; do not interpret 1.0 as "certainly true".
- `claims.csv` / `entities.csv` / `claims.json` under `results/processed/` are
  regenerable inspection artifacts, not committed and not a source of truth.
- Subject/object names like "Serine/threonine-protein kinase mTOR" are the UniProt
  canonical names, not the surface text the abstract used.

## Human feedback
<!-- Human will fill this later. -->
