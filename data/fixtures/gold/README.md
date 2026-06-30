# Gold labels for the self-evaluation (Milestone 8)

These tiny, hand-authored, version-controlled labels let `biosci eval` measure the
**pipeline** against a fixed reference, fully offline and reproducibly. They are
*not* a biological gold standard — they encode the authors' reading of this small,
**synthetic**, theme-focused corpus (cellular senescence / autophagy / longevity).
See `docs/EVALUATION.md` for how each metric uses them.

## Files

### `search_queries.json` — labeled retrieval queries

A handful of queries, each with the set of paper ids a human judges **relevant** by
topic. Relevance was decided by reading titles/abstracts, **independently of the
BM25F ranker**, so retrieval recall is a fair measurement (some relevant papers use
different surface words than the query and are retrieved only at larger `k` — an
honest result, not a tuned one).

| field | meaning |
|-------|---------|
| `query_id` | stable id |
| `query` | the query string passed to search |
| `relevant_paper_ids` | the human-judged relevant set (the recall denominator per query) |
| `note` | why these papers are relevant; any deliberately hard cases |

### `entity_labels.json` — gold entity sets per abstract

For a few abstracts, the distinct biomedical entities a human marks as present in
the **abstract text** (extraction reads the abstract, not the title). Granularity is
*distinct entity per abstract*, which matches what the dictionary recognizer emits
(one entity per id); exact-span correctness is separately guaranteed by construction
and tested in Milestone 4, so it is not re-measured here.

| field | meaning |
|-------|---------|
| `paper_id` | the abstract being labeled |
| `gold_entities[].entity_id` | the dictionary entity id for recognizable concepts; an in-theme id with no fixture record (e.g. `ent-IL8`) for genuine coverage gaps |
| `gold_entities[].surface` | the verbatim mention a reader would point at |
| `gold_entities[].modeled` | whether the dictionary *could* recognize it (cross-checked against the live dictionary by the eval tests) |
| `note` | clean cases and the deliberate misses |

Two recall misses are intentional and documented, so the reported recall is honestly
below 1.0:

- **`ent-IL8`** (paper-001): IL-8 has no UniProt fixture record, so the dictionary
  has no entity for it.
- **`ent-CDKN2A` in paper-003**: p16INK4a appears only as `p16INK4a-expressing`,
  which the tokenizer keeps as one hyphenated token, so the `p16ink4a` surface does
  not match.

These illustrate the rule-based baseline's known limits (no fuzzy/morphological
matching, no entities beyond the fixtures) rather than hiding them.
