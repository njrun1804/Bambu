"""World Cup neighbors v3 model compiled from structured YAML specs."""

from __future__ import annotations

import sys
from pathlib import Path


SOURCE_DIR = Path(__file__).resolve().parent
if str(SOURCE_DIR) not in sys.path:
    sys.path.insert(0, str(SOURCE_DIR))

from components import assemble_scene, load_specs  # noqa: E402


specs = load_specs()
model = assemble_scene(specs)
