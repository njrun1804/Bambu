# Bambu — Intelligence Map
_Built: 2026-06-30 | Commit: 7e2c8c6 | 1059 nodes · 69 communities · 1 skills_

> Read this before touching anything. Graphify answers structural questions.
> The docs below answer domain questions. This file tells you where everything is.


## Load-Bearing Nodes
Top 15 by total degree (in + out). These are the highest-risk refactor targets.

| Node | Degree | Source | What it does | Note |
|------|--------|--------|--------------|------|
| `cli.py` | 79 | bambu/cli.py:L1 | Command-line interface for the Bambu workbench. |  |
| `mcp_server.py` | 69 | bambu/mcp_server.py:L1 | Local MCP server for agent-assisted Bambu workflows.  Run with:     python3 -m b |  |
| `pipeline.py` | 60 | bambu/pipeline.py:L1 | Safe local build pipelines: prototypes and full project handoff. |  |
| `MeshyClient` | 45 | bambu/meshy.py:L86 | Async-task Meshy client with polling and test-mode support. |  |
| `mesh_fusion.py` | 44 | bambu/mesh_fusion.py:L1 | Automated hybrid-lane mesh fusion: build123d body + Meshy head STLs. |  |
| `main()` | 40 | bambu/cli.py:L357 |  |  |
| `run_project_pipeline()` | 35 | bambu/pipeline.py:L142 | Run hybrid/build123d pipeline through headless slice, QC, and handoff. |  |
| `MeshyError` | 33 | bambu/meshy.py:L57 | Meshy API or configuration error. |  |
| `review3d.py` | 32 | bambu/review3d.py:L1 | Agent-safe 3D review workflow for generated CAD artifacts. |  |
| `projects.py` | 31 | bambu/projects.py:L1 | Project manifests, artifact indexes, and revision feedback for Bambu. |  |
| `review_project_3d()` | 31 | bambu/review3d.py:L376 | Export, inspect, render, and summarize a project without printer contact. |  |
| `seated_diorama.py` | 31 | bambu/cad/archetypes/seated_diorama.py:L1 | Seated diorama archetype composition helpers. |  |
| `fuse_hybrid_project()` | 27 | bambu/mesh_fusion.py:L77 | Fuse body scaffold STL with Meshy head meshes per fusion_manifest.yaml. |  |
| `meshy_concept()` | 27 | bambu/meshy.py:L386 | Run Figure prototype, text-to-image from intake, or text-to-image fallback. |  |
| `create_project()` | 27 | bambu/projects.py:L29 | Create a structured model project workspace from a print idea. |  |

## Community Map
From graphify label — architectural groupings. Communities with <6 nodes omitted.
Full list: `graphify-out/GRAPH_REPORT.md`

Top communities by size (showing top 20):
| Community | Size | Key nodes |
|-----------|------|-----------|
| Community 0 | 83 | `review3d.py`, `review_project_3d()`, `analyze_islands()` |
| Community 1 | 79 | `MeshyClient`, `MeshyError`, `meshy_concept()` |
| Community 2 | 77 | `mcp_server.py`, `detect_tools()`, `test_mcp_tools.py` |
| Community 3 | 68 | `seated_diorama.py`, `make_seated_woman()`, `heads.py` |
| Community 4 | 62 | `mesh_fusion.py`, `fuse_hybrid_project()`, `fuse_head_specs()` |
| Community 5 | 39 | `intake.py`, `run_intake()`, `IntakeTests` |
| Community 6 | 35 | `projects.py`, `create_project()`, `load_project()` |
| Community 7 | 28 | `export_build123d_project()`, `load_build123d_model()`, `__init__.py` |
| Community 8 | 27 | `run_project_pipeline()`, `PipelineOptions`, `test_pipeline_run.py` |
| Community 9 | 26 | `validate_reference_photo()`, `reference_validation.py`, `select_reference_photo()` |
| Community 10 | 26 | `SliceRequest`, `slicer.py`, `build_slice_plan()` |
| Community 11 | 25 | `load_design_spec()`, `validate_design_spec()`, `design_pipeline.py` |
| Community 12 | 24 | `analyze_stl_overhangs()`, `qc_sliced_3mf()`, `load_printer_context()` |
| Community 13 | 22 | `pipeline.py`, `load_fusion_manifest()`, `_run_scene_strategy()` |
| Community 14 | 22 | `World Cup Neighbors V2 Build123d Design`, `Rejected Alternatives`, `V2 Visual Direction` |
| Community 15 | 21 | `_person_parts()`, `_front()`, `make_base()` |
| Community 16 | 20 | `cli.py`, `classify_archetype_from_intent()`, `export_build123d_project()` |
| Community 17 | 20 | `generate_scad()`, `default_world_cup_scene()`, `figurine.py` |
| Community 18 | 18 | `PersonSpec`, `make_person()`, `assemble_scene()` |
| Community 19 | 15 | `Best Buds — pivot off head-on-CSG-body (2026-06-19)`, `Three alternative architectures`, `Recommended path: **A — concept-first scene mesh**` |

