# The learning feedback loop

This repo's value compounds only if every print teaches the next one. The
loop below is the operating contract for any agent or human doing model
work here. The project manifest (`projects/<slug>/project.yaml`) always
names the loop's current position in `next_safe_action`; start there.

## The loop

```text
1. bambu intake <photo>         -> projects/<slug>/ + references/intake.yaml (lane: hybrid)
2. agent vision fills specs     -> designs/<rev>/*.yaml (gates, not CAD source)
3. bambu design-check           -> specs complete; hybrid requires concept_sheet path
4. bambu meshy concept + heads  -> concept PNG + mesh/*-head.stl (MESHY_API_KEY)
5. bambu export-body            -> body STEP with head stubs for Shapr3D
6. Shapr3D fuse                 -> outputs/<slug>-<rev>-fused.stl (manual)
7. bambu release-check --stl    -> mesh + overhangs + islands + Blender renders
8. human approves renders       -> 150px thumbnail + face closeups vs concept sheet
9. Bambu Studio GUI slice       -> authoritative time/cost (read print-path-qc.md)
10. bambu qc + bambu handoff    -> supportless, owned filament, plate/nozzle, markers
11. human starts the print      -> manual gate, always
12. bambu record-print-result   -> outcome + measurements + photos under photos/
13. reviews/NNN-*.md            -> what the physical object taught us
14. fold lessons back           -> docs/learning/*.md rules, gate budgets,
                                    spec defaults, and the next revision's deltas
```

Legacy build123d-only loop (functional parts, no Meshy heads): skip steps 4–6;
use `bambu release-check` on full CSG export instead of `--stl`.

Step 9 intake note: phone photos of the print usually land in the macOS
Photos library (iCloud sync), not Downloads - export/copy them into
`projects/<slug>/photos/<rev>-post-print/` (gitignored) so the evidence
lives beside the revision. Reviews are numbered and append-only;
`record_print_result` enforces this.

Steps 9-11 are the loop's whole point. A print that isn't recorded is a
print the repo never learns from: v001's feedback ("tree supports scarred
the face details") is why v2+ fuses everything, and v4's slicer warning is
why `analyze_islands` exists.

## Where lessons live

- `occt-step-geometry-rules.md` - CAD-side failure catalog. Read before
  writing build123d geometry; append when a new failure class is paid for.
- `print-path-qc.md` - print-side judgment: slope vs reachability, bridge
  classification, slicer trust hierarchy, proven A1 mini setup.
- `build123d-figurine-workflow.md` - the v2 learning pass that established
  the figurine lane.
- `hybrid-lane.md` - Meshy + Shapr3D likeness pipeline (default for photo gifts).
- `shapr3d-fusion-workflow.md` - manual Shapr3D fusion runbook after export-body.
- `projects/<slug>/reviews/NNN-*.md` - per-revision evidence, numbered and
  append-only. Build notes before the print, feedback after it.

## Rules for encoding a lesson

- A lesson is symptom + root cause + shipped fix, with the numbers that
  made it real. "Be careful with tangencies" teaches nothing;
  "a jaw sphere 0.3 mm off the neck axis self-intersects, exactly coaxial
  is clean" does.
- If a lesson can be a GATE, make it one (the island detector, the
  blocking/informational BOP split, the filament inventory check) and keep
  the prose as the why. Gates don't forget; docs alone do.
- If a lesson changes defaults, change them where they execute: spec YAMLs,
  gate budgets, `profiles/` inventory - not in conversation memory.
- Update the project manifest's `next_safe_action` whenever the loop
  advances; a stale manifest sends the next agent two revisions into the
  past.
