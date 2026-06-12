"""Durable printer, material, and workflow context for Bambu agents."""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

import yaml

from bambu.preflight import detect_tools, serialize_report


REPO_ROOT = Path(__file__).resolve().parents[1]
CONTEXT_PATH = REPO_ROOT / "profiles" / "bambu-a1-mini" / "context.yaml"


def context_view() -> dict[str, Any]:
    """Return printer, material, plate, tool, and safety context."""

    data = yaml.safe_load(CONTEXT_PATH.read_text()) or {}
    data["tools"] = serialize_report(detect_tools())
    data["safety"] = [
        "Do not start print jobs automatically.",
        "Treat slicer output as a plan requiring manual review.",
        "Review supports, scale, filament, plate side, and first layer before printing.",
        "Keep private photos and printer credentials under private/ and out of git.",
    ]
    return data


def rules_view() -> dict[str, Any]:
    """Return durable agent rules for CAD, artifacts, privacy, and print gates."""

    return {
        "cad_backends": {
            "serious": "build123d",
            "simple_public": "openscad",
            "figurine_first_pass": "openscad",
            "mesh_later": "blender",
        },
        "slicing": {
            "primary": "bambu-studio",
            "backup": "orcaslicer",
            "policy": "Bambu Studio is blessed but not trusted as the only durable state.",
        },
        "artifacts": {
            "source_of_truth": ["project.yaml", "source/model.py", "source/model.scad"],
            "generated_extensions": ["stl", "step", "3mf", "gcode", "gcode.3mf", "png"],
            "generated_policy": "Generated artifacts are indexed, not hand-edited source.",
        },
        "privacy": {
            "private_paths": ["private/", "projects/*/photos/"],
            "public_examples": "Use only non-private placeholder assets unless explicitly approved.",
        },
        "printer_contact": "manual_only",
        "gates": {
            "design": ["valid_manifest", "lane_chosen", "material_selected", "privacy_declared"],
            "export": ["source_exists", "artifact_hash_recorded", "fits_build_volume"],
            "slicer": ["profile_named", "material_profile_named", "plate_side_named", "manual_review"],
            "print_feedback": ["outcome_recorded", "failure_mode_classified", "next_revision_proposed"],
        },
    }


def default_project_context() -> dict[str, Any]:
    """Return the default project context derived from the durable machine state."""

    view = context_view()
    return {
        "printer": deepcopy(view["printer"]),
        "material": deepcopy(view["materials"][0]),
        "plate": deepcopy(view["plate"]),
    }
