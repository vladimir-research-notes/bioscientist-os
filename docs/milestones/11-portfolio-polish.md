# Milestone 11 — Website, final report, and portfolio polish

## Summary

A documentation- and website-only pass that reconciles the **README**, the **docs**,
and the **multi-page website** with what the repository actually contains now that the
full pipeline (Milestones 0–10) has landed. No pipeline code changed; the offline test
suite is unchanged at **274 passed, 1 skipped** (the figure-rendering test is skipped
without `matplotlib`). The goal is honesty and findability: state what exists, what is
prototype-only, the measured results (with denominators and Wilson intervals), what the
system explicitly does **not** claim, who it is for, and how it could become a research
paper — without describing any unimplemented feature as done.

## Deliverables

- **`README.md`** — the status block moved from a stale "Milestones 0–8 have landed"
  to a working-prototype framing covering M0–11 and the full CLI surface; the
  end-to-end run block (which still marked the memo "planned") now shows the complete
  pipeline including `memo` and the optional `llm`. New sections: a **measured-results
  table** (the M8 self-evaluation, every rate with its denominator and 95% Wilson
  interval); **"Who this is for, and what it is *not*"** (an explicit non-claims list);
  and **"From prototype to a research paper"**. The Documentation list gained
  `ARCHITECTURE.md`, `LLM_ADAPTER.md`, and `ROADMAP.md`, and the layout line now
  includes `llm`.
- **Website (`site/`)** — plain committed HTML + one stylesheet, no build step:
  - retired the misleading amber **`Scaffold`** page-head badge on the eight meta
    pages in favour of an honest **`Prototype`** badge (new `.badge-prototype` style);
  - **`index.html`**: status bumped to M0–11; added a **measured-results snapshot**
    table and a **"What it does *not* claim"** box;
  - **`architecture.html`**: corrected from the stale "Milestones 0–9 done / 243 tests
    / next: M10" to **M0–11 / 274 tests**, and added the `llm/` subpackage row;
  - **`reproducibility.html`**: the end-to-end run now lists **all eight** pipeline
    scripts (including the M9 memo and M10 LLM-demo wrappers), with the determinism
    note;
  - **`results.html`**: added a headline self-evaluation table; renamed the stale
    "Pending tables" to "Per-milestone results"; reconciled the status rows;
  - **`milestones.html`**: marked **M11 → Done** and added a "Milestone 11 — delivered"
    section (the per-milestone validation snapshots for M0–M10 are preserved as
    historical records);
  - **`roadmap.html`**: expanded the "From prototype to a research paper" content
    (multi-annotator gold labels, gold support/conflict annotations, ontology-grounded
    linking, a transparent-vs-LLM provenance-fidelity comparison, and a provenance
    user study) and an explicit non-goals block;
  - normalized every feature page's **current test total to 274** (each page keeps its
    own per-feature test count; the frozen running totals like "143 total" / "223
    total" were corrected).
- **`docs/RESULTS.md`** — added the M11 row to the build/test status table (docs/website
  only; suite unchanged).
- **Milestone bookkeeping** — this note, the human-review placeholder
  (`docs/review_notes/11-portfolio-polish-human-review.md`), and the commit note
  (`docs/commits/11-portfolio-polish.md`).

## Design notes / decisions

- **`Prototype`, not `Scaffold`, not `Done`.** The meta/overview pages previously
  carried an amber "Scaffold" badge from the pre-milestone setup; that now understates
  a working prototype, while "Done" (reserved for delivered feature pages) would
  overstate it. A distinct "Prototype" badge is the honest middle.
- **No new claims.** M11 makes the *existing*, honestly-scoped claims easier to find
  and audit; it adds no measured capability. Every number cited on the polished pages
  is copied from the already-committed `eval_report.json` / `docs/RESULTS.md`, not
  recomputed here.
- **Historical snapshots preserved.** The per-milestone "Validation: … N passed" notes
  on `milestones.html` are deliberately left at their as-of-milestone totals — they are
  a build log, not a current-status claim. Only the *current-status* rows on feature
  pages were normalized to 274.
- **Paper path stays a direction, not a promise.** The "how it could become a paper"
  content is framed as honest directions; the dedicated `docs/PAPER_PATH.md` and the
  final reproduction/quality-gate verification remain **Milestone 12** and are not
  pre-empted here.

## Validation

```bash
python3 -m pytest -q                 # 274 passed, 1 skipped (offline) — unchanged
# Website is static HTML; open over file:// — no build step:
#   site/index.html ... site/milestones.html
```

HTML tag balance (`<section>`, `<table>`, `<tr>`) was checked across all 18 site pages.
No stale milestone/test-count markers remain outside the intentional historical
references in `milestones.html`. No code, fixtures, or gold labels changed, so the
measured numbers are identical to Milestone 10's.

## Status

**Complete.** Next: **Milestone 12 — Final cleanup and quality gates** (tests, lint,
smoke scripts, a hygiene/secret check, confirm the website is viewable and no large
data/secrets/weights/caches are committed, confirm the end-to-end run reproduces all
artifacts, finalize `RESULTS.md` / `LIMITATIONS.md` / `REPRODUCIBILITY.md` /
`SAFETY.md`, and create `docs/PAPER_PATH.md`).
