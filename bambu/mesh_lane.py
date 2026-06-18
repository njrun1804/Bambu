"""Hybrid lane: fusion manifest, mesh artifact intake, and provenance."""

from __future__ import annotations

import hashlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from bambu.cad.specs import character_metrics, load_specs
from bambu.projects import load_project, write_artifact_manifest


FUSION_MANIFEST_NAME = "fusion_manifest.yaml"
MESH_DIR_NAME = "mesh"
PROVENANCE_NAME = "provenance.yaml"


def fusion_manifest_path(project_dir: Path | str, *, revision: str = "v1") -> Path:
    return Path(project_dir) / "designs" / revision / FUSION_MANIFEST_NAME


def load_fusion_manifest(project_dir: Path | str, *, revision: str = "v1") -> dict[str, Any]:
    """Load fusion manifest YAML for a design revision."""

    path = fusion_manifest_path(project_dir, revision=revision)
    if not path.exists():
        return {}
    return yaml.safe_load(path.read_text()) or {}


def write_fusion_manifest_stub(
    project_dir: Path | str,
    *,
    revision: str = "v1",
    slug: str | None = None,
) -> Path:
    """Write a fusion manifest stub with alignment hints from people.yaml."""

    project = Path(project_dir)
    manifest = load_project(project / "project.yaml")
    project_slug = slug or manifest.get("slug", project.name)
    specs = load_specs(project, revision=revision)
    head_meshes: list[dict[str, Any]] = []
    for metric in character_metrics(specs):
        person_id = metric.get("id")
        if not person_id:
            continue
        center = metric.get("face_center") or [0, 0, 0]
        head_mm = next(
            (
                p.get("head_mm", {})
                for p in specs.get("people", {}).get("people", [])
                if p.get("id") == person_id
            ),
            {},
        )
        scale = 1.0
        if head_mm.get("width"):
            scale = float(head_mm["width"]) / 20.0
        head_meshes.append(
            {
                "id": person_id,
                "source": f"mesh/{person_id}-head.stl",
                "align": {
                    "x": center[0] if len(center) > 0 else 0.0,
                    "y": center[1] if len(center) > 1 else 0.0,
                    "z": center[2] if len(center) > 2 else 0.0,
                    "scale": scale,
                },
            }
        )
    if not head_meshes:
        head_meshes = [
            {"id": "subject", "source": "mesh/subject-head.stl", "align": {"x": 0, "y": 0, "z": 0, "scale": 1.0}}
        ]

    data = {
        "schema_version": 1,
        "body_artifact": f"outputs/{project_slug}-{revision}-body.step",
        "head_meshes": head_meshes,
        "fused_artifact": f"outputs/{project_slug}-{revision}-fused.stl",
        "fusion_tool": "shapr3d",
        "fusion_status": "pending",
    }
    path = fusion_manifest_path(project, revision=revision)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(data, sort_keys=False))
    return path


def scaffold_hybrid_tree(project_dir: Path | str) -> None:
    """Create fusion/ and mesh/ directories for hybrid lane projects."""

    project = Path(project_dir)
    for child in ("fusion", MESH_DIR_NAME):
        directory = project / child
        directory.mkdir(parents=True, exist_ok=True)
        gitkeep = directory / ".gitkeep"
        if not gitkeep.exists():
            gitkeep.touch()


def mesh_intake(
    project_path: Path | str,
    *,
    file: Path | str,
    role: str,
    meshy_task_id: str = "",
    endpoint: str = "",
    revision: str | None = None,
) -> dict[str, Any]:
    """Copy a mesh into projects/<slug>/mesh/ and record provenance."""

    project = Path(project_path)
    manifest = load_project(project / "project.yaml")
    rev = revision or manifest.get("current_revision", "v1")
    src = Path(file)
    if not src.exists():
        raise FileNotFoundError(src)

    mesh_dir = project / MESH_DIR_NAME
    mesh_dir.mkdir(parents=True, exist_ok=True)
    dest = mesh_dir / src.name
    if src.resolve() != dest.resolve():
        shutil.copy2(src, dest)

    provenance_path = mesh_dir / PROVENANCE_NAME
    provenance = yaml.safe_load(provenance_path.read_text()) if provenance_path.exists() else {}
    provenance.setdefault("heads", {})
    entry = {
        "role": role,
        "artifact": f"mesh/{dest.name}",
        "sha256": hashlib.sha256(dest.read_bytes()).hexdigest(),
        "updated_at": _now(),
    }
    if meshy_task_id:
        entry["task_id"] = meshy_task_id
    if endpoint:
        entry["endpoint"] = endpoint
    provenance["heads"][role] = entry
    provenance_path.write_text(yaml.safe_dump(provenance, sort_keys=False))

    artifacts_path = project / "artifacts.json"
    existing: list[Path] = []
    if artifacts_path.exists():
        data = json.loads(artifacts_path.read_text())
        for item in data.get("artifacts", []):
            rel = item.get("path", "")
            candidate = project / rel
            if candidate.exists():
                existing.append(candidate)
    if dest not in existing:
        existing.append(dest)
    artifact_index = write_artifact_manifest(
        artifacts_path,
        project_slug=manifest["slug"],
        revision=rev,
        paths=existing,
    )
    return {
        "project": manifest["slug"],
        "revision": rev,
        "mesh_path": str(dest),
        "role": role,
        "provenance": provenance,
        "artifacts": artifact_index,
    }


def write_mesh_provenance(project_dir: Path | str, data: dict[str, Any]) -> Path:
    """Write or merge mesh/provenance.yaml for Meshy task chains."""

    project = Path(project_dir)
    mesh_dir = project / MESH_DIR_NAME
    mesh_dir.mkdir(parents=True, exist_ok=True)
    path = mesh_dir / PROVENANCE_NAME
    existing = yaml.safe_load(path.read_text()) if path.exists() else {}
    merged = {**existing, **data}
    path.write_text(yaml.safe_dump(merged, sort_keys=False))
    return path


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()
