"""Agent-safe 3D review workflow for generated CAD artifacts."""

from __future__ import annotations

from dataclasses import dataclass
import json
import os
from pathlib import Path
import shutil
import subprocess
from typing import Any

from bambu.cad import export_build123d_project
from bambu.mesh import analyze_islands, analyze_overhangs, inspect_mesh
from bambu.projects import sync_project_artifacts


FREECAD_JSON_BEGIN = "FREECAD_REVIEW_JSON_BEGIN"
FREECAD_JSON_END = "FREECAD_REVIEW_JSON_END"


@dataclass(frozen=True)
class FreeCADInstall:
    available: bool
    app: Path | None
    binary: Path | None
    env: dict[str, str]
    reason: str = ""

    @property
    def command(self) -> list[str]:
        if self.binary is None:
            return []
        return [str(self.binary), "-c"]


def detect_freecad(candidates: list[Path] | None = None, *, runtime_root: Path = Path(".freecad-runtime")) -> FreeCADInstall:
    """Detect FreeCAD.app and return a console-mode execution environment."""

    env_bin = os.environ.get("FREECAD_BIN")
    if env_bin:
        binary = Path(env_bin)
        if binary.exists():
            return _freecad_install(binary, app=None, runtime_root=runtime_root)
        return FreeCADInstall(False, None, None, {}, f"FREECAD_BIN does not exist: {binary}")

    app_candidates = candidates or [Path("/Applications/FreeCAD.app")]
    for app in app_candidates:
        binary = app / "Contents" / "MacOS" / "FreeCAD"
        if binary.exists():
            return _freecad_install(binary, app=app, runtime_root=runtime_root)

    return FreeCADInstall(False, None, None, {}, "FreeCAD.app not found")


def inspect_step_with_freecad(
    step_path: Path,
    output_json: Path,
    *,
    freecad: FreeCADInstall | None = None,
    script: Path = Path("tools/freecad_review.py"),
) -> dict[str, Any]:
    """Inspect a STEP file using FreeCAD console mode and return its JSON report."""

    install = freecad or detect_freecad()
    if not install.available:
        return {"available": False, "reason": install.reason}
    if not step_path.exists():
        raise FileNotFoundError(step_path)

    output_json.parent.mkdir(parents=True, exist_ok=True)
    command = install.command + [
        str(script.resolve()),
        "--pass",
        str(step_path.resolve()),
        str(output_json.resolve()),
    ]
    completed = subprocess.run(command, check=False, text=True, capture_output=True, env=install.env)
    if output_json.exists():
        parsed = json.loads(output_json.read_text())
        parsed.setdefault("available", True)
        parsed["freecad_returncode"] = completed.returncode
        if completed.stderr:
            parsed["freecad_stderr_tail"] = completed.stderr[-1000:]
        return parsed
    if completed.returncode != 0:
        return {
            "available": True,
            "ok": False,
            "returncode": completed.returncode,
            "stdout": completed.stdout,
            "stderr": completed.stderr,
            "warnings": ["freecad launch failed"],
        }
    parsed = parse_freecad_json(completed.stdout + "\n" + completed.stderr)
    parsed.setdefault("available", True)
    parsed["freecad_returncode"] = completed.returncode
    return parsed


def parse_freecad_json(output: str) -> dict[str, Any]:
    """Extract the marked FreeCAD JSON payload from noisy console output."""

    if FREECAD_JSON_BEGIN not in output or FREECAD_JSON_END not in output:
        raise ValueError("FreeCAD review JSON markers not found")
    payload = output.split(FREECAD_JSON_BEGIN, 1)[1].split(FREECAD_JSON_END, 1)[0].strip()
    return json.loads(payload)


def inspect_stl_mesh(stl_path: Path) -> dict[str, Any]:
    """Watertight/manifold mesh gate; see bambu.mesh.inspect_mesh."""

    return inspect_mesh(stl_path)


def detect_blender() -> str | None:
    """Return a usable Blender executable path if available."""

    return shutil.which("blender") or (
        "/opt/homebrew/bin/blender" if Path("/opt/homebrew/bin/blender").exists() else None
    )


DEFAULT_PREVIEW_VIEWS: list[dict[str, Any]] = [
    {"name": "front", "location": [0, -220, 48], "target": [0, 0, 32], "ortho_scale": 138},
    {"name": "front-angle", "location": [120, -190, 75], "target": [0, 0, 32], "ortho_scale": 145},
    {"name": "rear-angle", "location": [-120, 190, 75], "target": [0, 0, 32], "ortho_scale": 145},
]


