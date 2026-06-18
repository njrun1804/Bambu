---
name: bambu-operate
description: Use when operating the Bambu repo for photo-first 3D-print dioramas, intake, release-check, MCP use, or printer-safe hand holding.
---

# Bambu Operate

Bambu turns reference photos into reviewable build123d dioramas and slicing plans for a Bambu Lab A1 mini.

## Photo-first protocol

1. `bambu_context_view` + `bambu_doctor` (or `uv run bambu doctor`).
2. `bambu intake <photo> --intent "..."` (MCP: `bambu_intake`) — scaffolds project, copies photo to `photos/reference/`, emits vision prompt.
3. Fill `designs/v1/*.yaml` using vision on the reference photo (`agents/prompts/intake-from-photo.md`).
4. `bambu design-check <project> --revision v1` — must pass before CAD.
5. Author `source/v1/model.py` using `bambu.cad.archetypes.<archetype>` helpers. Multifuse entire scene; assert `len(scene.solids()) == 1`.
6. `bambu release-check <project> --revision v1` — FreeCAD, watertight mesh, overhangs, islands, Blender renders (150px thumbnail + face closeups).
7. Human approves renders, then **Bambu Studio GUI slice** (authoritative time/cost).
8. `bambu qc <sliced.gcode.3mf> --stl <model.stl>` + `bambu handoff`.
9. Manual print only after review.
10. `bambu record_print_result` after physical print.

## Safe surfaces

- MCP: `uv run bambu-mcp`
- CLI: `uv run bambu intake ~/photo.jpg --intent "..." --slug my-project`
- CLI: `uv run bambu design-check projects/best-buds-chair --revision v1`
- CLI: `uv run bambu release-check projects/best-buds-chair --revision v1 --no-render`
- CLI: `uv run bambu render-spec-sheet projects/best-buds-chair --revision v1`
- MCP: `bambu_release_check`, `bambu_qc`, `bambu_intake`

## Hard rules

- Specs gate acceptance; CAD is hand-authored (no automatic YAML→geometry on day one).
- build123d for likeness/diorama; OpenSCAD figurine lane is `examples/` only.
- Do not commit `private/`, photos under `photos/reference/`, or generated STL/3MF/G-code.
- Do not start print jobs without human approval.
- World Cup reference project lives in `projects/_archive/world-cup-neighbors/`.
