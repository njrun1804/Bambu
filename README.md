# Bambu

Agent-assisted 3D-print preparation for a **Bambu Lab A1 mini**.

Bambu is a photo-first workbench for turning reference images into print-safe build123d caricature dioramas on a **Bambu Lab A1 mini**, with human-gated slicing and printing. build123d is the sole CAD backend for likeness work; OpenSCAD remains in `examples/` for legacy/simple models.

## What It Does Today

- **`bambu intake`** — copy reference photo, scaffold specs, emit agent vision prompt.
- **Archetype profiles** (`seated_diorama`, etc.) with fusion-safe dimension and forbidden-trap gates.
- **`bambu/cad/` library** — v4 OCCT primitives, heads, animals, furniture, seated diorama composer.
- **`bambu design-check`** — validate YAML specs before CAD (no hardcoded subject names).
- **`bambu release-check`** — FreeCAD STEP, watertight mesh, overhangs, floating islands, Blender renders (150px thumbnail + dynamic face closeups).
- **`bambu render-spec-sheet`** — one-page markdown for human sign-off.
- MCP parity: `bambu_intake`, `bambu_release_check`, `bambu_qc`.
- Checks local tools, creates project workspaces, syncs artifact hashes, QC on sliced 3MF.
- Keeps private photos and generated meshes out of git.

## Quick Start

```bash
git clone https://github.com/njrun1804/Bambu.git
cd Bambu
uv run bambu doctor
uv run bambu intake ~/path/to/photo.jpg \
  --intent "Woman with dog on patio chair diorama" \
  --slug best-buds-chair
uv run bambu design-check projects/best-buds-chair --revision v1
uv run bambu release-check projects/best-buds-chair --revision v1 --no-render
```

Fill `designs/v1/*.yaml` from the reference photo (see `agents/prompts/intake-from-photo.md`), then author or refine `source/v1/model.py`. Legacy OpenSCAD figurines: `examples/world-cup-neighbors/`.

## Recommended Human-Agent Loop

1. `uv run bambu doctor` or MCP `bambu_context_view`.
2. `uv run bambu intake <photo> --intent "..."` — scaffold project + vision prompt.
3. Agent fills `designs/v1/*.yaml`; run `uv run bambu design-check <project> --revision v1`.
4. Author `source/v1/model.py` with `bambu.cad.archetypes.*` helpers (Multifuse + single solid).
5. `uv run bambu release-check <project> --revision v1` until all gates pass; human approves 150px thumbnail + face closeups.
6. Slice in **Bambu Studio GUI**, then `uv run bambu qc <sliced> --stl <model.stl>` and `uv run bambu handoff`.
7. Print only after manual review; record with `uv run bambu record-print-result`.

## Agent Operating Substrate

General model work lives under `projects/<slug>/`. Each project has a `project.yaml` manifest, `source/`, `reviews/`, `measurements/`, `photos/`, and `artifacts.json`.

Agents should answer these questions from repo state instead of improvising:

- What printer/material/plate constraints apply?
- Which CAD lane is this model in?
- Which files are source-of-truth versus generated?
- What validation has passed?
- What is the next safe action?
- What physical print feedback should inform the next revision?

The serious CAD default is `build123d`. OpenSCAD remains the simple public/remixable lane and the current figurine first-pass lane. Bambu Studio is the blessed slicer path, OrcaSlicer is a fallback/comparison path, and printer contact remains manual only.

For build123d projects, the first export gate is:

```bash
uv run bambu export-build123d projects/<slug> --output-dir outputs
uv run bambu sync-artifacts projects/<slug> --outputs-root outputs
```

That writes STEP/STL files locally, records artifact hashes, and reports whether the build123d bounding box fits the A1 mini volume. It does not slice or print.

The stronger CAD review gate is:

```bash
uv run python tools/review_3d.py projects/<slug>
```

That regenerates STEP/STL, runs the STEP through FreeCAD console mode for shape validity, solids, bounding box, volume, tessellation, and OpenCASCADE geometry checks, then renders Blender preview PNGs if Blender is installed. It never contacts Bambu Studio or the printer.

For agentic v3 work, the first gate is the structured design check:

```bash
uv run bambu design-check projects/<slug> --revision v3
```

That reads `designs/v3/*.yaml` and verifies the project has explicit intent, printer constraints, people/likeness cues, visual acceptance views, review tools, and next agent actions before any CAD source is generated. The design spec is the source of truth; build123d code is downstream.

## Python Runtime And External Tools

This repo is pinned to Python 3.12 through `.python-version` because build123d's current CAD stack is not available for every newer Python runtime. Use `uv run ...` for repo commands so the correct environment is used.

Python dependencies include:

