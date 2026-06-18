"""Structured, agent-first design pipeline specs for 3D print projects."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml


SPEC_FILES = {
    "design": "design.yaml",
    "people": "people.yaml",
    "print_constraints": "print_constraints.yaml",
    "visual_acceptance": "visual_acceptance.yaml",
    "build_plan": "build_plan.yaml",
    "views": "views.yaml",
}

ARCHETYPE_PROFILES_ROOT = Path("profiles/archetypes")

DEFAULT_FORBIDDEN_TRAPS = [
    "hair strands as free geometry",
    "separate eyeglass frames",
    "thin dog legs",
    "floating glasses frames",
    "unsupported hair strands",
    "thin separate fingers",
]


def load_design_spec(project_path: Path | str, *, revision: str = "v3") -> dict[str, Any]:
    """Load a structured design revision from designs/<revision> YAML files."""

    project = Path(project_path)
    design_dir = project / "designs" / revision
    manifest_path = project / "project.yaml"
    lane = ""
    if manifest_path.exists():
        manifest = yaml.safe_load(manifest_path.read_text()) or {}
        lane = manifest.get("lane", "")
    files: dict[str, Any] = {}
    missing: list[str] = []
    for key, filename in SPEC_FILES.items():
        path = design_dir / filename
        if path.exists():
            files[key] = yaml.safe_load(path.read_text()) or {}
        else:
            if key != "views":
                files[key] = {}
                missing.append(str(path))
            else:
                files[key] = {}
    return {
        "project_path": str(project),
        "revision": revision,
        "design_dir": str(design_dir),
        "lane": lane,
        "files": files,
        "missing_files": missing,
    }


def load_archetype_profile(archetype: str) -> dict[str, Any]:
    path = ARCHETYPE_PROFILES_ROOT / f"{archetype}.yaml"
    if not path.exists():
        return {}
    return yaml.safe_load(path.read_text()) or {}


def validate_design_spec(spec: dict[str, Any]) -> dict[str, Any]:
    """Validate a design spec and return an agent-readable gate report."""

    files = spec.get("files", {})
    design = files.get("design", {})
    people = files.get("people", {})
    constraints = files.get("print_constraints", {})
    visual = files.get("visual_acceptance", {})
    build_plan = files.get("build_plan", {})
    errors: list[str] = []
    warnings: list[str] = []

    if spec.get("missing_files"):
        errors.extend(f"missing spec file: {path}" for path in spec["missing_files"])
    if not design.get("intent"):
        errors.append("design.intent is required")

    archetype = design.get("archetype") or constraints.get("archetype")
    archetype_declared = bool(archetype)
    profile = load_archetype_profile(archetype) if archetype_declared else {}
    if not archetype_declared:
        warnings.append(
            "design.archetype is not declared; archetype profile gates are skipped for legacy specs"
        )

    source_of_truth = design.get("agentic_pipeline", {}).get("source_of_truth")
    if source_of_truth not in ("structured_specs", "authored_cad_with_spec_gates"):
        errors.append(
            "design.agentic_pipeline.source_of_truth must be structured_specs"
            " or authored_cad_with_spec_gates"
        )

    printer = constraints.get("printer", {})
    if printer.get("model") != "Bambu Lab A1 mini":
        errors.append("print_constraints.printer.model must be Bambu Lab A1 mini")
    if printer.get("printer_contact_allowed") is not False:
        errors.append("print_constraints.printer.printer_contact_allowed must be false")
    target_model = constraints.get("target_model", {})
    max_size = target_model.get("max_size_mm", {})
    for axis in ("x", "y", "z"):
        if not isinstance(max_size.get(axis), (int, float)) or max_size[axis] <= 0:
            errors.append(f"print_constraints.target_model.max_size_mm.{axis} must be positive")

    person_entries = people.get("people", [])
    person_ids = [p.get("id") for p in person_entries if p.get("id")]
    person_names = [p.get("name") for p in person_entries if p.get("name")]
    if not person_ids:
        errors.append("people.people must include at least one subject with id")
    for person in person_entries:
        if not person.get("id"):
            errors.append("each people.people entry must have id")
        if not person.get("name"):
            errors.append(f"people.people[{person.get('id', '?')}] must have name")

    min_feature = constraints.get("feature_minimums", {}).get("raised_detail_width_mm")
    if profile.get("min_feature_width_mm") and min_feature:
        if min_feature < profile["min_feature_width_mm"]:
            errors.append(
                f"print_constraints.feature_minimums.raised_detail_width_mm must be >= "
                f"{profile['min_feature_width_mm']} for archetype {archetype}"
            )

    forbidden_traps = design.get("forbidden_traps") or design.get("must_not_include") or []
    if profile.get("forbidden_traps"):
        for trap in profile["forbidden_traps"]:
            if trap not in forbidden_traps:
                warnings.append(f"design.forbidden_traps should include archetype trap: {trap}")

    required_elements = profile.get("required_scene_elements", []) if archetype_declared else []
    scene_props = design.get("scene", {}).get("props", []) + design.get("must_preserve", [])
    scene_text = " ".join(str(x) for x in scene_props).lower()
    for element in required_elements:
        if element.get("required") and element.get("id") not in scene_text and element.get("label", "").lower() not in scene_text:
            label = element.get("label", element.get("id", ""))
            if not _scene_has_element(design, element.get("id", "")):
                errors.append(f"archetype {archetype} requires scene element: {label}")

    required_views = visual.get("required_views", [])
    if "face_closeup" not in required_views and not any(v.startswith("face_closeup_") for v in required_views):
        errors.append("visual_acceptance.required_views must include face_closeup or face_closeup_<id>")
    if visual.get("thumbnail_check", {}).get("enabled") and not visual["thumbnail_check"].get("size_px"):
        errors.append("visual_acceptance.thumbnail_check.size_px is required when enabled")

    if not visual.get("human_review_questions"):
        errors.append("visual_acceptance.human_review_questions is required")

    lane = spec.get("lane", "")
    concept = design.get("reference_inputs", {}).get("concept_sheet", {})
    if lane == "hybrid":
        if not concept.get("path"):
            errors.append("design.reference_inputs.concept_sheet.path is required when lane is hybrid")
        if not concept.get("role"):
            warnings.append("design.reference_inputs.concept_sheet.role should describe visual acceptance target")

    review_tools = build_plan.get("review_tools", {})
    agent_tools = review_tools.get("agent", [])
    manual_tools = review_tools.get("manual", [])
    for tool in ("FreeCAD", "Blender"):
        if tool not in agent_tools:
            errors.append(f"build_plan.review_tools.agent must include {tool}")
    if "Bambu Studio" not in manual_tools:
        errors.append("build_plan.review_tools.manual must include Bambu Studio")

    revision = spec.get("revision", "v3")
    next_actions = build_plan.get("next_agent_actions", [])
    if not next_actions:
        errors.append("build_plan.next_agent_actions is required")
    if not any(f"designs/{revision}" in action for action in next_actions):
        warnings.append(f"next actions should reference designs/{revision}/*.yaml")

    geometry = constraints.get("geometry_contract", {})
    if geometry.get("single_fused_solid") is not True:
        warnings.append("print_constraints.geometry_contract.single_fused_solid should be true")

    gates = {
        "structured_specs_present": not spec.get("missing_files"),
        "a1_mini_specific": printer.get("model") == "Bambu Lab A1 mini",
        "printer_contact_blocked": printer.get("printer_contact_allowed") is False,
        "subjects_specified": bool(person_ids),
        "archetype_declared": archetype_declared,
        "visual_review_specified": bool(required_views),
        "agent_review_tools_specified": all(tool in agent_tools for tool in ("FreeCAD", "Blender")),
        "forbidden_traps_documented": bool(forbidden_traps),
        "concept_sheet_hybrid": not (lane == "hybrid" and not concept.get("path")),
    }

    return {
        "ok": not errors,
        "revision": spec.get("revision"),
        "design_dir": spec.get("design_dir"),
        "archetype": archetype,
        "errors": errors,
        "warnings": warnings,
        "gates": gates,
        "design": {
            "id": design.get("design_id", ""),
            "source_of_truth": source_of_truth,
            "direction": design.get("intent", {}).get("design_direction", design.get("intent", "")),
            "archetype": archetype,
        },
        "printer": {
            "model": printer.get("model", ""),
            "nozzle_mm": printer.get("nozzle_mm"),
            "material_first_pass": printer.get("material_first_pass", ""),
            "max_size_mm": max_size,
        },
        "printer_contact_allowed": printer.get("printer_contact_allowed"),
        "people": person_names,
        "people_ids": person_ids,
        "required_review_tools": agent_tools,
        "manual_review_tools": manual_tools,
        "required_views": required_views,
        "forbidden_traps": forbidden_traps,
        "next_agent_actions": next_actions,
    }


def _scene_has_element(design: dict[str, Any], element_id: str) -> bool:
    scene = design.get("scene", {})
    for key in ("props", "furniture", "subjects"):
        items = scene.get(key, [])
        for item in items:
            if isinstance(item, str) and element_id in item.lower():
                return True
            if isinstance(item, dict) and item.get("id") == element_id:
                return True
    must_preserve = " ".join(design.get("must_preserve", [])).lower()
    return element_id.replace("_", " ") in must_preserve or element_id in must_preserve


def render_spec_sheet(project_path: Path | str, *, revision: str = "v1") -> str:
    """Render a one-page markdown design sheet from YAML for human sign-off."""

    spec = load_design_spec(project_path, revision=revision)
    files = spec["files"]
    design = files.get("design", {})
    people = files.get("people", {})
    constraints = files.get("print_constraints", {})
    visual = files.get("visual_acceptance", {})
    project = Path(project_path)
    intake_path = project / "references" / "intake.yaml"
    intake = yaml.safe_load(intake_path.read_text()) if intake_path.exists() else {}
    photo = intake.get("reference_photo", "")

    lines = [
        f"# Design spec sheet — {design.get('design_id', project.name)} ({revision})",
        "",
        f"**Archetype:** {design.get('archetype', constraints.get('archetype', 'unknown'))}",
        "",
        "## Intent",
        "",
        str(design.get("intent", "")),
        "",
    ]
    if photo:
        lines.extend(["## Reference photo", "", f"`{photo}` (local, gitignored)", ""])
    lines.extend(["## Subjects", ""])
    for person in people.get("people", []):
        lines.append(f"- **{person.get('name', person.get('id'))}** ({person.get('id', '')}): "
                     f"{', '.join(person.get('likeness_cues', []))}")
    lines.extend(["", "## Must preserve", ""])
    for item in design.get("must_preserve", []):
        lines.append(f"- {item}")
    lines.extend(["", "## Forbidden traps", ""])
    for trap in design.get("forbidden_traps", DEFAULT_FORBIDDEN_TRAPS):
        lines.append(f"- [ ] {trap}")
    lines.extend(
        [
            "",
            "## Print envelope",
            "",
            f"- Max: {constraints.get('target_model', {}).get('max_size_mm', {})}",
            f"- Material: {constraints.get('printer', {}).get('material_first_pass', '')}",
            "",
            "## Human review questions",
            "",
        ]
    )
    for q in visual.get("human_review_questions", []):
        lines.append(f"- [ ] {q}")
    if visual.get("thumbnail_check", {}).get("enabled"):
        tc = visual["thumbnail_check"]
        lines.extend(
            [
                "",
                "## Thumbnail check",
                "",
                f"- Size: {tc.get('size_px')}px",
                f"- Question: {tc.get('question', '')}",
            ]
        )

    concept = design.get("reference_inputs", {}).get("concept_sheet", {})
    if spec.get("lane") == "hybrid" or concept.get("path"):
        lines.extend(["", "## Concept sheet (visual acceptance target)", ""])
        if concept.get("path"):
            lines.append(f"- Path: `{concept['path']}`")
        if concept.get("role"):
            lines.append(f"- Role: {concept['role']}")
        lines.extend(
            [
                "",
                "## Hybrid acceptance checklist",
                "",
                "Compare Meshy concept PNG to Blender face closeups before approving slice:",
                "",
                "- [ ] Woman: rectangular glasses shape matches concept",
                "- [ ] Woman: hair mass and silhouette readable at thumbnail",
                "- [ ] Dog: ears and muzzle visible from front closeup",
                "- [ ] Dog: reads as dog, not cushion or blob",
                "- [ ] Chair frame and nameplate still readable",
                "- [ ] Single green PLA legibility without paint",
            ]
        )

    shapr = visual.get("shapr3d_handoff", {})
    if shapr:
        lines.extend(["", "## Shapr3D handoff", ""])
        for key in ("body_step", "fused_stl", "note"):
            if shapr.get(key):
                lines.append(f"- {key}: {shapr[key]}")

    lines.append("")
    return "\n".join(lines)
