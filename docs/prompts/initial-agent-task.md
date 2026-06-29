# Initial build prompt for Claude Code

You are working in the `bioscientist-os` repository: a CPU-first, evidence-centered
research workbench for biomedical literature.

Read:

- `CLAUDE.md`
- `docs/PLAN.md`

Then execute the plan milestone by milestone, starting at the next incomplete
milestone (Milestone 0 if none are done).

## Important instructions

- Implement exactly one milestone per run; do not implement later milestones.
- Do not push. Commit locally after each coherent milestone.
- Do not wait for human review; create the review placeholder and continue.
- Keep all default tests CPU-only and offline. Do not require paid LLM API calls.
- Honor the non-clinical safety rules in `docs/SAFETY.md`. Keep provenance on
  every claim, link, and evidence cell.
- Do not commit secrets, credentials, virtualenvs, caches (`data/cache/`,
  `.pytest_cache`, ...), `node_modules`, model weights, large datasets, generated
  `results/` artifacts, or `.claude/settings.local.json`.
- Update the multi-page website under `site/` at every milestone (content + the
  `milestones.html` status). Never describe an unimplemented feature as done.
- Keep documentation professional, precise, and honest about limitations. Avoid a
  "learning project" or marketing tone.

After each milestone, print:

- milestone title;
- commit hash;
- tests run;
- website pages updated;
- review placeholder path;
- next milestone.

Continue only if there is no blocker that would risk secrets, paid API spend, data
loss, or repository corruption. The milestone runner
(`scripts/run_all_milestones_with_claude.sh`) drives this loop one milestone at a
time and stops on any failure, dirty tree, or missing commit.
