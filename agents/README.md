# Bambu Agent Layer

This directory is the public agent-facing control surface for Bambu.

The local MCP server command is:

```bash
uv run bambu-mcp
```

The server exposes safe workflow tools:

- `bambu_doctor`: inspect local CAD/slicer setup and next steps.
- `bambu_context_view`: inspect printer, material, plate, tool, and safety context.
- `bambu_rules_view`: inspect backend, artifact, privacy, slicer, and print-gate rules.
- `bambu_create_project`: create a structured `projects/<slug>/` workspace from a plain-English idea.
- `bambu_project_view`: inspect manifest, artifacts, validation status, and next safe action for a project.
- `bambu_design_check`: validate `designs/<revision>/*.yaml` before CAD generation.
- `bambu_sync_artifacts`: hash and classify generated files from `outputs/` into a project artifact index.
- `bambu_build123d_export`: export `source/model.py` build123d projects to STEP/STL with bounding-box fit metadata.
- `bambu_record_print_result`: capture measurements, material state, failure mode, and next revision notes after a physical print.
- `bambu_generate_world_cup_figurines`: generate the default figurine OpenSCAD source.
- `bambu_openscad_export_plan`: return the OpenSCAD export command for `.scad -> .stl`.
- `bambu_slice_plan`: return a Bambu Studio or OrcaSlicer command and review checklist.
- `bambu_build_world_cup_prototype`: generate SCAD, export STL, and slice 3MF without printer contact.
- `bambu_print_handoff`: inspect a generated `.gcode.3mf`, verify A1 mini markers, and return the Bambu Studio handoff.

The MCP server **does not start print jobs**. Agents must stop at source/export/slice plans and require manual approval before anything reaches the printer. Physical outcomes should come back through `bambu_record_print_result` so future revisions are based on measured feedback, not memory.

Keep private reference photos, printer credentials, and local slicer profiles under `private/`. Do not commit them.

General work should start from `bambu_context_view`, then `bambu_create_project` or `bambu_project_view`. For sophisticated designs, especially likeness-based or sketch/concept-sheet-driven work, agents should update `designs/<revision>/*.yaml` and call `bambu_design_check` before generating CAD. Use build123d for serious/dimensional CAD, OpenSCAD for simple public/remixable models, and Bambu Studio as the primary slicer handoff. After any export, call `bambu_sync_artifacts` so generated local files become visible to agents through hashes and artifact kinds.

## Suggested MCP Client Config

For clients that accept JSON MCP config, adapt this template:

```json
{
  "mcpServers": {
    "bambu": {
      "command": "uv",
      "args": ["--directory", "/Users/mikeedwards/CC/Bambu", "run", "bambu-mcp"]
    }
  }
}
```

For a portable public checkout, replace `/Users/mikeedwards/CC/Bambu` with the repo path.

## Agent Roles

- `agents/prompts/maker.md`: build or revise printable artifacts.
- `agents/prompts/reviewer.md`: inspect generated geometry plans before printing.
- `.agents/skills/bambu-operate/SKILL.md`: shared skill entrypoint for agent runtimes that support skills.
- `.codex/agents/bambu-maker.toml`: Codex custom agent sketch using `bambu-mcp`.
- `.claude/agents/bambu-maker.md`: Claude Code custom agent sketch with the same safety boundary.
