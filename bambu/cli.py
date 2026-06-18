"""Command-line interface for the Bambu workbench."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import shlex
import sys

from bambu.design_pipeline import load_design_spec, render_spec_sheet, validate_design_spec
from bambu.figurine import Figurine, Scene, generate_scad
from bambu.handoff import inspect_print_handoff
from bambu.preflight import detect_tools, next_steps
from bambu.projects import sync_project_artifacts
from bambu.slicer import SliceRequest, build_slice_plan


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="bambu",
        description="Agent-assisted 3D-print preparation for a Bambu Lab A1 mini.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("doctor", help="Check local CAD/slicer tools and print next steps.")
    subparsers.add_parser("next", help="Print beginner-friendly next steps.")

    handoff = subparsers.add_parser(
        "handoff",
        help="Check the generated .gcode.3mf and print the morning Bambu Studio handoff.",
    )
    handoff.add_argument(
        "--file",
        type=Path,
        default=Path("outputs/world-cup-neighbors.gcode.3mf"),
        help="Generated sliced project to open and review.",
    )

    figurines = subparsers.add_parser(
        "make-figurines",
        help="Generate the default World Cup neighbor figurine OpenSCAD scene.",
    )
    figurines.add_argument(
        "--output",
        type=Path,
        default=Path("outputs/world-cup-neighbors.scad"),
        help="Where to write the generated .scad file.",
    )

    slice_plan = subparsers.add_parser(
        "slice-plan",
        help="Print a dry-run slicer command for an STL or 3MF file.",
    )
    slice_plan.add_argument("model", type=Path, help="Input model path, usually an STL.")
    slice_plan.add_argument(
        "--output",
        type=Path,
        default=Path("outputs/model.gcode.3mf"),
        help="Output .gcode.3mf path.",
    )
    slice_plan.add_argument(
        "--slicer",
        default="bambu-studio",
        choices=["bambu-studio", "orcaslicer", "orca"],
        help="Slicer CLI to plan for.",
    )

    prototype = subparsers.add_parser(
        "prototype-world-cup",
        help="Generate SCAD, export STL, and slice 3MF for the World Cup figurine prototype.",
    )
    prototype.add_argument(
        "--output-dir",
        type=Path,
        default=Path("outputs"),
        help="Directory for generated prototype files.",
    )
    prototype.add_argument(
        "--slicer",
        default="bambu-studio",
        choices=["bambu-studio", "orcaslicer", "orca"],
        help="Slicer CLI to run.",
    )

    create = subparsers.add_parser(
        "create-project",
        help="Create a structured agent project workspace from a plain-English print idea.",
    )
    create.add_argument("intent", help="Plain-English model intent.")
    create.add_argument("--root", type=Path, default=Path("projects"), help="Project workspace root.")
    create.add_argument("--slug", help="Optional project slug. Defaults to a slug from the intent.")
    create.add_argument("--lane", default="build123d", choices=["build123d", "openscad", "figurine", "hybrid"])
    create.add_argument("--privacy", default="private")
    create.add_argument("--material", default="Bambu PLA Basic")
    create.add_argument("--plate-side", default="deferred")

    result = subparsers.add_parser(
        "record-print-result",
        help="Record physical print feedback for a project revision.",
    )
    result.add_argument("project", type=Path, help="Project directory containing project.yaml.")
    result.add_argument("--outcome", required=True, choices=["not_printed", "success", "partial_success", "failed"])
    result.add_argument("--failure-mode", default="")
    result.add_argument("--notes", default="")
    result.add_argument("--next-revision", default="")

    sync = subparsers.add_parser(
        "sync-artifacts",
        help="Hash and classify generated output files into a project artifact index.",
    )
    sync.add_argument("project", type=Path, help="Project directory containing project.yaml.")
    sync.add_argument("--outputs-root", type=Path, default=Path("outputs"))

    export = subparsers.add_parser(
        "export-build123d",
        help="Export a build123d project source/model.py to STEP and STL.",
    )
    export.add_argument("project", type=Path, help="Project directory containing project.yaml.")
    export.add_argument("--output-dir", type=Path, default=Path("outputs"))
    export.add_argument("--source-file", type=Path, default=None, help="Alternate build123d source file.")
    export.add_argument("--output-slug", default=None, help="Alternate output artifact name.")

    export_body = subparsers.add_parser(
        "export-body",
        help="Export build123d body scaffold (head stubs) to STEP and STL for Shapr3D fusion.",
    )
    export_body.add_argument("project", type=Path, help="Project directory containing project.yaml.")
    export_body.add_argument("--output-dir", type=Path, default=Path("outputs"))
    export_body.add_argument("--source-file", type=Path, default=None, help="Alternate build123d source file.")
    export_body.add_argument("--output-slug", default=None, help="Alternate output artifact name.")
    export_body.add_argument("--revision", default=None, help="Design revision for output slug.")

    design_check = subparsers.add_parser(
        "design-check",
        help="Validate structured agentic design specs before CAD generation.",
    )
    design_check.add_argument("project", type=Path, help="Project directory containing project.yaml.")
    design_check.add_argument("--revision", default="v3", help="Design revision under designs/<revision>.")
    design_check.add_argument("--json", type=Path, default=None, help="Optional path to write report JSON.")

    qc = subparsers.add_parser(
        "qc",
        help="Printability QC: supportless overhang check on the STL plus printer/filament checks on the sliced .gcode.3mf.",
    )
    qc.add_argument("sliced", type=Path, help="Sliced .gcode.3mf to inspect.")
    qc.add_argument("--stl", type=Path, default=None, help="Exported STL for overhang analysis.")
    qc.add_argument("--context", type=Path, default=Path("profiles/bambu-a1-mini/context.yaml"))
    qc.add_argument("--overhang-budget-mm2", type=float, default=150.0)
    qc.add_argument("--json", type=Path, default=None, help="Optional path to write report JSON.")

    release = subparsers.add_parser(
        "release-check",
        help="Run every release gate in one pass: design-check, export, FreeCAD, mesh, overhangs, islands, renders.",
    )
    release.add_argument("project", type=Path, help="Project directory containing project.yaml.")
    release.add_argument("--revision", default=None, help="Design revision to gate under designs/<revision>.")
    release.add_argument("--source-file", type=Path, default=None, help="Alternate build123d source file.")
    release.add_argument("--output-slug", default=None, help="Alternate output artifact name.")
    release.add_argument("--views", type=Path, default=None, help="YAML file with Blender review views.")
    release.add_argument("--no-render", action="store_true", help="Skip Blender preview rendering.")
    release.add_argument("--outputs-root", type=Path, default=Path("outputs"))
    release.add_argument("--json", type=Path, default=None, help="Optional path to write report JSON.")
    release.add_argument("--stl", type=Path, default=None, help="Fused STL artifact (skips build123d export).")
    release.add_argument("--skip-export", action="store_true", help="Use existing outputs instead of re-exporting.")
    release.add_argument("--skip-freecad", action="store_true", help="Skip FreeCAD STEP gate.")
    release.add_argument("--body-step", type=Path, default=None, help="Optional body STEP for FreeCAD when reviewing fused STL.")

    review_mesh = subparsers.add_parser(
        "review-mesh",
        help="Quick mesh gates and Blender renders on an existing STL.",
    )
    review_mesh.add_argument("stl", type=Path, help="STL path to review.")
    review_mesh.add_argument("--project", type=Path, default=None, help="Project for views and thumbnail spec.")
    review_mesh.add_argument("--revision", default=None, help="Design revision for views.")
    review_mesh.add_argument("--body-step", type=Path, default=None, help="Optional body STEP for FreeCAD review.")
    review_mesh.add_argument("--no-render", action="store_true", help="Skip Blender preview rendering.")
    review_mesh.add_argument("--outputs-root", type=Path, default=Path("outputs"))
    review_mesh.add_argument("--json", type=Path, default=None, help="Optional path to write report JSON.")

    mesh_intake_cmd = subparsers.add_parser(
        "mesh-intake",
        help="Register a head mesh in projects/<slug>/mesh/ with provenance.",
    )
    mesh_intake_cmd.add_argument("project", type=Path, help="Project directory.")
    mesh_intake_cmd.add_argument("--file", type=Path, required=True, help="STL file to copy into mesh/.")
    mesh_intake_cmd.add_argument("--role", required=True, help="Artifact role, e.g. head_woman.")
    mesh_intake_cmd.add_argument("--meshy-task-id", default="", help="Optional Meshy task id for provenance.")

    meshy = subparsers.add_parser("meshy", help="Meshy Pro integration for hybrid lane likeness.")
    meshy_sub = meshy.add_subparsers(dest="meshy_command", required=True)

    meshy_concept = meshy_sub.add_parser("concept", help="Figure prototype or text-to-image concept sheet.")
    meshy_concept.add_argument("project", type=Path, help="Project directory.")
    meshy_concept.add_argument("--photo", type=Path, default=None, help="Override reference photo path.")

    meshy_head = meshy_sub.add_parser("head", help="Image-to-3d head mesh from cropped photo.")
    meshy_head.add_argument("project", type=Path, help="Project directory.")
    meshy_head.add_argument("--subject", required=True, choices=["woman", "dog"], help="Head subject id.")
    meshy_head.add_argument("--crop", type=Path, default=None, help="Override crop image path.")

    meshy_analyze = meshy_sub.add_parser("analyze", help="Free Meshy analyze-printability report.")
    meshy_analyze.add_argument("project", type=Path, help="Project directory.")
    meshy_analyze.add_argument("--subject", default=None, help="Subject id for provenance lookup.")
    meshy_analyze.add_argument("--task-id", default=None, help="Meshy task id to analyze.")

    meshy_repair = meshy_sub.add_parser("repair", help="Repair printability on a prior Meshy task.")
    meshy_repair.add_argument("project", type=Path, help="Project directory.")
    meshy_repair.add_argument("--task-id", default=None, help="Input image-to-3d task id.")
    meshy_repair.add_argument("--subject", default=None, choices=["woman", "dog"])

    meshy_remesh = meshy_sub.add_parser("remesh", help="Remesh a prior Meshy task to lower polycount.")
    meshy_remesh.add_argument("project", type=Path, help="Project directory.")
    meshy_remesh.add_argument("--task-id", default=None, help="Input task id.")
    meshy_remesh.add_argument("--subject", default=None, choices=["woman", "dog"])
    meshy_remesh.add_argument("--target-polycount", type=int, default=30000)

    meshy_sub.add_parser("balance", help="Print remaining Meshy credits.")

    meshy_poll = meshy_sub.add_parser("poll", help="Poll a Meshy task by type and id.")
    meshy_poll.add_argument("task_type", choices=["image-to-3d", "figure-prototype", "analyze", "remesh", "repair"])
    meshy_poll.add_argument("task_id", help="Meshy task id.")

    from bambu.intake import archetypes_with_templates

    intake = subparsers.add_parser(
        "intake",
        help="Photo-first intake: scaffold project, copy reference photo, emit agent prompt.",
    )
    intake.add_argument("photo", type=Path, help="Reference photo path.")
    intake.add_argument("--intent", required=True, help="Plain-English print intent.")
    intake.add_argument("--slug", help="Project slug (defaults from intent).")
    intake.add_argument("--root", type=Path, default=Path("projects"), help="Projects root.")
    intake.add_argument(
        "--archetype",
        default=None,
        choices=archetypes_with_templates(),
        help="Scene archetype with spec templates (defaults from intent keywords).",
    )

    spec_sheet = subparsers.add_parser(
        "render-spec-sheet",
        help="Render a one-page markdown design sheet from YAML for human sign-off.",
    )
    spec_sheet.add_argument("project", type=Path, help="Project directory.")
    spec_sheet.add_argument("--revision", default="v1", help="Design revision.")
    spec_sheet.add_argument("--output", type=Path, default=None, help="Optional output markdown path.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    if args.command == "doctor":
        return _doctor()
    if args.command == "next":
        return _next()
    if args.command == "handoff":
        return _handoff(args.file)
    if args.command == "make-figurines":
        return _make_figurines(args.output)
    if args.command == "slice-plan":
        return _slice_plan(args.model, args.output, args.slicer)
    if args.command == "prototype-world-cup":
        return _prototype_world_cup(args.output_dir, args.slicer)
    if args.command == "create-project":
        return _create_project(args)
    if args.command == "record-print-result":
        return _record_print_result(args)
    if args.command == "sync-artifacts":
        return _sync_artifacts(args)
    if args.command == "export-build123d":
        return _export_build123d(args)
    if args.command == "export-body":
        return _export_body(args)
    if args.command == "design-check":
        return _design_check(args)
    if args.command == "qc":
        return _qc(args)
    if args.command == "release-check":
        return _release_check(args)
    if args.command == "review-mesh":
        return _review_mesh(args)
    if args.command == "mesh-intake":
        return _mesh_intake(args)
    if args.command == "meshy":
        return _meshy(args)
    if args.command == "intake":
        return _intake(args)
    if args.command == "render-spec-sheet":
        return _render_spec_sheet(args)

    raise AssertionError(f"Unhandled command: {args.command}")


def _doctor() -> int:
    report = detect_tools()
    print("Bambu preflight")
    print("===============")
    labels = {
        "openscad": "OpenSCAD",
        "bambu_studio": "Bambu Studio",
        "orcaslicer": "OrcaSlicer",
        "blender": "Blender",
    }
    for key, status in report.items():
        marker = "ok" if status.available else "missing"
        detail = status.path if status.available else status.hint
        print(f"- {labels[key]}: {marker} - {detail}")
    print()
    _print_next_steps(report)
    return 0


def _prototype_world_cup(output_dir: Path, slicer: str) -> int:
    from bambu.pipeline import build_world_cup_prototype

    result = build_world_cup_prototype(output_dir, slicer=slicer)
    print("Prototype built")
    print("---------------")
    for key in ("scad", "stl", "sliced"):
        print(f"{key}: {result[key]}")
    print()
    print(result["manual_boundary"])
    return 0


def _next() -> int:
    _print_next_steps(detect_tools())
    return 0


def _handoff(file: Path) -> int:
    report = inspect_print_handoff(file)
    print("Morning print handoff")
    print("---------------------")
    print(f"file: {report.file}")
    print(f"exists: {'yes' if report.exists else 'no'}")
    print(f"valid 3MF package: {'yes' if report.is_3mf else 'no'}")
    print()
    print("Expected A1 mini markers")
    print("------------------------")
    for marker in report.found_markers:
        print(f"- ok: {marker}")
    for marker in report.missing_markers:
        print(f"- missing: {marker}")
    print()
    print("Open in Bambu Studio")
    print("--------------------")
    print(report.open_command)
    print()
    print("Manual boundary")
    print("---------------")
    print("Install/enable the Bambu Network plug-in in Bambu Studio if the setup wizard asks.")
    print("On the Device tab, confirm the physical printer is online and is the Bambu Lab A1 mini.")
    print("Do not start the physical print unattended; inspect plate, filament, supports, and first layer first.")
    return 0 if report.ready_for_manual_review else 1


def _print_next_steps(report: dict[str, object]) -> None:
    print("Next")
    print("----")
    for index, step in enumerate(next_steps(report), start=1):
        print(f"{index}. {step}")


def _make_figurines(output: Path) -> int:
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(generate_scad(default_world_cup_scene()))
    print(f"Wrote {output}")
    print("Next: open it in OpenSCAD, export STL, then run `bambu slice-plan <model.stl>`.")
    return 0


def _slice_plan(model: Path, output: Path, slicer: str) -> int:
    executable = _detected_slicer_path(slicer)
    plan = build_slice_plan(
        SliceRequest(
            model_path=model,
            output_path=output,
            slicer=slicer,
            executable=executable,
            resolve_paths=True,
        )
    )
    print("Slicer command")
    print("--------------")
    print(" ".join(shlex.quote(part) for part in plan.command))
    print()
    print("Checklist")
    print("---------")
    for item in plan.checklist:
        print(f"- {item}")
    return 0


def _create_project(args: argparse.Namespace) -> int:
    from bambu.projects import create_project

    project = create_project(
        args.intent,
        root=args.root,
        slug=args.slug,
        lane=args.lane,
        privacy=args.privacy,
        material=args.material,
        plate_side=args.plate_side,
    )
    print(f"Created project: {args.root / project['slug']}")
    print(f"Lane: {project['lane']}")
    print(f"Next safe action: {project['next_safe_action']}")
    return 0


def _record_print_result(args: argparse.Namespace) -> int:
    from bambu.projects import record_print_result

    result = record_print_result(
        args.project,
        outcome=args.outcome,
        failure_mode=args.failure_mode,
        notes=args.notes,
        next_revision=args.next_revision,
    )
    print(f"Recorded print result: {result['project_slug']} {result['revision']} {result['outcome']}")
    print("Next: revise source from the recorded physical feedback before exporting again.")
    return 0


def _sync_artifacts(args: argparse.Namespace) -> int:
    result = sync_project_artifacts(args.project, outputs_root=args.outputs_root)
    print(f"Synced artifacts: {result['project_slug']} {result['revision']}")
    print(f"Count: {len(result['artifacts'])}")
    return 0


def _export_build123d(args: argparse.Namespace) -> int:
    result = export_build123d_project(
        args.project,
        output_dir=args.output_dir,
        source_file=args.source_file,
        output_slug=args.output_slug,
    )
    print("build123d export")
    print("---------------")
    print(f"STEP: {result['step']}")
    print(f"STL: {result['stl']}")
    print(f"bounding box mm: {result['bounding_box_mm']}")
    print(f"fits A1 mini: {'yes' if result['fits_a1_mini'] else 'no'}")
    print("Manual boundary: review exported geometry before slicing or printing.")
    return 0


def _design_check(args: argparse.Namespace) -> int:
    spec = load_design_spec(args.project, revision=args.revision)
    report = validate_design_spec(spec)
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(report, indent=2) + "\n")

    print("Agentic design check")
    print("--------------------")
    print(f"project: {args.project}")
    print(f"revision: {report['revision']}")
    print(f"status: {'pass' if report['ok'] else 'fail'}")
    print(f"printer: {report['printer']['model']}")
    print(f"printer contact allowed: {'yes' if report['printer_contact_allowed'] else 'no'}")
    print()
    print("Gates")
    print("-----")
    for name, passed in report["gates"].items():
        print(f"- {name}: {'pass' if passed else 'fail'}")
    if report["errors"]:
        print()
        print("Errors")
        print("------")
        for error in report["errors"]:
            print(f"- {error}")
    if report["warnings"]:
        print()
        print("Warnings")
        print("--------")
        for warning in report["warnings"]:
            print(f"- {warning}")
    print()
    print("Next agent actions")
    print("------------------")
    for action in report["next_agent_actions"]:
        print(f"- {action}")
    return 0 if report["ok"] else 1


def export_build123d_project(*args, **kwargs):
    from bambu.cad import export_build123d_project as _export_build123d_project

    return _export_build123d_project(*args, **kwargs)


def _detected_slicer_path(slicer: str) -> str | None:
    key = "orcaslicer" if slicer in {"orca", "orcaslicer"} else "bambu_studio"
    status = detect_tools().get(key)
    if status and status.available:
        return status.path
    return None


def default_world_cup_scene() -> Scene:
    return Scene(
        title="World Cup neighbors",
        figures=[
            Figurine(
                name="Dan",
                height_mm=72,
                body_shape="slim",
                hair="short gray hair",
                accessories=["glasses"],
                jersey_number="10",
                profile="tall_neighbor",
            ),
            Figurine(
                name="Carrie",
                height_mm=64,
                body_shape="curvy",
                hair="short light hair",
                accessories=["sunglasses"],
                jersey_number="9",
                profile="smiling_neighbor",
            ),
        ],
    )


if __name__ == "__main__":
    sys.exit(main())


def _qc(args: argparse.Namespace) -> int:
    from bambu.mesh import analyze_islands
    from bambu.printability import analyze_stl_overhangs, load_printer_context, qc_report_lines, qc_sliced_3mf

    context = load_printer_context(args.context)
    stl_report = (
        analyze_stl_overhangs(args.stl, patch_budget_mm2=args.overhang_budget_mm2)
        if args.stl
        else {"available": False, "reason": "no --stl provided", "ok": True}
    )
    island_report = analyze_islands(args.stl) if args.stl else {"available": False, "ok": True}
    slice_report = qc_sliced_3mf(args.sliced, context=context)
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(
            json.dumps({"stl": stl_report, "islands": island_report, "sliced": slice_report}, indent=2) + "\n"
        )
    for line in qc_report_lines(stl_report, slice_report, island_report):
        print(line)
    ok = slice_report.get("ok") and stl_report.get("ok", True) and island_report.get("ok", True)
    print()
    print(f"QC: {'pass' if ok else 'FAIL'} (printing remains a manual decision)")
    return 0 if ok else 1


def _export_body(args: argparse.Namespace) -> int:
    from bambu.projects import load_project

    project = load_project(args.project / "project.yaml")
    rev = args.revision or project.get("current_revision", "v1")
    rev_base = rev.split(".", 1)[0]
    output_slug = args.output_slug or f"{project['slug']}-{rev_base}-body"
    result = export_build123d_project(
        args.project,
        output_dir=args.output_dir,
        source_file=args.source_file,
        output_slug=output_slug,
        revision=rev,
        body_only=True,
    )
    print("build123d body export")
    print("--------------------")
    print(f"STEP: {result['step']}")
    print(f"STL: {result['stl']}")
    print(f"bounding box mm: {result['bounding_box_mm']}")
    print(f"fits A1 mini: {'yes' if result['fits_a1_mini'] else 'no'}")
    print("Head stubs only — fuse Meshy heads in Shapr3D before release-check --stl.")
    return 0


def _review_mesh(args: argparse.Namespace) -> int:
    from bambu.review3d import review_mesh_stl

    review = review_mesh_stl(
        args.stl,
        project_path=args.project,
        outputs_root=args.outputs_root,
        render=not args.no_render,
        revision=args.revision,
        body_step=args.body_step,
        skip_freecad=args.body_step is None,
    )
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(review, indent=2) + "\n")
    print("Mesh review")
    print("-----------")
    print(f"STL: {review.get('stl')}")
    print(f"watertight: {'yes' if review.get('mesh', {}).get('watertight_manifold') else 'no'}")
    print(f"overhangs ok: {'yes' if review.get('overhangs', {}).get('ok') else 'no'}")
    print(f"islands ok: {'yes' if review.get('islands', {}).get('ok') else 'no'}")
    if not args.no_render:
        print(f"renders: {len(review.get('blender', {}).get('paths', []))}")
    print(review.get("manual_boundary", ""))
    ok = (
        review.get("mesh", {}).get("watertight_manifold")
        and review.get("overhangs", {}).get("ok")
        and review.get("islands", {}).get("ok")
    )
    return 0 if ok else 1


def _mesh_intake(args: argparse.Namespace) -> int:
    from bambu.mesh_lane import mesh_intake

    result = mesh_intake(
        args.project,
        file=args.file,
        role=args.role,
        meshy_task_id=args.meshy_task_id,
    )
    print(f"Mesh intake: {result['mesh_path']} ({result['role']})")
    return 0


def _meshy(args: argparse.Namespace) -> int:
    from bambu.meshy import MeshyClient, MeshyError, meshy_analyze, meshy_concept, meshy_head

    poll_paths = {
        "image-to-3d": "v1/image-to-3d",
        "figure-prototype": "creative-lab/figure/v1/prototype",
        "analyze": "v1/print/analyze",
        "remesh": "v1/remesh",
        "repair": "v1/print/repair",
    }
    try:
        if args.meshy_command == "concept":
            client = MeshyClient.from_env() if not getattr(args, "photo", None) else None
            result = meshy_concept(args.project, photo=args.photo, client=client)
            print(f"Concept sheet: {result['concept_path']}")
            return 0
        if args.meshy_command == "head":
            result = meshy_head(args.project, subject=args.subject, crop=args.crop)
            print(f"Head STL: {result['stl_path']}")
            return 0
        if args.meshy_command == "analyze":
            if not args.subject and not args.task_id:
                raise MeshyError("analyze requires --subject or --task-id")
            result = meshy_analyze(args.project, subject=args.subject, input_task_id=args.task_id)
            print(f"Analyze report: {result['report_path']}")
            return 0
        if args.meshy_command == "repair":
            client = MeshyClient.from_env()
            if args.task_id:
                task = client.repair_printability(input_task_id=args.task_id)
                print(json.dumps(task, indent=2))
            elif args.subject:
                import yaml

                prov_path = args.project / "mesh" / "provenance.yaml"
                prov = yaml.safe_load(prov_path.read_text()) if prov_path.exists() else {}
                task_id = (prov.get("heads", {}).get(args.subject) or {}).get("task_id")
                if not task_id:
                    raise MeshyError(f"No task_id for subject {args.subject} in mesh/provenance.yaml")
                task = client.repair_printability(input_task_id=task_id)
                print(json.dumps(task, indent=2))
            else:
                raise MeshyError("repair requires --task-id or --subject")
            return 0
        if args.meshy_command == "remesh":
            client = MeshyClient.from_env()
            if args.task_id:
                task = client.remesh(input_task_id=args.task_id, target_polycount=args.target_polycount)
                print(json.dumps(task, indent=2))
            elif args.subject:
                import yaml

                prov_path = args.project / "mesh" / "provenance.yaml"
                prov = yaml.safe_load(prov_path.read_text()) if prov_path.exists() else {}
                task_id = (prov.get("heads", {}).get(args.subject) or {}).get("task_id")
                if not task_id:
                    raise MeshyError(f"No task_id for subject {args.subject} in mesh/provenance.yaml")
                task = client.remesh(input_task_id=task_id, target_polycount=args.target_polycount)
                print(json.dumps(task, indent=2))
            else:
                raise MeshyError("remesh requires --task-id or --subject")
            return 0
        if args.meshy_command == "balance":
            print(json.dumps(MeshyClient.from_env().balance(), indent=2))
            return 0
        if args.meshy_command == "poll":
            client = MeshyClient.from_env()
            path = poll_paths[args.task_type]
            task = client.get_task(path, args.task_id)
            print(json.dumps(task, indent=2))
            return 0
    except MeshyError as exc:
        print(f"meshy error: {exc}", file=sys.stderr)
        return 1
    raise AssertionError(f"Unhandled meshy command: {args.meshy_command}")


def _release_check(args: argparse.Namespace) -> int:
    """Every release gate in one pass with a unified verdict."""

    import yaml

    from bambu.review3d import review_project_3d

    gates: list[tuple[str, bool, str]] = []

    if args.revision:
        spec = load_design_spec(args.project, revision=args.revision)
        design_report = validate_design_spec(spec)
        gates.append(("design-check", design_report["ok"], "; ".join(design_report["errors"]) or "specs valid"))
    else:
        design_report = None

    views = None
    if args.views:
        views = yaml.safe_load(args.views.read_text())["views"]
    elif args.revision:
        from bambu.review3d import load_review_views

        views = load_review_views(args.project, revision=args.revision)
    review = review_project_3d(
        args.project,
        outputs_root=args.outputs_root,
        render=not args.no_render,
        source_file=args.source_file,
        output_slug=args.output_slug,
        views=views,
        revision=args.revision,
        stl_path=args.stl,
        skip_export=args.skip_export or bool(args.stl),
        skip_freecad=args.skip_freecad or bool(args.stl),
        body_step=args.body_step,
    )
    freecad = review.get("freecad", {})
    mesh = review.get("mesh", {})
    overhangs = review.get("overhangs", {})
    islands = review.get("islands", {})
    blender = review.get("blender", {})

    gates.append(("fits A1 mini", bool(review.get("fits_a1_mini")), str(review.get("bounding_box_mm"))))
    freecad_skipped = freecad.get("skipped") or args.skip_freecad or bool(args.stl)
    freecad_ok = freecad_skipped or (freecad.get("available", False) and not freecad.get("warnings"))
    gates.append(
        (
            "FreeCAD geometry",
            freecad_ok,
            freecad.get("reason")
            or "valid=%s closed=%s solids=%s blocking=%s"
            % (
                freecad.get("is_valid"),
                freecad.get("is_closed"),
                freecad.get("counts", {}).get("solids"),
                freecad.get("geometry_error_classes", {}).get("blocking") or "none",
            ),
        )
    )
    gates.append(
        (
            "mesh watertight",
            bool(mesh.get("watertight_manifold")),
            "open=%s non-manifold=%s" % (mesh.get("open_edges"), mesh.get("non_manifold_edges")),
        )
    )
    gates.append(
        (
            "overhang patches",
            bool(overhangs.get("ok")),
            "largest steep %s mm2 (budget %s)"
            % (overhangs.get("largest_steep_patch_mm2"), overhangs.get("patch_budget_mm2")),
        )
    )
    gates.append(
        (
            "floating islands",
            bool(islands.get("ok")),
            "%s blocking of %s seeds" % (islands.get("blocking_count"), islands.get("island_count")),
        )
    )
    if not args.no_render:
        gates.append(("review renders", bool(blender.get("paths")), f"{len(blender.get('paths', []))} views"))

    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps({"design": design_report, "review": review}, indent=2) + "\n")

    print("Release check")
    print("=============")
    print(f"project: {args.project}")
    if args.revision:
        print(f"revision: {args.revision}")
    print(f"STEP: {review.get('step')}")
    print(f"STL: {review.get('stl')}")
    print()
    all_ok = True
    for name, ok, detail in gates:
        all_ok = all_ok and ok
        print(f"- {name}: {'pass' if ok else 'FAIL'} ({detail})")
    print()
    print(f"release check: {'PASS' if all_ok else 'FAIL'}")
    print("Next: slice, then `bambu qc <sliced.gcode.3mf> --stl <model.stl>`, then `bambu handoff`.")
    print(review.get("manual_boundary", ""))
    return 0 if all_ok else 1


def _intake(args: argparse.Namespace) -> int:
    from bambu.intake import classify_archetype_from_intent, run_intake

    archetype = args.archetype or classify_archetype_from_intent(args.intent)
    result = run_intake(
        args.photo,
        intent=args.intent,
        slug=args.slug,
        root=args.root,
        archetype=archetype,
    )
    print("Photo intake")
    print("------------")
    print(f"project: {result['project_dir']}")
    print(f"archetype: {result['archetype']}")
    print(f"reference photo: {result['reference_photo']}")
    print()
    print("Next steps")
    print("----------")
    for step in result["next_steps"]:
        print(f"- {step}")
    print()
    print("Agent prompt (also in agents/prompts/intake-from-photo.md)")
    print("-----------------------------------------------------------")
    print(result["agent_prompt"][:2000])
    if len(result["agent_prompt"]) > 2000:
        print("... (truncated)")
    return 0


def _render_spec_sheet(args: argparse.Namespace) -> int:
    sheet = render_spec_sheet(args.project, revision=args.revision)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(sheet + "\n")
        print(f"Wrote {args.output}")
    else:
        print(sheet)
    return 0
