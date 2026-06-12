"""Printer/filament QC for the Bambu Lab A1 mini and the spools we actually own.

Two gates, both judging the real print path rather than CAD intent:

- ``analyze_stl_overhangs``: per-facet overhang analysis of the exported STL
  against the supportless 45-degree rule, ignoring plate-touching faces.
- ``qc_sliced_3mf``: facts from the sliced ``.gcode.3mf`` - no supports,
  filament profile matches an owned spool, plate/nozzle/bed sanity, and the
  time/material estimates a human should see before printing.
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any
from xml.etree import ElementTree
from zipfile import BadZipFile, ZipFile

import yaml

from bambu.mesh import analyze_overhangs


FILAMENT_DIAMETER_MM = 1.75
DEFAULT_CONTEXT = Path("profiles/bambu-a1-mini/context.yaml")


def load_printer_context(path: Path = DEFAULT_CONTEXT) -> dict[str, Any]:
    return yaml.safe_load(Path(path).read_text())


def analyze_stl_overhangs(stl_path: Path, **kwargs: Any) -> dict[str, Any]:
    """Connected-patch overhang analysis; see bambu.mesh.analyze_overhangs."""

    return analyze_overhangs(stl_path, **kwargs)


def qc_sliced_3mf(path: Path, *, context: dict[str, Any] | None = None) -> dict[str, Any]:
    """QC facts from a Bambu Studio ``.gcode.3mf`` against printer + inventory."""

    context = context or load_printer_context()
    sliced = Path(path)
    report: dict[str, Any] = {"file": str(sliced), "checks": {}, "facts": {}}
    failures: list[str] = []

    try:
        with ZipFile(sliced) as archive:
            slice_info = archive.read("Metadata/slice_info.config").decode()
            plate_json = json.loads(archive.read("Metadata/plate_1.json"))
            names = set(archive.namelist())
    except (FileNotFoundError, BadZipFile, KeyError) as error:
        report["checks"]["readable_3mf"] = False
        report["failures"] = [f"cannot read sliced 3mf: {error}"]
        report["ok"] = False
        return report
    report["checks"]["readable_3mf"] = True
    report["checks"]["gcode_present"] = "Metadata/plate_1.gcode" in names

    root = ElementTree.fromstring(slice_info)
    plate = root.find("plate")
    metadata = {item.get("key"): item.get("value") for item in plate.findall("metadata")}
    filaments = [f.attrib for f in plate.findall("filament")]

    # Supportless contract.
    support_used = metadata.get("support_used") == "true"
    report["checks"]["supportless"] = not support_used
    if support_used:
        failures.append("slicer enabled supports; v4 contract is supportless")

    # Fits the plate.
    outside = metadata.get("outside") == "true"
    report["checks"]["fits_plate"] = not outside
    if outside:
        failures.append("object marked outside the printable area")

    # Nozzle and bed.
    nozzle = metadata.get("nozzle_diameters", "")
    printer_nozzle = str(context["printer"]["nozzle_mm"])
    report["checks"]["nozzle_matches"] = nozzle == printer_nozzle
    if nozzle != printer_nozzle:
        failures.append(f"sliced for nozzle {nozzle}, printer has {printer_nozzle}")
    bed_type = plate_json.get("bed_type", "")
    report["checks"]["textured_plate"] = bed_type == "textured_plate"
    if bed_type != "textured_plate":
        failures.append(f"bed type is {bed_type!r}, expected textured_plate")

    # Filament must be a spool we own.
    owned_types = {m.get("filament_type") for m in context.get("materials", [])}
    inventory = {
        (m.get("filament_type"), spool.get("color"))
        for m in context.get("materials", [])
        for spool in m.get("owned_spools", [])
    }
    report["facts"]["filaments"] = [
        {"type": f.get("type"), "color": f.get("color"), "used_m": f.get("used_m")} for f in filaments
    ]
    types_ok = all(f.get("type") in owned_types for f in filaments)
    report["checks"]["filament_type_owned"] = types_ok
    if not types_ok:
        failures.append(f"sliced filament types {[f.get('type') for f in filaments]} not all in inventory {sorted(owned_types)}")
    report["facts"]["owned_spools"] = sorted(f"{c} {t}" for t, c in inventory)

    # Human-facing estimates.
    seconds = int(metadata.get("prediction", "0") or 0)
    used_m = sum(float(f.get("used_m", "0") or 0) for f in filaments)
    density = next(
        (m.get("density_g_cm3", 1.24) for m in context.get("materials", []) if m.get("filament_type") == (filaments[0].get("type") if filaments else "PLA")),
        1.24,
    )
    cross_section_mm2 = math.pi * (FILAMENT_DIAMETER_MM / 2.0) ** 2
    grams = used_m * 1000.0 * cross_section_mm2 * density / 1000.0
    report["facts"]["print_time"] = f"{seconds // 3600}h{(seconds % 3600) // 60:02d}m"
    report["facts"]["filament_m"] = round(used_m, 2)
    report["facts"]["filament_g_estimate"] = round(grams, 1)
    report["checks"]["time_estimate_present"] = seconds > 0
    if seconds <= 0:
        failures.append("no print time prediction in sliced file")

    report["failures"] = failures
    report["ok"] = not failures
    return report


def qc_report_lines(
    stl_report: dict[str, Any],
    slice_report: dict[str, Any],
    island_report: dict[str, Any] | None = None,
) -> list[str]:
    lines = ["Printability QC", "---------------"]
    if stl_report.get("available"):
        lines.append(
            "overhangs >%g deg: largest steep patch %.1f mm2 (budget %.0f mm2); %.1f mm2 flat bridging area handled by slicer -> %s"
            % (
                stl_report["max_overhang_deg"],
                stl_report["largest_steep_patch_mm2"],
                stl_report["patch_budget_mm2"],
                stl_report["bridge_area_mm2"],
                "ok" if stl_report["ok"] else "LARGEST STEEP PATCH OVER BUDGET",
            )
        )
        for patch in stl_report.get("top_patches", []):
            lines.append(
                f"  steep {patch['steep_mm2']} mm2 / bridge {patch['bridge_mm2']} mm2 near {patch['near']}"
            )
    if island_report and island_report.get("available"):
        lines.append(
            "floating islands: %d blocking, %d total (support scan %.1f mm radius, %.1f mm band) -> %s"
            % (
                island_report["blocking_count"],
                island_report["island_count"],
                island_report["support_radius_mm"],
                island_report["support_band_mm"],
                "ok" if island_report["ok"] else "MID-AIR START",
            )
        )
        for island in island_report.get("islands", [])[:6]:
            marker = "BLOCKING" if island["blocking"] else "tolerated nub"
            lines.append(f"  island seed at {island['seed']} ({marker})")
    else:
        lines.append(f"overhang analysis unavailable: {stl_report.get('reason')}")
    lines.append("")
    lines.append(f"sliced file: {slice_report.get('file')}")
    for name, ok in slice_report.get("checks", {}).items():
        lines.append(f"- {name}: {'ok' if ok else 'FAIL'}")
    facts = slice_report.get("facts", {})
    if facts:
        lines.append(f"print time: {facts.get('print_time')} | filament: {facts.get('filament_m')} m (~{facts.get('filament_g_estimate')} g)")
        lines.append(f"filaments in file: {facts.get('filaments')}")
        lines.append(f"owned spools: {facts.get('owned_spools')}")
    for failure in slice_report.get("failures", []):
        lines.append(f"! {failure}")
    return lines
