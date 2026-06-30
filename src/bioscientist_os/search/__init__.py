"""CPU-only lexical search and topic grouping (Milestone 3).

Transparent, offline baselines over the ingested paper corpus:

* :class:`SearchIndex` — a field-aware (title / keywords / abstract) in-memory
  index offering **BM25F** lexical search with a per-term, per-field score
  breakdown (:meth:`SearchIndex.search`) and an optional TF-IDF cosine mode;
* :func:`group_topics` — **single-link clustering at a cosine threshold**
  (connected components of a similarity graph), labeled by distinctive terms.

Nothing here makes a claim: results are rankings and groupings of
*observed-metadata* papers, each carrying its provenance (matched fields/terms,
scoring method, data source). See :mod:`bioscientist_os.search.index` and
:mod:`bioscientist_os.search.topics`.
"""

from __future__ import annotations

from bioscientist_os.search.index import (
    BM25_B,
    BM25_K1,
    FIELD_WEIGHTS,
    FIELDS,
    SearchIndex,
    load_index,
)
from bioscientist_os.search.model import (
    SearchHit,
    SearchResponse,
    TermMatch,
    TopicGroup,
    TopicReport,
)
from bioscientist_os.search.tokenize import content_tokens, tokenize
from bioscientist_os.search.topics import (
    DEFAULT_THRESHOLD,
    DEFAULT_TOP_TERMS,
    group_topics,
)

__all__ = [
    "SearchIndex",
    "load_index",
    "group_topics",
    "tokenize",
    "content_tokens",
    "SearchHit",
    "SearchResponse",
    "TermMatch",
    "TopicGroup",
    "TopicReport",
    "FIELDS",
    "FIELD_WEIGHTS",
    "BM25_K1",
    "BM25_B",
    "DEFAULT_THRESHOLD",
    "DEFAULT_TOP_TERMS",
]
