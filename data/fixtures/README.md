# Fixtures

Small, clearly-labeled fixtures for offline development, tests, and the
end-to-end demo. Created in Milestone 1. Theme: **cellular senescence /
longevity / autophagy**.

## Contents (after Milestone 1)

```
papers/        ≈15–30 paper records: title, authors, journal, year, abstract,
               keywords, url, external_ids (PMID/DOI-shaped), synthetic flag
uniprot/       5–10 UniProt-style protein records (accession, name, gene,
               organism, function, xrefs, synthetic flag)
opentargets/   a few disease/gene/protein link records (association-shaped)
```

## Labeling convention

Every record includes:

- `synthetic: true|false` — fabricated vs. modeled-on-real (see `../README.md`).
- `data_source: "fixture"` — set on load so downstream provenance is explicit.

## Rules

- Keep fixtures **small** and human-readable (JSON/JSONL or YAML).
- Do **not** paste large abstracts verbatim from sources with unclear licensing;
  prefer short, paraphrased, or synthetic text and mark it `synthetic: true`.
- Do **not** add real author personal data beyond what public metadata exposes.
- Fixtures must be sufficient to exercise the full pipeline (search, extraction,
  evidence tables, links, evaluation) on a CPU in seconds.
