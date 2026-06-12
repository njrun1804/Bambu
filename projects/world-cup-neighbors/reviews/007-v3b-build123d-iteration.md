# v3b build123d iteration

Date: 2026-06-12

## Inputs

- Primary visual target: `references/ai-concepts/68869cef-6756-47e8-8d5f-e3901f822af1.png`
- Primary monochrome review target: `references/ai-concepts/6ba80d93-b4b2-49ff-a608-3da9876d2053.png`
- Constraint change from Mike: the finished print should not depend on painting. Color concepts are useful only for proportions, personality, and relief zones.

## What changed

- Updated the v3 structured specs to `revision: v3b`.
- Made monochrome green PLA readability a hard requirement.
- Rebuilt `source/v3/components.py` around the v3b target:
  - 24 mm heads and chibi proportions.
  - Dan/Carrie visible side by side.
  - raised glasses, noses, cheeks, smiles, jersey marks.
  - soccer goal reduced to side-panel netting so it supports the scene instead of covering the faces.
  - soccer ball fused at the front-center.
  - raised block labels on the front face of the base.

## Current automated review

Command:

```bash
uv run python tools/review_3d.py projects/world-cup-neighbors \
  --source-file projects/world-cup-neighbors/source/v3/model.py \
  --output-slug world-cup-neighbors-v3 \
  --json outputs/review/world-cup-neighbors-v3/review-report.json
```

Current envelope:

```text
125.0 mm W x 69.6 mm D x 69.25 mm H
```

Fits the Bambu Lab A1 mini envelope.

## What improved

- The single-green render now reads as two toy people, not a block robot or abstract trophy.
- Dan and Carrie have different silhouettes: Dan is taller with swept hair; Carrie is shorter/rounder with bob hair.
- The faces read better in front and three-quarter renders because the glasses, nose, cheeks, and smiles are large raised masses.
- The goal now frames the figures instead of filling the whole center behind their faces.
- The base labels are more visible in three-quarter view.

## Release blockers

- FreeCAD still reports invalid geometry, although the latest export is closed. This is caused by the explicit multi-solid compound and overlapping decorative/body solids.
- The straight-on label read is still weaker than the three-quarter label read.
- Carrie hair is improved from slabs, but still needs a more polished bob silhouette.
- The current Blender harness only generates three views. The v3b spec calls for top, close-up, low-silhouette, contact sheet, and measurement outputs.

## Decision

Do not proceed to slicer from this iteration. It is a visual baseline and learning artifact, not a print handoff.

Next work should focus on a geometry-valid release path:

1. Either make each figure/base/goal a cleaner fused solid before top-level assembly.
2. Or add a mesh-healing/export lane explicitly marked as slicer-preview-only and keep FreeCAD STEP validity as the release gate.
3. Then add the richer Blender review harness from `designs/v3/render_review.yaml`.
