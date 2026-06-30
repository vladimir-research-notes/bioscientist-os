# Human review: Milestone 11 — Website, final report, and portfolio polish

## TL;DR
A docs/website-only pass that brings the README, docs, and the multi-page website into
line with the actual repository state (full pipeline M0–10 landed). No pipeline code
changed; the offline suite is unchanged at **274 passed, 1 skipped**. The work is
honesty/findability: measured results with denominators, an explicit non-claims list,
a who-it's-for section, and a prototype→paper narrative — nothing unimplemented is
described as done.

## What changed
- `README.md`: rewrote the stale "Milestones 0–8" status block to a working-prototype
  framing (M0–11, full CLI); fixed the end-to-end run block (memo was still marked
  "planned"); added a measured-results table, a "what this does *not* claim" section,
  a who-it's-for section, and a "from prototype to a research paper" section; updated
  the docs list and the layout line.
- `site/`: added a `.badge-prototype` style and retired the amber "Scaffold" page-head
  badge on the 8 meta pages; updated `index.html` (status M0–11 + results snapshot +
  non-claims box), `architecture.html` (corrected from "M0–9 / 243 tests / next: M10"
  to M0–11 / 274 and added the `llm/` row), `reproducibility.html` (all 8 pipeline
  scripts), `results.html` (headline self-eval table; renamed "Pending tables"),
  `milestones.html` (M11 → Done + a "Milestone 11 — delivered" section),
  `roadmap.html` (expanded paper-path content); normalized every feature page's
  current test total to 274 (per-feature counts preserved).
- `docs/RESULTS.md`: added the M11 status row.

## Commands run
```bash
python3 -m pytest -q          # 274 passed, 1 skipped (offline)
# HTML tag-balance check across all 18 site pages (section/table/tr) — balanced
# grep sweeps for stale milestone/test-count markers — none outside intended history
```

## Test status
274 passed, 1 skipped (the matplotlib PNG-rendering test) — unchanged from Milestone 10,
since this milestone adds no code.

## Known limitations
- This milestone changes documentation/website only; it adds no measured pipeline
  capability and makes no new empirical claim.
- The per-milestone "Validation: … N passed" notes on `milestones.html` are left at
  their as-of-milestone totals on purpose (a build log, not current status).
- `docs/PAPER_PATH.md` and the final reproduction/quality-gate verification are
  Milestone 12 and are intentionally not done here.

## Possible misleading artifacts
- The polished pages restate measured numbers from the committed `eval_report.json`;
  they are pipeline-behaviour metrics on a tiny, partly-synthetic corpus, not
  population performance or biological truth (the pages say so, but a skimmer may
  miss it).
- The new "Prototype" badge is a deliberate honesty signal — it should not be read as
  "production-ready".

## Human feedback
<!-- Human will fill this later. -->