def build_blender_preview_command(
    *, blender: str, stl: Path, output_dir: Path, views: list[dict[str, Any]] | None = None
) -> list[str]:
    """Build a read-only Blender preview command for an STL."""

    views = views or DEFAULT_PREVIEW_VIEWS
    views_literal = json.dumps(views)
    script = f"""
import bpy
from mathutils import Vector
bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete()
bpy.ops.wm.stl_import(filepath={str(stl)!r})
obj = bpy.context.object
bpy.context.view_layer.update()
coords = [obj.matrix_world @ Vector(corner) for corner in obj.bound_box]
min_v = Vector((min(v.x for v in coords), min(v.y for v in coords), min(v.z for v in coords)))
max_v = Vector((max(v.x for v in coords), max(v.y for v in coords), max(v.z for v in coords)))
center = (min_v + max_v) / 2
obj.location -= Vector((center.x, center.y, min_v.z))
mat = bpy.data.materials.new('Green PLA preview')
mat.diffuse_color = (0.03, 0.90, 0.25, 1.0)
obj.data.materials.append(mat)
bpy.context.scene.render.engine = 'BLENDER_WORKBENCH'
bpy.context.scene.display.shading.light = 'STUDIO'
bpy.context.scene.display.shading.color_type = 'MATERIAL'
# Cavity + shadow shading makes low-relief detail (engraved pupils, smile
# lines, hair grooves) legible in renders, which flat shading hides.
bpy.context.scene.display.shading.show_cavity = True
bpy.context.scene.display.shading.cavity_type = 'BOTH'
bpy.context.scene.display.shading.cavity_ridge_factor = 1.5
bpy.context.scene.display.shading.cavity_valley_factor = 1.5
bpy.context.scene.display.shading.curvature_ridge_factor = 1.5
bpy.context.scene.display.shading.curvature_valley_factor = 1.5
bpy.context.scene.display.shading.show_shadows = True
bpy.context.scene.render.resolution_x = 1600
bpy.context.scene.render.resolution_y = 1100
bpy.ops.object.camera_add()
cam = bpy.context.object
bpy.context.scene.camera = cam
cam.data.type = 'ORTHO'
def look_at(target):
    direction = Vector(target) - Vector(cam.location)
    cam.rotation_euler = direction.to_track_quat('-Z', 'Y').to_euler()
for view in {views_literal}:
    cam.location = view['location']
    cam.data.ortho_scale = view['ortho_scale']
    look_at(view['target'])
    bpy.context.scene.render.filepath = {str(output_dir)!r} + '/' + view['name'] + '.png'
    bpy.ops.render.render(write_still=True)
"""
    return [blender, "--background", "--python-expr", script]


def render_blender_previews(
    stl: Path,
    output_dir: Path,
    *,
    blender: str | None = None,
    views: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Render preview PNGs through Blender if available."""

    executable = blender or detect_blender()
    if not executable:
        return {"available": False, "reason": "Blender not found", "paths": []}
    output_dir.mkdir(parents=True, exist_ok=True)
    command = build_blender_preview_command(blender=executable, stl=stl, output_dir=output_dir, views=views)
    completed = subprocess.run(command, check=False, text=True, capture_output=True)
    paths = sorted(str(path) for path in output_dir.glob("*.png"))
    return {
        "available": True,
        "ok": completed.returncode == 0,
        "returncode": completed.returncode,
        "paths": paths,
        "stderr_tail": completed.stderr[-1000:],
    }


def review_project_3d(
    project_path: Path | str,
    *,
    outputs_root: Path = Path("outputs"),
    render: bool = True,
    source_file: Path | None = None,
    output_slug: str | None = None,
    views: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Export, inspect, render, and summarize a project without printer contact."""

    project = Path(project_path)
    export = export_build123d_project(
        project, output_dir=outputs_root, source_file=source_file, output_slug=output_slug
    )
    artifacts = sync_project_artifacts(project, outputs_root=outputs_root)
    step = Path(export["step"])
    stl = Path(export["stl"])
    review_dir = outputs_root / "review" / export["project_slug"]
    freecad_report = inspect_step_with_freecad(step, review_dir / "freecad_review.json")
    mesh_report = inspect_mesh(stl)
    overhang_report = analyze_overhangs(stl)
    island_report = analyze_islands(stl)
    blender_report = (
        render_blender_previews(stl, review_dir, views=views) if render else {"available": False, "paths": []}
    )
    return {
        "project": export["project_slug"],
        "step": str(step),
        "stl": str(stl),
        "bounding_box_mm": export["bounding_box_mm"],
        "fits_a1_mini": export["fits_a1_mini"],
        "freecad": freecad_report,
        "mesh": mesh_report,
        "overhangs": overhang_report,
        "islands": island_report,
        "blender": blender_report,
        "artifact_count": len(artifacts.get("artifacts", [])),
        "printer_contact": False,
        "manual_boundary": "No printer contact. Review CAD, previews, slicer settings, and supports manually.",
    }


def _freecad_install(binary: Path, *, app: Path | None, runtime_root: Path) -> FreeCADInstall:
    runtime = runtime_root.resolve()
    home = runtime / "home"
    data = runtime / "data"
    temp = runtime / "temp"
    for path in (home, data, temp):
        path.mkdir(parents=True, exist_ok=True)
    resources = binary.parents[1] / "Resources"
    env = {
        "HOME": str(home),
        "PATH": "/usr/bin:/bin:/opt/homebrew/bin",
        "FREECAD_USER_HOME": str(home),
        "FREECAD_USER_DATA": str(data),
        "FREECAD_USER_TEMP": str(temp),
        "PYTHONHOME": str(resources),
        "PYTHONPATH": str(resources),
        "LD_LIBRARY_PATH": str(resources / "lib"),
        "SSL_CERT_FILE": str(resources / "ssl" / "cacert.pem"),
        "GIT_SSL_CAINFO": str(resources / "ssl" / "cacert.pem"),
    }
    return FreeCADInstall(True, app, binary, env)
