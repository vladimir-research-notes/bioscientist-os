# Evaluation

## TL;DR

A small but rigorous self-evaluation of the workbench (Milestone 8): ingestion
correctness, search recall on hand-labeled queries, entity-extraction
precision/recall against tiny gold labels, claim-extraction sanity, evidence-table
completeness, and provenance coverage. Every metric reports its **denominator**;
proportions report a Wilson confidence interval. Small N is stated honestly.

## Short explanation

The evaluation does not benchmark biological truth. It measures whether the
*pipeline* does what it claims on a known, committed fixture set with known gold
labels.

| Metric | What it checks | Denominator |
|--------|----------------|-------------|
| ingestion correctness | every fixture row lands intact | # fixture records |
| search recall@k | labeled-relevant papers retrieved | # labeled queries |
| entity P / R / F1 | dictionary hits vs. gold spans | # gold entity spans |
| claim sanity | extracted claims are well-formed + traceable | # extracted claims |
| evidence completeness | required columns populated | # evidence rows |
| provenance coverage | cells with full provenance | # evidence cells |

## Longer explanation

### Gold labels

Gold labels are tiny, hand-authored, and committed alongside the fixtures
(e.g. relevant-paper sets for a handful of queries; gold entity spans for a few
abstracts). They are version-controlled so the eval is fully reproducible offline.

### Confidence intervals

For proportion metrics we report a 95% Wilson score interval, which is well-behaved
at small N (unlike the normal approximation). The point estimate is always shown
*with* its denominator so a reader cannot mistake `2/2 = 100%` for a strong result.

### Honesty rules

- No metric is reported without its denominator.
- We do not aggregate across heterogeneous tasks into a single headline number.
- Known failure modes (low rule-based recall, paraphrase misses) are listed, not
  hidden behind averages.

## Exact commands

```bash
# After Milestone 8:
biosci eval --db results/raw/bioscientist.db --out results/processed/eval_report.json
python3 scripts/06_run_eval.py
```

## Limitations

- N is small by construction; intervals are wide and meant to convey uncertainty,
  not to certify performance.
- Gold labels reflect the authors' judgment on a narrow theme.
- Passing the self-eval means the *pipeline* behaves as specified — not that its
  extractions are biologically authoritative.
