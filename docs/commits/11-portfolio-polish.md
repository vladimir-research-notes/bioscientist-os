# Commit note: Milestone 11 — Polish website, results, and portfolio documentation

## Intent
Reconcile the README, the docs, and the multi-page website with what the repository
actually contains now that the full pipeline (M0–10) has landed: state what exists,
what is prototype-only, the measured results (with denominators and Wilson intervals),
what the system explicitly does **not** claim, who it is for, and how it could become a
research paper — without describing any unimplemented feature as done. Documentation and
website only; no pipeline behaviour changes.

## What the commit contains
- `README.md`: working-prototype status block (M0–11, full CLI surface) replacing the
  stale "Milestones 0–8"; corrected end-to-end run block (memo no longer "planned",
  plus the optional `llm` step); new **measured-results table**, **"what this does *not*
  claim"** section, **who-it's-for** section, and **"from prototype to a research
  paper"** section; expanded docs list; `llm` added to the layout line.
- `site/style.css`: new `.badge-prototype` style.
- `site/*.html`: retired the amber "Scaffold" page-head badge on the 8 meta pages →
  "Prototype". `index.html` (status M0–11, results snapshot, non-claims box);
  `architecture.html` (corrected to M0–11 / 274 tests, added the `llm/` subpackage row);
  `reproducibility.html` (all 8 pipeline scripts + determinism note); `results.html`
  (headline self-eval table; "Pending tables" → "Per-milestone results"; reconciled
  status rows); `milestones.html` (M11 → Done; new "Milestone 11 — delivered" section;
  historical per-milestone validation snapshots preserved); `roadmap.html` (expanded
  paper-path content + non-goals block); every feature page's current test total
  normalized to **274** (per-feature counts kept).
- `docs/RESULTS.md`: M11 row added to the build/test status table (docs/website only;
  suite unchanged).
- `docs/milestones/11-portfolio-polish.md`, `docs/commits/11-portfolio-polish.md`,
  `docs/review_notes/11-portfolio-polish-human-review.md`.

## Why it is safe to commit
No source, fixtures, or gold labels changed, so the offline suite is unchanged at
**274 passed, 1 skipped** and every measured number is identical to Milestone 10's
(restated, not recomputed). CPU-only, offline, no network/paid API/GPU. The website is
plain committed HTML + one stylesheet, viewable over `file://` with no build step; HTML
tag balance was checked across all 18 pages. No new claim is made — the change makes the
existing, honestly-scoped claims easier to find and audit, and nothing unimplemented is
described as done (M12's `docs/PAPER_PATH.md` and the final quality-gate verification are
left for Milestone 12). No secrets, caches, virtualenvs, weights, or large data are
staged; the working tree is clean after commit.
