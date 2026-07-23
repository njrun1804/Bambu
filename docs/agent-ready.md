# Agent-ready execution contract

- **Bootstrap:** `.python-version` selects Python 3.12; run
  `uv sync --python 3.12 --frozen --all-groups`.
- **Targeted verification:**
  `uv run python -m unittest discover -s tests -p 'test_design_pipeline.py' -v` plus the relevant
  `uv run ruff check` path.
- **Full gate:** `scripts/check.sh`, followed by `scripts/check-status.sh --strict`.
- **Safe exercise:** `uv run bambu --help`, design checks, release checks, and local geometry
  generation are safe when they use repository fixtures or generated scratch output.
- **Fixtures and state:** tests and example projects are safe; private reference photos and
  generated STL/3MF/G-code/PNG outputs stay local and out of git.
- **Environment and services:** FreeCAD, Blender, OpenSCAD, and Bambu Studio are optional local
  capabilities; their absence must be reported rather than bypassed.
- **Safety and resources:** never start a printer, contact printer/cloud/LAN credentials, or treat
  slicer output as approval. Bound geometry/render work to the changed project.
- **Architecture and invariants:** use the repo shape, working rules, and primary loop in
  `AGENTS.md`; build123d is the active CAD backend for likeness work.
