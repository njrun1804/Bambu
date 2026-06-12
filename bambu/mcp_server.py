"""Local MCP server for agent-assisted Bambu workflows.

Run with:
    python3 -m bambu.mcp_server
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from bambu.cli import default_world_cup_scene
from bambu.context import context_view, rules_view
from bambu.design_pipeline import load_design_spec, validate_design_spec
from bambu.figurine import generate_scad
from bambu.handoff import inspect_print_handoff
from bambu.preflight import detect_tools, next_steps, serialize_report
from bambu.pipeline import build_world_cup_prototype
from bambu.projects import create_project, project_view, record_print_result, sync_project_artifacts
from bambu.slicer import SliceRequest, build_slice_plan


def bambu_doctor() -> dict[str, Any]:
    """Return setup status and beginner-friendly next steps."""

    report = detect_tools()
    return {
        "tools": serialize_report(report),
        "next_steps": next_steps(report),
        "safety": [
            "This MCP server does not start print jobs.",
            "Review meshes, supports, scale, filament, bed type, and first layer before printing.",
            "Keep private reference photos under private/ and out of git.",
        ],
    }


def bambu_context_view() -> dict[str, Any]:
    """Return deterministic printer, material, plate, tool, and safety context."""

    return context_view()


def bambu_rules_view() -> dict[str, Any]:
    """Return agent rules for CAD backends, artifacts, privacy, and print gates."""

    return rules_view()


def bambu_create_project(
    intent: str,
    root: str = "projects",
    slug: str | None = None,
    lane: str = "build123d",
    privacy: str = "private",
    material: str = "Bambu PLA Basic",
    plate_side: str = "deferred",
) -> dict[str, Any]:
    """Create a structured project workspace from a plain-English print idea."""

    project = create_project(
        intent,
        root=Path(root),
        slug=slug,
        lane=lane,
        privacy=privacy,
        material=material,
        plate_side=plate_side,
    )
    return {"project": project, "project_dir": str(Path(root) / project["slug"])}


def bambu_project_view(project: str) -> dict[str, Any]:
    """Return manifest, artifact, validation, and next-action state for a project."""

    return project_view(Path(project))


def bambu_design_check(project: str, revision: str = "v3") -> dict[str, Any]:
    """Validate structured design specs before CAD generation or printer work."""

    return validate_design_spec(load_design_spec(Path(project), revision=revision))


def bambu_sync_artifacts(
    project: str,
    outputs_root: str = "outputs",
) -> dict[str, Any]:
    """Hash and classify generated output files into the project artifact index."""

    return sync_project_artifacts(Path(project), outputs_root=Path(outputs_root))


def bambu_build123d_export(
    project: str,
    output_dir: str = "outputs",
) -> dict[str, Any]:
    """Export a build123d project model to STEP/STL without slicing or printer contact."""

    return export_build123d_project(Path(project), output_dir=Path(output_dir))


def bambu_record_print_result(
    project: str,
    outcome: str,
    failure_mode: str = "",
    measurements: dict[str, Any] | None = None,
    material_state: dict[str, Any] | None = None,
    notes: str = "",
    next_revision: str = "",
) -> dict[str, Any]:
    """Record physical print feedback for the current project revision."""

    return record_print_result(
        Path(project),
        outcome=outcome,
        failure_mode=failure_mode,
        measurements=measurements,
        material_state=material_state,
        notes=notes,
        next_revision=next_revision,
    )


def bambu_generate_world_cup_figurines(
    output: str = "outputs/world-cup-neighbors.scad",
) -> dict[str, Any]:
    """Generate the default Brazil-watch-party figurine OpenSCAD source."""

    out = Path(output)
    out.parent.mkdir(parents=True, exist_ok=True)
    scad = generate_scad(default_world_cup_scene())
    out.write_text(scad)
    return {
        "output": str(out),
        "bytes": len(scad.encode("utf-8")),
        "next": [
            "Open the .scad file in OpenSCAD and export STL.",
            "Call bambu_slice_plan with the STL path before opening the slicer.",
        ],
    }


def bambu_openscad_export_plan(
    scad_path: str,
    output_path: str = "outputs/model.stl",
) -> dict[str, Any]:
    """Return the OpenSCAD command to export a .scad file to STL."""

    report = detect_tools()
    openscad = report["openscad"].path or "openscad"
    command = [openscad, "-o", output_path, scad_path]
    return {
        "tool": "openscad",
        "command": command,
        "checklist": [
            "Render preview before export if the model changed materially.",
            "If OpenSCAD hangs on first launch, open the app once from /Applications.",
            "Use STL for first slice; keep the .scad file as the editable source.",
        ],
    }


def bambu_slice_plan(
    model_path: str,
    output_path: str = "outputs/model.gcode.3mf",
    slicer: str = "bambu-studio",
) -> dict[str, Any]:
    """Return a slicer command and print-review checklist without starting the printer."""

    executable = _detected_slicer_path(slicer)
    plan = build_slice_plan(
        SliceRequest(
            model_path=Path(model_path),
            output_path=Path(output_path),
            slicer=slicer,
            executable=executable,
            resolve_paths=True,
        )
    )
    return {
        "tool": plan.tool,
        "command": plan.command,
        "checklist": plan.checklist,
    }


def bambu_build_world_cup_prototype(
    output_dir: str = "outputs",
    slicer: str = "bambu-studio",
) -> dict[str, Any]:
    """Generate SCAD, export STL, and slice 3MF for the watch-party prototype."""

    return build_world_cup_prototype(Path(output_dir), slicer=slicer)


def bambu_print_handoff(
    file: str = "outputs/world-cup-neighbors.gcode.3mf",
) -> dict[str, Any]:
    """Inspect a sliced .gcode.3mf and return the manual Bambu Studio handoff."""

    report = inspect_print_handoff(Path(file))
    return {
        "file": str(report.file),
        "exists": report.exists,
        "is_3mf": report.is_3mf,
        "ready_for_manual_review": report.ready_for_manual_review,
        "found_markers": list(report.found_markers),
        "missing_markers": report.missing_markers,
        "open_command": report.open_command,
        "manual_boundary": [
            "Install/enable the Bambu Network plug-in in Bambu Studio if the setup wizard asks.",
            "On the Device tab, confirm the physical printer is online and is the Bambu Lab A1 mini.",
            "Do not start the physical print unattended; inspect plate, filament, supports, and first layer first.",
        ],
    }


def _detected_slicer_path(slicer: str) -> str | None:
    normalized = slicer.strip().lower().replace("_", "-")
    key = "orcaslicer" if normalized in {"orca", "orca-slicer", "orcaslicer"} else "bambu_studio"
    status = detect_tools().get(key)
    if status and status.available:
        return status.path
    return None


def export_build123d_project(*args, **kwargs):
    from bambu.cad import export_build123d_project as _export_build123d_project

    return _export_build123d_project(*args, **kwargs)


def _build_mcp():
    from mcp.server.fastmcp import FastMCP

    server = FastMCP("bambu_mcp")

    server.tool()(bambu_doctor)
    server.tool()(bambu_context_view)
    server.tool()(bambu_rules_view)
    server.tool()(bambu_create_project)
    server.tool()(bambu_project_view)
    server.tool()(bambu_design_check)
    server.tool()(bambu_sync_artifacts)
    server.tool()(bambu_build123d_export)
    server.tool()(bambu_record_print_result)
    server.tool()(bambu_generate_world_cup_figurines)
    server.tool()(bambu_openscad_export_plan)
    server.tool()(bambu_slice_plan)
    server.tool()(bambu_build_world_cup_prototype)
    server.tool()(bambu_print_handoff)
    return server


def main() -> None:
    """Run the local stdio MCP server."""

    _build_mcp().run()


if __name__ == "__main__":
    main()
