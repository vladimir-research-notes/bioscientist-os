# Milestone 9 — End-to-end research memo generation

## Summary

The workbench gains its **narrative capstone**: a structured research memo assembled
for one research question by **composing** the existing pipeline layers — and
introducing no new, unaudited computation. The memo re-presents BM25F key papers
(M3), the evidence table (M5), the UniProt/HGNC + Open Targets database links, and the
conflicts/uncertainties, and it suggests next experiments **only** as explicitly
*unsupported* hypotheses. Its nine sections are each tagged with the epistemic level
they belong to, so the four levels (observed metadata / extracted claim / inferred
relation / unsupported hypothesis) are never collapsed; every evidence row carries
full provenance (paper, verbatim snippet, exact span, method, data source); and the
memo opens and closes with the non-clinical, no-medical-advice statement. New `biosci
memo` CLI and `scripts/07_generate_memo.py`; the Markdown and JSON are deterministic.

## Deliverables

- **`src/bioscientist_os/evidence/memo.py`** — the memo engine:
  - `MemoReport` (a frozen container with a deterministic `to_dict()` JSON view and a
    GitHub-flavored `to_markdown()` view; carries the resolved question, the M5
    `EvidenceReport`, and the derived sections);
  - `build_memo_report(question, papers, extraction, dictionary, records, …)` — the
    in-memory assembler, and `load_memo(db, …)` — the database-backed entry point that
    mirrors `load_evidence` / `load_visualizations` (same not-a-database guard, same
    `KeyError` on an unknown `question_id`);
  - the section result containers `KeyPaper`, `EntityLinks`, `DirectionalDisagreement`,
    `Hypothesis`;
  - a candidate cross-paper directional-disagreement detector (groups the relation
    triples of the question's evidence-row claims by their `{subject, object}` entity
    pair and flags pairs where ≥ 2 papers assert different relation verbs), and a
    mechanical unsupported-hypothesis generator (directional disagreements →
    affirmed relation triples → unmatched-term coverage gaps).
- **CLI** (`cli.py`): a `biosci memo` command (`--question`, `--question-id`, `--out`,
  `--json`, `--min-confidence`, `--limit`, `--max-papers`, `--max-hypotheses`); the
  default output is the Markdown memo itself, `--json` emits the structured report.
  The module docstring and `info` status are updated to Milestones 0–9.
