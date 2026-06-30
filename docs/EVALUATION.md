# Evaluation

## TL;DR

A small but rigorous self-evaluation of the workbench (**Milestone 8, done**):
ingestion correctness, BM25F search recall on hand-labeled queries,
entity-extraction precision/recall against tiny gold labels, claim-extraction
sanity, evidence-table completeness, and provenance coverage. Every metric reports
its **denominator**; proportions report a 95% Wilson confidence interval. Small N is
stated honestly. The measured numbers live in `docs/RESULTS.md` (Self-evaluation
section); this page is the method.

## Short explanation

The evaluation does not benchmark biological truth. It measures whether the
*pipeline* does what it claims on a known, committed fixture set with known gold
labels.

| Metric | What it checks | Denominator |
|--------|----------------|-------------|
| ingestion correctness | every fixture row round-trips through the db | # fixture records |
| search recall@k | labeled-relevant papers retrieved in the top k | # relevant (query, paper) pairs |
| entity precision / recall / F1 | dictionary hits vs. gold entity sets | # recognized / # gold |
| claim sanity | extracted claims are well-formed + span-traceable | # extracted claims |
| evidence completeness | required columns populated | # evidence rows |
| provenance coverage | rows with full provenance | # evidence rows |

## Longer explanation

### Gold labels

Gold labels are tiny, hand-authored, and committed under `data/fixtures/gold/`
(documented in its `README.md`), so the eval is fully reproducible offline:

- **`search_queries.json`** — a handful of queries, each with its human-judged
  relevant paper set. Relevance was decided by reading titles/abstracts
  *independently of the BM25F ranker*, so recall is a fair measurement.
- **`entity_labels.json`** — for a few abstracts, the distinct biomedical entities a
  reader marks present in the **abstract** text. Granularity is *distinct entity per
  abstract*, which matches what the recognizer emits (one entity per id); exact-span
  correctness is separately guaranteed by construction and tested in Milestone 4, so
  it is not re-measured here.

A true positive is a gold entity id the recognizer reports; a false positive is a
reported id not in gold; a false negative is a gold id not reported. Two recall
misses are **deliberate and documented**, so reported recall is honestly below 1.0:
`IL-8` has no UniProt fixture record (unmodeled), and `p16INK4a-expressing`
tokenizes as one hyphenated token so the `p16INK4a` surface does not match. The
`modeled` flag on each gold entity is cross-checked against the live dictionary by
the test suite, so a drift between labels and dictionary is caught.

### Confidence intervals

For proportion metrics we report a 95% Wilson score interval, which is well-behaved
at small N and near 0/1 (unlike the normal/Wald approximation, which can leave
`[0, 1]` or collapse to zero width at `k = 0` / `k = n`). The critical value `z` is
computed from the stdlib `statistics.NormalDist`, so any confidence level works with
no numerics dependency. The point estimate is always shown *with* its denominator so
a reader cannot mistake `2/2 = 100%` for a strong result — even `40/40` carries a
95% lower bound of only 0.912.

### Honesty rules

- No metric is reported without its denominator.
- We do not aggregate across heterogeneous tasks into a single headline number.
- Known failure modes (rule-based recall gaps, the tokenization and unmodeled-entity
  misses above) are surfaced in the per-abstract / per-query detail, not hidden
  behind averages.
- Metrics that are 1.0 by construction (claim sanity, completeness, provenance) are
  framed as **regression floors**, not achievements.

## Implementation

- `src/bioscientist_os/evals/metrics.py` — the `Proportion` container and the Wilson
  interval.
- `src/bioscientist_os/evals/gold.py` — typed loaders for the committed gold labels.
- `src/bioscientist_os/evals/harness.py` — the per-task evaluators, the `EvalReport`
  container (text + JSON views), and the database-backed `run_eval(db)`.
- `biosci eval` / `scripts/06_run_eval.py` — thin wrappers; both write
  `eval_report.json` and print a denominator-first summary.

## Exact commands

```bash
biosci eval --db results/raw/bioscientist.db --out results/processed/eval_report.json
python3 scripts/06_run_eval.py
python3 scripts/06_run_eval.py --confidence 0.9 --recall-k 1 --recall-k 5
```

## Limitations

- N is small by construction; intervals are wide and meant to convey uncertainty,
  not to certify performance.
- Gold labels reflect the authors' judgment on a narrow, partly-synthetic theme.
- Entity scoring is at distinct-entity-per-abstract granularity, not per-span.
- The support/conflict/unknown label is **not** scored against gold support
  annotations (a possible future metric — see `docs/ROADMAP.md`); M8 measures the
  evidence table's *structural* quality (completeness + provenance), not the label's
  agreement with a human verdict.
- Passing the self-eval means the *pipeline* behaves as specified — not that its
  extractions are biologically authoritative.
