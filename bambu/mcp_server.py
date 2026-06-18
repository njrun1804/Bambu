"""Local MCP server for agent-assisted Bambu workflows.

Run with:
    python3 -m bambu.mcp_server
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from bambu.cli import default_world_cup_scene
from bambu.context import context_view, rules_view
from bambu.design_pipeline import load_design_spec, render_spec_sheet, validate_design_spec
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


def bambu_design_check(project: str, revision: str = "v1") -> dict[str, Any]:
    """Validate structured design specs before CAD generation or printer work."""

    return validate_design_spec(load_design_spec(Path(project), revision=revision))


def bambu_intake(
    photo: str,
    intent: str,
    slug: str | None = None,
    root: str = "projects",
    archetype: str | None = None,
) -> dict[str, Any]:
    """Photo-first intake: scaffold project and return agent prompt."""

    from bambu.intake import classify_archetype_from_intent, run_intake

    selected = archetype or classify_archetype_from_intent(intent)
    return run_intake(photo, intent=intent, slug=slug, root=Path(root), archetype=selected)


def bambu_render_spec_sheet(project: str, revision: str = "v1") -> dict[str, Any]:
    """Render markdown design sheet from YAML specs."""

    sheet = render_spec_sheet(Path(project), revision=revision)
    return {"project": project, "revision": revision, "markdown": sheet}


def bambu_release_check(
    project: str,
    revision: str = "v1",
    output_dir: str = "outputs",
    no_render: bool = False,
    source_file: str | None = None,
    output_slug: str | None = None,
    stl: str | None = None,
    skip_export: bool = False,
    skip_freecad: bool = False,
    body_step: str | None = None,
) -> dict[str, Any]:
    """Run every release gate: design-check, export, FreeCAD, mesh, overhangs, islands, renders."""

    from bambu.review3d import load_review_views, review_project_3d

    spec = load_design_spec(Path(project), revision=revision)
    design_report = validate_design_spec(spec)
    views = load_review_views(project, revision=revision)
    review = review_project_3d(
        Path(project),
        outputs_root=Path(output_dir),
        render=not no_render,
        source_file=Path(source_file) if source_file else None,
        output_slug=output_slug,
        views=views,
        revision=revision,
        stl_path=Path(stl) if stl else None,
        skip_export=skip_export or bool(stl),
        skip_freecad=skip_freecad or bool(stl),
        body_step=Path(body_step) if body_step else None,
    )
    freecad = review.get("freecad", {})
    freecad_skipped = freecad.get("skipped") or skip_freecad or bool(stl)
    freecad_ok = freecad_skipped or (freecad.get("available") and not freecad.get("warnings"))
    gates = {
        "design_check": design_report["ok"],
        "fits_a1_mini": review.get("fits_a1_mini"),
        "freecad": freecad_ok,
        "mesh_watertight": review.get("mesh", {}).get("watertight_manifold"),
        "overhangs": review.get("overhangs", {}).get("ok"),
        "islands": review.get("islands", {}).get("ok"),
    }
    if not no_render:
        gates["renders"] = bool(review.get("blender", {}).get("paths"))
    return {
        "ok": all(gates.values()),
        "gates": gates,
        "design": design_report,
        "review": review,
    }


def bambu_review_mesh(
    stl: str,
    project: str | None = None,
    revision: str = "v1",
    output_dir: str = "outputs",
    no_render: bool = False,
    body_step: str | None = None,
) -> dict[str, Any]:
    """Quick mesh gates and Blender renders on an existing STL."""

    from bambu.review3d import review_mesh_stl

    review = review_mesh_stl(
        Path(stl),
        project_path=Path(project) if project else None,
        outputs_root=Path(output_dir),
        render=not no_render,
        revision=revision,
        body_step=Path(body_step) if body_step else None,
        skip_freecad=body_step is None,
    )
    ok = (
        review.get("mesh", {}).get("watertight_manifold")
        and review.get("overhangs", {}).get("ok")
        and review.get("islands", {}).get("ok")
    )
    return {"ok": ok, "review": review}


def bambu_meshy_concept(project: str, photo: str | None = None) -> dict[str, Any]:
    from bambu.meshy import meshy_concept

    return meshy_concept(Path(project), photo=Path(photo) if photo else None)


def bambu_meshy_head(project: str, subject: str, crop: str | None = None) -> dict[str, Any]:
    from bambu.meshy import meshy_head

    return meshy_head(Path(project), subject=subject, crop=Path(crop) if crop else None)


def bambu_meshy_balance() -> dict[str, Any]:
    from bambu.meshy import MeshyClient

    return MeshyClient.from_env().balance()


def bambu_meshy_analyze(project: str, subject: str | None = None, task_id: str | None = None) -> dict[str, Any]:
    from bambu.meshy import meshy_analyze

    return meshy_analyze(Path(project), subject=subject, input_task_id=task_id)


def bambu_qc(
    sliced: str,
    stl: str | None = None,
    context: str = "profiles/bambu-a1-mini/context.yaml",
    overhang_budget_mm2: float = 150.0,
) -> dict[str, Any]:
    """Printability QC on sliced 3MF and optional STL overhang/island analysis."""

    from bambu.mesh import analyze_islands
    from bambu.printability import analyze_stl_overhangs, load_printer_context, qc_sliced_3mf

    ctx = load_printer_context(Path(context))
    stl_report = (
        analyze_stl_overhangs(Path(stl), patch_budget_mm2=overhang_budget_mm2)
        if stl
        else {"available": False, "reason": "no stl provided", "ok": True}
    )
    island_report = analyze_islands(Path(stl)) if stl else {"available": False, "ok": True}
    slice_report = qc_sliced_3mf(Path(sliced), context=ctx)
    ok = slice_report.get("ok") and stl_report.get("ok", True) and island_report.get("ok", True)
    return {"ok": ok, "stl": stl_report, "islands": island_report, "sliced": slice_report}


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
    server.tool()(bambu_intake)
    server.tool()(bambu_render_spec_sheet)
    server.tool()(bambu_release_check)
    server.tool()(bambu_review_mesh)
    server.tool()(bambu_meshy_concept)
    server.tool()(bambu_meshy_head)
    server.tool()(bambu_meshy_balance)
    server.tool()(bambu_meshy_analyze)
    server.tool()(bambu_qc)
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
