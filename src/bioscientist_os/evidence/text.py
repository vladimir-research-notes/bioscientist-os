"""Span-aware tokenization and sentence splitting for extraction (Milestone 4).

Entity and claim extraction must report the **exact** span of text a result was
read from, so the recognizer needs token and sentence boundaries with character
offsets — not just a bag of tokens. The two helpers here provide exactly that and
share the search tokenizer's conventions so the two stages agree on what a "term"
is:

* :func:`token_spans` — the same token shape as
  :func:`bioscientist_os.search.tokenize.tokenize` (lower-cased, ASCII
  alphanumerics with internal hyphens kept), but each token carries the
  ``[start, end)`` offsets of the surface form *in the original text*. Because the
  offsets index the original (un-lowercased) string, ``text[start:end]`` is the
  verbatim surface — this is what every extraction stores as its ``source_snippet``.
* :func:`sentence_spans` — a deliberately simple sentence splitter: a sentence runs
  up to and including a run of ``.``/``!``/``?``, with leading whitespace trimmed,
  so ``text[start:end]`` is the verbatim sentence. It does **no** abbreviation
  handling (``e.g.``, ``i.e.``, ``et al.``); the committed abstracts avoid those,
  and the limitation is documented rather than hidden.

Both assume ASCII text (lower-casing is length-preserving, so offsets computed on a
lower-cased copy align with the original). The fixtures avoid non-ASCII letters; see
``bioscientist_os.search.tokenize``.
"""

from __future__ import annotations

import re

# A token: ASCII alphanumerics with optional internal single hyphens, anchored on
# alphanumerics at both ends. Identical in spirit to the search tokenizer, so
# "IL-6", "p16INK4a", and "ATG7-dependent" survive as single tokens. Applied to a
# lower-cased copy of the text; offsets are valid for the original (ASCII) text.
_TOKEN_RE = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")

# A sentence: any run of non-terminator characters followed by one or more
# sentence terminators. Naive on purpose (no abbreviation handling).
_SENT_RE = re.compile(r"[^.!?]*[.!?]+", re.DOTALL)


def token_spans(text: str) -> list[tuple[str, int, int]]:
    """Return ``(token, start, end)`` for every token, in order.

    ``token`` is lower-cased; ``text[start:end]`` is the verbatim surface form.
    """
    if not text:
        return []
    low = text.lower()
    return [(m.group(0), m.start(), m.end()) for m in _TOKEN_RE.finditer(low)]


def surface_key(surface: str) -> tuple[str, ...]:
    """Tokenize a dictionary surface form into the tuple key used for matching.

    ``surface_key("Cellular Senescence")`` -> ``("cellular", "senescence")``; an
    empty/punctuation-only surface yields ``()`` (never indexed).
    """
    return tuple(m.group(0) for m in _TOKEN_RE.finditer(surface.lower()))


def sentence_spans(text: str) -> list[tuple[int, int]]:
    """Split ``text`` into sentence ``[start, end)`` spans (verbatim, leading ws trimmed).

    ``text[start:end]`` includes the sentence's terminating punctuation and excludes
    surrounding whitespace, so it reconstructs the sentence exactly. A trailing
    fragment with no terminal punctuation is returned as a final span.
    """
    if not text:
        return []
    spans: list[tuple[int, int]] = []
    for m in _SENT_RE.finditer(text):
        seg_start, seg_end = m.start(), m.end()
        start = seg_start
        while start < seg_end and text[start].isspace():
            start += 1
        if start < seg_end:
            spans.append((start, seg_end))
    # A final fragment after the last terminator (no trailing punctuation).
    last_end = spans[-1][1] if spans else 0
    rem = last_end
    while rem < len(text) and text[rem].isspace():
        rem += 1
    if rem < len(text):
        spans.append((rem, len(text)))
    return spans


__all__ = ["token_spans", "surface_key", "sentence_spans"]
