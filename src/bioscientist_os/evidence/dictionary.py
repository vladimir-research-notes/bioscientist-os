"""A transparent, fixture-built dictionary for biomedical entity recognition (M4).

The recognizer is deliberately a **dictionary matcher**, not a model: a reviewer
can print the whole dictionary, see every surface form it will match, and verify
each recognized span against the source text. The dictionary is built from the
committed fixtures plus a small, explicit curated seed:

* **UniProt protein records** (``data/fixtures/uniprot/``) contribute one
  :class:`DictionaryEntity` per protein. Its surface forms are the gene symbol,
  the common name, the full protein name, and the accession; its ``db_xrefs`` are
  the real UniProt accession and HGNC symbol. These are the authoritative,
  non-synthetic anchors of the dictionary.
* **Open Targets association records** (``data/fixtures/opentargets/``) contribute
  *extra surface synonyms* to the protein they name via ``target_symbol`` — e.g.
  ``IL-6`` for the IL6 protein, a surface the UniProt record does not list. The
  associations add no new entities (their gene is already a UniProt protein); they
  only widen recognition of forms that actually appear in abstracts.
* A small **curated seed** (:data:`CURATED_TERMS`) adds process / phenotype /
  chemical terms central to the corpus theme (senescence, autophagy, inflammation,
  the SASP, …) that have no protein record. It is short, fully listed in this
  module, and carries no ``db_xrefs`` (there is no database record behind it).

Matching is **longest-match (max-munch)**: at each position the recognizer prefers
the longest dictionary surface, so ``senescence-associated secretory phenotype`` is
one SASP mention rather than three. Surface keys are tokenized with the same rule
as search (:mod:`bioscientist_os.evidence.text`), so ``IL-6`` and ``IL6`` remain
distinct tokens — the dictionary, not the tokenizer, unifies them (UniProt lists
``IL6``; Open Targets adds ``IL-6``). Entity typing is coarse by design
(see :class:`bioscientist_os.schemas.EntityType`); this is a baseline, not an
ontology, and its limits are documented rather than hidden.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass, field

from bioscientist_os.evidence.model import EntityMention
from bioscientist_os.evidence.text import surface_key, token_spans
from bioscientist_os.schemas import DatabaseRecord, EntityType

# A small, explicit curated seed of process / phenotype / chemical terms central to
# the cellular-senescence / autophagy / longevity theme. These have no protein
# record, so they are listed here rather than derived from a fixture — kept short
# and transparent on purpose. Each entry is (canonical_name, entity_type, surfaces).
# Coarse typing is intentional (EntityType is blunt); `other` is the honest bucket
# for named phenotypes/markers that are not a gene/protein/disease/process.
CURATED_TERMS: tuple[tuple[str, EntityType, tuple[str, ...]], ...] = (
    ("cellular senescence", EntityType.process, ("cellular senescence", "senescence", "senescent")),
    ("paracrine senescence", EntityType.process, ("paracrine senescence",)),
    ("senescence-associated secretory phenotype", EntityType.other,
     ("senescence-associated secretory phenotype", "SASP")),
    ("autophagy", EntityType.process, ("autophagy", "autophagic flux", "autophagic")),
    ("inflammation", EntityType.process, ("inflammation", "inflammatory")),
    ("inflammaging", EntityType.other, ("inflammaging",)),
    ("cell-cycle arrest", EntityType.process, ("cell-cycle arrest", "cell cycle arrest")),
    ("DNA damage", EntityType.process, ("DNA damage",)),
    ("oxidative stress", EntityType.process, ("oxidative stress",)),
    ("caloric restriction", EntityType.process, ("caloric restriction",)),
    ("partial reprogramming", EntityType.process, ("partial reprogramming", "reprogramming")),
    ("senolytic", EntityType.other, ("senolytic", "senolytics")),
    ("lifespan", EntityType.other, ("lifespan",)),
    ("longevity", EntityType.other, ("longevity",)),
    ("healthspan", EntityType.other, ("healthspan",)),
    ("rapamycin", EntityType.chemical, ("rapamycin",)),
)

_SLUG_RE = re.compile(r"[^a-z0-9]+")


def _slug(name: str) -> str:
    return _SLUG_RE.sub("-", name.lower()).strip("-")


@dataclass(frozen=True)
class DictionaryEntity:
    """A canonical entity: its id, type, recognized surface forms, and xrefs."""

    entity_id: str
    canonical_name: str
    entity_type: EntityType
    surfaces: tuple[str, ...]
    db_xrefs: dict[str, str] = field(default_factory=dict)


class EntityDictionary:
    """A surface-form index over :class:`DictionaryEntity` with longest-match lookup.

    Build via :func:`build_dictionary` (the supported path) or directly from a list
    of entities. On a surface-key collision the first-inserted entity wins, so
    UniProt anchors take precedence over the curated seed (a documented, stable
    rule). The dictionary is immutable after construction.
    """

    def __init__(self, entities: Iterable[DictionaryEntity]) -> None:
        self.entities: dict[str, DictionaryEntity] = {}
        self._index: dict[tuple[str, ...], DictionaryEntity] = {}
        self.max_len = 1
        for ent in entities:
            self.entities.setdefault(ent.entity_id, ent)
            for surface in ent.surfaces:
                key = surface_key(surface)
                if not key:
                    continue
                self._index.setdefault(key, ent)
                self.max_len = max(self.max_len, len(key))

    def __len__(self) -> int:
        return len(self.entities)

    def num_surfaces(self) -> int:
        """Distinct surface keys the dictionary can match."""
        return len(self._index)

    def stats(self) -> dict[str, object]:
        """Compact, inspectable dictionary statistics for the extraction report."""
        by_type: dict[str, int] = {}
        for ent in self.entities.values():
            by_type[ent.entity_type.value] = by_type.get(ent.entity_type.value, 0) + 1
        return {
            "entities": len(self.entities),
            "surfaces": self.num_surfaces(),
            "by_type": dict(sorted(by_type.items())),
        }

    def find(self, text: str) -> list[EntityMention]:
        """Recognize dictionary entities in ``text`` by longest-match, with spans.

        Returns mentions in document order. Each mention's ``surface`` is the
        verbatim ``text[start:end]``, so a reader can verify it against the source.
        Matched tokens are consumed, so overlapping shorter matches inside a longer
        one are not double-counted.
        """
        toks = token_spans(text)
        n = len(toks)
        out: list[EntityMention] = []
        i = 0
        while i < n:
            matched: tuple[DictionaryEntity, int, int, int] | None = None
            for length in range(min(self.max_len, n - i), 0, -1):
                key = tuple(toks[i + j][0] for j in range(length))
                ent = self._index.get(key)
                if ent is not None:
                    start = toks[i][1]
                    end = toks[i + length - 1][2]
                    matched = (ent, start, end, length)
                    break
            if matched is None:
                i += 1
                continue
            ent, start, end, length = matched
            out.append(
                EntityMention(
                    entity_id=ent.entity_id,
                    canonical_name=ent.canonical_name,
                    entity_type=ent.entity_type.value,
                    surface=text[start:end],
                    start=start,
                    end=end,
                )
            )
            i += length
        return out


def build_dictionary(
    records: Iterable[DatabaseRecord], *, include_curated: bool = True
) -> EntityDictionary:
    """Build the entity dictionary from database records (+ the curated seed).

    UniProt protein records become protein entities; Open Targets associations add
    ``target_symbol`` surface synonyms to the protein they name. Pass
    ``include_curated=False`` to build a database-only dictionary (used to measure
    how much the curated seed contributes).
    """
    proteins: dict[str, dict] = {}
    gene_to_eid: dict[str, str] = {}

    for r in records:
        if r.source == "UniProt" and r.record_type == "protein":
            f = r.fields
            gene = f.get("gene")
            accession = f.get("accession") or r.record_id
            entity_id = f"ent-{gene}" if gene else f"ent-{accession}"
            surfaces: list[str] = []
            for key in ("gene", "common_name", "protein_name", "accession"):
                value = f.get(key)
                if isinstance(value, str) and value and value not in surfaces:
                    surfaces.append(value)
            xrefs = {"UniProt": accession}
            hgnc = (f.get("xrefs") or {}).get("HGNC_symbol")
            if hgnc:
                xrefs["HGNC"] = hgnc
            proteins[entity_id] = {
                "name": f.get("protein_name") or gene or accession,
                "type": EntityType.protein,
                "surfaces": surfaces,
                "xrefs": xrefs,
            }
            if gene:
                gene_to_eid[gene] = entity_id

    for r in records:
        if r.record_type == "association":
            gene = r.fields.get("target_gene")
            symbol = r.fields.get("target_symbol")
            entity_id = gene_to_eid.get(gene)
            if entity_id and isinstance(symbol, str):
                surfaces = proteins[entity_id]["surfaces"]
                if symbol not in surfaces:
                    surfaces.append(symbol)

    entities = [
        DictionaryEntity(
            entity_id=eid,
            canonical_name=d["name"],
            entity_type=d["type"],
            surfaces=tuple(d["surfaces"]),
            db_xrefs=d["xrefs"],
        )
        for eid, d in proteins.items()
    ]

    if include_curated:
        for name, etype, surfaces in CURATED_TERMS:
            entities.append(
                DictionaryEntity(
                    entity_id=f"ent-{_slug(name)}",
                    canonical_name=name,
                    entity_type=etype,
                    surfaces=surfaces,
                )
            )

    return EntityDictionary(entities)


__all__ = [
    "DictionaryEntity",
    "EntityDictionary",
    "build_dictionary",
    "CURATED_TERMS",
]
