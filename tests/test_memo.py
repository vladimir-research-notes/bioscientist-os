"""Tests for the end-to-end research-memo generator (Milestone 9).

The memo is the workbench's narrative capstone: it composes the M3 retrieval, M4
extraction, and M5 evidence table for one research question into a single
structured document. These tests pin the properties that make it trustworthy
rather than its exact prose:

* the four epistemic levels are visibly separated (observed metadata / extracted
  claim / inferred relation / unsupported hypothesis), and never collapsed;
* suggested next experiments are emitted **only** as explicitly *unsupported*
  hypotheses, framed as research questions — never as recommendations or advice;
* the non-clinical / no-medical-advice framing is present (a safety requirement);
* every evidence row carries full provenance (paper, verbatim snippet, exact span)
  and provenance coverage is 100% by construction;
* the memo's counts and database links reconcile exactly with the M5 evidence
  table it is built on (no new, unaudited computation);
* the designed cross-paper directional disagreement (autophagy promotes vs.
  restrains senescence) is surfaced as a *candidate* uncertainty;
* assembly is deterministic and offline.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from bioscientist_os import fixtures
from bioscientist_os.cli import app
from bioscientist_os.evidence import (
    EvidenceReport,
    build_dictionary,
    build_evidence_report,
    build_memo_report,
    extract_corpus,
    load_memo,
)
from bioscientist_os.evidence.dictionary import EntityDictionary
from bioscientist_os.evidence.memo import MemoReport
from bioscientist_os.evidence.model import ExtractionReport
from bioscientist_os.ingest import ingest_fixtures
from bioscientist_os.schemas import ResearchQuestion, SupportLabel

runner = CliRunner()


# --- fixtures / helpers ---------------------------------------------------


@pytest.fixture(scope="module")
def bundle() -> fixtures.FixtureBundle:
    return fixtures.load_all()


@pytest.fixture(scope="module")
def records(bundle: fixtures.FixtureBundle):
    return bundle.proteins + bundle.associations


@pytest.fixture(scope="module")
def dictionary(records) -> EntityDictionary:
    return build_dictionary(records)


@pytest.fixture(scope="module")
def extraction(bundle: fixtures.FixtureBundle, dictionary: EntityDictionary) -> ExtractionReport:
    return extract_corpus(bundle.papers, dictionary)


def _question(bundle: fixtures.FixtureBundle, qid: str) -> ResearchQuestion:
    return next(q for q in bundle.questions if q.question_id == qid)


def _memo(bundle, dictionary, extraction, records, question, **kw) -> MemoReport:
    return build_memo_report(question, bundle.papers, extraction, dictionary, records, **kw)


# --- structure + epistemic separation -------------------------------------

# All four epistemic-level tags the memo must visibly carry.
_LEVEL_TAGS = (
    "_[observed metadata]_",
    "_[extracted claim]_",
    "_[inferred relation]_",
    "_[unsupported hypothesis]_",
)

# The section headers PLAN.md requires the memo to contain.
_REQUIRED_SECTIONS = (
    "## 1. Research question",
    "## 2. Corpus and method",
    "## 3. Key papers",
    "## 4. Evidence table",
    "## 5. Database links",
    "## 6. Conflicts and uncertainties",
    "## 7. Suggested next experiments",
    "## 8. Limitations",
    "## 9. Provenance",
)


def test_markdown_has_all_required_sections(bundle, dictionary, extraction, records) -> None:
    q = _question(bundle, "rq-senescence-inflammation")
    md = _memo(bundle, dictionary, extraction, records, q).to_markdown()
    for section in _REQUIRED_SECTIONS:
        assert section in md, f"missing section: {section}"
    assert md.startswith("# Research memo: ")


def test_four_epistemic_levels_are_all_present_and_separated(
    bundle, dictionary, extraction, records
) -> None:
    q = _question(bundle, "rq-senescence-inflammation")
    md = _memo(bundle, dictionary, extraction, records, q).to_markdown()
    for tag in _LEVEL_TAGS:
        assert tag in md, f"missing epistemic-level tag: {tag}"
    # The legend lists all four levels explicitly.
    for level, _ in MemoReport.EPISTEMIC_LEGEND:
        assert level in md


def test_no_medical_advice_framing_present(bundle, dictionary, extraction, records) -> None:
    # A hard safety constraint: the memo must carry the non-clinical statement.
    q = _question(bundle, "rq-senescence-inflammation")
    md = _memo(bundle, dictionary, extraction, records, q).to_markdown()
    assert "Not medical advice" in md
    assert "medical-advice" in md  # footer reiterates it
    assert "not** a medical-advice" in md or "not a medical-advice" in md.replace("**", "")
    # The support label and links are labeled for what they are, not as verdicts.
    assert "heuristic" in md and "inferred relation" in md


# --- suggested next experiments are unsupported hypotheses only -----------


def test_hypotheses_are_all_unsupported_and_question_framed(
    bundle, dictionary, extraction, records
) -> None:
    q = _question(bundle, "rq-autophagy-senescence")
    report = _memo(bundle, dictionary, extraction, records, q)
    assert report.hypotheses, "expected at least one suggested hypothesis"
    for h in report.hypotheses:
        assert h.status == "unsupported"
        # Framed as a research question ("Whether ..."), never an imperative/recommendation.
        assert h.text.startswith("Whether ")
        assert h.basis
    md = report.to_markdown()
    assert "UNSUPPORTED HYPOTHESES" in md
    assert "not** evidence" in md or "not evidence" in md.replace("**", "")
    # rendered hypothesis lines are explicitly marked unsupported + untested
    assert md.count("Hypothesis (UNSUPPORTED):") == len(report.hypotheses)
    assert "UNTESTED" in md


def test_max_hypotheses_is_honored(bundle, dictionary, extraction, records) -> None:
    q = _question(bundle, "rq-senescence-inflammation")
    report = _memo(bundle, dictionary, extraction, records, q, max_hypotheses=2)
    assert len(report.hypotheses) == 2


# --- conflicts / uncertainties --------------------------------------------


def test_directional_disagreement_surfaces_autophagy_pair(
    bundle, dictionary, extraction, records
) -> None:
    # Papers 006 and 007 deliberately disagree on the direction of autophagy<->senescence.
    q = _question(bundle, "rq-autophagy-senescence")
    report = _memo(bundle, dictionary, extraction, records, q)
    pairs = {
        (d.entity_a, d.entity_b): d for d in report.directional_disagreements
    }
    key = ("autophagy", "cellular senescence")
    assert key in pairs, pairs.keys()
    d = pairs[key]
    assert set(d.relations) == {"promotes", "restrains"}
    papers = {c["paper_id"] for c in d.claims}
    assert {"biosci-paper-006", "biosci-paper-007"} <= papers
    # It is surfaced as a candidate to verify, not asserted as a real conflict.
    md = report.to_markdown()
    assert "candidate" in md.lower()
    assert "does **not** detect" in md or "not detect" in md.replace("**", "")


def test_conflict_rows_match_conflict_labels(bundle, dictionary, extraction, records) -> None:
    q = _question(bundle, "rq-senescence-inflammation")
    report = _memo(bundle, dictionary, extraction, records, q)
    assert report.conflict_rows  # the senescence corpus exercises conflict phrasing
    assert all(
        r.support_conflict_unknown is SupportLabel.conflict for r in report.conflict_rows
    )
    assert len(report.conflict_rows) == report.support_counts["conflict"]


# --- key papers ------------------------------------------------------------


def test_key_papers_only_contributors_ranked_with_retrieval_signal(
    bundle, dictionary, extraction, records
) -> None:
    q = _question(bundle, "rq-senescence-inflammation")
    report = _memo(bundle, dictionary, extraction, records, q, max_papers=4)
    assert report.key_papers
    assert len(report.key_papers) <= 4
    assert report.total_contributing_papers >= len(report.key_papers)

    row_paper_ids = {r.paper_id for r in report.evidence.rows}
    for k in report.key_papers:
        # only papers that actually contributed evidence rows are "key"
        assert k.paper_id in row_paper_ids
        assert k.num_evidence_rows >= 1
        assert sum(k.support_counts.values()) == k.num_evidence_rows
        assert k.bm25f_score >= 0.0

    # ranked by (-num_rows, -summed_confidence, -bm25f_score, paper_id)
    keys = [
        (-k.num_evidence_rows, -k.summed_confidence, -k.bm25f_score, k.paper_id)
        for k in report.key_papers
    ]
    assert keys == sorted(keys)


# --- database links reconcile with the M5 table ---------------------------


def test_database_links_match_evidence_and_detail_il6(
    bundle, dictionary, extraction, records
) -> None:
    q = _question(bundle, "rq-senescence-inflammation")
    report = _memo(bundle, dictionary, extraction, records, q)

    # the aggregate distinct links equal the union over the evidence rows
    union = sorted({link for r in report.evidence.rows for link in r.database_links})
    assert report.database_links == union
    assert "UniProt:P05231" in report.database_links
    assert "HGNC:IL6" in report.database_links
    assert "OpenTargets:OTAF-0002" in report.database_links

    # IL-6 appears in the per-entity link detail with xrefs + the association descriptor
    il6 = next((d for d in report.link_details if d.entity_name == "Interleukin-6"), None)
    assert il6 is not None
    assert il6.xrefs.get("UniProt") == "P05231"
    assert il6.xrefs.get("HGNC") == "IL6"
    assert any("OTAF-0002" in a and "inflammaging" in a for a in il6.associations)


def test_memo_counts_reconcile_with_m5_table(bundle, dictionary, extraction, records) -> None:
    # The memo introduces no new computation: its rows/labels equal the M5 table's.
    q = _question(bundle, "rq-autophagy-senescence")
    report = _memo(bundle, dictionary, extraction, records, q)
    table = build_evidence_report(q, extraction, dictionary, records)
    assert report.num_rows == table.num_rows
    assert report.support_counts == table.support_counts()
    assert report.evidence.provenance_coverage == 1.0


# --- provenance ------------------------------------------------------------


def test_every_evidence_row_in_json_carries_full_provenance(
    bundle, dictionary, extraction, records
) -> None:
    q = _question(bundle, "rq-senescence-inflammation")
    report = _memo(bundle, dictionary, extraction, records, q)
    rows = report.to_dict()["evidence_rows"]
    assert rows
    assert all(set(r) == set(EvidenceReport.EVIDENCE_COLUMNS) for r in rows)
    for r in rows:
        assert r["paper_id"]
        assert r["source_snippet"]
        assert r["char_start"] is not None and r["char_end"] is not None
        assert r["extraction_method"]
        assert r["epistemic_level"] == "extracted_claim"
    # the markdown renders the coverage line and every row's span
    md = report.to_markdown()
    assert "Provenance coverage: **100%**" in md
    assert "abstract chars [" in md


# --- filters passthrough ---------------------------------------------------


def test_min_confidence_and_limit_passthrough(bundle, dictionary, extraction, records) -> None:
    q = _question(bundle, "rq-senescence-inflammation")
    full = _memo(bundle, dictionary, extraction, records, q)
    filtered = _memo(bundle, dictionary, extraction, records, q, min_confidence=0.7)
    assert filtered.num_rows < full.num_rows
    assert all(r.confidence >= 0.7 for r in filtered.evidence.rows)
    limited = _memo(bundle, dictionary, extraction, records, q, limit=3)
    assert limited.num_rows == 3


# --- determinism + DB-backed equivalence ----------------------------------


def test_build_is_deterministic(bundle, dictionary, extraction, records) -> None:
    q = _question(bundle, "rq-senescence-inflammation")
    first = _memo(bundle, dictionary, extraction, records, q)
    second = _memo(bundle, dictionary, extraction, records, q)
    assert first.to_dict() == second.to_dict()
    assert first.to_markdown() == second.to_markdown()


def test_load_memo_matches_in_memory_build(
    tmp_path: Path, bundle, dictionary, extraction, records
) -> None:
    db = tmp_path / "bioscientist.db"
    ingest_fixtures(db_path=db)
    loaded = load_memo(db, question_id="rq-autophagy-senescence")
    q = _question(bundle, "rq-autophagy-senescence")
    built = _memo(bundle, dictionary, extraction, records, q)
    assert loaded.to_dict() == built.to_dict()
    assert loaded.to_markdown() == built.to_markdown()


def test_adhoc_question_resolves_and_builds(tmp_path: Path) -> None:
    db = tmp_path / "bioscientist.db"
    ingest_fixtures(db_path=db)
    report = load_memo(db, question_text="What about rapamycin and mTOR?")
    assert report.question.question_id.startswith("rq-adhoc-")
    # a free-text question still produces a valid, provenance-clean memo
    assert report.evidence.provenance_coverage == 1.0
    md = report.to_markdown()
    assert "# Research memo: What about rapamycin and mTOR?" in md


# --- CLI ------------------------------------------------------------------


@pytest.fixture(scope="module")
def cli_db(tmp_path_factory: pytest.TempPathFactory) -> Path:
    db = tmp_path_factory.mktemp("memocli") / "bioscientist.db"
    ingest_fixtures(db_path=db)
    return db


def test_cli_memo_markdown_output(cli_db: Path) -> None:
    res = runner.invoke(
        app,
        ["memo", "--db", str(cli_db),
         "--question", "What evidence links cellular senescence to chronic inflammation?"],
    )
    assert res.exit_code == 0, res.output
    assert res.output.startswith("# Research memo:")
    assert "Not medical advice" in res.output
    assert "UNSUPPORTED HYPOTHESES" in res.output
    assert "rq-senescence-inflammation" in res.output


def test_cli_memo_json_and_out(cli_db: Path, tmp_path: Path) -> None:
    out_md = tmp_path / "sub" / "memo.md"
    res = runner.invoke(
        app,
        ["memo", "--db", str(cli_db), "--question-id", "rq-autophagy-senescence",
         "--out", str(out_md), "--json"],
    )
    assert res.exit_code == 0, res.output
    payload = json.loads(res.output)
    assert payload["question"]["question_id"] == "rq-autophagy-senescence"
    assert payload["corpus"]["provenance_coverage"] == 1.0
    assert all(h["status"] == "unsupported" for h in payload["hypotheses"])

    # --out writes the Markdown memo (parent dirs created)
    assert out_md.is_file()
    assert out_md.read_text(encoding="utf-8").startswith("# Research memo:")


def test_cli_memo_requires_a_question(cli_db: Path) -> None:
    res = runner.invoke(app, ["memo", "--db", str(cli_db)])
    assert res.exit_code == 2
    assert "--question" in res.output


def test_cli_memo_unknown_question_id_errors(cli_db: Path) -> None:
    res = runner.invoke(app, ["memo", "--db", str(cli_db), "--question-id", "nope"])
    assert res.exit_code == 1
    assert "no stored research question" in res.output


def test_cli_memo_on_uninitialized_db_errors(tmp_path: Path) -> None:
    empty = tmp_path / "empty.db"
    empty.touch()
    res = runner.invoke(app, ["memo", "--db", str(empty), "--question", "anything"])
    assert res.exit_code == 1
    assert "not a bioscientist-os database" in res.output
