"""Photo-first project intake: scaffold specs and agent vision prompt."""

from __future__ import annotations

from datetime import datetime, timezone
import shutil
from pathlib import Path
from typing import Any

import yaml

from bambu.projects import slugify, validate_project, write_artifact_manifest
from bambu.context import context_view


ARCHETYPES = ("seated_diorama", "standing_figurines", "relief_plaque")
SPEC_TEMPLATE_ROOT = Path(__file__).resolve().parent / "spec_templates"
PROMPT_PATH = Path("agents/prompts/intake-from-photo.md")


def archetypes_with_templates() -> tuple[str, ...]:
    """Return archetypes that have spec template directories."""

    return tuple(
        archetype
        for archetype in ARCHETYPES
        if (SPEC_TEMPLATE_ROOT / archetype).is_dir()
    )


def _fill_prompt_template(template: str, **values: str) -> str:
    """Fill named prompt slots without interpreting braces in user-provided values."""

    filled = template
    for key, value in values.items():
        filled = filled.replace(f"{{{key}}}", value)
    return filled


def run_intake(
    photo: Path | str,
    *,
    intent: str,
    slug: str | None = None,
    root: Path = Path("projects"),
    archetype: str = "seated_diorama",
    privacy: str = "private",
    material: str = "Bambu PLA Basic",
) -> dict[str, Any]:
    """Copy reference photo, scaffold project tree, and emit agent-fillable intake."""

    photo_path = Path(photo)
    if not photo_path.exists():
        raise FileNotFoundError(f"Reference photo not found: {photo_path}")

    if archetype not in ARCHETYPES:
        raise ValueError(f"archetype must be one of {', '.join(ARCHETYPES)}")

    supported = archetypes_with_templates()
    if archetype not in supported:
        raise ValueError(
            f"archetype {archetype} has no spec templates yet; choose one of {', '.join(supported)}"
        )

    project_slug = slug or slugify(intent)
    project_dir = root / project_slug
    manifest_path = project_dir / "project.yaml"
    if manifest_path.exists():
        raise FileExistsError(
            f"project already exists: {project_dir}; use a different --slug or remove it first"
        )
    _scaffold_project_tree(project_dir, archetype=archetype)

    ref_photo_dir = project_dir / "photos" / "reference"
    ref_photo_dir.mkdir(parents=True, exist_ok=True)
    dest_photo = ref_photo_dir / photo_path.name
    shutil.copy2(photo_path, dest_photo)

    intake_yaml = _write_intake_yaml(
        project_dir,
        intent=intent,
        archetype=archetype,
        photo_rel=f"photos/reference/{photo_path.name}",
    )
    _copy_spec_templates(project_dir, archetype=archetype, revision="v1")
    manifest = _write_project_manifest(
        project_dir,
        slug=project_slug,
        intent=intent,
        archetype=archetype,
        privacy=privacy,
        material=material,
        lane="hybrid",
    )

    from bambu.mesh_lane import scaffold_hybrid_tree, write_fusion_manifest_stub

    scaffold_hybrid_tree(project_dir)
    write_fusion_manifest_stub(project_dir, revision="v1", slug=project_slug)

    prompt = load_intake_prompt(project_dir)
    return {
        "project_dir": str(project_dir),
        "slug": project_slug,
        "archetype": archetype,
        "intent": intent,
        "reference_photo": str(dest_photo),
        "intake_yaml": str(intake_yaml),
        "design_revision": "v1",
        "manifest": manifest,
        "agent_prompt": prompt,
        "next_steps": [
            f"Fill designs/v1/*.yaml using vision on {dest_photo}",
            f"Run: uv run bambu design-check {project_dir} --revision v1",
            f"Run: uv run bambu meshy concept {project_dir} (requires MESHY_API_KEY)",
            f"Author source/v1/model.py using bambu.cad.archetypes.{archetype}",
            f"Run: uv run bambu export-body {project_dir} --revision v1",
            "Shapr3D fuse per docs/learning/shapr3d-fusion-workflow.md",
            f"Run: uv run bambu release-check {project_dir} --revision v1 --stl outputs/<slug>-v1-fused.stl --skip-export --skip-freecad",
        ],
    }


