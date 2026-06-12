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
    parser.add_argument("--no-render", action="store_true", help="Skip Blender preview rendering.")
    parser.add_argument("--json", type=Path, default=None, help="Optional report JSON path.")
    parser.add_argument("--source-file", type=Path, default=None, help="Alternate build123d source file.")
    parser.add_argument("--output-slug", default=None, help="Alternate output artifact name.")
    parser.add_argument("--views", type=Path, default=None, help="YAML file with Blender review views.")
    args = parser.parse_args(argv)

    views = None
    if args.views:
        import yaml

        views = yaml.safe_load(args.views.read_text())["views"]

    report = review_project_3d(
        args.project,
        outputs_root=args.outputs_root,
        render=not args.no_render,
        source_file=args.source_file,
        output_slug=args.output_slug,
        views=views,
    )
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(report, indent=2) + "\n")
    print_summary(report)
    gates = (
        report.get("fits_a1_mini"),
        not report.get("freecad", {}).get("warnings"),
        report.get("mesh", {}).get("watertight_manifold"),
        report.get("overhangs", {}).get("ok", True),
        report.get("islands", {}).get("ok", True),
    )
    return 0 if all(gates) else 1


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
        classes = freecad.get("geometry_error_classes", {})
        if classes:
            print(f"blocking geometry errors: {classes.get('blocking') or 'none'}")
            print(f"informational geometry notes: {classes.get('informational') or 'none'}")
    else:
        print(f"reason: {freecad.get('reason', 'unknown')}")
    mesh = report.get("mesh", {})
    if mesh:
        print()
        print("STL mesh")
        print("--------")
        print(f"facets: {mesh.get('facets')}")
        print(f"open edges: {mesh.get('open_edges')}")
        print(f"non-manifold edges: {mesh.get('non_manifold_edges')}")
        print(f"degenerate facets: {mesh.get('degenerate_facets')} (tolerated; slicers discard zero-area triangles)")
        print(f"watertight manifold: {'yes' if mesh.get('watertight_manifold') else 'no'}")
    overhangs = report.get("overhangs", {})
    islands = report.get("islands", {})
    if overhangs.get("available"):
        print()
        print("Print-path gates")
        print("----------------")
        print(
            "overhangs: largest steep patch %s mm2 (budget %s) -> %s"
            % (
                overhangs.get("largest_steep_patch_mm2"),
                overhangs.get("patch_budget_mm2"),
                "ok" if overhangs.get("ok") else "OVER BUDGET",
            )
        )
        print(
            "islands: %s blocking of %s seeds -> %s"
            % (
                islands.get("blocking_count"),
                islands.get("island_count"),
                "ok" if islands.get("ok") else "MID-AIR START",
            )
        )
        for island in islands.get("islands", [])[:5]:
            marker = "BLOCKING" if island.get("blocking") else "tolerated nub"
            print(f"  seed {island.get('seed')} ({marker})")
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