- **build123d**: default serious Python CAD backend.
- **PyYAML**: project manifest and context parsing.
- **mcp**: local agent tool server.

External tools are optional but useful:

- **OpenSCAD**: exports `.scad` to `.stl`, `.3mf`, or `.png`.
- **FreeCAD**: headless STEP/BRep inspection through `/Applications/FreeCAD.app/Contents/MacOS/FreeCAD -c`.
- **Bambu Studio**: slices and exports `.gcode.3mf` for Bambu printers.
- **OrcaSlicer**: alternate slicer CLI.
- **Blender**: preview rendering, and later sculpting/mesh repair for more organic figurines.

On Mike's Mac, the verified toolchain is:

- `openscad@snapshot` 2026.06.10
- Bambu Studio 02.07.01.57
- OrcaSlicer 2.3.2
- Blender 5.1.2
- FreeCAD 1.1.1

Run:

```bash
uv run bambu doctor
```

That command tells you what is missing and what to do next.

## World Cup Figurine Example

Full safe prototype build:

```bash
uv run bambu prototype-world-cup --output-dir outputs --slicer bambu-studio
uv run bambu handoff
```

This creates:

- `outputs/world-cup-neighbors.scad`
- `outputs/world-cup-neighbors.stl`
- `outputs/world-cup-neighbors.gcode.3mf`

It does not send anything to the printer. Open the sliced project in Bambu Studio, inspect supports, scale, filament, bed type, and first layer, then manually print if it looks right.

For the current generated file, the handoff command checks the sliced package for:

- Bambu Lab A1 mini
- `0.20mm Standard @BBL A1M`
- Bambu PLA Basic
- Textured PEI Plate

It also prints:

```bash
open -a /Applications/BambuStudio.app /Users/mikeedwards/CC/Bambu/outputs/world-cup-neighbors.gcode.3mf
```

If Bambu Studio opens the setup wizard, finish the Bambu Network plug-in setup before using the Device tab. That plug-in is what Bambu Studio uses for cloud/WLAN sending, remote control, live view, printer status, and profile sync.

Source-only generation:

```bash
uv run bambu make-figurines --output outputs/world-cup-neighbors.scad
```

The example creates two simplified soccer-supporter figures with Brazil-inspired jersey panels and raised number guides. It is designed for single-material printing and post-print painting. It does not include private photos or official team marks.

## World Cup Neighbors V2 Learning Path

World Cup neighbors v2 is the first build123d learning pass for a personal figurine scene. The active source lives in `projects/world-cup-neighbors/source/model.py`, with project-specific notes in `projects/world-cup-neighbors/source/README.md`.

Reusable lessons are captured in `docs/learning/build123d-figurine-workflow.md`: chunky attached face cues, structural scene props, low-relief soccer details, and the safe export-review loop before slicing or printing.

Current v2 CAD review command:

```bash
uv run python tools/review_3d.py projects/world-cup-neighbors --json outputs/review/world-cup-neighbors/review-report.json
```

FreeCAD can report a model as valid and closed while still finding deeper geometry-check warnings. Treat those warnings as design cleanup input before printing the next revision.

## World Cup Neighbors V4

v4.1 is the shipped revision: a chibi couple with engraved-pupil faces,
joined hands grounded in the base, a fused ball at Dan's foot, and a
WORLD CUP 2026 deck banner — one fused solid, supportless, sliced at
1h45m / 52.6 g of green PLA Basic. Specs are gates
(`designs/v4/*.yaml`), the build123d source is hand-authored
(`source/v4/model.py`), and review cameras are data
(`designs/v4/views.yaml`).

```bash
uv run bambu design-check projects/world-cup-neighbors --revision v4
uv run bambu release-check projects/world-cup-neighbors --revision v4 \
  --source-file projects/world-cup-neighbors/source/v4/model.py \
  --output-slug world-cup-neighbors-v4 \
  --views projects/world-cup-neighbors/designs/v4/views.yaml
```

The build's full failure catalog and fixes live in
`docs/learning/occt-step-geometry-rules.md` (CAD-side) and
`docs/learning/print-path-qc.md` (print-side); the per-revision record is
`projects/world-cup-neighbors/reviews/008-v4-build-notes.md`.

## Public Repo Safety

Do not commit:

- private reference photos
- printer access codes, LAN credentials, or cloud tokens
- generated STL/3MF/G-code files unless they are intentionally published releases

The `.gitignore` is set up for this by default.

## Development

Run tests:

```bash
uv run python -m unittest discover -s tests -v
```

Run the local helper:

```bash
scripts/bambu doctor
```

Run the local MCP server for agent clients:

```bash
uv run bambu-mcp
```

See `agents/README.md` for MCP client config and agent role prompts.
