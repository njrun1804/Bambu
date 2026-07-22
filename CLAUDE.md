# Bambu

## Agent verification loop

- Each implementation task names and runs its exact targeted checks.
- Subagents set `CHECK_PROFILE=focused`, run only those commands, and never invoke `check.sh`.
- Before delivery, root reuses an unchanged strict receipt or runs the authoritative gate once and
  verifies it with `scripts/check-status.sh --strict`.

Bambu is a photo-first, safety-conscious 3D-print workbench for a Bambu Lab A1 mini.

Workspace-wide rules live in `~/CC/Zion/CLAUDE.md`; this file records only what is specific to
Bambu.

## Search and Code Intelligence

- Use `rg`/`fd` for live repo evidence and file discovery.
- Use `ast-grep` for syntax-shape searches.
- This is a Python repo: use `uv`, `pyproject.toml`, `uv.lock`, `ruff`, and `unittest`.
- Use Pyright only when it provides useful signal for the touched area.

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
- Meshy-AI mesh lane: `bambu/pipeline.py` → `meshy.py` (`MeshyClient`) → `mesh.py` /
  `mesh_fusion.py` / `mesh_lane.py`, plus `figurine.py`, `printability.py`, `slicer.py`,
  `preflight.py` — the mesh-generation + fusion pipeline alongside the photo-first CAD loop.
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
