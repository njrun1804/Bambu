# Bambu

Agent-assisted 3D-print preparation for a **Bambu Lab A1 mini**.

Bambu is a public-ready workbench for describing what you want in plain English, letting Codex or Claude help turn it into printable source files, and keeping the actual print step reviewable. It uses build123d as the serious Python CAD backend and keeps OpenSCAD for simple public/remixable models and the current figurine lane.

## What It Does Today

- Checks whether local 3D-printing tools are installed.
- Exposes printer/material/plate rules as agent-readable context.
- Creates structured `projects/<slug>/` workspaces with manifests, reviews, measurements, photos placeholders, and artifact indexes.
- Generates a stylized pair of Brazil-watch-party figurines as OpenSCAD.
- Builds dry-run slicer commands for Bambu Studio or OrcaSlicer.
- Builds the current safe prototype through SCAD, STL, and sliced 3MF without printer contact.
- Reviews build123d STEP/STL outputs through headless FreeCAD and Blender previews without printer contact.
- Validates agent-readable design specs before CAD generation, so v3 work starts from YAML constraints instead of hand-tweaking model code.
- Checks the generated `.gcode.3mf` for A1 mini handoff metadata and prints the exact Bambu Studio open command.
- Keeps private photos, printer credentials, and generated meshes out of git.
- Refuses to pretend the printer is safe to automate blindly: v1 stops at reviewable files and command plans.

## Quick Start

```bash
git clone https://github.com/njrun1804/Bambu.git
cd Bambu
uv run bambu doctor
uv run bambu make-figurines --output outputs/world-cup-neighbors.scad
uv run bambu slice-plan outputs/world-cup-neighbors.stl --output outputs/world-cup-neighbors.gcode.3mf
```

If OpenSCAD is installed, open `outputs/world-cup-neighbors.scad` and export an STL. If Bambu Studio or OrcaSlicer is installed, use the generated slicer command as the starting point, then inspect supports, scale, filament, and first-layer settings before printing.

## Recommended Human-Agent Loop

1. Start with `uv run bambu doctor` or the MCP `bambu_context_view`.
2. Create a structured workspace with `uv run bambu create-project "<idea>"`.
3. Choose the lane from the manifest: build123d for serious/dimensional CAD, OpenSCAD for simple public/remixable models, or the current figurine lane.
4. Generate or revise source before exporting artifacts.
5. Render/export source, record artifact hashes with `uv run bambu sync-artifacts <project>`, then build a slicer command with `bambu slice-plan`.
6. Open the sliced project in Bambu Studio, inspect supports, scale, filament, plate side, and first layer.
7. Print only after manual review.
8. Record the physical result with `uv run bambu record-print-result` before making the next revision.

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

## World Cup Neighbors V3 Agentic Pipeline

World Cup neighbors v3 starts from structured specs:

- `projects/world-cup-neighbors/designs/v3/design.yaml`
- `projects/world-cup-neighbors/designs/v3/people.yaml`
- `projects/world-cup-neighbors/designs/v3/print_constraints.yaml`
- `projects/world-cup-neighbors/designs/v3/visual_acceptance.yaml`
- `projects/world-cup-neighbors/designs/v3/build_plan.yaml`

Run:

```bash
uv run bambu design-check projects/world-cup-neighbors --revision v3
```

Only after that gate passes should an agent generate `source/v3/` build123d components, export STEP/STL, run FreeCAD, render Blender review views, and ask for human approval before Bambu Studio slicing or any physical print.

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
