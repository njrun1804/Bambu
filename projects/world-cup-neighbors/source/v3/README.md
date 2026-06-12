# World Cup Neighbors V3 Source

This directory contains the build123d source compiled from `projects/world-cup-neighbors/designs/v3/*.yaml`.

The design intent is not embedded only in Python. Agents should read and validate the YAML specs first:

```bash
uv run bambu design-check projects/world-cup-neighbors --revision v3
```

Then export and review this source:

```bash
uv run python tools/review_3d.py projects/world-cup-neighbors \
  --source-file projects/world-cup-neighbors/source/v3/model.py \
  --output-slug world-cup-neighbors-v3 \
  --json outputs/review/world-cup-neighbors-v3/review-report.json
```

`components.py` uses the v3/v3b specs for person cues, printer limits, and component choices. It favors rounded toy caricature heads, fused raised face/glasses features, monochrome-readable jersey relief, a structural goal backdrop, and a fused low-relief ball. The model must read in single green PLA without paint.
