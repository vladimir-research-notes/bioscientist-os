# Human-review notes

One file per milestone: `XX-<short-name>-human-review.md`. These are written by
the autonomous build as **placeholders for a human reviewer**. The build never
claims that human review happened; it only prepares the note and fills the
`Human feedback` section with a placeholder for a person to complete later.

Required structure:

```markdown
# Human review: <milestone title>

## TL;DR
## What changed
## Commands run
## Test status
## Known limitations
## Possible misleading artifacts
## Human feedback
<!-- Human will fill this later. -->
```

The "Possible misleading artifacts" section is mandatory: it forces the build to
name ways a reader could over-trust the output (clean tables, synthetic fixtures,
small-N metrics, heuristic support/conflict labels).
