# Human review: Milestone 5 — Evidence table builder

## TL;DR
Added the evidence-table builder: for a research question, recognize its entities
(M4 dictionary), keep extracted claims that mention one of them, and turn each into
one `EvidenceItem` row with full per-cell provenance, database links (UniProt/HGNC
xrefs + Open Targets associations), and a heuristic support/conflict/unknown label.
The four epistemic levels stay separate within a row; provenance coverage is 100%
by construction. New `biosci evidence` command and `scripts/04_build_evidence_table.py`.
24 new tests (143 total), all offline. The support label is a heuristic **textual**
signal, never a biological or clinical verdict.

## What changed
- `src/bioscientist_os/evidence/table.py`: `classify_support`,
  `resolve_question_entities`, `resolve_question`, `build_evidence_report`,
  `load_evidence`, and the `EvidenceReport` container (CSV/JSON views); re-exported
  from `evidence/__init__.py`.
- `src/bioscientist_os/cli.py`: `evidence` subcommand (`--question`,
  `--question-id`, `--out`, `--min-confidence`, `--limit`, `--json`); `info` status
  line updated to Milestones 0–5.
- `scripts/04_build_evidence_table.py`: install-free wrapper; writes
  `results/processed/evidence_<question_id>.csv`, `evidence_table.csv`, and
  `evidence_tables.json` (gitignored).
- `tests/test_evidence_table.py`: support heuristic, question resolution, relevance
  filter, span round-trips, provenance coverage, database links, determinism,
  column completeness, CLI.
- Docs + website: this note, the milestone note, the commit note; `RESULTS.md`,
  `METHODOLOGY.md`, `REPRODUCIBILITY.md`, `DATA_MODEL.md`; and `site/`
  (`evidence` → Done, and `milestones`/`index`/`architecture`/`results`/`extraction`
  updated).

## Commands run
- `python3 -m pytest -q` → 143 passed (offline).
- `ruff check` on the new/changed files → clean.
- `python3 scripts/01_ingest_fixtures.py`, then
  `python3 scripts/04_build_evidence_table.py` (and a second run to confirm
  `evidence_tables.json` is byte-identical).
- `biosci evidence --db ... --question "What evidence links cellular senescence to
  chronic inflammation?" --limit 3`,
  `biosci evidence --db ... --question-id rq-autophagy-senescence --json`.

## Test status
143 passed, 0 failed, offline. 24 of the tests are new (`tests/test_evidence_table.py`).

## Known limitations
- The support/conflict/unknown label is a **textual** cue heuristic, not a biological
  verdict. It reads one sentence's phrasing.
- It does **not** detect cross-paper *directional* conflict: paper-006 (autophagy
  promotes senescence) and paper-007 (autophagy restrains senescence) both read as
  `support`, because each sentence asserts a relationship. Cross-paper conflict
  detection is future work.
- The negation/contrast cue lists are short, hand-written substring matches with no
  syntax; they will mislabel sentences whose negation scope or double negatives they
  cannot parse (e.g. "not metabolically silent").
- Relevance is membership-based (a claim must mention a recognized question entity),
  so broad entities (e.g. "senescence") pull many rows and an entity absent from the
  dictionary contributes nothing (reported as unmatched).
- Database links and association scores come from the partly-synthetic fixtures;
  Open Targets-style scores are fabricated for illustration.
- Counts are on a tiny, partly-synthetic corpus and describe builder *behavior*, not
  quality; support-label precision/recall is Milestone 8.

## Possible misleading artifacts
- A `support` label can look like an endorsement of the research question's
  hypothesis; it only means the sentence's phrasing asserts *a* relationship. A
  `conflict` label likewise only flags negation/contrast phrasing.
- `confidence` is carried through from the M4 claim salience heuristic in [0, 1],
  **not** a probability of correctness.
- `database_links` mixes entity cross-references (e.g. `UniProt:P05231`) with
  association record ids (e.g. `OpenTargets:OTAF-0002`); the latter are inferred
  relations from combining records, spelled out in `notes`.
- `evidence_*.csv` / `evidence_tables.json` under `results/processed/` are
  regenerable inspection artifacts, not committed and not a source of truth.
- Entity names in rows are canonical (e.g. "Serine/threonine-protein kinase mTOR"),
  not the surface text the abstract used.

## Human feedback
<!-- Human will fill this later. -->
