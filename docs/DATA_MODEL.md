# Data model

## TL;DR

Typed `pydantic` v2 schemas with explicit provenance. The core entities are
`Paper`, `Author`, `BiomedicalEntity`, `Claim`, `EvidenceItem`,
`DatabaseRecord`, `EvidenceTable`, `ResearchQuestion`, and `WorkbenchRun`. They
are implemented in Milestone 1 (`src/bioscientist_os/schemas.py`), alongside a
shared `Provenance` submodel, four controlled vocabularies (`DataSource`,
`EpistemicLevel`, `EntityType`, `SupportLabel`), and a thin fixture loader
(`src/bioscientist_os/fixtures.py`) that parses the committed corpus into these
types. **Status: implemented.**

## Short explanation

The schemas encode the evidence chain and force every derived object to point
back at its source.

| Schema | Purpose | Key provenance fields |
|--------|---------|-----------------------|
| `Paper` | normalized paper metadata + abstract | `paper_id`, `external_ids`, `data_source`, `synthetic` |
| `Author` | author identity | `name`, `orcid?` |
| `BiomedicalEntity` | gene / protein / disease / process mention | `name`, `entity_type`, `db_xrefs`, `extraction_method` |
| `Claim` | a claim extracted from text | `claim_text`, `source_snippet`, `paper_id`, `extraction_method`, `confidence` |
| `EvidenceItem` | one row linking claim ↔ paper ↔ entities ↔ DB | `support_conflict_unknown`, `database_links`, `provenance` |
| `DatabaseRecord` | a record fetched from a connector | `source`, `record_id`, `data_source` (fixture/cache/live) |
| `EvidenceTable` | a set of EvidenceItems for a question | `research_question_id`, `rows`, `generated_by` |
| `ResearchQuestion` | the question driving a table/memo | `text`, `entities_of_interest` |
| `WorkbenchRun` | a reproducible run record | `run_id`, `inputs`, `versions`, `timestamps` |

## Longer explanation

### Two object families

- **Observed-metadata objects** — `Paper` and `DatabaseRecord` — *are* the
  source. They carry `data_source` and `synthetic` directly and have no
  `Provenance` block (there is nothing upstream to point at).
- **Derived objects** — `BiomedicalEntity`, `Claim`, `EvidenceItem` — carry a
  required `Provenance` submodel that points back at a paper, a snippet (with an
  optional `char_span`), the `extraction_method`, the `data_source`, and an
  `epistemic_level`. By project policy a derived object without provenance is
  incomplete; here that policy is enforced by the type system (the field is
  required), not left to convention.

### Provenance and epistemic typing

- `data_source` ∈ {`fixture`, `cache`, `live`} appears on every externally
  sourced object so a reader can tell whether data is committed, cached, or freshly
  fetched. The fixture loader **stamps** it (`fixture`) on load rather than reading
  it from the file.
- `synthetic: bool` marks fabricated fixture records so they are never mistaken
  for real curated data.
- `extraction_method` (on `Provenance`) names the exact rule/model that produced
  the object (e.g. `rule:svo`, `dict:entity`, `fixture:load`).
- `EpistemicLevel` ∈ {`observed_metadata`, `extracted_claim`, `inferred_relation`,
  `unsupported_hypothesis`} is the same four-level vocabulary the CLI prints; the
  enum is asserted at import time to match `bioscientist_os.EPISTEMIC_LEVELS`.
- `SupportLabel` (`support` / `conflict` / `unknown`, default `unknown`) on
  `EvidenceItem.support_conflict_unknown` is a heuristic *textual* signal, not a
  biological verdict (see `docs/SAFETY.md`).

### Validation enforced at construction

- `extra="forbid"` on every model: an unexpected key (e.g. a typo'd field in a
  fixture) is rejected, not silently dropped.
- `confidence` is constrained to `[0, 1]`; `year` to a sane range.
- `Provenance.char_span` must be non-negative and ordered (`start <= end`).
- A `Claim`'s `provenance.paper_id`, when set, must equal its `paper_id`.
- `EvidenceTable.provenance_coverage` reports the fraction of rows whose
  provenance names both a paper and a source snippet (used by the M8 evaluation).
- Round-trip (`model_dump_json` → `model_validate_json`) tests guard stability;
  the fixture loader rejects malformed records with file-and-index errors.

## Exact commands

```bash
# Inspect a schema:
python3 -c "from bioscientist_os.schemas import Paper; print(Paper.model_json_schema())"

# Load and summarize the committed fixtures (no database; that is Milestone 2):
python3 -c "from bioscientist_os.fixtures import load_all; print(load_all().summary())"
# -> {'papers': 18, 'proteins': 10, 'associations': 9, 'questions': 3}
```

## Limitations

- The schema set is intentionally minimal; it is not a full biomedical ontology.
- Entity typing is coarse (`gene`/`protein`/`disease`/`process`/`pathway`/
  `cell_type`/`chemical`/`other`) and is dictionary-driven (done, M4:
  `evidence/dictionary.py` builds the dictionary from the UniProt/Open Targets
  fixtures plus a small curated process seed).
- `db_xrefs` are only as complete as the fixtures/connectors provide.
- The loader does parsing/validation only; normalization, deduplication, and
  storage are Milestone 2.
