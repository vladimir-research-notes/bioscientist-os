# Commit note: Milestone 5 — Add evidence table builder

## Intent
Assemble the project's headline artifact — an evidence table grouped by a research
question — from the M4 extraction, on CPU and offline, with auditability first.
Each row keeps the four epistemic levels separate and carries full per-cell
provenance, so a scientist can inspect the chain (claim → entities → database links
→ support/conflict/unknown) rather than trust a summary. The support label is a
heuristic *textual* signal, never a biological or clinical verdict.

## What the commit contains
- `src/bioscientist_os/evidence/table.py`: the builder.
  - `classify_support` — transparent cue heuristic (negation → conflict, asserted
    relationship → support, weak contrast → conflict, else unknown), reusing the M4
    `ASSOCIATION_CUES` + directed-verb vocabulary and returning the firing cue.
  - `resolve_question_entities` / `resolve_question` — recognize a question's
    entities and map the CLI input to a stored or synthesized `ResearchQuestion`.
  - `build_evidence_report` — relevance filter (claim mentions ≥1 question entity),
    per-row support label, database links (UniProt/HGNC xrefs + Open Targets
    associations), deterministic `(-confidence, paper_id, claim_id)` sort, optional
    `min_confidence` / `limit`; returns `EvidenceReport`.
  - `load_evidence` — database-backed convenience with the not-a-database guard.
  - `EvidenceReport` — frozen container over the typed `EvidenceTable` with support
    counts, provenance coverage, and CSV/JSON views (`EVIDENCE_COLUMNS`).
- `src/bioscientist_os/evidence/__init__.py`: re-export the M5 surface.
- `src/bioscientist_os/cli.py`: `biosci evidence` command (`--question`,
  `--question-id`, `--out`, `--min-confidence`, `--limit`, `--json`); `info` updated
  to Milestones 0–5.
- `scripts/04_build_evidence_table.py`: install-free wrapper; writes
  `results/processed/evidence_<question_id>.csv`, `evidence_table.csv`, and
  `evidence_tables.json` (gitignored, regenerable, deterministic).
- `tests/test_evidence_table.py` (24): the support heuristic (support/conflict/
  unknown, negation-wins, contrast-vs-triple), question resolution, the relevance
  filter, span round-trips against the abstract, 100% provenance coverage, the
  epistemic-level anchor, database-link assembly, determinism, column completeness,
  and the CLI (text/JSON/CSV-out/error paths). 143 total, all offline.
- Docs + website: milestone/commit/review notes; `RESULTS.md`, `METHODOLOGY.md`,
  `REPRODUCIBILITY.md`, `DATA_MODEL.md`; `site/` (`evidence` → Done with the row
  recipe + columns + metrics, and `milestones`/`index`/`architecture`/`results`/
  `extraction` updated to M5 → Done and 143 tests).

## Why it is safe to commit
CPU-only, offline, no network or paid API, no GPU. The only generated artifacts are
under `results/` (the SQLite database and the evidence-table CSV/JSON), which is
gitignored and regenerable from the committed fixtures; they are **not** staged. No
secrets, caches, virtualenvs, weights, or large data are staged. The evidence table
produces no clinical content and no biological verdict: the snippet is an extracted
claim, entity names are observed metadata, database links are inferred relations,
and support/conflict/unknown is an explicitly-labeled heuristic textual signal.
Every row carries its provenance and provenance coverage is 100% by construction
(and tested). Working tree is clean after commit.
