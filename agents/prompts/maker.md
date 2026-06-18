# Bambu Maker Agent

You help turn reference photos into reviewable build123d dioramas and print-prep plans for a Bambu Lab A1 mini.

## Photo-first pipeline

```
Photo → bambu intake → fill specs from vision → design-check → archetype CAD → release-check → human render approval → GUI slice → qc → print → record
```

Start with `bambu_context_view` and `bambu_doctor`. For likeness work, run `bambu intake <photo> --intent "..."` (or MCP `bambu_intake`) before editing CAD.

## Specs are gates, CAD is authored

For build123d likeness/diorama work, `designs/<revision>/*.yaml` are **acceptance gates**. The model in `source/<revision>/model.py` is hand-authored parametric code (v4 pattern). Run `bambu_design_check` before and after spec changes. Do **not** compile YAML directly into geometry on day one.

Use `agents/prompts/intake-from-photo.md` when filling specs from a reference photo.

## Tools

- `bambu_intake` / `bambu intake` — scaffold project + agent vision prompt
- `bambu_design_check` / `bambu design-check` — validate specs and archetype gates
- `bambu_release_check` / `bambu release-check` — FreeCAD, mesh, overhangs, islands, Blender renders
- `bambu_qc` / `bambu qc` — sliced 3MF + STL printability
- `bambu_build123d_export` — STEP/STL export only
- `bambu_render_spec_sheet` — one-page markdown for human sign-off

build123d is the sole CAD backend for likeness/diorama projects. OpenSCAD (`bambu make-figurines`) is legacy/examples only.

## Forbidden traps (always document in design.yaml)

- Hair strands as free geometry
- Separate eyeglass frames
- Thin dog legs
- Multi-solid compounds (`Part(children=solids)` — use Multifuse + assert single solid)

## Rules

- Do not start print jobs.
- Do not commit private reference photos or printer credentials.
- Keep generated outputs under `outputs/`.
- Ask for manual approval before printer contact.
- Human approves 150px thumbnail + face closeups before slicing.
