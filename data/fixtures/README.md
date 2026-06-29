# Fixtures

Small, clearly-labeled fixtures for offline development, tests, and the
end-to-end demo. Created in Milestone 1. Theme: **cellular senescence /
longevity / autophagy**.

## Contents (Milestone 1, current)

```
papers/papers.json            18 paper records: paper_id, title, authors, journal,
                              year, abstract, keywords, url, external_ids (DOI),
                              synthetic flag
uniprot/proteins.json         10 UniProt-style protein records: record_id +
                              source/record_type envelope and a `fields` payload
                              (accession, protein_name, gene, organism, function,
                              keywords, xrefs)
opentargets/associations.json  9 Open Targets-style disease/gene association records
                              (target_gene, disease_id, disease_label,
                              association_score, ...)
questions.json                 3 ResearchQuestion seeds for evidence tables / memos
```

These are loaded and validated by `bioscientist_os.fixtures.load_all()` against
the typed schemas in `src/bioscientist_os/schemas.py`. The loader does no
storage or normalization — that is Milestone 2's ingestion layer.

## Labeling convention

Every paper and database record includes:

- `synthetic: true|false` — fabricated vs. modeled-on-real (see `../README.md`).
- `data_source: "fixture"` — **set by the loader**, not stored in the file, so
  downstream provenance is explicit. Fixture files must not set this field.

### What is synthetic here, and what is not

- **Papers (`synthetic: true`).** All 18 abstracts are **fabricated** for
  illustration. Author names, journals, and `external_ids` are invented; DOIs use
  the reserved `10.0000/` test prefix and do **not** resolve to real articles.
  They are written to be biologically plausible and internally consistent (and
  they include a deliberate support/conflict tension between papers 006 and 007
  on whether autophagy promotes or restrains senescence), but they are not real
  publications and must never be presented as such.
- **Proteins (`synthetic: false`).** Modeled on real public UniProt records: the
  accession (`record_id`), recommended protein name, gene symbol, and organism
  are taken from real entries (e.g. `P05231` / IL6). The `function` text is
  **condensed/paraphrased**, not redistributed bulk content. Cross-references are
  limited to the HGNC gene symbol to avoid asserting IDs we have not verified.
- **Associations (`synthetic: true`).** Gene symbols are real, but every
  `association_score` is **fabricated** and every `disease_id` is a synthetic
  `SYN-DIS-*` placeholder. These are **not** Open Targets values; do not read the
  scores as evidence of anything.

## Rules

- Keep fixtures **small** and human-readable (JSON/JSONL or YAML).
- Do **not** paste large abstracts verbatim from sources with unclear licensing;
  prefer short, paraphrased, or synthetic text and mark it `synthetic: true`.
- Do **not** add real author personal data beyond what public metadata exposes.
- Fixtures must be sufficient to exercise the full pipeline (search, extraction,
  evidence tables, links, evaluation) on a CPU in seconds.
