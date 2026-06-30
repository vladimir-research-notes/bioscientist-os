"""Transparent topic grouping by single-linkage clustering (Milestone 3).

The method is deliberately simple and named exactly for what it is — **single-link
clustering at a cosine-similarity threshold**, implemented as the connected
components of a graph:

1. build the L2-normalized TF-IDF vectors of every paper
   (:meth:`bioscientist_os.search.index.SearchIndex.tfidf_vectors`);
2. add an undirected edge between two papers when their cosine similarity is at
   least ``threshold``;
3. each connected component is one topic group; label it by the terms carrying the
   most TF-IDF mass across its members.

Properties a reader can rely on:

* **Deterministic.** Node order, component order (by size then smallest paper id),
  member order (by paper id), and label order (by mass then term) are all sorted.
* **Monotone in the threshold.** Raising ``threshold`` only removes edges, so the
  number of groups never decreases — a clean knob with predictable behavior.
* **Honest about its limits.** Single linkage produces *hard, possibly chaining*
  clusters and cannot represent a paper that belongs to two themes (e.g. a paper on
  autophagy *and* the SASP). The labels describe a group; they are not asserted
  topics of the corpus. This is a baseline, not a topic model.

``networkx`` (already a core dependency) provides the graph and connected
components; no clustering library or model training is involved.
"""

from __future__ import annotations

from itertools import combinations

import networkx as nx

from bioscientist_os.search.index import SearchIndex
from bioscientist_os.search.model import TopicGroup, TopicReport

# Default cosine threshold for an edge. Chosen on the committed fixtures to yield a
# small number of readable groups (SASP/secretion, senescence markers,
# autophagy/mTOR/longevity, senolytics, plus distinct singletons) while keeping
# loosely-related papers apart. Below ~0.10 single linkage chains the whole
# thematically-related corpus into one component; above ~0.20 it shatters into
# mostly singletons. The exact value is reported in every TopicReport and is
# overridable on the CLI.
DEFAULT_THRESHOLD = 0.15

# Number of label terms per group (most TF-IDF mass first).
DEFAULT_TOP_TERMS = 6


def _label_terms(
    vectors: dict[str, dict[str, float]], members: list[str], top_terms: int
) -> list[str]:
    """Top terms by summed TF-IDF mass across ``members`` (ties broken alphabetically)."""
    mass: dict[str, float] = {}
    for pid in members:
        for term, weight in vectors[pid].items():
            mass[term] = mass.get(term, 0.0) + weight
    ranked = sorted(mass.items(), key=lambda kv: (-kv[1], kv[0]))
    return [term for term, _ in ranked[:top_terms]]


def group_topics(
    index: SearchIndex,
    *,
    threshold: float = DEFAULT_THRESHOLD,
    top_terms: int = DEFAULT_TOP_TERMS,
) -> TopicReport:
    """Group the indexed corpus into topics by single-link cosine clustering.

    Every paper appears in exactly one group; a paper similar to no other above
    ``threshold`` forms a singleton group.
    """
    vectors = index.tfidf_vectors()
    pids = sorted(vectors)

    graph: nx.Graph = nx.Graph()
    graph.add_nodes_from(pids)
    for a, b in combinations(pids, 2):
        sim = SearchIndex.cosine(vectors[a], vectors[b])
        if sim >= threshold:
            graph.add_edge(a, b, weight=sim)

    components = nx.connected_components(graph)
    # Largest groups first; ties broken by the group's smallest paper id.
    ordered = sorted(components, key=lambda comp: (-len(comp), min(comp)))

    groups: list[TopicGroup] = []
    for i, comp in enumerate(ordered, start=1):
        members = sorted(comp)
        groups.append(
            TopicGroup(
                topic_id=f"topic-{i:02d}",
                label_terms=_label_terms(vectors, members, top_terms),
                paper_ids=members,
            )
        )

    return TopicReport(
        method="tfidf-cosine + single-linkage (connected components)",
        threshold=threshold,
        params={"top_terms": float(top_terms)},
        total_papers=index.num_docs,
        data_source=index.data_source,
        groups=groups,
    )


__all__ = ["group_topics", "DEFAULT_THRESHOLD", "DEFAULT_TOP_TERMS"]
