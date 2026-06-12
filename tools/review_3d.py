"""Run the agent-safe 3D review workflow for a Bambu project."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from bambu.review3d import review_project_3d


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Review a generated 3D project without printer contact.")
    parser.add_argument("project", type=Path, help="Project directory containing project.yaml.")
    parser.add_argument("--outputs-root", type=Path, default=Path("outputs"))
    parser.add_argument("--source-file", type=Path, default=None, help="Optional build123d source file override.")
    parser.add_argument("--output-slug", default=None, help="Optional output artifact slug override.")
    parser.add_argument("--no-render", action="store_true", help="Skip Blender preview rendering.")
    parser.add_argument("--json", type=Path, default=None, help="Optional report JSON path.")
    args = parser.parse_args(argv)

    report = review_project_3d(
        args.project,
        outputs_root=args.outputs_root,
        render=not args.no_render,
        source_file=args.source_file,
        output_slug=args.output_slug,
    )
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(report, indent=2) + "\n")
    print_summary(report)
    return 0 if report.get("fits_a1_mini") and not report.get("freecad", {}).get("warnings") else 1


def print_summary(report: dict) -> None:
    print("3D review")
    print("---------")
    print(f"project: {report['project']}")
    print(f"STEP: {report['step']}")
    print(f"STL: {report['stl']}")
    print(f"bounding box mm: {report['bounding_box_mm']}")
    print(f"fits A1 mini: {'yes' if report['fits_a1_mini'] else 'no'}")
    freecad = report.get("freecad", {})
    print()
    print("FreeCAD")
    print("-------")
    print(f"available: {'yes' if freecad.get('available') else 'no'}")
    if freecad.get("available"):
        print(f"version: {freecad.get('freecad_version', 'unknown')}")
        print(f"valid: {'yes' if freecad.get('is_valid') else 'no'}")
        print(f"closed: {'yes' if freecad.get('is_closed') else 'no'}")
        print(f"counts: {freecad.get('counts')}")
        print(f"volume: {freecad.get('volume')}")
        warnings = freecad.get("warnings") or []
        print(f"warnings: {warnings if warnings else 'none'}")
    else:
        print(f"reason: {freecad.get('reason', 'unknown')}")
    blender = report.get("blender", {})
    print()
    print("Blender previews")
    print("----------------")
    for path in blender.get("paths", []):
        print(f"- {path}")
    print()
    print(report["manual_boundary"])


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
