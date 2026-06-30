"""Transparent tokenization for the search and topic baselines (Milestone 3).

The whole point of these baselines is auditability: a scientist must be able to
see *which literal terms* matched. So tokenization is deliberately simple and
documented, and does **no stemming and no synonym/identifier expansion** — those
would hide which surface form actually matched. Mapping surface forms to
canonical gene/protein identifiers (e.g. ``IL-6`` ↔ ``IL6``) is the job of entity
extraction (Milestone 4), not search.

A token is a maximal run of ASCII alphanumerics that may contain *internal*
hyphens, folded to lowercase. Internal hyphens are kept so common biomedical
surface forms survive as single tokens::

    "Senescent fibroblasts secrete IL-6"  -> ["senescent", "fibroblasts", "secrete", "il-6"]
    "p16INK4a accumulation"               -> ["p16ink4a", "accumulation"]
    "ATG7-dependent autophagy"            -> ["atg7-dependent", "autophagy"]

Consequences a reader should know:

* ``IL-6`` and ``IL6`` tokenize to **different** tokens (``il-6`` vs ``il6``);
  search does not unify them (entity linking does).
* non-ASCII letters (e.g. Greek ``α``) are dropped; the fixtures avoid them.
"""

from __future__ import annotations

import math
import re
from collections import Counter

# A token: alphanumerics with optional internal single hyphens. Anchored on
# alphanumerics at both ends, so leading/trailing/standalone hyphens are not part
# of a token. Applied to lower-cased text.
_TOKEN_RE = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")

# A small, deliberately conservative stop list of generic English function words
# plus a few corpus-generic research words ("study", "results", ...). Used ONLY by
# the TF-IDF / topic-clustering path (:func:`content_tokens`), where common words
# inflate document similarity; the BM25 search path keeps *all* tokens and lets
# inverse document frequency down-weight them instead. Kept short on purpose so it
# never silently removes domain vocabulary.
STOPWORDS: frozenset[str] = frozenset(
    {
        "a", "an", "and", "are", "as", "at", "be", "been", "but", "by", "for",
        "from", "had", "has", "have", "in", "into", "is", "it", "its", "of", "on",
        "or", "over", "that", "the", "their", "these", "this", "those", "to",
        "was", "we", "were", "which", "while", "with", "without",
        # corpus-generic research words that carry little topical signal here
        "study", "studies", "results", "result", "report", "reports", "reported",
        "findings", "show", "shows", "showed", "observed", "found", "using",
    }
)


def tokenize(text: str) -> list[str]:
    """Lower-case ``text`` and return its tokens, in order, with duplicates.

    The raw tokenization used by lexical (BM25) search: every term is kept so
    matches are fully explainable.
    """
    if not text:
        return []
    return _TOKEN_RE.findall(text.lower())


def content_tokens(text: str) -> list[str]:
    """Tokens for TF-IDF / topic similarity: drop stop words and pure-digit tokens.

    Pure-number tokens (years like ``2008``, counts) and the :data:`STOPWORDS`
    carry little topical signal and would otherwise inflate cosine similarity
    between unrelated papers. Hyphenated identifiers and alphanumerics like
    ``p16ink4a`` or ``il-6`` are preserved.
    """
    return [t for t in tokenize(text) if t not in STOPWORDS and not t.isdigit()]


def term_frequencies(tokens: list[str]) -> Counter[str]:
    """Count term occurrences (a thin, named wrapper around :class:`Counter`)."""
    return Counter(tokens)


def bm25_idf(num_docs: int, doc_freq: int) -> float:
    """The standard (Robertson) BM25 inverse document frequency, always ≥ 0.

    ``ln(1 + (N - df + 0.5) / (df + 0.5))``. Non-negative for all ``0 ≤ df ≤ N``,
    so a term occurring in every document contributes a small positive weight
    rather than a negative one (the un-clamped Robertson-Spärck-Jones form can go
    negative for very common terms).
    """
    return math.log(1.0 + (num_docs - doc_freq + 0.5) / (doc_freq + 0.5))


def tfidf_idf(num_docs: int, doc_freq: int) -> float:
    """Smoothed TF-IDF inverse document frequency: ``ln((1+N)/(1+df)) + 1``.

    The ``+1`` smoothing (sklearn-style) keeps the weight strictly positive even
    for a term present in every document, so L2-normalized vectors are well
    defined. Used for cosine similarity and topic clustering.
    """
    return math.log((1.0 + num_docs) / (1.0 + doc_freq)) + 1.0


__all__ = [
    "STOPWORDS",
    "tokenize",
    "content_tokens",
    "term_frequencies",
    "bm25_idf",
    "tfidf_idf",
]
