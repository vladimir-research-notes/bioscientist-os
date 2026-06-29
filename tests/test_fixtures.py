"""Tests for the committed fixtures and their loader (Milestone 1).

The committed corpus is tiny and theme-focused (cellular senescence / longevity /
autophagy). These tests assert it loads and validates against the schemas, that
every record is labeled (`synthetic`) and stamped (`data_source = fixture`), and
that the loader fails loudly on malformed input.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from bioscientist_os import fixtures
from bioscientist_os.schemas import DatabaseRecord, DataSource, Paper, ResearchQuestion


def test_fixtures_load_and_validate() -> None:
    bundle = fixtures.load_all()
    summary = bundle.summary()
    # Plan calls for 15-30 papers, 5-10 proteins, a handful of links.
    assert 15 <= summary["papers"] <= 30
    assert 5 <= summary["proteins"] <= 10
    assert summary["associations"] >= 3
    assert summary["questions"] >= 1
    assert all(isinstance(p, Paper) for p in bundle.papers)
    assert all(isinstance(r, DatabaseRecord) for r in bundle.proteins)
    assert all(isinstance(q, ResearchQuestion) for q in bundle.questions)


def test_every_record_is_stamped_fixture() -> None:
    bundle = fixtures.load_all()
    for rec in (*bundle.papers, *bundle.proteins, *bundle.associations):
        assert rec.data_source is DataSource.fixture


def test_synthetic_flag_is_present_and_correct() -> None:
    """Every paper/record carries an explicit synthetic flag with the labeling we documented."""
    bundle = fixtures.load_all()
    # Papers: all abstracts are fabricated.
    assert all(p.synthetic is True for p in bundle.papers)
    # Proteins: modeled on real public UniProt records.
    assert all(r.synthetic is False for r in bundle.proteins)
    # Associations: scores are fabricated.
    assert all(r.synthetic is True for r in bundle.associations)


def test_paper_ids_unique_and_external_ids_are_synthetic() -> None:
    bundle = fixtures.load_all()
    ids = [p.paper_id for p in bundle.papers]
    assert len(ids) == len(set(ids)), "paper_ids must be unique"
    for p in bundle.papers:
        doi = p.external_ids.get("DOI", "")
        # The reserved 10.0000/ test prefix guarantees these do not resolve to real papers.
        assert doi.startswith("10.0000/"), f"{p.paper_id} should use a non-resolving test DOI"


def test_protein_records_have_accession_and_gene() -> None:
    bundle = fixtures.load_all()
    seen_genes = set()
    for r in bundle.proteins:
        assert r.source == "UniProt"
        assert r.record_type == "protein"
        # The record_id is the UniProt accession, mirrored in the payload.
        assert r.fields.get("accession") == r.record_id
        gene = r.fields.get("gene")
        assert gene, f"{r.record_id} missing gene symbol"
        seen_genes.add(gene)
    # Sanity: the corpus's headline senescence/longevity genes are present.
    assert {"IL6", "CDKN2A", "TP53", "MTOR", "FOXO3"} <= seen_genes


def test_association_records_shape() -> None:
    bundle = fixtures.load_all()
    for r in bundle.associations:
        assert r.source == "OpenTargets"
        assert r.record_type == "association"
        assert r.fields.get("target_gene")
        score = r.fields.get("association_score")
        assert isinstance(score, (int, float)) and 0.0 <= score <= 1.0
        # Disease ids are explicit synthetic placeholders, not real ontology ids.
        assert str(r.fields.get("disease_id", "")).startswith("SYN-DIS-")


def test_loading_is_deterministic() -> None:
    assert fixtures.load_all() == fixtures.load_all()


# --- error handling -------------------------------------------------------


def _write_papers(root: Path, records: list[dict]) -> None:
    (root / "papers").mkdir(parents=True, exist_ok=True)
    (root / "papers" / "papers.json").write_text(json.dumps(records), encoding="utf-8")


def test_missing_file_raises_fixture_error(tmp_path: Path) -> None:
    with pytest.raises(fixtures.FixtureError, match="not found"):
        fixtures.load_papers(root=tmp_path)


def test_invalid_record_raises_fixture_error_with_index(tmp_path: Path) -> None:
    # Second record is missing the required `synthetic` flag.
    _write_papers(
        tmp_path,
        [
            {"paper_id": "p1", "title": "ok", "abstract": "", "synthetic": True},
            {"paper_id": "p2", "title": "bad", "abstract": ""},
        ],
    )
    with pytest.raises(fixtures.FixtureError, match=r"papers\.json\[1\]"):
        fixtures.load_papers(root=tmp_path)


def test_fixture_cannot_set_loader_stamped_field(tmp_path: Path) -> None:
    # A fixture that hard-codes data_source conflicts with the loader's stamp.
    record = {
        "paper_id": "p1",
        "title": "t",
        "abstract": "",
        "synthetic": True,
        "data_source": "live",
    }
    _write_papers(tmp_path, [record])
    with pytest.raises(fixtures.FixtureError, match="loader-stamped"):
        fixtures.load_papers(root=tmp_path)


def test_non_array_fixture_raises(tmp_path: Path) -> None:
    (tmp_path / "papers").mkdir(parents=True)
    (tmp_path / "papers" / "papers.json").write_text('{"not": "an array"}', encoding="utf-8")
    with pytest.raises(fixtures.FixtureError, match="expected a JSON array"):
        fixtures.load_papers(root=tmp_path)
