# Print Feedback

- project: world-cup-neighbors
- revision: v001
- outcome: partial_success
- failure_mode: support_removal_pending
- notes: Finished on Bambu Lab A1 mini using green Bambu PLA Basic in AMS slot A3 on textured PEI. Auto bed leveling and flow dynamics calibration were enabled. First layer and base adhesion looked good; raised DAN/CARRIE labels, BRAZIL WATCH PARTY text, soccer ball, and shallow net details printed legibly. Tree supports protected heads/arms/accessories but were visually large and material-heavy before removal. Photo evidence stored locally under private/world-cup-neighbors/v001-post-print/ and ignored project photos under projects/world-cup-neighbors/photos/v001-post-print/. Final support-removal outcome still needs confirmation.
- next_revision: For v002, reduce support dependency: thicken/merge glasses, hair, arms, and accessory details into body surfaces; use integrated soccer-goal arches or body-adjacent props instead of slicer-generated tree supports where possible; consider slightly larger heads/facial cues and separate optional color-inlay/paint guide pieces for Brazil jersey accents.

## Measurements

```yaml
slicer_total_time: 1h39m28s
slicer_material_total_g: 36.07
slicer_model_material_g: 32.1
slicer_support_material_g: 3.97
slicer_layers: 371
model_footprint_mm:
- 118
- 62
model_height_mm: 74.25
photo_observed:
  base_adhesion: good
  first_layer: flat
  labels: legible
  tree_supports: large but stable
  stringing: minor wisps near support/head features
```

## Material State

```yaml
printer: Bambu Lab A1 mini
nozzle_mm: 0.4
filament: Bambu PLA Basic green
ams_slot: A3
plate: Bambu Dual-Texture PEI Plate, textured side
bed_cleaning: washed/dried/reinstalled before print
auto_bed_leveling: true
flow_dynamics_calibration: true
timelapse: false
supports: tree(auto), threshold 30 degrees
```

## Photo Review

- Successful: first layer and shared base adhered cleanly on the textured PEI plate.
- Successful: raised labels and soccer details are legible at the chosen scale.
- Successful: tree supports stayed stable through full-height head and arm features.
- Watch item: final rating depends on support removal; large supports may scar small face, glasses, arm, and hair details.
- Watch item: minor stringing/wisps appeared near upper support and head details.

## V002 Learnings

- Preserve the shared base footprint and label sizes; they printed well.
- Reduce slicer-generated supports by making facial/accessory cues more embedded, less free-standing.
- Consider bolder caricature features over tiny likeness details; this scale rewards chunky geometry.
- If using one-color green PLA again, design paint-friendly raised jersey panels and optional color-fill recesses.
- Add a post-removal feedback pass before declaring the revision a full success.
