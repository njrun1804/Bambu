"""World Cup neighbors v3b build123d components compiled from YAML specs."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from build123d import Box, BuildPart, Cylinder, Locations, Part, Sphere


def load_specs(project_dir: Path | None = None, revision: str = "v3") -> dict[str, Any]:
    """Load the structured design specs that drive this CAD assembly."""

    project = project_dir or Path(__file__).resolve().parents[2]
    design_dir = project / "designs" / revision
    return {
        "design": _load_yaml(design_dir / "design.yaml"),
        "people": _load_yaml(design_dir / "people.yaml"),
        "print_constraints": _load_yaml(design_dir / "print_constraints.yaml"),
        "visual_acceptance": _load_yaml(design_dir / "visual_acceptance.yaml"),
        "build_plan": _load_yaml(design_dir / "build_plan.yaml"),
    }


def character_metrics(person: dict[str, Any]) -> dict[str, float]:
    """Return the dimensions the generator will use for one character."""

    head = person["head"]
    target_height = float(person["target_height_mm"])
    head_height = float(head["height_mm"])
    return {
        "height_mm": target_height,
        "head_width_mm": float(head["width_mm"]),
        "head_height_mm": head_height,
        "head_to_height_ratio": round(head_height / target_height, 3),
    }


def assemble_scene(specs: dict[str, Any] | None = None):
    """Assemble the v3b scene from structured specs."""

    specs = specs or load_specs()
    constraints = specs["print_constraints"]
    people = specs["people"]["people"]
    base_size = constraints["target_model"]["base_size_mm"]
    scene_targets = constraints["scene_targets"]

    components = [
        make_base(base_size),
        make_goal(base_size, scene_targets),
        make_soccer_ball(base_size, scene_targets),
        make_person(people[0], x=-17.5, y=-10.5, base_z=float(base_size["z"])),
        make_person(people[1], x=18.5, y=-10.5, base_z=float(base_size["z"])),
    ]
    solids = [solid for component in components for solid in component.solids()]
    return Part(children=solids)


def make_base(base_size: dict[str, float]):
    """Rounded display base with large raised labels."""

    width = float(base_size["x"])
    depth = float(base_size["y"]) - 1.4
    height = float(base_size["z"])
    corner_radius = 8.0
    with BuildPart() as base:
        with Locations((0, 0, height / 2)):
            Box(width - 2 * corner_radius, depth, height)
            Box(width, depth - 2 * corner_radius, height)
        with Locations(
            (-width / 2 + corner_radius, -depth / 2 + corner_radius, height / 2),
            (width / 2 - corner_radius, -depth / 2 + corner_radius, height / 2),
            (-width / 2 + corner_radius, depth / 2 - corner_radius, height / 2),
            (width / 2 - corner_radius, depth / 2 - corner_radius, height / 2),
        ):
            Cylinder(radius=corner_radius, height=height)

        label_y = -depth / 2 - 0.35
        _front_word("DAN", -39.0, label_y, 3.0, cell=1.65, relief=1.2)
        _front_star(0.0, label_y, 6.7)
        _front_word("CARRIE", 15.0, label_y, 3.0, cell=1.25, relief=1.2)

    return base.part


LETTER_PATTERNS = {
    "A": ("010", "101", "111", "101", "101"),
    "B": ("110", "101", "110", "101", "110"),
    "C": ("111", "100", "100", "100", "111"),
    "D": ("110", "101", "101", "101", "110"),
    "E": ("111", "100", "110", "100", "111"),
    "I": ("111", "010", "010", "010", "111"),
    "N": ("101", "111", "111", "111", "101"),
    "R": ("110", "101", "110", "101", "101"),
}


def _front_word(text: str, x: float, y: float, z: float, *, cell: float, relief: float) -> None:
    cursor = x
    for char in text:
        pattern = LETTER_PATTERNS.get(char.upper())
        if pattern is None:
            cursor += cell * 2.0
            continue
        for row, line in enumerate(reversed(pattern)):
            for col, filled in enumerate(line):
                if filled == "1":
                    with Locations((cursor + col * cell, y, z + row * cell)):
                        Box(cell * 0.86, relief, cell * 0.86)
        cursor += cell * 4.0


def _front_star(x: float, y: float, z: float) -> None:
    with Locations((x, y, z)):
        Box(6.0, 1.3, 1.0)
        Box(1.0, 1.3, 6.0)
        Box(4.8, 1.3, 0.9, rotation=(0, 45, 0))
        Box(4.8, 1.3, 0.9, rotation=(0, -45, 0))


def make_goal(base_size: dict[str, float], targets: dict[str, float]):
    """Soccer goal backdrop: contextual, chunky, and visually secondary."""

    base_h = float(base_size["z"])
    width = min(float(targets["goal_outer_width_mm"]), 98.0)
    height = min(float(targets["goal_outer_height_mm"]), 40.0)
    post_radius = float(targets["goal_bar_mm"]) / 2.0
    net_bar = float(targets["net_bar_mm"])
    rail_y = 25.5
    with BuildPart() as goal:
        with Locations((-width / 2, rail_y, base_h + height / 2), (width / 2, rail_y, base_h + height / 2)):
            Cylinder(radius=post_radius, height=height)
        with Locations((0, rail_y, base_h + height)):
            Box(width + 4.0, post_radius * 2, post_radius * 2)
        with Locations((0, rail_y, base_h + 2.0)):
            Box(width + 4.0, post_radius * 2, 4.0)

        for x_center in (-33.0, 33.0):
            for z in (base_h + 11.0, base_h + 21.0, base_h + 31.0):
                with Locations((x_center, rail_y + 1.7, z)):
                    Box(30.0, net_bar, net_bar)
            for x in (x_center - 12.0, x_center, x_center + 12.0):
                with Locations((x, rail_y + 1.8, base_h + 21.0)):
                    Box(net_bar, net_bar, 30.0)

    return goal.part


def make_soccer_ball(base_size: dict[str, float], targets: dict[str, float]):
    """Fused front-center ball with broad panel relief."""

    base_h = float(base_size["z"])
    radius = float(targets["ball_diameter_mm"]) / 2.0
    x = 0.0
    y = -17.5
    with BuildPart() as ball:
        with Locations((x, y, base_h + radius * 0.65)):
            Sphere(radius=radius)
        with Locations((x, y, base_h + 1.0)):
            Cylinder(radius=radius * 0.92, height=2.0)
        with Locations((x, y - radius - 0.35, base_h + radius * 0.9)):
            Cylinder(radius=2.2, height=1.0, rotation=(90, 0, 0))
            Box(radius * 1.45, 1.0, 1.0)
            Box(1.0, 1.0, radius * 1.45)
            Box(radius * 1.25, 1.0, 1.0, rotation=(0, 0, 45))
            Box(radius * 1.25, 1.0, 1.0, rotation=(0, 0, -45))

    return ball.part


def make_person(person: dict[str, Any], *, x: float, y: float, base_z: float):
    """Build one monochrome-readable toy caricature."""

    is_dan = person["id"] == "dan"
    target_height = float(person["target_height_mm"])
    head_width = float(person["head"]["width_mm"])
    head_height = float(person["head"]["height_mm"])
    head_radius = head_width / 2.0

    leg_height = 11.5 if is_dan else 9.5
    torso_height = 18.0 if is_dan else 16.5
    torso_width = 17.0 if is_dan else 21.0
    torso_depth = 12.0 if is_dan else 13.5
    neck_height = 2.0
    shoe_z = base_z + 1.1
    leg_z = base_z + 2.0 + leg_height / 2.0
    torso_z = base_z + 2.0 + leg_height + torso_height / 2.0
    head_z = base_z + target_height - head_height / 2.0 - 2.0
    front_y = y - torso_depth / 2.0 - 0.45
    face_y = y - head_radius - 0.45

    with BuildPart() as figure:
        _feet(x, y, shoe_z, is_dan)
        _legs(x, y, leg_z, leg_height, is_dan)
        _rounded_torso(x, y, torso_z, torso_width, torso_depth, torso_height, is_dan)
        _jersey_relief(x, front_y, torso_z, torso_height, person)
        _arms(x, y, base_z, leg_height, torso_height, torso_width, torso_depth, is_dan)
        with Locations((x, y, base_z + 2.0 + leg_height + torso_height + neck_height / 2.0)):
            Cylinder(radius=3.2, height=neck_height)
        _head(x, y, face_y, head_z, head_radius, head_height, is_dan)

    return figure.part


def _feet(x: float, y: float, shoe_z: float, is_dan: bool) -> None:
    spacing = 4.0 if is_dan else 4.3
    for dx in (-spacing, spacing):
        with Locations((x + dx, y - 2.0, shoe_z)):
            Box(7.2, 8.0, 2.2)
        with Locations((x + dx, y - 5.4, shoe_z)):
            Cylinder(radius=3.6, height=2.2)


def _legs(x: float, y: float, leg_z: float, leg_height: float, is_dan: bool) -> None:
    radius = 2.7 if is_dan else 2.9
    spacing = 4.0 if is_dan else 4.3
    for dx in (-spacing, spacing):
        with Locations((x + dx, y, leg_z)):
            Cylinder(radius=radius, height=leg_height)


def _rounded_torso(
    x: float,
    y: float,
    torso_z: float,
    width: float,
    depth: float,
    height: float,
    is_dan: bool,
) -> None:
    with Locations((x, y, torso_z)):
        Box(width - 4.0, depth, height)
        Box(width, depth - 4.0, height)
    for dx in (-(width / 2.0 - 2.0), width / 2.0 - 2.0):
        with Locations((x + dx, y, torso_z)):
            Cylinder(radius=2.0, height=height)
    with Locations((x, y - depth / 2.0, torso_z)):
        Cylinder(radius=width / 2.0, height=2.2, rotation=(90, 0, 0))
    if not is_dan:
        with Locations((x, y, torso_z - height / 2.0 + 2.0)):
            Cylinder(radius=width / 2.0 - 1.0, height=4.0)


def _jersey_relief(x: float, front_y: float, torso_z: float, torso_height: float, person: dict[str, Any]) -> None:
    panel_h = torso_height - 4.0
    with Locations((x, front_y, torso_z)):
        Box(11.5, 1.1, panel_h)
    with Locations((x, front_y - 0.2, torso_z + panel_h / 2.0 - 2.0)):
        Box(6.0, 1.0, 1.4)

    if person["id"] == "dan":
        mark_z = torso_z - 0.2
        with Locations((x - 2.3, front_y - 0.35, mark_z)):
            Box(1.3, 1.1, 8.5)
        with Locations((x + 2.3, front_y - 0.35, mark_z)):
            Cylinder(radius=2.8, height=1.1, rotation=(90, 0, 0))
        with Locations((x + 2.3, front_y - 0.45, mark_z)):
            Box(1.8, 1.1, 6.7)
    else:
        mark_z = torso_z - 0.2
        with Locations((x - 2.6, front_y - 0.35, mark_z + 1.8), (x + 2.6, front_y - 0.35, mark_z + 1.8)):
            Sphere(radius=2.4)
        with Locations((x, front_y - 0.35, mark_z - 1.4)):
            Box(6.4, 1.1, 5.0, rotation=(0, 0, 45))


def _arms(
    x: float,
    y: float,
    base_z: float,
    leg_height: float,
    torso_height: float,
    torso_width: float,
    torso_depth: float,
    is_dan: bool,
) -> None:
    shoulder_z = base_z + 2.0 + leg_height + torso_height - 3.5
    hip_z = base_z + 2.0 + leg_height + 5.5
    side = torso_width / 2.0 + 1.8
    front_y = y - torso_depth / 2.0 + 1.0

    # Fused arm segments. They are intentionally chunky and intersect torso/hands.
    with Locations((x - side, y, (shoulder_z + hip_z) / 2.0)):
        Cylinder(radius=2.3, height=shoulder_z - hip_z)
    with Locations((x + side, y, (shoulder_z + hip_z) / 2.0)):
        Cylinder(radius=2.3, height=shoulder_z - hip_z)
    with Locations((x - side, front_y, hip_z), (x + side, front_y, hip_z)):
        Sphere(radius=2.8)

    if is_dan:
        with Locations((x - side - 1.6, y - 1.2, shoulder_z + 6.0)):
            Cylinder(radius=2.1, height=13.0)
        with Locations((x - side - 1.6, y - 3.4, shoulder_z + 13.0)):
            Sphere(radius=3.0)
    else:
        with Locations((x + side + 1.0, y - 1.0, shoulder_z + 4.0)):
            Cylinder(radius=2.0, height=9.5)
        with Locations((x + side + 1.0, y - 3.0, shoulder_z + 9.0)):
            Sphere(radius=2.8)


def _head(x: float, y: float, face_y: float, head_z: float, radius: float, head_height: float, is_dan: bool) -> None:
    with Locations((x, y, head_z)):
        Sphere(radius=radius)
    with Locations((x, y, head_z - radius + 1.5)):
        Sphere(radius=radius * 0.82)
    with Locations((x - radius - 0.8, y, head_z), (x + radius + 0.8, y, head_z)):
        Sphere(radius=2.8)
    if is_dan:
        _dan_hair(x, y, face_y, head_z, radius)
    else:
        _carrie_hair(x, y, face_y, head_z, radius, head_height)
    _glasses(x, face_y, head_z, is_dan)
    _face(x, face_y, head_z)


def _dan_hair(x: float, y: float, face_y: float, head_z: float, radius: float) -> None:
    with Locations((x, y - 0.4, head_z + radius - 0.5)):
        Cylinder(radius=radius * 0.88, height=3.0)
    for dx, dz, rot in [(-6.0, 0.2, 18), (-3.0, 1.0, 12), (0.5, 1.4, 8), (4.0, 0.9, 0), (7.0, 0.1, -10)]:
        with Locations((x + dx, face_y + 0.1, head_z + radius - 2.4 + dz)):
            Box(2.1, 2.0, 7.5, rotation=(0, 0, rot))


def _carrie_hair(x: float, y: float, face_y: float, head_z: float, radius: float, head_height: float) -> None:
    with Locations((x, y + 0.2, head_z + radius - 0.8)):
        Cylinder(radius=radius * 0.98, height=3.2)
    for dx in (-(radius - 1.2), radius - 1.2):
        with Locations((x + dx, y - 0.1, head_z - 1.8)):
            Cylinder(radius=3.4, height=head_height * 0.72)
        with Locations((x + dx, face_y + 1.7, head_z - 4.8)):
            Sphere(radius=3.2)
    with Locations((x - 3.2, face_y - 0.1, head_z + 4.6)):
        Box(1.5, 1.4, 11.5, rotation=(0, 0, -28))
    with Locations((x + 3.0, face_y - 0.1, head_z + 3.4)):
        Box(1.3, 1.4, 8.5, rotation=(0, 0, 24))


def _glasses(x: float, face_y: float, head_z: float, is_dan: bool) -> None:
    frame_w = 6.2 if is_dan else 6.6
    frame_h = 4.1 if is_dan else 4.4
    eye_z = head_z + 1.3
    stroke = 1.25
    for eye_x in (-4.0, 4.0):
        with Locations((x + eye_x, face_y, eye_z + frame_h / 2), (x + eye_x, face_y, eye_z - frame_h / 2)):
            Box(frame_w, 1.35, stroke)
        with Locations((x + eye_x - frame_w / 2, face_y, eye_z), (x + eye_x + frame_w / 2, face_y, eye_z)):
            Box(stroke, 1.35, frame_h)
        with Locations((x + eye_x, face_y - 0.2, eye_z)):
            Sphere(radius=1.35)
    with Locations((x, face_y, eye_z)):
        Box(2.7, 1.35, stroke)


def _face(x: float, face_y: float, head_z: float) -> None:
    with Locations((x, face_y - 0.25, head_z - 1.8)):
        Sphere(radius=1.8)
    with Locations((x, face_y - 0.35, head_z - 4.9)):
        Box(7.0, 1.2, 1.1)
    with Locations((x - 6.2, face_y - 0.25, head_z - 2.9), (x + 6.2, face_y - 0.25, head_z - 2.9)):
        Sphere(radius=1.5)


def _load_yaml(path: Path) -> dict[str, Any]:
    return yaml.safe_load(path.read_text()) or {}
