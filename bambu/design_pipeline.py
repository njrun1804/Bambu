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
}


def load_design_spec(project_path: Path | str, *, revision: str = "v3") -> dict[str, Any]:
    """Load a structured design revision from designs/<revision> YAML files."""

    project = Path(project_path)
    design_dir = project / "designs" / revision
    files: dict[str, Any] = {}
    missing: list[str] = []
    for key, filename in SPEC_FILES.items():
        path = design_dir / filename
        if path.exists():
            files[key] = yaml.safe_load(path.read_text()) or {}
        else:
            files[key] = {}
            missing.append(str(path))
    return {
        "project_path": str(project),
        "revision": revision,
        "design_dir": str(design_dir),
        "files": files,
        "missing_files": missing,
    }


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
    source_of_truth = design.get("agentic_pipeline", {}).get("source_of_truth")
    if source_of_truth != "structured_specs":
        errors.append("design.agentic_pipeline.source_of_truth must be structured_specs")

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

    person_names = [person.get("name") for person in people.get("people", []) if person.get("name")]
    for name in ("Dan", "Carrie"):
        if name not in person_names:
            errors.append(f"people.people must include {name}")

    required_views = visual.get("required_views", [])
    if "face_closeup" not in required_views:
        errors.append("visual_acceptance.required_views must include face_closeup")
    if not visual.get("human_review_questions"):
        errors.append("visual_acceptance.human_review_questions is required")

    review_tools = build_plan.get("review_tools", {})
    agent_tools = review_tools.get("agent", [])
    manual_tools = review_tools.get("manual", [])
    for tool in ("FreeCAD", "Blender"):
        if tool not in agent_tools:
            errors.append(f"build_plan.review_tools.agent must include {tool}")
    if "Bambu Studio" not in manual_tools:
        errors.append("build_plan.review_tools.manual must include Bambu Studio")

    next_actions = build_plan.get("next_agent_actions", [])
    if not next_actions:
        errors.append("build_plan.next_agent_actions is required")
    if "generate build123d components from designs/v3/*.yaml" not in next_actions:
        warnings.append("next actions should start by generating build123d components from designs/v3/*.yaml")

    gates = {
        "structured_specs_present": not spec.get("missing_files"),
        "a1_mini_specific": printer.get("model") == "Bambu Lab A1 mini",
        "printer_contact_blocked": printer.get("printer_contact_allowed") is False,
        "people_specified": all(name in person_names for name in ("Dan", "Carrie")),
        "visual_review_specified": "face_closeup" in required_views,
        "agent_review_tools_specified": all(tool in agent_tools for tool in ("FreeCAD", "Blender")),
    }

    return {
        "ok": not errors,
        "revision": spec.get("revision"),
        "design_dir": spec.get("design_dir"),
        "errors": errors,
        "warnings": warnings,
        "gates": gates,
        "design": {
            "id": design.get("design_id", ""),
            "source_of_truth": source_of_truth,
            "direction": design.get("intent", {}).get("design_direction", ""),
        },
        "printer": {
            "model": printer.get("model", ""),
            "nozzle_mm": printer.get("nozzle_mm"),
            "material_first_pass": printer.get("material_first_pass", ""),
            "max_size_mm": max_size,
        },
        "printer_contact_allowed": printer.get("printer_contact_allowed"),
        "people": person_names,
        "required_review_tools": agent_tools,
        "manual_review_tools": manual_tools,
        "required_views": required_views,
        "next_agent_actions": next_actions,
    }
