"""Photo-first project intake: scaffold specs and agent vision prompt."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import shutil
import subprocess
from pathlib import Path
from typing import Any

import yaml

from bambu.projects import slugify, validate_project, write_artifact_manifest
from bambu.context import context_view
from bambu.reference_validation import KNOWN_WRONG_REFERENCE_MARKERS


ARCHETYPES = ("seated_diorama", "standing_figurines", "relief_plaque")
SPEC_TEMPLATE_ROOT = Path(__file__).resolve().parent / "spec_templates"
PROMPT_PATH = Path("agents/prompts/intake-from-photo.md")
REPO_ROOT = Path(__file__).resolve().parent.parent
CURSOR_WORKSPACE_STORAGE = (
    Path.home() / "Library/Application Support/Cursor/User/workspaceStorage"
)
CURSOR_UPLOAD_SENTINELS = frozenset({"@cursor", "cursor", "cursor-upload", "latest"})
FORBIDDEN_DEFAULT_REFERENCES = (
    REPO_ROOT / "private/references/clear-right-pair.jpg",
    REPO_ROOT / "private/references/group-right-pair.jpg",
)


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


def find_cursor_upload_photos() -> list[Path]:
    """Return chat-upload images from Cursor workspaceStorage caches, newest first."""

    if not CURSOR_WORKSPACE_STORAGE.is_dir():
        return []
    uploads: list[Path] = []
    for images_dir in CURSOR_WORKSPACE_STORAGE.glob("*/images"):
        uploads.extend(
            path
            for path in images_dir.iterdir()
            if path.is_file() and path.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp", ".heic"}
        )
    return sorted(uploads, key=lambda path: path.stat().st_mtime, reverse=True)


def _looks_like_cursor_upload_name(name: str) -> bool:
    lowered = name.lower()
    return lowered in CURSOR_UPLOAD_SENTINELS or (
        len(name) >= 32 and any(ch in lowered for ch in ("_", "-"))
    )


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _reject_wrong_reference(
    photo_path: Path,
    *,
    archetype: str,
    slug: str | None,
    force_reference: bool,
) -> None:
    if force_reference:
        return

    resolved = photo_path.resolve()
    if archetype == "seated_diorama" or slug == "best-buds-chair":
        photo_digest: str | None = None
        for forbidden in FORBIDDEN_DEFAULT_REFERENCES:
            if not forbidden.exists():
                continue
            # Block both the literal file and any renamed byte-identical copy: the
            # original mistake was copying clear-right-pair.jpg to patio-reference.jpg.
            if resolved == forbidden.resolve():
                raise ValueError(
                    f"Refusing default neighbor reference ({forbidden.name}) for "
                    f"{slug or archetype}. Provide the actual reference photo path or "
                    "a Cursor chat upload (@cursor)."
                )
            if photo_digest is None:
                photo_digest = _sha256(resolved)
            if photo_digest == _sha256(forbidden):
                raise ValueError(
                    f"Refusing reference byte-identical to {forbidden.name} (marina "
                    f"neighbors, not the patio woman+dog+chair scene) for {slug or archetype}. "
                    "Provide the actual reference photo path or a Cursor chat upload (@cursor)."
                )

    if any(marker in photo_path.as_posix().lower() for marker in KNOWN_WRONG_REFERENCE_MARKERS):
        raise ValueError(
            f"Refusing intake from known wrong reference ({photo_path.name}). "
            "Use the actual patio woman+dog+chair photo or pass --force-reference after review."
        )


def resolve_photo_path(
    photo: Path | str,
    *,
    slug: str | None = None,
    archetype: str = "seated_diorama",
    force_reference: bool = False,
) -> Path:
    """Resolve an explicit photo path or a Cursor chat upload cache image."""

    raw = str(photo).strip()
    if raw in CURSOR_UPLOAD_SENTINELS:
        uploads = find_cursor_upload_photos()
        if not uploads:
            raise FileNotFoundError(
                "No Cursor chat upload found in workspaceStorage cache. "
                "Attach the photo in chat or pass an explicit path."
            )
        photo_path = uploads[0]
        _reject_wrong_reference(photo_path, archetype=archetype, slug=slug, force_reference=force_reference)
        return photo_path

    photo_path = Path(raw).expanduser()
    candidates = [photo_path]
    if not photo_path.is_absolute():
        candidates.append(Path.cwd() / photo_path)

    for candidate in candidates:
        if candidate.exists():
            resolved = candidate.resolve()
            _reject_wrong_reference(
                resolved, archetype=archetype, slug=slug, force_reference=force_reference
            )
            return resolved

    if photo_path.name:
        for cached in find_cursor_upload_photos():
            if cached.name == photo_path.name:
                _reject_wrong_reference(
                    cached, archetype=archetype, slug=slug, force_reference=force_reference
                )
                return cached

    raise FileNotFoundError(f"Reference photo not found: {photo_path}")


def _reference_dest_name(source: Path, *, slug: str | None = None) -> str:
    if slug and _looks_like_cursor_upload_name(source.name):
        return f"{slug}-reference.jpg"
    if source.suffix.lower() in {".jpg", ".jpeg"}:
        return source.name
    return f"{source.stem}.jpg"


def persist_reference_photo(
    source: Path,
    project_dir: Path,
    *,
    slug: str | None = None,
    dest_name: str | None = None,
) -> Path:
    """Copy or convert a resolved reference photo into photos/reference/."""

    ref_photo_dir = project_dir / "photos" / "reference"
    ref_photo_dir.mkdir(parents=True, exist_ok=True)
    filename = dest_name or _reference_dest_name(source, slug=slug)
    dest_photo = ref_photo_dir / filename

    if source.suffix.lower() in {".jpg", ".jpeg"} and source.resolve() != dest_photo.resolve():
        shutil.copy2(source, dest_photo)
        return dest_photo

    try:
        from PIL import Image

        with Image.open(source) as image:
            image.convert("RGB").save(dest_photo, format="JPEG", quality=92, optimize=True)
        return dest_photo
    except ImportError:
        dest_photo.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(
            ["sips", "-s", "format", "jpeg", str(source), "--out", str(dest_photo)],
            check=True,
            capture_output=True,
        )
        return dest_photo


def run_intake(
    photo: Path | str,
    *,
    intent: str,
    slug: str | None = None,
    root: Path = Path("projects"),
    archetype: str = "seated_diorama",
    privacy: str = "private",
    material: str = "Bambu PLA Basic",
    force_reference: bool = False,
) -> dict[str, Any]:
    """Copy reference photo, scaffold project tree, and emit agent-fillable intake."""

    project_slug = slug or slugify(intent)
    photo_path = resolve_photo_path(
        photo,
        slug=project_slug,
        archetype=archetype,
        force_reference=force_reference,
    )

    if archetype not in ARCHETYPES:
        raise ValueError(f"archetype must be one of {', '.join(ARCHETYPES)}")

    supported = archetypes_with_templates()
    if archetype not in supported:
        raise ValueError(
            f"archetype {archetype} has no spec templates yet; choose one of {', '.join(supported)}"
        )

    project_dir = root / project_slug
    manifest_path = project_dir / "project.yaml"
    if manifest_path.exists():
        raise FileExistsError(
            f"project already exists: {project_dir}; use a different --slug or remove it first"
        )
    _scaffold_project_tree(project_dir, archetype=archetype)

    dest_photo = persist_reference_photo(photo_path, project_dir, slug=project_slug)
    photo_source_note = (
        f"Cursor upload cache: {photo_path}"
        if str(photo).strip() in CURSOR_UPLOAD_SENTINELS
        else None
    )

    intake_yaml = _write_intake_yaml(
        project_dir,
        intent=intent,
        archetype=archetype,
        photo_rel=f"photos/reference/{dest_photo.name}",
        reference_photo_confirmed=force_reference,
        photo_source=photo_source_note,
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
            f"Run: uv run bambu fuse-mesh {project_dir} --revision v1",
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
    reference_photo_confirmed: bool = False,
    photo_source: str | None = None,
) -> Path:
    data = {
        "schema_version": 1,
        "slug": project_dir.name,
        "intent": intent,
        "archetype": archetype,
        "reference_photo": photo_rel,
        "reference_photo_confirmed": reference_photo_confirmed,
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
    if photo_source:
        data["reference_source"] = photo_source
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
