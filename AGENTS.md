# AGENTS.md - Bambu

Bambu is a photo-first, safety-conscious 3D-print workbench for a Bambu Lab A1 mini.

## Working Rules

- Keep private reference photos under `projects/<slug>/photos/reference/` (gitignored); never commit them.
- Keep generated STL, 3MF, G-code, and PNG outputs out of git unless explicitly requested.
- Do not add automatic printer-start behavior.
- build123d is the sole CAD backend for likeness/diorama work. OpenSCAD figurines are `examples/` only.
- Specs in `designs/<rev>/*.yaml` are **gates**; CAD in `source/<rev>/model.py` is hand-authored (v4 pattern).
- Treat slicer output as a plan, not proof. Human approves 150px thumbnail + face closeups before slicing.

## Repo Shape

- `bambu/intake.py`: photo-first project scaffolding and agent vision prompt.
- `bambu/cad/`: fusion-safe build123d library (primitives, heads, animals, furniture, archetypes).
- `bambu/design_pipeline.py`: archetype-aware spec validation + `render_spec_sheet`.
- `bambu/review3d.py`: FreeCAD + Blender (thumbnail crop, paint-guide, dynamic face closeups).
- `bambu/cli.py`: intake, design-check, release-check, render-spec-sheet, qc, handoff.
- `bambu/mcp_server.py`: MCP tools including `bambu_intake`, `bambu_release_check`, `bambu_qc`.
- `profiles/archetypes/`: seated_diorama and future scene grammars.
- `agents/prompts/intake-from-photo.md`: vision checklist for spec filling.
- `projects/<slug>/`: manifests, designs/, references/, source/, reviews/.
- `projects/_archive/world-cup-neighbors/`: archived World Cup learning project.
- `examples/world-cup-neighbors/`: legacy OpenSCAD figurine docs.

## Verification

```bash
uv run python -m unittest discover -s tests -v
uv run ruff check bambu tools tests
```

## Primary loop

```
Photo → bambu intake → fill specs → design-check → archetype CAD → release-check → human renders → GUI slice → qc → print → record
```
