# Data model

## TL;DR

Typed `pydantic` schemas with explicit provenance. The core entities are
`Paper`, `Author`, `BiomedicalEntity`, `Claim`, `EvidenceItem`,
`DatabaseRecord`, `EvidenceTable`, `ResearchQuestion`, and `WorkbenchRun`. They
are implemented in Milestone 1 (`src/bioscientist_os/schemas.py`).

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

### Provenance and epistemic typing

- `data_source` ∈ {`fixture`, `cache`, `live`} appears on every externally
  sourced object so a reader can tell whether data is committed, cached, or freshly
  fetched.
- `synthetic: bool` marks fabricated fixture records so they are never mistaken
  for real curated data.
- `Claim.extraction_method` and `BiomedicalEntity.extraction_method` name the
  exact rule/model that produced the object (e.g. `rule:svo`, `dict:entity`).
- `EvidenceItem.support_conflict_unknown` is a heuristic *textual* signal, not a
  biological verdict (see `docs/SAFETY.md`).

### Validation

All schemas validate on construction. Fixture loading (M2) rejects malformed
records with readable errors. Round-trip (serialize → parse) tests guard schema
stability.

## Exact commands

```bash
# After Milestone 1:
python3 -c "from bioscientist_os.schemas import Paper; print(Paper.model_json_schema())"
```

## Limitations

- The schema set is intentionally minimal; it is not a full biomedical ontology.
- Entity typing is coarse (gene/protein/disease/process) and dictionary-driven.
- `db_xrefs` are only as complete as the fixtures/connectors provide.
