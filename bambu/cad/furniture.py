"""Chunky structural furniture frames for seated dioramas."""

from __future__ import annotations

from build123d import Box, Pos

from bambu.cad.primitives import rounded_block


def make_patio_chair(
    *,
    cx: float,
    cy: float,
    base_z: float,
    seat_w: float = 34.0,
    seat_d: float = 28.0,
    seat_h: float = 8.0,
    back_h: float = 32.0,
    back_thickness: float = 10.0,
):
    """Chunky cushion-back patio chair — no wicker weave, fusion-safe masses."""

    seat = Pos(cx, cy, base_z) * rounded_block(seat_w, seat_d, seat_h, 4.0, top_fillet=2.0)
    # Cushion back sits at the rear of the seat (+Y), not in front of the lap dog.
    back_y = cy + seat_d / 2.0 - back_thickness / 2.0
    back = Pos(cx, back_y, base_z + seat_h) * Box(seat_w, back_thickness, back_h)
    arm_l = Pos(cx - seat_w / 2.0 + 3.0, cy, base_z + seat_h + 4.0) * Box(6.0, seat_d - 4.0, 6.0)
    arm_r = Pos(cx + seat_w / 2.0 - 3.0, cy, base_z + seat_h + 4.0) * Box(6.0, seat_d - 4.0, 6.0)
    return seat + back + arm_l + arm_r
