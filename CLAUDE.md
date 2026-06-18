# Bambu

Photo-first agent-assisted 3D-print preparation for a Bambu Lab A1 mini: reference photo → intake → YAML spec gates → hand-authored build123d → release-check → human-gated slice and print.

## Stack

- Python 3.11–3.12 (pinned 3.12 via `.python-version`), `uv`-managed
- Deps: build123d (CAD), PyYAML, mcp (local agent tool server)
- Optional: FreeCAD, Bambu Studio, OrcaSlicer, Blender
- CLI: `uv run bambu ...` — start with `bambu intake`, then `design-check`, `release-check`
- MCP: `uv run bambu-mcp` — `bambu_intake`, `bambu_release_check`, `bambu_qc`

## Test

```bash
uv run python -m unittest discover -s tests -v
uv run ruff check bambu tools tests
```

## Primary project

- `projects/best-buds-chair/` — seated woman + dog patio chair diorama (test case)
- `projects/_archive/world-cup-neighbors/` — archived standing figurine learning project

## Knowledge Surfaces

Cross-repo conventions live in **Zion** (`~/CC/Zion/CLAUDE.md`).
