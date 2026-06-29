#!/usr/bin/env bash
# -----------------------------------------------------------------------------
# Autonomous milestone runner for bioscientist-os.
#
# Runs the project milestones one at a time, each as a single `claude -p`
# invocation, committing locally after each. It mirrors the approach in
# ~/claude/code-agent-runtime: one milestone per Claude run, hard stops between
# milestones on any failure, dirty tree, missing commit, pytest failure, or the
# optional cost guard.
#
# Usage:
#   ./scripts/run_all_milestones_with_claude.sh            # milestones 0..12
#   ./scripts/run_all_milestones_with_claude.sh 3 5        # milestones 3..5
#   ./scripts/run_all_milestones_with_claude.sh 7          # milestone 7 only-ish (7..12)
#
# Environment knobs:
#   WEEKLY_BUDGET_USD  enable a best-effort cost guard (e.g. 50)
#   COST_FRACTION      stop fraction of that budget (default 0.80)
#   MAX_TURNS          per-milestone agent turn cap (runaway guard; empty = none)
#   MODEL              optional model id passed to `claude --model` (empty = default)
#
# It does NOT push. The permission policy in .claude/settings.json denies push,
# network fetch (curl/wget), and secret reads.
# -----------------------------------------------------------------------------
set -euo pipefail

# Resolve repo root from this script's location so it works from any CWD.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "$REPO_ROOT"

START="${1:-0}"
END="${2:-12}"

TEMPLATE="docs/prompts/run-one-milestone-template.md"

# ---------------------------------------------------------------------------
# Cost / usage guard (best-effort)
# ---------------------------------------------------------------------------
# Set WEEKLY_BUDGET_USD to enable. Before each milestone the script stops if the
# cumulative estimated cost has reached COST_FRACTION (default 0.80) of it. Cost
# comes from Claude Code's own `total_cost_usd` estimate (--output-format json).
# For Pro/Max subscriptions this is only an APPROXIMATION; the authoritative
# figure is the interactive `/usage` command. The guard can only stop BETWEEN
# milestones; use MAX_TURNS to bound a single milestone.
WEEKLY_BUDGET_USD="${WEEKLY_BUDGET_USD:-}"
COST_FRACTION="${COST_FRACTION:-0.80}"
MAX_TURNS="${MAX_TURNS:-}"
MODEL="${MODEL:-}"

LOG_DIR="logs"
COST_LOG="${LOG_DIR}/milestone-costs.log"
CUMULATIVE_USD=0

if ! command -v claude >/dev/null 2>&1; then
  echo "ERROR: the 'claude' CLI is not on PATH. Install Claude Code first."
  exit 1
fi

if [ ! -f "$TEMPLATE" ]; then
  echo "ERROR: missing $TEMPLATE"
  exit 1
fi

if ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  echo "ERROR: not inside a git work tree. Run 'git init' and make an initial commit first."
  exit 1
fi

if [ -n "$(git status --porcelain)" ]; then
  echo "ERROR: working tree is not clean. Commit or stash changes before running."
  git status --short
  exit 1
fi

mkdir -p "$LOG_DIR"

THRESHOLD_USD=""
if [ -n "$WEEKLY_BUDGET_USD" ]; then
  THRESHOLD_USD="$(python3 -c "print(f'{float(${WEEKLY_BUDGET_USD}) * float(${COST_FRACTION}):.4f}')")"
  echo "Cost guard : ON"
  echo "  weekly budget : \$${WEEKLY_BUDGET_USD}"
  echo "  stop fraction : ${COST_FRACTION}"
  echo "  stop at >=    : \$${THRESHOLD_USD} cumulative estimated cost"
else
  echo "Cost guard : OFF  (set WEEKLY_BUDGET_USD to enable a ${COST_FRACTION} stop)"
fi
[ -n "$MAX_TURNS" ] && echo "Per-milestone turn cap : ${MAX_TURNS}"
[ -n "$MODEL" ] && echo "Model                  : ${MODEL}"

