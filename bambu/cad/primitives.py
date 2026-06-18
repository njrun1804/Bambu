"""Fusion-safe build123d primitives extracted from World Cup v4 OCCT rules."""

from __future__ import annotations

import math
from typing import Any, Iterable

from build123d import (
    Axis,
    Cylinder,
    EllipticalCenterArc,
    Line,
    Plane,
    Pos,
    RectangleRounded,
    Rot,
    Sphere,
    extrude,
    fillet,
    make_face,
    revolve,
)


def head_fusion_stub(*, cx: float, cy: float, cz: float, radius: float = 6.0, height: float = 8.0):
    """Neck/head cap stub at face_center for Shapr3D Meshy head fusion."""

    return Pos(cx, cy, cz - height / 2.0) * Cylinder(radius, height)


def front_extrude(profile, x: float, z: float, y_out: float, depth: float):
    """Extrude a 2D profile from a -Y-facing plane back into the model (+Y)."""

    plane = Plane(origin=(x, y_out, z), x_dir=(1, 0, 0), z_dir=(0, -1, 0))
    return extrude(plane * profile, amount=-depth)


def capsule(r: float, length: float):
    """Capsule along local +Z from 0 to length: cylinder with sphere caps."""

    return Pos(0, 0, length / 2) * Cylinder(r, length) + Sphere(r) + Pos(0, 0, length) * Sphere(r)


def capsule_between(a: tuple[float, float, float], b: tuple[float, float, float], r: float):
    """Capsule between two world points."""

    d = tuple(b[i] - a[i] for i in range(3))
    length = math.sqrt(sum(c * c for c in d))
    if length < 1e-6:
        return Pos(*a) * Sphere(r)
    polar = math.degrees(math.acos(d[2] / length))
    azimuth = math.degrees(math.atan2(d[1], d[0]))
    return Pos(*a) * Rot(Z=azimuth) * Rot(Y=polar) * capsule(r, length)


def ellipsoid(r_xy: float, r_z: float):
    """Prolate ellipsoid of revolution about Z (requires r_z >= r_xy)."""

    if r_z < r_xy:
        return Sphere(r_xy)
    arc = EllipticalCenterArc((0, 0), r_xy, r_z, start_angle=-90, end_angle=90)
    profile = make_face([arc.edge(), Line(arc @ 1, arc @ 0).edge()])
    return revolve(Plane.XZ * profile, Axis.Z, 360)


def rounded_block(w: float, d: float, h: float, corner_r: float, top_fillet: float = 0.0):
    block = extrude(RectangleRounded(w, d, corner_r), h)
    if top_fillet:
        top_edges = block.edges().group_by(lambda e: e.center().Z)[-1]
        block = fillet(top_edges, top_fillet)
    return block


def multifuse(*parts: Any) -> Any:
    """Fuse geometry with + operator; caller subtracts engraves after."""

    if not parts:
        raise ValueError("multifuse requires at least one solid")
    scene = parts[0]
    for part in parts[1:]:
        scene = scene + part
    return scene


def assert_single_solid(scene: Any, *, label: str = "scene") -> Any:
    """Assert exactly one fused solid (v4 lesson: never Part(children=solids))."""

    solids = scene.solids()
    count = len(solids)
    if count != 1:
        raise ValueError(f"{label} must be one fused solid, got {count}")
    return scene


def subtract_engraves(body: Any, engraves: Iterable[Any]) -> Any:
    for cut in engraves:
        body = body - cut
    return body
