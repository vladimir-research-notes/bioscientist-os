# Website notes

## TL;DR

The website under `site/` is plain static HTML with one shared `style.css`. There
is **no build step** — open `site/index.html` in a browser (or serve the folder).
This is the lowest-friction, most reliable option and works offline.

## Pages

| File | Page |
|------|------|
| `index.html` | Overview |
| `architecture.html` | Architecture |
| `data-model.html` | Data model |
| `ingestion.html` | Ingestion |
| `evidence.html` | Evidence tables |
| `databases.html` | Database connectors |
| `visualizations.html` | Visualizations |
| `evaluation.html` | Evaluation |
| `results.html` | Results |
| `limitations.html` | Limitations |
| `safety.html` | Safety / non-clinical use |
| `reproducibility.html` | Reproducibility |
| `roadmap.html` | Roadmap |
| `milestones.html` | Milestones (live status) |

## Each page must contain

1. a brief explanation,
2. a deeper technical explanation,
3. current implementation status,
4. relevant files,
5. current test/result status,
6. open questions / limitations.

## Update discipline (every milestone)

- Update the page(s) for the subsystem the milestone touched.
- Update `milestones.html` status (Planned → Done) for the milestone.
- Never describe an unimplemented feature as done. The website must reflect the
  repository's actual state and the current contents of `docs/RESULTS.md`.

## Viewing locally

```bash
# Simplest: open the file directly.
xdg-open site/index.html        # or: open site/index.html (macOS)

# Or serve it (no external deps):
python3 -m http.server -d site 8000   # then visit http://localhost:8000
```

## Why not MkDocs

MkDocs is fine, but it adds a build step and a dependency. Hand-written static
HTML is viewable from a clean checkout with zero setup and survives offline/CI
constraints — matching the project's CPU-first, offline-first principles.