echo "Running milestones $START..$END with Claude Code (one 'claude -p' run per milestone)."
echo "Stops on: Claude failure, no new commit, dirty tree, pytest failure, or cost guard."
echo

for MILESTONE in $(seq "$START" "$END"); do
  echo "======================================================================"
  echo "Milestone $MILESTONE"
  echo "======================================================================"

  # Pre-flight cost guard (only stops between milestones).
  if [ -n "$THRESHOLD_USD" ]; then
    OVER="$(python3 -c "print(1 if float(${CUMULATIVE_USD}) >= float(${THRESHOLD_USD}) else 0)")"
    if [ "$OVER" = "1" ]; then
      echo "COST GUARD TRIPPED: cumulative \$${CUMULATIVE_USD} >= \$${THRESHOLD_USD}."
      echo "Stopping BEFORE Milestone $MILESTONE to stay under ${COST_FRACTION} of your weekly budget."
      echo "Resume later with: ./scripts/run_all_milestones_with_claude.sh $MILESTONE $END"
      exit 0
    fi
  fi

  BEFORE_COMMIT="$(git rev-parse HEAD)"
  RUN_LOG="${LOG_DIR}/milestone-$(printf '%02d' "$MILESTONE").log"

  PROMPT="Use ${TEMPLATE}. Implement Milestone ${MILESTONE} only. Do not implement later milestones. Do not push. Commit locally when the milestone is complete. Stop after exactly this one milestone."

  CLAUDE_ARGS=(-p "$PROMPT" --output-format json)
  [ -n "$MAX_TURNS" ] && CLAUDE_ARGS+=(--max-turns "$MAX_TURNS")
  [ -n "$MODEL" ] && CLAUDE_ARGS+=(--model "$MODEL")

  # Run Claude; capture the JSON result to a log (gitignored via *.log).
  claude "${CLAUDE_ARGS[@]}" | tee "$RUN_LOG"
  echo

  # Surface the agent's final summary text (commit hash, tests, pages, next).
  python3 -c "import json; d=json.load(open('${RUN_LOG}')); print(d.get('result',''))" 2>/dev/null || true

  # Accumulate estimated cost.
  RUN_USD="$(python3 -c "import json; d=json.load(open('${RUN_LOG}')); print(d.get('total_cost_usd') or d.get('cost_usd') or 0)" 2>/dev/null || echo 0)"
  CUMULATIVE_USD="$(python3 -c "print(f'{float(${CUMULATIVE_USD}) + float(${RUN_USD}):.4f}')")"
  echo "$(date -u +%FT%TZ) milestone=$MILESTONE run_usd=$RUN_USD cumulative_usd=$CUMULATIVE_USD" >> "$COST_LOG"

  AFTER_COMMIT="$(git rev-parse HEAD)"

  if [ "$BEFORE_COMMIT" = "$AFTER_COMMIT" ]; then
    echo "ERROR: Milestone $MILESTONE did not create a new commit."
    echo "Stopping so you can inspect."
    git status
    exit 1
  fi

  if [ -n "$(git status --porcelain)" ]; then
    echo "ERROR: working tree is not clean after Milestone $MILESTONE."
    echo "Stopping so you can inspect."
    git status
    exit 1
  fi

  echo
  echo "Milestone $MILESTONE completed."
  echo "Commit        : $AFTER_COMMIT"
  echo "Run est. cost : \$${RUN_USD}"
  echo "Cumulative    : \$${CUMULATIVE_USD}"
  echo

  if [ -f pyproject.toml ]; then
    echo "Running smoke validation after Milestone $MILESTONE..."
    python3 -m pytest -q || {
      echo "ERROR: pytest failed after Milestone $MILESTONE."
      echo "Stopping so you can inspect."
      exit 1
    }
  fi

  echo
done

echo "======================================================================"
echo "All requested milestones completed: $START..$END"
echo "Total estimated cost: \$${CUMULATIVE_USD}"
echo "======================================================================"
git log --oneline -20
