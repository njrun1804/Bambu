"""Project manifests, artifact indexes, and revision feedback for Bambu."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
from typing import Any

import yaml

from bambu.context import context_view, rules_view


PROJECTS_ROOT = Path("projects")
LANES = {"build123d", "openscad", "figurine", "hybrid"}
OUTCOMES = {"not_printed", "success", "partial_success", "failed"}


def slugify(value: str) -> str:
    """Return a filesystem-safe slug for a model project."""

    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or "model"


def create_project(
    intent: str,
    *,
    root: Path = PROJECTS_ROOT,
    slug: str | None = None,
    lane: str = "build123d",
    privacy: str = "private",
    material: str = "Bambu PLA Basic",
    plate_side: str = "deferred",
) -> dict[str, Any]:
    """Create a structured model project workspace from a print idea."""

    project_slug = slug or slugify(intent)
    project_dir = root / project_slug
    for child in (
        "source",
        "source/v1",
        "designs/v1",
        "references",
        "references/ai-concepts",
        "reviews",
        "measurements",
        "photos",
    ):
        directory = project_dir / child
        directory.mkdir(parents=True, exist_ok=True)
        (directory / ".gitkeep").touch()

    if lane == "hybrid":
        from bambu.mesh_lane import scaffold_hybrid_tree, write_fusion_manifest_stub

        scaffold_hybrid_tree(project_dir)
        write_fusion_manifest_stub(project_dir, revision="v1", slug=project_slug)

    context = context_view()
    selected_material = _select_material(context["materials"], material)
    manifest = {
        "schema_version": 2,
        "slug": project_slug,
        "intent": intent,
        "privacy": privacy,
        "lane": lane,
        "archetype": "seated_diorama" if lane in {"build123d", "hybrid"} else "",
        "status": "design",
        "current_revision": "v1" if lane in {"build123d", "hybrid"} else "v001",
        "next_safe_action": "run bambu intake or complete design gate",
        "printer": context["printer"],
        "material": selected_material,
        "plate": {**context["plate"], "side": plate_side},
        "constraints": {
            "dimensions_mm": [],
            "tolerance_notes": "",
        },
        "manual_gates": ["export_review", "slicer_review", "print_start"],
        "source_files": _default_source_files(lane),
    }
    errors = validate_project(manifest)
    if errors:
        raise ValueError("; ".join(errors))

    _write_yaml(project_dir / "project.yaml", manifest)
    rev = manifest["current_revision"]
    if not (project_dir / "artifacts.json").exists():
        write_artifact_manifest(project_dir / "artifacts.json", project_slug=project_slug, revision=rev, paths=[])
    return manifest


def load_project(path: Path | str) -> dict[str, Any]:
    """Load a YAML project manifest."""

    return yaml.safe_load(Path(path).read_text()) or {}


def validate_project(project: dict[str, Any]) -> list[str]:
    """Return design-gate validation errors for a project manifest."""

    errors: list[str] = []
    if not project.get("intent"):
        errors.append("intent is required")
    if project.get("lane") not in LANES:
        errors.append("lane must be one of build123d, openscad, figurine, hybrid")
    if not project.get("privacy"):
        errors.append("privacy is required")
    if not project.get("printer", {}).get("model"):
        errors.append("printer.model is required")
    if not project.get("material", {}).get("name"):
        errors.append("material.name is required")
    if not project.get("plate", {}).get("name"):
        errors.append("plate.name is required")
    if not project.get("current_revision"):
        errors.append("current_revision is required")
    return errors


def project_view(project_path: Path | str) -> dict[str, Any]:
    """Return manifest, artifact, validation, rule, and next-action state."""

    path = Path(project_path)
    manifest_path = path / "project.yaml" if path.is_dir() else path
    project = load_project(manifest_path)
    project_dir = manifest_path.parent
    artifacts_path = project_dir / "artifacts.json"
    artifacts = json.loads(artifacts_path.read_text()) if artifacts_path.exists() else {}
    errors = validate_project(project)
    return {
        "project": project,
        "validation_errors": errors,
        "artifacts": artifacts,
        "rules": rules_view(),
        "next_safe_action": project.get("next_safe_action", "fix manifest validation errors" if errors else "review project"),
    }


def write_artifact_manifest(
    manifest_path: Path | str,
    *,
    project_slug: str,
    revision: str,
    paths: list[Path],
) -> dict[str, Any]:
    """Write a generated artifact index with hashes."""

    path = Path(manifest_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    artifacts = [_artifact_entry(path.parent, item) for item in paths]
    data = {
        "schema_version": 1,
        "project_slug": project_slug,
        "revision": revision,
        "updated_at": _now(),
        "artifacts": artifacts,
    }
    path.write_text(json.dumps(data, indent=2) + "\n")
    return data


def sync_project_artifacts(
    project_path: Path | str,
    *,
    outputs_root: Path = Path("outputs"),
) -> dict[str, Any]:
    """Index generated output files matching a project slug into artifacts.json."""

    project_dir = Path(project_path)
    project = load_project(project_dir / "project.yaml")
    slug = project["slug"]
    revision = project.get("current_revision", "v001")
    paths = sorted(path for path in outputs_root.glob(f"{slug}*") if path.is_file())
    return write_artifact_manifest(
        project_dir / "artifacts.json",
        project_slug=slug,
        revision=revision,
        paths=paths,
    )


def record_print_result(
    project_path: Path | str,
    *,
    outcome: str,
    failure_mode: str = "",
    measurements: dict[str, Any] | None = None,
    material_state: dict[str, Any] | None = None,
    notes: str = "",
    next_revision: str = "",
) -> dict[str, Any]:
    """Record physical print feedback for the current project revision."""

    if outcome not in OUTCOMES:
        raise ValueError(f"outcome must be one of {', '.join(sorted(OUTCOMES))}")

    project_dir = Path(project_path)
    manifest_path = project_dir / "project.yaml"
    project = load_project(manifest_path)
    revision = project.get("current_revision", "v001")
    result = {
        "schema_version": 1,
        "project_slug": project["slug"],
        "revision": revision,
        "recorded_at": _now(),
        "outcome": outcome,
        "failure_mode": failure_mode,
        "measurements": measurements or {},
        "material_state": material_state or {},
        "notes": notes,
        "next_revision": next_revision,
    }

    measurements_dir = project_dir / "measurements"
    reviews_dir = project_dir / "reviews"
    measurements_dir.mkdir(parents=True, exist_ok=True)
    reviews_dir.mkdir(parents=True, exist_ok=True)
    _write_yaml(measurements_dir / f"{revision}.yaml", result)
    (reviews_dir / _next_review_name(reviews_dir, f"print-feedback-{revision}")).write_text(
        _feedback_markdown(result)
    )

    project["status"] = "print_feedback"
    project["next_safe_action"] = "revise source from print feedback" if next_revision else "review print feedback"
    _write_yaml(manifest_path, project)
    return result


def _next_review_name(reviews_dir: Path, slug: str) -> str:
    """Reviews are numbered and append-only; never overwrite earlier evidence."""

    numbers = [
        int(path.name[:3])
        for path in reviews_dir.glob("[0-9][0-9][0-9]-*.md")
        if path.name[:3].isdigit()
    ]
    return f"{max(numbers, default=0) + 1:03d}-{slug}.md"


def _artifact_entry(base: Path, path: Path) -> dict[str, Any]:
    resolved = path.resolve()
    return {
        "path": _relative_to_or_name(path, base),
        "kind": _artifact_kind(path),
        "sha256": hashlib.sha256(resolved.read_bytes()).hexdigest(),
        "bytes": resolved.stat().st_size,
        "generated": True,
    }


def _feedback_markdown(result: dict[str, Any]) -> str:
    lines = [
        "# Print Feedback",
        "",
        f"- project: {result['project_slug']}",
        f"- revision: {result['revision']}",
        f"- outcome: {result['outcome']}",
        f"- failure_mode: {result['failure_mode'] or 'none'}",
        f"- notes: {result['notes'] or 'none'}",
        f"- next_revision: {result['next_revision'] or 'none'}",
        "",
        "## Measurements",
        "",
        "```yaml",
        yaml.safe_dump(result["measurements"], sort_keys=False).strip(),
        "```",
        "",
        "## Material State",
        "",
        "```yaml",
        yaml.safe_dump(result["material_state"], sort_keys=False).strip(),
        "```",
        "",
    ]
    return "\n".join(lines)


def _select_material(materials: list[dict[str, Any]], name: str) -> dict[str, Any]:
    for material in materials:
        if material["name"] == name:
            return material
    raise ValueError(f"Unknown material: {name}")


def _default_source_files(lane: str) -> list[str]:
    if lane in {"build123d", "hybrid"}:
        return ["source/v1/model.py"]
    if lane == "openscad":
        return ["source/model.scad"]
    return ["source/model.scad"]


def _relative_to_or_name(path: Path, base: Path) -> str:
    try:
        return str(path.resolve().relative_to(base.resolve()))
    except ValueError:
        try:
            return str(path.resolve().relative_to(Path.cwd().resolve()))
        except ValueError:
            return str(path.resolve())


def _artifact_kind(path: Path) -> str:
    name = path.name.lower()
    suffix = path.suffix.lower()
    if name.endswith(".gcode.3mf"):
        return "sliced_gcode_3mf"
    if suffix == ".3mf":
        return "project_3mf"
    if suffix == ".stl":
        return "mesh_stl"
    if suffix in {".step", ".stp"}:
        return "cad_step"
    if suffix == ".png":
        return "preview_png"
    if suffix in {".scad", ".py"}:
        return "source_snapshot"
    if suffix == ".gcode":
        return "gcode"
    return "generated_file"


def _write_yaml(path: Path, data: dict[str, Any]) -> None:
    path.write_text(yaml.safe_dump(data, sort_keys=False))


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()
