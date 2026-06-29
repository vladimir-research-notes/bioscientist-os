Read `CLAUDE.md` and `docs/PLAN.md`. Inspect `git status`, `git log --oneline -5`,
`docs/milestones/`, `docs/review_notes/`, and `docs/commits/`. Determine the next
incomplete milestone unless a specific milestone number is provided. Implement
exactly one milestone from `docs/PLAN.md`. Do not implement later milestones.

Honor the project's hard constraints: CPU-only, offline-by-default, no paid API in
the default path, no secrets/caches/large data committed, and the non-clinical
safety rules in `docs/SAFETY.md`. Keep provenance fields on every claim, link, and
evidence cell.

Run that milestone's validation commands (tests + the relevant smoke script).
Update the relevant docs and the multi-page website under `site/` (including the
`milestones.html` status). Create or update the milestone note
(`docs/milestones/XX-...md`), the human-review placeholder
(`docs/review_notes/XX-...-human-review.md`), and, if used, the commit note
(`docs/commits/XX-...md`).

Before committing: run the tests, run the smoke script, check `git status`, and
confirm no secrets/caches/large data/virtualenvs are staged. Then `git add -A` and
commit locally with a specific, professional message. Do not push.

Stop after exactly one milestone and print: milestone title, commit hash, tests
run, website pages updated, review placeholder path, and the next milestone.
