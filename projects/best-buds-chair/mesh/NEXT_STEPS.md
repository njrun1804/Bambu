# Meshy head meshes — next steps

## Blocked (2026-06-18)

Meshy API returned **401 Invalid API key** on `bambu meshy balance` and `bambu meshy concept`.
The key provided in shell was rejected by `https://api.meshy.ai/openapi/v2/balance`.

1. Rotate or copy a valid Pro API key from [Meshy API settings](https://www.meshy.ai/settings/api).
2. `export MESHY_API_KEY=msy_...` (shell only — never commit).
3. `uv sync --extra meshy`
4. `uv run bambu meshy balance` — confirm credits visible.

## Prepared locally

- Reference photo: `photos/reference/patio-reference.jpg` (from `private/references/clear-right-pair.jpg`)
- Head crops: `photos/reference/crop-woman.jpg`, `photos/reference/crop-dog.jpg`

## Meshy pipeline (after key fix)

```bash
uv run bambu meshy concept projects/best-buds-chair
uv run bambu meshy head projects/best-buds-chair --subject woman
uv run bambu meshy head projects/best-buds-chair --subject dog
uv run bambu meshy analyze projects/best-buds-chair --subject woman
uv run bambu meshy analyze projects/best-buds-chair --subject dog
```

Expected credits (from plan): concept ~6, each head ~20, analyze free.

## Shapr3D fusion (after heads)

Body STEP exists: `outputs/best-buds-chair-v1-body.step`

Fusion manifest expects:

- `mesh/woman-head.stl` → align x=14, y=4, z=48, scale=1.0
- `mesh/dog-head.stl` → align x=-6, y=6, z=44, scale=1.05
- Export `outputs/best-buds-chair-v1-fused.stl`

See `docs/learning/shapr3d-fusion-workflow.md` and `designs/v1/fusion_manifest.yaml`.

Not ready for Shapr3D until both head STLs exist.
