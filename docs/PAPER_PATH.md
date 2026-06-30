# From prototype to a research paper (a candid assessment)

## TL;DR

`bioscientist-os` is, as of Milestone 12, a **working prototype and a platform** —
not a research result. It demonstrates that a literature→evidence pipeline can be
built so that every output traces back to a specific paper, snippet, extraction
method, and `data_source`, and so that four epistemic levels (observed metadata,
extracted claim, inferred relation, unsupported hypothesis) are never collapsed.
That is an **engineering and methodological** contribution. It is **not** an
empirical finding, and nothing here has been validated at a scale or with a study
design that would support a scientific claim. This document states honestly what
would have to be true for a credible paper to come out of this line of work, and
what is deliberately missing today.

## What the prototype actually establishes

These are claims the repository can currently back with a test, a reproducible
command, or a measured table (see `docs/RESULTS.md`, `docs/EVALUATION.md`):

- A small biomedical corpus can be ingested into a **deterministic** local store
  (same fixtures → identical content digest), searched (BM25F), grouped into
  topics, and run through a **transparent, non-LLM** entity/claim extractor whose
  every span round-trips against the source abstract.
- Evidence tables can be assembled per research question with **100% per-cell
  provenance coverage by construction** (a row is only emitted when it already
  carries a paper id and a source snippet), each cell tagged with its epistemic
  level and a heuristic support/conflict/unknown signal.
- The pipeline can **evaluate itself** against committed gold labels with explicit
  denominators and 95% Wilson intervals, and is honest that small N → wide
  intervals.
- The whole default path runs **CPU-only and offline**; any LLM is optional,
  off by default, mock-backed in tests, and cost-guarded.

None of the above is a claim about biology. Every measured number describes
**pipeline behavior on a tiny, partly-synthetic, theme-focused fixture set**.

## What it explicitly is *not* (yet)

- Not a measurement of recall/precision against the real literature. The corpus is
  18 papers on one theme, several synthetic; the gold labels reflect the authors'
  judgment on that narrow theme.
- Not a validated extractor. Dictionary NER and template relations are deliberately
  simple; recall is low and brittle to paraphrase/negation by design.
- Not an adjudicator of biological correctness. "Support/conflict/unknown" is a
  *textual* signal about one sentence's phrasing, and it does not even detect
  cross-paper *directional* conflict on its own (a documented limitation; the memo
  surfaces such pairs only as candidates for a human).
- Not a clinical tool of any kind (`docs/SAFETY.md`).

## The actual research question

The publishable idea here is **methodological**, and it is a question about
*people*, not about F1:

> Which provenance fields, and which separation of epistemic levels, measurably
> change whether a biomedical scientist can correctly **audit** an evidence table —
> accept a well-supported claim, reject an over-stated one, and notice a conflict —
> compared to an opaque summary of the same papers?

Phrased that way, the contribution is not "our extractor is good"; it is "here is a
provenance design, and here is evidence that it improves human auditing." Extraction
quality is a *confound to control*, not the result.

## What a credible paper would require (the gaps)

In rough order of how load-bearing each gap is:

1. **A human-subjects study on auditability.** The core payoff. Give scientists
   evidence tables with vs. without specific provenance fields (snippet spans,
   method labels, support/conflict, database links) and measure decision accuracy,
   calibration, and time. Without this, the central claim is untested. This needs
   IRB review, a task design, and enough participants for the effect size — none of
   which exists here.
2. **Gold support/conflict annotations.** Today Milestone 8 scores only the table's
   *structural* quality (completeness, provenance coverage). To claim the
   support/conflict signal is useful, it must be scored against multi-annotator
   human verdicts with inter-annotator agreement reported.
3. **A real, properly-licensed corpus.** Hundreds–thousands of papers from a source
   whose license permits redistribution or whose access is reproducible, replacing
   synthetic fixtures. Sampling and inclusion criteria must be pre-registered to
   avoid theme cherry-picking.
4. **Ontology-grounded entity linking that stays auditable.** Replace the fixture
   dictionary with linking to a standard ontology (e.g. a gene/protein/disease
   vocabulary) *without* introducing an opaque step — every link still inspectable.
5. **A controlled transparent-baseline vs. LLM-adapter comparison — on provenance
   fidelity, not recall.** The interesting question is whether an LLM produces
   *more faithfully attributable* claims, not just more of them; measure how often
   each method's output can be traced to a correct supporting span.
6. **Robustness and generalization.** Multiple themes/domains, sensitivity to
   corpus size, and a determinism/version-drift analysis beyond the current
   single-machine guarantee.

## Honest threats to validity (even if the gaps were closed)

- **Construct validity:** "auditability" must be operationalized into a task whose
  outcome is not trivially driven by extraction errors.
- **Generalization:** results on one theme/ontology may not transfer.
- **Annotator bias:** gold labels and "correct audit" judgments encode expert
  opinion; agreement and adjudication must be reported, not hidden.
- **The provenance/quality confound:** better provenance can't rescue wrong
  extractions; a study must separate "the claim is wrong" from "the provenance is
  insufficient."

## Realistic near-term steps (still prototype-scale)

These are achievable without overclaiming and move toward, not past, a paper:

- Add gold support/conflict labels for the existing fixtures and an evaluator for
  them, reporting agreement and clearly labeling the tiny N.
- Add 1–2 additional themes as fixtures to probe cross-theme behavior.
- Prototype an auditability task (even at pilot N) to pressure-test the task design
  before any real study.
- Implement a minimal ontology-linking pass behind the existing connector interface
  and measure its auditability cost.

## Where this fits

If pursued, the most defensible framing is a **methods / resources** paper or a
**human-factors** study about evidence provenance in literature triage — explicitly
*not* a biomedical-findings paper and *not* an extraction-SOTA paper. Until at least
gaps (1) and (2) are closed, the right description of this repository is exactly
what it says on the website: a **prototype workbench** that makes provenance
inspectable, with honest, reproducible, small-N pipeline measurements and no
biological or clinical claims.

See also: `docs/ROADMAP.md` (directions), `docs/LIMITATIONS.md` (what not to read
into the numbers), `docs/EVALUATION.md` (what is and isn't measured), and
`docs/SAFETY.md` (non-clinical scope).
