# V3 Agentic Design Pipeline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a spec-first, agentic v3 3D design pipeline where structured YAML drives CAD generation and review for the Bambu Lab A1 mini.

**Architecture:** Add `bambu.design_pipeline` as the validator/loader for `designs/<revision>/*.yaml`, plus a `bambu design-check` command that returns agent-readable gates and next actions without contacting the printer. Add v3 structured specs for the World Cup neighbors project so future CAD and print work compiles from explicit design intent, printer constraints, visual acceptance criteria, and review gates.

**Tech Stack:** Python 3.12, PyYAML, unittest, build123d downstream, FreeCAD/Blender/Bambu Studio review boundaries.

---

### Task 1: Contract Tests

**Files:**
- Create: `tests/test_design_pipeline.py`

- [x] Write tests requiring `bambu.design_pipeline.load_design_spec`, `validate_design_spec`, `bambu design-check`, A1 mini constraints, printer-contact safety, named people, required review tools, and agent next actions.
- [x] Run `uv run python -m unittest tests.test_design_pipeline -v`.
- [x] Confirm tests fail because the module, CLI command, and v3 specs do not exist.

### Task 2: Pipeline Module And CLI

**Files:**
- Create: `bambu/design_pipeline.py`
- Modify: `bambu/cli.py`

- [x] Implement spec loading from `designs/<revision>/{design,people,print_constraints,visual_acceptance,build_plan}.yaml`.
- [x] Implement validation errors for missing intent, Bambu Lab A1 mini constraints, face close-up visual review, and printer-contact safety.
- [x] Implement `bambu design-check <project> --revision v3 --json <path>`.
- [x] Run `uv run python -m unittest tests.test_design_pipeline -v`.

### Task 3: World Cup V3 Specs

**Files:**
- Create: `projects/world-cup-neighbors/designs/v3/design.yaml`
- Create: `projects/world-cup-neighbors/designs/v3/people.yaml`
- Create: `projects/world-cup-neighbors/designs/v3/print_constraints.yaml`
- Create: `projects/world-cup-neighbors/designs/v3/visual_acceptance.yaml`
- Create: `projects/world-cup-neighbors/designs/v3/build_plan.yaml`
- Create: `projects/world-cup-neighbors/references/manifest.yaml`
- Modify: `projects/world-cup-neighbors/project.yaml`

- [x] Encode the Option C/A hybrid sheet as structured YAML for agentic use.
- [x] Make the spec A1 mini and green PLA first-pass specific.
- [x] Declare FreeCAD and Blender as agent review tools, Bambu Studio as manual slicer review only, and printer contact as disallowed.
- [x] Run `uv run python -m unittest tests.test_design_pipeline -v`.

### Task 4: Documentation And Verification

**Files:**
- Modify: `README.md`
- Modify: `docs/learning/build123d-figurine-workflow.md`

- [x] Document that v3 work starts with `designs/v3/*.yaml` and `bambu design-check`, not by editing CAD first.
- [x] Run `uv run python -m unittest discover -s tests -v`.
- [x] Commit and push the branch.
