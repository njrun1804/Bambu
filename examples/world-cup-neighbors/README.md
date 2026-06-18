# World Cup Neighbors — OpenSCAD Example (Legacy)

This folder documents the **legacy OpenSCAD figurine lane** for the archived
`projects/_archive/world-cup-neighbors/` learning project.

The default Bambu workflow is now **photo-first build123d**:

```bash
uv run bambu intake <photo.jpg> --intent "..." --slug my-project
uv run bambu design-check projects/my-project --revision v1
uv run bambu release-check projects/my-project --revision v1
```

OpenSCAD figurines remain available for simple public/remixable models:

```bash
uv run bambu make-figurines --output outputs/example-figurines.scad
```

See `projects/_archive/world-cup-neighbors/` for the full World Cup v2–v4 build123d history.