def load_intake_prompt(project_dir: Path | str) -> str:
    """Return intake prompt with project-specific slots filled."""

    project = Path(project_dir)
    intake_path = project / "references" / "intake.yaml"
    intake = yaml.safe_load(intake_path.read_text()) if intake_path.exists() else {}
    template = PROMPT_PATH.read_text() if PROMPT_PATH.exists() else ""
    return _fill_prompt_template(
        template,
        project=str(project),
        slug=intake.get("slug", project.name),
        archetype=intake.get("archetype", "seated_diorama"),
        intent=intake.get("intent", ""),
        photo_path=intake.get("reference_photo", ""),
    )


def classify_archetype_from_intent(intent: str) -> str:
    """Heuristic archetype classifier from plain-English intent."""

    supported = set(archetypes_with_templates())
    text = intent.lower()
    if any(word in text for word in ("chair", "couch", "seated", "sitting", "patio", "diorama")):
        return "seated_diorama" if "seated_diorama" in supported else next(iter(supported))
    if any(word in text for word in ("standing", "figurine", "soccer", "goal")):
        if "standing_figurines" in supported:
            return "standing_figurines"
    if "bust" in text or "relief" in text or "plaque" in text:
        if "relief_plaque" in supported:
            return "relief_plaque"
    return "seated_diorama" if "seated_diorama" in supported else next(iter(supported))


def _scaffold_project_tree(project_dir: Path, *, archetype: str) -> None:
    for child in (
        "source/v1",
        "designs/v1",
        "reviews",
        "measurements",
        "photos",
        "references",
        "references/ai-concepts",
        "fusion",
        "mesh",
    ):
        directory = project_dir / child
        directory.mkdir(parents=True, exist_ok=True)
        gitkeep = directory / ".gitkeep"
        if not gitkeep.exists():
            gitkeep.touch()


def _write_intake_yaml(
    project_dir: Path,
    *,
    intent: str,
    archetype: str,
    photo_rel: str,
) -> Path:
    data = {
        "schema_version": 1,
        "slug": project_dir.name,
        "intent": intent,
        "archetype": archetype,
        "reference_photo": photo_rel,
        "created_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "agent_fill": {
            "subjects": [],
            "pose": "",
            "props": [],
            "recognition_cues": [],
            "forbidden_traps": [],
            "dimensions_mm": {"width": None, "depth": None, "height": None},
        },
        "status": "awaiting_agent_vision",
    }
    path = project_dir / "references" / "intake.yaml"
    path.write_text(yaml.safe_dump(data, sort_keys=False))
    return path


def _copy_spec_templates(project_dir: Path, *, archetype: str, revision: str) -> None:
    template_dir = SPEC_TEMPLATE_ROOT / archetype
    if not template_dir.is_dir():
        raise ValueError(f"missing spec templates for archetype: {archetype}")
    design_dir = project_dir / "designs" / revision
    design_dir.mkdir(parents=True, exist_ok=True)
    for template in template_dir.glob("*.yaml"):
        dest = design_dir / template.name
        if not dest.exists():
            shutil.copy2(template, dest)


def _write_project_manifest(
    project_dir: Path,
    *,
    slug: str,
    intent: str,
    archetype: str,
    privacy: str,
    material: str,
    lane: str = "hybrid",
) -> dict[str, Any]:
    context = context_view()
    selected_material = next(m for m in context["materials"] if m["name"] == material)
    manifest = {
        "schema_version": 2,
        "slug": slug,
        "intent": intent,
        "privacy": privacy,
        "lane": lane,
        "archetype": archetype,
        "status": "intake",
        "current_revision": "v1",
        "next_safe_action": "fill specs from reference photo via agent vision",
        "printer": context["printer"],
        "material": selected_material,
        "plate": {**context["plate"], "side": "textured"},
        "constraints": {"dimensions_mm": [], "tolerance_notes": ""},
        "manual_gates": ["design_check", "release_check", "render_approval", "slicer_review", "print_start"],
        "source_files": ["source/v1/model.py"],
    }
    errors = validate_project(manifest)
    if errors:
        raise ValueError("; ".join(errors))
    path = project_dir / "project.yaml"
    path.write_text(yaml.safe_dump(manifest, sort_keys=False))
    artifacts_path = project_dir / "artifacts.json"
    if not artifacts_path.exists():
        write_artifact_manifest(artifacts_path, project_slug=slug, revision="v1", paths=[])
    return manifest
