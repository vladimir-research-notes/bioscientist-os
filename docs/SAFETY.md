# Safety and non-clinical-use statement

## TL;DR

`bioscientist-os` is a **research-assistance tool** for biomedical literature and
public-database metadata. It is **not** a medical device. It does **not** provide
diagnosis, treatment recommendations, drug-efficacy claims, or any
patient-specific clinical decision support. Outputs are for research triage and
hypothesis *organization* only.

## Non-clinical use (hard constraints)

The system, and any contributor extending it, must not:

- present output as medical advice, diagnosis, or treatment guidance;
- provide patient-specific clinical decision support;
- assert drug efficacy, safety, or dosing recommendations;
- imply that an extracted/inferred relation is a clinical fact.

Any output that could reasonably be read as clinical advice is a **defect** and
should be fixed or removed.

## Provenance and epistemic honesty

Every generated summary or memo must clearly separate, and visibly label, four
levels (see `docs/METHODOLOGY.md` and `docs/DATA_MODEL.md`):

1. **directly observed metadata** — copied from the record;
2. **extracted claim** — pulled from text by a named method, with the snippet;
3. **inferred relation** — asserted by combining records, with the basis shown;
4. **unsupported hypothesis** — a suggestion, explicitly *not* evidence.

The "support / conflict / unknown" signal describes **textual agreement between
claims**, not biological truth or study quality. Confidence values reflect
*extraction* confidence, not clinical certainty.

## Data handling

- No patient data. Fixtures are public-style or synthetic and labeled.
- No secrets, credentials, or private datasets are committed.
- Optional live connectors hit only public, non-credentialed endpoints and are
  off by default.

## Suggested-experiment outputs

The research memo (Milestone 9) may list "suggested next experiments." These are
**hypotheses for human researchers to evaluate**, explicitly marked as
unsupported, and are never instructions, protocols, or clinical recommendations.

## Reporting a safety concern

If any output reads as clinical advice or hides provenance, open an issue / note
it in the relevant `docs/review_notes/*` file describing the output and the
expected behavior. Treat it as a correctness bug.
