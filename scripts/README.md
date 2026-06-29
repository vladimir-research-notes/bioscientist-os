# scripts/

Thin, install-free wrappers and the autonomous milestone runner.

| Script | Purpose | Created in |
|--------|---------|-----------|
| `run_all_milestones_with_claude.sh` | autonomous milestone runner (one `claude -p` per milestone) | setup |
| `00_check_environment.py` | offline, stdlib-only environment report | setup |
| `01_ingest_fixtures.py` | ingest fixtures → `results/raw/bioscientist.db` | Milestone 2 |
| `02_build_index.py` | build search index / topics | Milestone 3 |
| `03_extract_claims.py` | extract entities + claims | Milestone 4 |
| `04_build_evidence_table.py` | build evidence table for a question | Milestone 5 |
| `05_generate_visualizations.py` | regenerate figures under `results/figures/` | Milestone 7 |
| `06_run_eval.py` | run the evaluation harness | Milestone 8 |

The numbered pipeline scripts (`01`–`06`) are created by the milestones that
introduce their functionality. Each is a thin wrapper around the
`bioscientist_os` package and prints exactly what it wrote.

## Running the milestone build

```bash
./scripts/run_all_milestones_with_claude.sh         # milestones 0..12
./scripts/run_all_milestones_with_claude.sh 3 5     # a specific range
WEEKLY_BUDGET_USD=50 MAX_TURNS=200 \
  ./scripts/run_all_milestones_with_claude.sh       # with cost + turn guards
```

See `docs/REPRODUCIBILITY.md` for details and `.claude/settings.json` for the
permission policy (no push, no network fetch, no secret reads).
