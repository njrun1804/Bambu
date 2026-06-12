"""build123d export gate for project source models."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType
from typing import Any

from build123d import export_step, export_stl

from bambu.projects import load_project, sync_project_artifacts


def export_build123d_project(
    project_path: Path | str,
    *,
    output_dir: Path = Path("outputs"),
    source_file: Path | None = None,
    model_symbol: str = "model",
) -> dict[str, Any]:
    """Export a build123d project model to STEP and STL and record artifacts."""

    project_dir = Path(project_path)
    project = load_project(project_dir / "project.yaml")
    slug = project["slug"]
    source = source_file or project_dir / "source" / "model.py"
    model = load_build123d_model(source, model_symbol=model_symbol)

    output_dir.mkdir(parents=True, exist_ok=True)
    step_path = output_dir / f"{slug}.step"
    stl_path = output_dir / f"{slug}.stl"
    export_step(model, step_path)
    export_stl(model, stl_path)

    bounding_box = _bounding_box_mm(model)
    artifacts = sync_project_artifacts(project_dir, outputs_root=output_dir)
    return {
        "project_slug": slug,
        "source": str(source),
        "step": str(step_path),
        "stl": str(stl_path),
        "bounding_box_mm": bounding_box,
        "fits_a1_mini": _fits_volume(bounding_box, project["printer"]["build_volume_mm"]),
        "artifacts": artifacts,
        "manual_boundary": "Open exported artifacts in CAD/slicer tools for review before printing.",
    }


def load_build123d_model(source_file: Path | str, *, model_symbol: str = "model") -> Any:
    """Load a build123d model object from a Python source file."""

    source = Path(source_file)
    module = _load_module(source)
    if not hasattr(module, model_symbol):
        raise ValueError(f"build123d source must define `{model_symbol}`")
    return getattr(module, model_symbol)


def _load_module(source: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location(f"bambu_project_{source.stem}", source)
    if spec is None or spec.loader is None:
        raise ValueError(f"Cannot load build123d source: {source}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _bounding_box_mm(model: Any) -> list[float]:
    box = model.bounding_box()
    return [float(box.size.X), float(box.size.Y), float(box.size.Z)]


def _fits_volume(bounding_box_mm: list[float], build_volume_mm: list[float]) -> bool:
    return all(size <= limit for size, limit in zip(bounding_box_mm, build_volume_mm))