## Work Streams
Recent specs and low-degree recently-modified files. Check here before building anything new.

| Spec / Area | Artifacts | Status |
|-------------|-----------|--------|
| README | `project.yaml` ✓ | spec |
| build123d-figurine-workflow | `build_plan.yaml` ✓, `design.yaml` ✓, `*.yaml` ✓, `people.yaml` ✓, `print_constraints.yaml` ✓, `project.yaml` ✓, `visual_acceptance.yaml` ✓ | spec |
| hybrid-lane | `design.yaml` ✓, `fusion_manifest.yaml` ✓, `visual_acceptance.yaml` ✓, `provenance.yaml` ✓, `project.yaml` ✓, `model.py` ✓, `views.yaml` ✓ | spec |
| occt-step-geometry-rules | `mesh.py` ✓, `freecad_review.py` ✓ | spec |
| print-path-qc | `mesh.py` ✓, `printability.py` ✓, `views.yaml` ✓, `context.yaml` ✓ | spec |
| shapr3d-fusion-workflow | `fusion_manifest.yaml` ✓, `people.yaml` ✓, `fusion_manifest.yaml` ✓, `people.yaml` ✓ | spec |
| 2026-06-12-agent-operating-substrate-implementatio | `cli.py` ✓, `context.py` ✓, `mcp_server.py` ✓, `projects.py` ✓, `context.yaml` ✓, `project.yaml` ✓, `artifacts.json` ✓, `project.yaml` ✓ | spec |
| 2026-06-12-bambu-implementation | `__init__.py` ✓, `cli.py` ✓, `figurine.py` ✓, `preflight.py` ✓, `slicer.py` ✓, `brief.yaml` ✓, `test_figurine.py` ✓, `test_preflight.py` ✓ | spec |
| 2026-06-12-freecad-review-workflow-implementation | `review3d.py` ✓, `test_review3d.py` ✓, `review_3d.py` ✓ | spec |
| 2026-06-12-profile-artifact-build123d-implementati | `artifacts.json` ✓, `cad.py` ✗, `cli.py` ✓, `mcp_server.py` ✓, `projects.py` ✓, `slicer.py` ✓, `model.py` ✓, `test_cad.py` ✓ | spec |
| 2026-06-12-v3-agentic-design-pipeline | `cli.py` ✓, `design_pipeline.py` ✓, `*.yaml` ✓, `{design,people,print_constraints,visual_acceptance,build_plan}.yaml` ✗, `*.yaml` ✓, `build_plan.yaml` ✓, `design.yaml` ✓, `people.yaml` ✓ | spec |
| 2026-06-12-world-cup-neighbors-v2-build123d-implem | `artifacts.json` ✓, `artifacts.json` ✓, `project.yaml` ✓, `model.py` ✓, `model.py` ✓, `test_cad.py` ✓, `test_world_cup_v2.py` ✓ | spec |
| 2026-06-12-agent-operating-substrate-design | `artifacts.json` ✓, `vNNN.yaml` ✗, `project.yaml` ✓ | spec |
| 2026-06-12-project-evidence-layout-design | `artifacts.json` ✓, `print-result.yaml` ✗, `print-result.yaml` ✗, `v001.yaml` ✓, `print-result.yaml` ✗, `project.yaml` ✓, `manifest.yaml` ✓ | spec |
| 2026-06-12-world-cup-neighbors-v2-build123d-design | `artifacts.json` ✓, `model.py` ✓, `model.py` ✓ | spec |

## Operational Skills
Run these before or instead of writing code for common task types.
| Skill | Use when |
|-------|----------|
| bambu-operate | Use when operating the Bambu repo for photo-first 3D-print dioramas, intake, ... |

## Domain Intelligence
These docs answer questions graphify cannot:
_(no domain docs detected)_

## Known Blind Spots
What graphify cannot see for this repo:
- The Meshy AI API runtime, the slicer (Bambu Studio) output, and the printer. graphify sees the
  client code, not the meshes/G-code/printer.
- The safety boundary: no auto printer-start; payloads (STL/3MF/G-code/photos) stay out of git (`mem:core`).

## Navigation
| Question | Answer |
|----------|--------|
| How does A connect to B? | `graphify path A B` |
| What breaks if I touch X? | `graphify affected X` |
| What is X's community? | `graphify explain X` |
| What else is thematically related? | `python3 ~/.claude/skills/graph/embed.py search "..."` |
| Is X canon? Where does Y belong? | `.agent/orientation.md` → `docs/operating-model.md` |
| What does term X mean? | `.agent/orientation.md` |
| What MCP tool do I use for Z? | `docs/cloudflare-ops.md` |