- **`scripts/07_generate_memo.py`** — a thin, install-free wrapper that writes one
  `memo_<question_id>.md` per stored research question plus `memo.md` (the PLAN
  example's name) and `memos.json`.
- **Package exports** (`evidence/__init__.py`): the M9 public API is re-exported
  alongside M4/M5.
- **Tests**: `tests/test_memo.py` (20) — 243 total (1 skipped without `matplotlib`).

## Design notes / decisions

- **A composition, not a new model.** The memo deliberately introduces no new
  computation. The evidence table is its spine; the key papers reuse the M3 BM25F
  index; the candidate-disagreement detector reads the M4 claim triples; the database
  links mirror the M5 link assembly. A test asserts the memo's row counts, support
  labels, and links **reconcile exactly** with `build_evidence_report` for the same
  question — there is no second, silent path to a number.
- **The four levels are tagged in the prose.** Every section header carries an inline
  level tag (`_[observed metadata]_`, `_[extracted claim]_`, `_[inferred relation]_`,
  `_[unsupported hypothesis]_`) and a legend lists all four up front. The JSON view
  keeps the facets in separate fields. Collapsing the levels would be a defect.
- **Suggested experiments are unsupported hypotheses, full stop.** They are generated
  mechanically, framed as research questions (`"Whether X …"`), emitted only as
  `Hypothesis(status="unsupported")`, and rendered under a header that states they are
  "not evidence, not findings, not recommendations, and not clinical or treatment
  advice" and are UNTESTED. This is the SAFETY.md requirement made executable.
- **Conflicts are textual or candidate — never an asserted verdict.** The memo lists
  the per-sentence `conflict`-labeled rows (phrasing that negates/contrasts) and,
  separately, *candidate* cross-paper directional disagreements for a human to verify.
  The detector is recall-oriented (differing relation verbs on an entity pair); some
  differing verbs are not truly contradictory, so it is explicitly framed as a
  candidate, and the memo states the per-row label cannot detect cross-paper conflict.
- **Honest coverage gaps.** Unmatched question terms (no fixture record) and the
  retrieval recall gap (top BM25F hits that contributed no extractable claim) are
  surfaced in the uncertainties section, not hidden.
- **Deterministic and offline.** Papers, rows, links, disagreements, and hypotheses
  are all sorted before they enter the memo; there are no timestamps or run ids in the
  output, so the Markdown and `memos.json` are byte-identical across runs. A test
  pins this, and a second pins that the DB-backed `load_memo` equals the in-memory
  build.

## Validation

```bash
python3 -m pytest -q                                   # 243 passed, 1 skipped (offline)
python3 scripts/01_ingest_fixtures.py --reset          # -> results/raw/bioscientist.db
python3 scripts/07_generate_memo.py                    # -> results/processed/memo*.md, memos.json
biosci memo --db results/raw/bioscientist.db \
  --question "What evidence links cellular senescence to chronic inflammation?"
biosci memo --db results/raw/bioscientist.db --question-id rq-autophagy-senescence --json
ruff check src/bioscientist_os/evidence/memo.py src/bioscientist_os/cli.py \
    scripts/07_generate_memo.py tests/test_memo.py     # clean
```

Measured on the committed fixtures (these are *memo-builder* counts and behavior, on a
tiny, partly-synthetic corpus — not biological truth):

| Research question | Evidence rows (S / C / U) | Key papers shown | Candidate disagreements | Unsupported hypotheses |
|-------------------|---------------------------|------------------|-------------------------|------------------------|
| `rq-senescence-inflammation` | 31 (17 / 6 / 8) | 8 | 0 | 6 |
| `rq-autophagy-senescence`    | 29 (15 / 6 / 8) | 8 | 1 | 6 |
| `rq-longevity-pathways`      | 8 (4 / 1 / 3)   | 4 | 0 | 4 |

The row counts and support labels match the Milestone-5 evidence tables exactly. The
designed direction conflict (paper-006 `autophagy --promotes--> senescence` vs.
paper-007 `autophagy --restrains--> senescence`) is detected as the one candidate
directional disagreement for `rq-autophagy-senescence`.

The 20 memo tests pin: all nine required sections present and the memo header; the four
epistemic-level tags and the legend present; the no-medical-advice framing present;
every suggested experiment `status="unsupported"` and question-framed, under an
UNSUPPORTED/UNTESTED header; the conflict rows matching the `conflict` label and their
count; key papers limited to contributors, ranked by `(-rows, -confidence, -bm25f,
paper_id)`, each with its BM25F signal; the aggregate + per-entity database links
(IL-6 → UniProt:P05231, HGNC:IL6, OpenTargets:OTAF-0002); the memo reconciling with the
M5 table and 100% provenance coverage; `--min-confidence` / `--limit` / `--max-papers`
/ `--max-hypotheses` passthrough; determinism of both views; `load_memo` equalling the
in-memory build and handling an ad-hoc free-text question; and the `biosci memo` CLI
(Markdown, JSON, `--out`, requires-a-question exit 2, unknown-id exit 1, empty-db exit
1). All tests are offline (no network, no paid API, no GPU).

## Status

**Complete.** Next: **Milestone 10 — Optional LLM adapter (not required)** (an
adapter interface for LLM-assisted claim extraction / memo polish — a mock adapter used
in all tests, a cost guard, a response cache, disabled by default, never required for
CI; ship the interface + mock if a real adapter would slow the project).
