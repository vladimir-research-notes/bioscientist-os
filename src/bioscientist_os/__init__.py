"""bioscientist-os: a CPU-first, evidence-centered research workbench.

The package ingests small biomedical paper corpora, normalizes them, searches
and clusters them, extracts **structured claims** with transparent non-LLM
baselines, links claims to biological entities and database records, and
assembles **evidence tables** in which every cell carries explicit provenance.

The key artifact is the inspectable chain, not a summary::

    paper -> extracted claim -> biological entities -> database links
          -> support / conflict / uncertainty -> visual report

This module is intentionally import-light: importing ``bioscientist_os`` pulls in
no third-party dependency, so the offline environment check
(``bioscientist_os.environment``) and the package metadata can be read on a host
that has not yet installed the core dependencies. Heavier imports (``typer`` in
:mod:`bioscientist_os.cli`, ``pydantic`` in later milestones) live in the
submodules that need them.

Subpackages are created empty-but-importable at Milestone 0 and gain real
behavior milestone by milestone (see ``docs/PLAN.md``):

============== ============================================== ==========
subpackage     responsibility                                 milestone
============== ============================================== ==========
schemas         typed pydantic models + provenance fields      M1
ingest          fixture loaders, normalization                 M2
storage         sqlite / duckdb persistence                    M2
search          lexical + TF-IDF search, topic grouping        M3
evidence        entity + claim extraction, evidence tables     M4-M5
databases       connector interface + offline-first adapters   M6
visualization   timeline, clusters, evidence matrix, graph     M7
evals           gold-label evaluation harness                  M8
============== ============================================== ==========

One further subpackage is **optional and off the pipeline**: ``llm`` (Milestone 10)
is a disabled-by-default, cost-guarded LLM-adapter layer that the default path and
the test suite never use. It is intentionally *not* listed in :data:`SUBPACKAGES`
(those are the core pipeline subpackages); see ``docs/LLM_ADAPTER.md``.
"""

from __future__ import annotations

__version__ = "0.0.0"

PACKAGE_NAME = "bioscientist-os"

DESCRIPTION = (
    "CPU-first, evidence-centered research workbench for biomedical literature: "
    "ingest papers, extract structured claims with transparent non-LLM baselines, "
    "link them to biological entities and database records, and build inspectable "
    "evidence tables in which every cell carries explicit provenance."
)

# The four epistemic levels the project never collapses. Every evidence-table
# cell and every memo line is tagged with exactly one of these. The gloss is the
# short description shown by ``biosci info``. See docs/PLAN.md and docs/SAFETY.md.
EPISTEMIC_LEVELS: tuple[tuple[str, str], ...] = (
    ("observed metadata", "title, authors, year, IDs — directly read from a record"),
    ("extracted claim", "a sentence/relation pulled from text by a named method"),
    ("inferred relation", "a link asserted by combining records, not stated outright"),
    ("unsupported hypothesis", "a suggestion, explicitly flagged as not evidence"),
)

# Hard constraint surfaced in the CLI and docs: this is a research-assistance
# tool, not a clinical one. See docs/SAFETY.md for the full statement.
SAFETY_NOTE = (
    "bioscientist-os is a research-assistance tool, NOT a medical-advice, "
    "diagnostic, or treatment-recommendation tool. It gives no diagnosis, "
    "treatment, or drug-efficacy advice. See docs/SAFETY.md."
)

# The named subpackages, in pipeline order. Kept here so tests and docs can
# assert the skeleton matches the plan without hardcoding the list twice.
SUBPACKAGES: tuple[str, ...] = (
    "ingest",
    "search",
    "evidence",
    "databases",
    "visualization",
    "storage",
    "evals",
)

__all__ = [
    "__version__",
    "PACKAGE_NAME",
    "DESCRIPTION",
    "EPISTEMIC_LEVELS",
    "SAFETY_NOTE",
    "SUBPACKAGES",
]
