# Shapr3D fusion workflow (hybrid lane)

Manual gate between Meshy head meshes and Bambu release-check. Shapr3D has no CLI in this repo — Mike owns this step, like Bambu Studio slicing.

## Inputs

| Artifact | Path (best-buds-chair v1) |
|----------|---------------------------|
| Body STEP (neck stubs) | `outputs/best-buds-chair-v1-body.step` |
| Woman head STL | `mesh/woman-head.stl` |
| Dog head STL | `mesh/dog-head.stl` |
| Alignment hints | `designs/v1/fusion_manifest.yaml` |
| Face centers | `designs/v1/people.yaml` → `review.face_center` |

Generate body STEP:

```bash
uv run bambu export-body projects/best-buds-chair --revision v1
```

## Steps

1. Open `outputs/best-buds-chair-v1-body.step` in Shapr3D.
2. Import `mesh/woman-head.stl` and `mesh/dog-head.stl`.
3. Scale and position using `fusion_manifest.yaml` align hints and `people.yaml` `head_mm` / `face_center`.
4. Boolean **Union** each head to its neck stub; verify lap contact between arm and dog.
5. Fillet lap contacts ≥ 1 mm where heads meet body stubs.
6. Check wall thickness ≥ 1.2 mm on thin AI mesh spots (Replace Face / offset if needed).
7. Export `outputs/best-buds-chair-v1-fused.stl`.
8. Run release gates on the fused mesh:

```bash
uv run bambu release-check projects/best-buds-chair --revision v1 \
  --stl outputs/best-buds-chair-v1-fused.stl \
  --skip-export --skip-freecad
```

Optional body STEP validation after fusion:

```bash
uv run bambu release-check projects/best-buds-chair --revision v1 \
  --stl outputs/best-buds-chair-v1-fused.stl \
  --skip-export --body-step outputs/best-buds-chair-v1-body.step
```

9. Compare Blender face closeups to `photos/reference/concept-meshy.png` before slice.

## Success criteria

- Fused STL passes watertight, overhang, and island gates.
- Woman: glasses + hair readable at 150px thumbnail vs concept PNG.
- Dog: ears + muzzle visible in face closeup — reads as dog, not cushion.
- Single green PLA legibility without paint.
