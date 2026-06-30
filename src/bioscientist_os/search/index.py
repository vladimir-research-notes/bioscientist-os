"""CPU-only, in-memory search index over the ingested paper corpus (Milestone 3).

The index holds three weighted fields per paper — ``title``, ``keywords``,
``abstract`` — and offers two transparent scorers:

* :meth:`SearchIndex.search` — **BM25F**, the multi-field Okapi BM25 variant. Each
  query term's contribution to a paper's score is computed explicitly and returned
  in the result, so the total score is exactly the sum of its parts and a reader
  can see which terms matched, in which fields, and how much each was worth.
* :meth:`SearchIndex.tfidf_vectors` / :meth:`SearchIndex.tfidf_search` — smoothed
  TF-IDF document vectors and cosine similarity, used both for an optional search
  mode and as the similarity basis for topic grouping
  (:mod:`bioscientist_os.search.topics`).

Everything is recomputed from the corpus in memory: for the small corpora this
workbench targets there is no benefit to a persisted inverted index, and an
in-memory build keeps the result a pure, deterministic function of the database
contents. The cost is O(papers × query-terms) per query, which is negligible
here; this is noted as a scaling limitation rather than hidden.

No claims are produced: a search result is a *ranking of observed-metadata
papers*, and topic groups are *groupings of papers*. Provenance (paper id, matched
fields/terms, method, data source) travels on every result object.
"""

from __future__ import annotations

import math
from collections import Counter
from pathlib import Path

from bioscientist_os.schemas import Paper
from bioscientist_os.search.model import SearchHit, SearchResponse, TermMatch
from bioscientist_os.search.tokenize import (
    bm25_idf,
    content_tokens,
    tfidf_idf,
    tokenize,
)

# The three searchable fields and their BM25F weights. Title and keywords are
# short, curated, high-signal fields, so a match there counts for more than a match
# in the longer abstract. Documented and exposed in every result's ``params``.
FIELDS: tuple[str, ...] = ("title", "keywords", "abstract")
FIELD_WEIGHTS: dict[str, float] = {"title": 3.0, "keywords": 2.0, "abstract": 1.0}

# BM25 saturation (k1) and length-normalization (b). Standard mid-range defaults;
# b is shared across fields for simplicity (a single, explainable knob).
BM25_K1 = 1.5
BM25_B = 0.75


