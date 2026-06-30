# Roadmap

## TL;DR

Near term: the 13 milestones in `docs/PLAN.md` (schemas → ingestion → search →
extraction → evidence tables → connectors → visualizations → evaluation → memo →
optional LLM adapter → polish → cleanup). Later: larger licensed corpora, stronger
auditable entity linking, and an empirical study of provenance's effect on trust.

## Near term — the milestones

See `docs/PLAN.md` and the website's *Milestones* page for live status. Each is a
single autonomous Claude run that commits locally; the runner stops on any
failure. **All 13 milestones (0–12) are delivered** — including the **optional,
cost-guarded LLM adapter** (M10), off the default path and mock-backed in tests
(see `docs/LLM_ADAPTER.md`); the website/report polish (M11); and the final
cleanup / quality-gate pass (M12), whose green gates are recorded in
`docs/RESULTS.md`. The planned build is complete; what follows is research
direction, not committed work.

## Later — research directions (honest)

- Larger, properly-licensed corpora and richer, multi-annotator gold labels.
- Gold support/conflict annotations so the evidence table's support label can be
  scored against a human verdict (Milestone 8 scores only the table's *structural*
  quality — completeness and provenance coverage).
- Ontology-grounded entity linking that preserves auditability (no opaque steps).
- A controlled comparison of transparent baselines vs. an optional LLM adapter on
  *provenance fidelity*, not just extraction recall.
- A user-facing study of which provenance fields actually change a scientist's
  trust or decision — the core methodological payoff.

These are directions, not promises. The repository is a platform/prototype unless
and until a novel empirical result is demonstrated. A candid assessment of the
publishable path — what the prototype establishes, what is deliberately missing,
and the threats to validity — is in `docs/PAPER_PATH.md`.

## Non-goals (unchanged)

No clinical decision support, no diagnosis/treatment claims, no production
knowledge graph, no benchmark leaderboard. See `docs/SAFETY.md` and
`docs/LIMITATIONS.md`.
