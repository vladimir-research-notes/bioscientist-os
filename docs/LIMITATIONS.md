# Limitations

## TL;DR

`bioscientist-os` is a prototype research workbench, not a validated scientific
instrument. Its corpus is tiny and partly synthetic, its extraction is
deliberately simple and transparent (low recall), and its support/conflict
signals describe *text*, not biology. It makes no clinical claims.

## Short explanation

The project optimizes for **auditability and provenance**, accepting lower
coverage and sophistication as the price. Read every result with the denominators
shown in `docs/RESULTS.md`.

## Longer explanation

### Data limitations

- The fixture corpus is **15–30 papers** on a narrow theme; several records are
  **synthetic** and labeled `synthetic: true`.
- Fixtures are not a representative literature sample; nothing here estimates
  field-wide prevalence or effect.
- No bulk database content is redistributed.

### Method limitations

- Entity recognition is **dictionary-based**: it misses synonyms, novel entities,
  and ambiguous mentions; it can over-match common tokens.
- Claim extraction is **rule/template-based**: limited recall, brittle to complex
  syntax, paraphrase, and negation.
- "Support / conflict / unknown" is a **heuristic textual signal**, not an
  adjudication of biological correctness or study quality.
- Topic clustering uses simple lexical features; clusters are descriptive, not
  canonical.

### Evaluation limitations

- N is small; confidence intervals are wide. A high point estimate at small N is
  not a strong result.
- Gold labels reflect the authors' judgment on a narrow theme.

### Scope limitations (non-goals)

- Not a medical-advice / diagnostic / treatment tool (`docs/SAFETY.md`).
- Not a production knowledge graph or a paid-API pipeline.
- Not a benchmark leaderboard or a claim of state-of-the-art extraction.

## Exact commands

```bash
python3 -m pytest -q          # what is actually verified
cat docs/RESULTS.md           # what is actually measured
```

## Possible misleading artifacts

- Clean-looking evidence tables can imply more certainty than warranted — always
  read the `confidence`, `extraction_method`, and `support_conflict_unknown`
  columns.
- Synthetic fixtures look like real papers; they are marked `synthetic: true`.
- Visualizations summarize a tiny corpus and should not be read as field maps.