class SearchIndex:
    """An in-memory, field-aware index built from a list of :class:`Paper`.

    Construct directly from papers, or via :meth:`from_papers` /
    :meth:`from_store`. The index is immutable after construction; all scoring is
    derived from the precomputed per-field statistics, so repeated queries are
    deterministic.
    """

    def __init__(self, papers: list[Paper]) -> None:
        # Sort by paper_id so the index — and every tie-break that falls back to
        # corpus order — is independent of how papers arrived.
        self.papers: list[Paper] = sorted(papers, key=lambda p: p.paper_id)
        self.num_docs: int = len(self.papers)
        self.data_source: str = self._single_data_source()

        # Per-paper, per-field token frequencies and lengths.
        self._field_tf: dict[str, dict[str, Counter[str]]] = {}
        self._field_len: dict[str, dict[str, int]] = {}
        # Corpus statistics.
        self._doc_freq: Counter[str] = Counter()  # docs containing a term in ANY field
        self._avg_field_len: dict[str, float] = {f: 0.0 for f in FIELDS}
        # TF-IDF vectors, L2-normalized, computed lazily and cached.
        self._tfidf: dict[str, dict[str, float]] | None = None

        self._build()

    # -- construction ------------------------------------------------------

    @classmethod
    def from_papers(cls, papers: list[Paper]) -> SearchIndex:
        return cls(list(papers))

    @classmethod
    def from_store(cls, store: object) -> SearchIndex:
        """Build from an open :class:`bioscientist_os.storage.SQLiteStore`."""
        return cls(list(store.iter_papers()))  # type: ignore[attr-defined]

    def _single_data_source(self) -> str:
        sources = {p.data_source.value for p in self.papers}
        if not sources:
            return "fixture"
        return next(iter(sources)) if len(sources) == 1 else "mixed"

    @staticmethod
    def _field_text(paper: Paper, field: str) -> str:
        if field == "title":
            return paper.title
        if field == "keywords":
            return " ".join(paper.keywords)
        if field == "abstract":
            return paper.abstract
        raise ValueError(f"unknown field {field!r}")  # pragma: no cover

    def _build(self) -> None:
        totals = {f: 0 for f in FIELDS}
        for paper in self.papers:
            pid = paper.paper_id
            self._field_tf[pid] = {}
            self._field_len[pid] = {}
            seen_terms: set[str] = set()
            for f in FIELDS:
                toks = tokenize(self._field_text(paper, f))
                tf = Counter(toks)
                self._field_tf[pid][f] = tf
                self._field_len[pid][f] = len(toks)
                totals[f] += len(toks)
                seen_terms.update(tf)
            # Document frequency counts a term once per paper, across all fields.
            for term in seen_terms:
                self._doc_freq[term] += 1
        if self.num_docs:
            self._avg_field_len = {f: totals[f] / self.num_docs for f in FIELDS}

    # -- BM25F search ------------------------------------------------------

    def vocabulary_size(self) -> int:
        """Number of distinct terms across all fields of all papers."""
        return len(self._doc_freq)

    def corpus_stats(self) -> dict[str, object]:
        """Compact, inspectable corpus statistics for the build-index report."""
        return {
            "num_papers": self.num_docs,
            "vocabulary_size": self.vocabulary_size(),
            "avg_field_length": {f: round(self._avg_field_len[f], 3) for f in FIELDS},
            "field_weights": dict(FIELD_WEIGHTS),
            "data_source": self.data_source,
        }

    def _bm25f_term(self, pid: str, term: str) -> tuple[dict[str, int], float, float]:
        """Return (per-field tf, weighted_tf, idf) for one term against one paper."""
        field_tf: dict[str, int] = {}
        weighted_tf = 0.0
        for f in FIELDS:
            tf = self._field_tf[pid][f].get(term, 0)
            if tf == 0:
                continue
            field_tf[f] = tf
            avg = self._avg_field_len[f]
            norm = 1.0 - BM25_B + BM25_B * (self._field_len[pid][f] / avg) if avg > 0 else 1.0
            weighted_tf += FIELD_WEIGHTS[f] * tf / norm
        df = self._doc_freq.get(term, 0)
        idf = bm25_idf(self.num_docs, df) if df else 0.0
        return field_tf, weighted_tf, idf

    def search(self, query: str, *, limit: int = 10) -> SearchResponse:
        """Rank papers for ``query`` with BM25F; return hits with full explanations.

        Only papers with a positive score are returned, sorted by descending score
        then ascending ``paper_id`` (a deterministic tie-break). ``limit`` caps the
        number of hits (``limit <= 0`` returns all scored papers).
        """
        # Unique query terms, preserving first-occurrence order, so the explanation
        # lists each term once in a stable order.
        query_terms: list[str] = []
        for t in tokenize(query):
            if t not in query_terms:
                query_terms.append(t)

        hits: list[SearchHit] = []
        for paper in self.papers:
            pid = paper.paper_id
            term_matches: list[TermMatch] = []
            score = 0.0
            for term in query_terms:
                field_tf, weighted_tf, idf = self._bm25f_term(pid, term)
                contribution = (
                    idf * weighted_tf / (BM25_K1 + weighted_tf) if weighted_tf > 0 else 0.0
                )
                score += contribution
                term_matches.append(
                    TermMatch(
                        term=term,
                        matched=weighted_tf > 0,
                        idf=idf,
                        field_tf=field_tf,
                        weighted_tf=weighted_tf,
                        contribution=contribution,
                    )
                )
            if score > 0:
                hits.append(
                    SearchHit(
                        rank=0,  # assigned after sorting
                        paper_id=pid,
                        title=paper.title,
                        year=paper.year,
                        score=score,
                        term_matches=term_matches,
                    )
                )

        hits.sort(key=lambda h: (-h.score, h.paper_id))
        if limit and limit > 0:
            hits = hits[:limit]
        ranked = [
            SearchHit(
                rank=i,
                paper_id=h.paper_id,
                title=h.title,
                year=h.year,
                score=h.score,
                term_matches=h.term_matches,
            )
            for i, h in enumerate(hits, start=1)
        ]
        return SearchResponse(
            query=query,
            query_terms=query_terms,
            method="bm25f",
            params={"k1": BM25_K1, "b": BM25_B, **{f"w_{k}": v for k, v in FIELD_WEIGHTS.items()}},
            total_papers=self.num_docs,
            data_source=self.data_source,
            hits=ranked,
        )

    # -- TF-IDF vectors + cosine ------------------------------------------

    def tfidf_vectors(self) -> dict[str, dict[str, float]]:
        """L2-normalized smoothed TF-IDF vectors per paper (cached).

        Built over :func:`content_tokens` of the concatenated fields (stop words
        and pure-digit tokens removed). Term weight = ``(1 + ln tf) * idf`` with the
        smoothed idf from :func:`tfidf_idf`, then the vector is L2-normalized so a
        dot product is a cosine similarity.
        """
        if self._tfidf is not None:
            return self._tfidf

        doc_tokens: dict[str, Counter[str]] = {}
        doc_freq: Counter[str] = Counter()
        for paper in self.papers:
            toks = content_tokens(
                " ".join(self._field_text(paper, f) for f in FIELDS)
            )
            tf = Counter(toks)
            doc_tokens[paper.paper_id] = tf
            for term in tf:
                doc_freq[term] += 1

        vectors: dict[str, dict[str, float]] = {}
        for pid, tf in doc_tokens.items():
            vec: dict[str, float] = {}
            for term, count in tf.items():
                vec[term] = (1.0 + math.log(count)) * tfidf_idf(self.num_docs, doc_freq[term])
            norm = math.sqrt(sum(w * w for w in vec.values()))
            if norm > 0:
                vec = {term: w / norm for term, w in vec.items()}
            vectors[pid] = vec

        self._tfidf = vectors
        return vectors

    @staticmethod
    def cosine(a: dict[str, float], b: dict[str, float]) -> float:
        """Cosine similarity of two (already L2-normalized) sparse vectors."""
        # Iterate the smaller vector's keys for speed; vectors are L2-normalized,
        # so the dot product is the cosine.
        if len(b) < len(a):
            a, b = b, a
        return sum(w * b.get(term, 0.0) for term, w in a.items())

    def tfidf_search(self, query: str, *, limit: int = 10) -> SearchResponse:
        """Optional cosine-similarity search: score papers by TF-IDF cosine to the query."""
        q_tf = Counter(content_tokens(query))
        query_terms = list(dict.fromkeys(content_tokens(query)))
        vectors = self.tfidf_vectors()
        # Build a query vector with the same smoothed idf, L2-normalized.
        doc_freq_lookup = self._tfidf_doc_freq()
        q_vec: dict[str, float] = {}
        for term, count in q_tf.items():
            df = doc_freq_lookup.get(term, 0)
            q_vec[term] = (1.0 + math.log(count)) * tfidf_idf(self.num_docs, df)
        qnorm = math.sqrt(sum(w * w for w in q_vec.values()))
        if qnorm > 0:
            q_vec = {term: w / qnorm for term, w in q_vec.items()}

        scored: list[SearchHit] = []
        for paper in self.papers:
            sim = self.cosine(q_vec, vectors[paper.paper_id])
            if sim > 0:
                matched = sorted(set(q_vec) & set(vectors[paper.paper_id]))
                term_matches = [
                    TermMatch(term=t, matched=True, idf=0.0, field_tf={}, weighted_tf=0.0,
                              contribution=0.0)
                    for t in matched
                ]
                scored.append(
                    SearchHit(rank=0, paper_id=paper.paper_id, title=paper.title,
                              year=paper.year, score=sim, term_matches=term_matches)
                )
        scored.sort(key=lambda h: (-h.score, h.paper_id))
        if limit and limit > 0:
            scored = scored[:limit]
        ranked = [
            SearchHit(rank=i, paper_id=h.paper_id, title=h.title, year=h.year,
                      score=h.score, term_matches=h.term_matches)
            for i, h in enumerate(scored, start=1)
        ]
        return SearchResponse(
            query=query, query_terms=query_terms, method="tfidf-cosine", params={},
            total_papers=self.num_docs, data_source=self.data_source, hits=ranked,
        )

    def _tfidf_doc_freq(self) -> Counter[str]:
        df: Counter[str] = Counter()
        for paper in self.papers:
            for term in set(content_tokens(" ".join(self._field_text(paper, f) for f in FIELDS))):
                df[term] += 1
        return df


def load_index(db_path: str | Path) -> SearchIndex:
    """Open an ingested SQLite database and build a :class:`SearchIndex` from it.

    Raises :class:`ValueError` if the file is not a bioscientist-os database (no
    ingested tables), mirroring the guard used by ``biosci stats``.
    """
    from bioscientist_os.storage import SQLiteStore

    with SQLiteStore(db_path) as store:
        if not store.is_initialized():
            raise ValueError(
                f"{db_path} is not a bioscientist-os database (no ingested tables)"
            )
        return SearchIndex.from_store(store)


__all__ = [
    "SearchIndex",
    "load_index",
    "FIELDS",
    "FIELD_WEIGHTS",
    "BM25_K1",
    "BM25_B",
]
