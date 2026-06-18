# Hybrid lane

Likeness gifts default to `lane: hybrid` in `project.yaml`: build123d structure, Meshy Pro heads, Shapr3D fusion, existing Bambu mesh gates and Blender renders.

## Tool responsibilities

| Component | Tool | Role |
|-----------|------|------|
| Base, chair, torsos, nameplate | build123d → STEP | Parametric, FreeCAD-valid structure |
| Woman + dog heads | Meshy Pro → STL | Organic recognition at figurine scale |
| Boolean union, cleanup | Shapr3D (manual) | Fuse heads to neck stubs |
| Ortho renders, thumbnail | Blender | Automated from `views.yaml` |
| Print contract | `bambu release-check --stl` | Watertight, overhang, island gates |

Pure CSG (`lane: build123d`) remains for functional parts without likeness requirements.

## Key files per revision

- `designs/v1/design.yaml` — must include `reference_inputs.concept_sheet` when `lane: hybrid`
- `designs/v1/fusion_manifest.yaml` — body/head/fused artifact paths and Shapr3D align hints
- `designs/v1/visual_acceptance.yaml` — `shapr3d_handoff`, concept sheet, human review questions
- `mesh/provenance.yaml` — Meshy task ids and credits (gitignored under `projects/*/mesh/`)
- `source/v1/model.py` — exports `model` (full CSG regression) and `body_model` (head stubs)

## CLI quick reference

```bash
# Concept sheet (Figure prototype, 6 credits)
uv run bambu meshy concept projects/<slug>

# Head meshes (image-to-3d on crops, ~20 credits each)
uv run bambu meshy head projects/<slug> --subject woman
uv run bambu meshy head projects/<slug> --subject dog

# Free printability pre-check
uv run bambu meshy analyze projects/<slug> --subject woman

# Body for Shapr3D
uv run bambu export-body projects/<slug> --revision v1

# After Shapr3D export
uv run bambu release-check projects/<slug> --revision v1 \
  --stl outputs/<slug>-v1-fused.stl --skip-export --skip-freecad
```

Set `MESHY_API_KEY` in the environment (`export MESHY_API_KEY=msy_...`). Never commit keys. Test mode: `msy_dummy_api_key_for_test_mode_12345678`.

## Credit budget (first prototype)

| Step | Credits |
|------|---------|
| Figure prototype (concept) | 6 |
| Image-to-3d × 2 heads | 40 |
| Analyze × 2 | 0 |
| Remesh/repair (if needed) | 5–20 |

See [shapr3d-fusion-workflow.md](shapr3d-fusion-workflow.md) for the manual fusion runbook.
