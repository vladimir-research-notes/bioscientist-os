# Milestone 5 — Evidence table builder

## Summary

The workbench now assembles its headline artifact: an **evidence table** grouped
by a research question, entirely on CPU and offline. Given a question, the builder
recognizes the question's entities with the M4 dictionary, keeps every extracted
claim that mentions one of them, and turns each into one
`EvidenceItem` row carrying full per-cell provenance, database links, and a
heuristic support/conflict/unknown label. The four epistemic levels are kept
separate *within* a row: the snippet is an *extracted claim* (the row's provenance
anchor), entity names are *observed metadata*, database links are *inferred
relations*, and the support label is a heuristic **textual** signal — never a
biological or clinical verdict.

## Deliverables

- **`src/bioscientist_os/evidence/table.py`** — the builder:
  - `classify_support(text, has_relation) -> (SupportLabel, reason)` — the
    transparent cue heuristic. Precedence: a strong `NEGATION_CUES` cue → `conflict`
    (overrides any relation verb); an asserted relationship (a relation triple, or a
    support cue reusing the M4 `ASSOCIATION_CUES` + directed-verb stems) → `support`;
    a weak `CONTRAST_CUES` cue with nothing affirming → `conflict`; else → `unknown`.
    The firing cue is returned so the label reconstructs from the sentence.
  - `resolve_question_entities(question, dictionary)` — recognize the question's
    entities in its text + `entities_of_interest`; returns `(entity_ids, unmatched)`
    so terms with no fixture record are reported, not silently dropped.
  - `resolve_question(stored, dictionary, question_text=, question_id=)` — map the
    CLI input to a `ResearchQuestion`: a stored question by id, a stored question by
    text/id match (so curated `entities_of_interest` are used), or a synthesized
    ad-hoc question whose entities are resolved from the text alone.
  - `build_evidence_report(question, extraction, dictionary, records, …)` — the
    assembly: relevance filter (claim mentions ≥1 question entity), per-row support
    label, database links (UniProt/HGNC xrefs + Open Targets associations) with
    human descriptors in `notes`, deterministic sort `(-confidence, paper_id,
    claim_id)`, optional `min_confidence` / `limit`. Returns an `EvidenceReport`.
  - `load_evidence(db, …)` — database-backed convenience (open store → dictionary →
    `extract_corpus` → resolve question → build), with the same not-a-database guard
    as the other subcommands.
  - `EvidenceReport` — a frozen container wrapping the typed `EvidenceTable` with the
    resolved question, corpus totals, support counts, provenance coverage, and CSV /
    JSON views (`EVIDENCE_COLUMNS`, `evidence_rows()`, `to_dict()`).
- **CLI** (`cli.py`): `biosci evidence --db <path> [--question "<text>"]
  [--question-id <id>] [--out <csv>] [--min-confidence X] [--limit N] [--json]`;
  `info` status updated to Milestones 0–5.
- **`scripts/04_build_evidence_table.py`** — install-free wrapper: builds a table for
  each stored question (or one passed in), prints a per-question summary, and writes
  `evidence_<question_id>.csv`, `evidence_table.csv` (PLAN example name), and
  `evidence_tables.json` (gitignored, regenerable, deterministic).
- **Tests**: `tests/test_evidence_table.py` (24) — 143 total, all offline.

## Design notes / decisions

- **Provenance anchored to the claim.** A row's `provenance.epistemic_level` is
  `extracted_claim` and its `source_snippet` is the claim sentence (with the exact
  `char_span` from M4). This is the deliberate choice that makes
  `provenance_coverage` 100% *by construction* — a row is only emitted from a claim
  that already has a paper and a snippet — and it keeps the auditable anchor a single
  verbatim span rather than a blend of levels. The other facets (entity names, links,
  support) live in their own typed fields, each labeled for what it is.
- **Support/conflict/unknown is textual, not biological.** The label describes how a
  sentence's phrasing reads (asserts vs. negates/contrasts a relationship). The cue
  lists are short and fully listed in `table.py`, reusing the M4 relation vocabulary
  so the project has one cue set. Negation wins over a relation verb (so a spurious
  triple from "did not increase" is still `conflict`); a weak contrast loses to an
  asserted relation triple (so "reduced IL-6 without affecting proliferation" stays
  `support`). `unknown` is the honest default and the most common label on neutral
  sentences.
- **Relevance is grounded, not lexical.** A claim qualifies only if it mentions a
  recognized question entity — no fuzzy scoring. This favors precision and keeps every
  row traceable to a shared entity; broad entities (e.g. "senescence") naturally pull
  more rows, which is honest, not a bug.
- **Database links are inferred relations, labeled.** Links combine a UniProt-anchored
  entity with Open Targets-style associations by gene; the `database_links` column
  holds clean identifiers and the `notes` field spells out the association descriptor
  (symbol → disease; score). Association scores are synthetic fixture values.
- **Question resolution is forgiving but explicit.** Passing the canonical question
  text (or its id) picks up the curated `entities_of_interest`; any other text
  synthesizes an ad-hoc question and resolves entities from the text. Unmatched
  entities of interest are surfaced.

## Validation

```bash
python3 -m pytest -q                                  # 143 passed (offline)
python3 scripts/01_ingest_fixtures.py --reset         # -> results/raw/bioscientist.db
python3 scripts/04_build_evidence_table.py            # builds 3 tables + artifacts
biosci evidence --db results/raw/bioscientist.db \
  --question "What evidence links cellular senescence to chronic inflammation?" \
  --limit 3
biosci evidence --db results/raw/bioscientist.db --question-id rq-autophagy-senescence --json | head
ruff check src/bioscientist_os/evidence/table.py src/bioscientist_os/cli.py \
           scripts/04_build_evidence_table.py tests/test_evidence_table.py   # clean
```

Measured on the committed fixtures (18 abstracts, 42 claims, 3 stored questions):

| Research question | Rows | support / conflict / unknown | Provenance coverage |
|-------------------|------|------------------------------|---------------------|
| `rq-senescence-inflammation` | 31 | 17 / 6 / 8 | 100% |
| `rq-autophagy-senescence` | 29 | 15 / 6 / 8 | 100% |
| `rq-longevity-pathways` | 8 | 4 / 1 / 3 | 100% |

These are **builder counts and behavior**, not quality metrics; support-label
precision/recall against gold labels (with denominators and Wilson intervals) is
Milestone 8. The per-row label is textual: paper-006 (`autophagy --promotes-->
senescence`) and paper-007 (`autophagy --restrains--> senescence`) both read as
`support`, because each sentence asserts a relationship — the cross-paper
directional conflict is a documented limitation, not detected here. All offline;
no network, no paid API, no GPU.

## Status

**Complete.** Next: **Milestone 6 — Database connector layer** (a base connector
interface, a required fixture-backed connector, a gitignored cache layer, retry /
error handling, and a `provenance` field on every record; optional live connectors
off by default and never required for tests).
