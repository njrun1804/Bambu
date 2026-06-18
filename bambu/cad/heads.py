"""Print-safe chibi head cues: glasses ridges, hair caps, engraved pupils."""

from __future__ import annotations

from build123d import Box, Circle, Cone, Cylinder, Pos, RectangleRounded, Rot, Sphere

from bambu.cad.primitives import capsule_between, ellipsoid, front_extrude


def open_rect_glasses_frame(*, lens_dx: float = 4.7):
    return (
        Pos(-lens_dx, 0) * RectangleRounded(8.2, 4.9, 0.8)
        - Pos(-lens_dx, 0) * RectangleRounded(5.5, 2.5, 0.4)
        + Pos(lens_dx, 0) * RectangleRounded(8.2, 4.9, 0.8)
        - Pos(lens_dx, 0) * RectangleRounded(5.5, 2.5, 0.4)
        + RectangleRounded(3.4, 1.4, 0.5)
    )


def open_round_glasses_frame(*, lens_dx: float = 4.15):
    return (
        Pos(-lens_dx, 0) * Circle(4.8)
        - Pos(-lens_dx, 0) * Circle(3.1)
        + Pos(lens_dx, 0) * Circle(4.8)
        - Pos(lens_dx, 0) * Circle(3.1)
        + RectangleRounded(3.0, 1.5, 0.6)
    )


def add_glasses_ridge(
    adds: list,
    *,
    fx: float,
    eye_z: float,
    face_y: float,
    round_frames: bool = False,
    lens_dx: float | None = None,
):
    frame = open_round_glasses_frame(lens_dx=lens_dx or 4.15) if round_frames else open_rect_glasses_frame(lens_dx=lens_dx or 4.7)
    adds.append(front_extrude(frame, fx, eye_z, face_y - 1.45, 7.2))
    return lens_dx or (4.15 if round_frames else 4.7)


def add_engraved_pupils(
    engraves: list,
    *,
    fx: float,
    eye_z: float,
    face_y: float,
    pupil_dx: float,
):
    for sx in (-1, 1):
        engraves.append(front_extrude(Circle(0.95), fx + sx * pupil_dx, eye_z, face_y - 0.3, 2.2))


def add_brows(adds: list, *, fx: float, brow_z: float, face_y: float, wide: bool = False):
    for sx in (-1, 1):
        w = 5.2 if wide else 4.8
        adds.append(
            front_extrude(
                Rot(Z=sx * 8) * RectangleRounded(w, 1.6, 0.7),
                fx + sx * 4.1,
                brow_z,
                face_y - 1.3,
                6.5,
            )
        )


def add_swept_hair_cap(
    adds: list,
    *,
    fx: float,
    fy: float,
    head_c: float,
    head_r: float,
    clip_tilt: float = -25.0,
):
    cap = Pos(fx, fy + 0.6, head_c + 0.3) * ellipsoid(head_r + 1.3, head_r + 1.6)
    clip = Pos(fx, fy, head_c + 1.0) * Rot(X=clip_tilt) * Pos(0, 0, 22) * Box(46, 46, 44)
    adds.append(cap & clip)


def add_hair_grooves(
    engraves: list,
    *,
    fx: float,
    fy: float,
    crown_z: float,
    band_count: int = 4,
    band_spacing: float = 2.4,
):
    """Horizontal groove bands across the hair cap (readable from front view)."""

    for i in range(band_count):
        z = crown_z - i * band_spacing
        engraves.append(Pos(fx, fy + 2.5, z) * Box(18.0, 10.0, 1.2))


def add_side_hair_lobes(
    adds: list,
    *,
    fx: float,
    fy: float,
    head_c: float,
    head_r: float,
    torso_top: float,
):
    """Side lobes carry layered hair down past the cheeks to the shoulders."""

    for sx in (-1, 1):
        adds.append(
            capsule_between(
                (fx + sx * (head_r - 1.0), fy + 0.5, head_c - 6.5),
                (fx + sx * (head_r - 2.2), fy + 0.5, torso_top - 1.0),
                3.3,
            )
        )


def add_woman_bob_hair(
    adds: list,
    *,
    fx: float,
    fy: float,
    head_c: float,
    head_r: float,
    head_h: float,
    torso_top: float,
):
    """Layered bob cap with tapered underside and rounded face window (v4 Carrie pattern)."""

    bob = Pos(fx, fy + 0.8, head_c + 0.1) * ellipsoid(head_r + 1.8, head_r + 1.4)
    taper = Pos(fx, fy + 0.8, head_c - 9.5) * Cone(bottom_radius=4.0, top_radius=26.0, height=26.0)
    bob = bob & taper
    bob = bob - Pos(fx, fy - head_r - 1.0, head_c + 0.8) * Rot(X=90) * Cylinder(8.4, 13.0)
    adds.append(bob)
    add_side_hair_lobes(adds, fx=fx, fy=fy, head_c=head_c, head_r=head_r, torso_top=torso_top)


def add_jaw_sphere(adds: list, *, fx: float, jaw_y: float, jaw_z: float, jaw_r: float):
    adds.append(Pos(fx, jaw_y, jaw_z) * Sphere(jaw_r))


def add_cheek_pads(
    adds: list,
    *,
    fx: float,
    smile_z: float,
    face_y: float,
    cheek_r: float = 2.0,
):
    for sx in (-1, 1):
        adds.append(front_extrude(Circle(cheek_r), fx + sx * 5.8, smile_z + 1.8, face_y - 0.8, 4.5))


def add_trimmed_nose(adds: list, *, fx: float, face_y: float, nose_z: float):
    nose = Pos(fx, face_y + 0.1, nose_z) * ellipsoid(1.6, 2.3)
    adds.append(nose & Pos(fx, face_y + 0.1, nose_z - 1.4 + 5.0) * Box(10, 10, 10))


def add_smile_engrave(
    engraves: list,
    *,
    fx: float,
    smile_z: float,
    face_y: float,
    jaw_front: float,
):
    lune = Circle(3.2) - Pos(0, 1.5) * Circle(3.2)
    engraves.append(front_extrude(lune, fx, smile_z, face_y - 2.0, (jaw_front + 1.7) - (face_y - 2.0)))
