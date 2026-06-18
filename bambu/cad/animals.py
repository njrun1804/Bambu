"""Fusion-safe animal geometry — validate dog in isolation before full scenes."""

from __future__ import annotations

from build123d import Circle, Pos, Sphere

from bambu.cad.primitives import assert_single_solid, capsule_between, front_extrude, head_fusion_stub, multifuse, subtract_engraves


def make_dog_head(
    *,
    cx: float,
    cy: float,
    cz: float,
    head_r: float = 12.5,
    ear_length: float = 9.0,
    face_y: float | None = None,
):
    """Oversized dog head with teardrop floppy ears and forward muzzle."""

    face_y = face_y if face_y is not None else cy - head_r - 0.4
    adds = []
    engraves = []

    adds.append(Pos(cx, cy, cz) * Sphere(head_r))

    # Teardrop floppy ears: wide roots buried in skull, tips hugging the cheek.
    for sx in (-1, 1):
        root = (cx + sx * (head_r - 0.5), cy - 0.2, cz + 1.0)
        mid = (cx + sx * (head_r - 0.8), cy + 1.5, cz - 3.5)
        tip = (cx + sx * (head_r - 2.5), cy + 2.5, cz - 7.0)
        adds.append(Pos(cx + sx * (head_r - 1.2), cy + 0.8, cz - 2.0) * Sphere(4.2))
        adds.append(capsule_between(root, mid, 5.0))
        adds.append(capsule_between(mid, tip, 3.8))

    # Forward muzzle mass — shallow ridge fused into the skull front.
    adds.append(front_extrude(Circle(5.5), cx, cz - 2.8, face_y, 2.8))

    # White chest patch zone; keep it high/shallow so its first layer fuses into the head.
    adds.append(front_extrude(Circle(3.8), cx, cz - 2.7, face_y - 0.15, 2.4))

    # Tri-color mask cues: dark patches as shallow engraves (paint zones).
    for sx, dx in ((-1, -4.0), (1, 4.0)):
        engraves.append(front_extrude(Circle(3.2), cx + dx, cz + 2.5, face_y - 0.2, 1.8))
    engraves.append(front_extrude(Circle(2.4), cx, cz + 4.8, face_y - 0.2, 1.6))

    # Nose bump — shallow ridge inside the muzzle pad.
    adds.append(front_extrude(Circle(1.8), cx, cz - 1.0, face_y - 0.15, 2.2))

    body = multifuse(*adds)
    return subtract_engraves(body, engraves)


def make_dog_lap_pose(
    *,
    cx: float,
    cy: float,
    base_z: float,
    head_r: float = 12.5,
    body_length: float = 16.0,
    include_head: bool = True,
):
    """Seated lap dog: fused head + compact body blob anchored to base."""

    head_cz = base_z + 16.0
    face_y = cy - head_r - 0.4
    if include_head:
        head = make_dog_head(cx=cx, cy=cy, cz=head_cz, head_r=head_r, face_y=face_y)
    else:
        head = head_fusion_stub(cx=cx, cy=cy, cz=head_cz, radius=head_r * 0.5, height=head_r * 0.55)
    # Body and chest overlap the lower head to anchor chin and ears for printability.
    body = Pos(cx, cy + 6.0, base_z + 7.5) * Sphere(10.0)
    chest = Pos(cx, cy - 5.0, head_cz - 8.0) * Sphere(8.5)
    tail = capsule_between((cx + 5.0, cy + 10.0, base_z + 7.0), (cx + 8.0, cy + 14.0, base_z + 3.0), 2.8)
    scene = multifuse(head, body, chest, tail)
    return assert_single_solid(scene, label="dog_lap_pose")


def validate_dog_geometry() -> None:
    """Smoke-build dog geometry; raises if not a single solid."""

    make_dog_lap_pose(cx=0.0, cy=0.0, base_z=10.0)
