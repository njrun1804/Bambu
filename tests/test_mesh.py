import math
import struct
import tempfile
import unittest
from pathlib import Path


def write_stl(path: Path, facets: list[tuple[tuple[float, float, float], ...]]) -> None:
    with open(path, "wb") as handle:
        handle.write(b"\0" * 80)
        handle.write(struct.pack("<I", len(facets)))
        for a, b, c in facets:
            handle.write(struct.pack("<3f", 0, 0, 0))
            for vertex in (a, b, c):
                handle.write(struct.pack("<3f", *vertex))
            handle.write(struct.pack("<H", 0))


def octahedron(cx: float, cy: float, cz: float, r: float):
    """Closed octahedron: a stand-in for a floating mitten dome."""

    top, bottom = (cx, cy, cz + r), (cx, cy, cz - r)
    ring = [
        (cx + r, cy, cz),
        (cx, cy + r, cz),
        (cx - r, cy, cz),
        (cx, cy - r, cz),
    ]
    facets = []
    for i in range(4):
        a, b = ring[i], ring[(i + 1) % 4]
        facets.append((a, b, top))
        facets.append((b, a, bottom))
    return facets


class IslandAnalysisTests(unittest.TestCase):
    def test_floating_dome_is_a_blocking_island(self):
        from bambu.mesh import analyze_islands

        # A 7 mm solid hovering at z=12: exactly the floating-mitten failure
        # that passed the overhang gate and was caught by the slicer.
        with tempfile.TemporaryDirectory() as tmp:
            stl = Path(tmp) / "mitten.stl"
            write_stl(stl, octahedron(0, 0, 12.0, 3.5))
            report = analyze_islands(stl)

        self.assertFalse(report["ok"])
        self.assertEqual(report["blocking_count"], 1)
        seed = report["islands"][0]["seed"]
        self.assertAlmostEqual(seed[2], 8.5, delta=0.1)

    def test_upward_pocket_floor_is_not_an_island(self):
        from bambu.mesh import analyze_islands

        # A V-groove floor: strict local minimum but upward-facing - the
        # bottom of an engraved slot, supported by design.
        facets = [
            ((0, 0, 10), (5, 0, 12), (5, 5, 12)),
            ((0, 0, 10), (5, 5, 12), (0, 5, 12)),
            ((0, 0, 10), (-5, 5, 12), (-5, 0, 12)),
            ((0, 0, 10), (0, 5, 12), (-5, 5, 12)),
        ]
        with tempfile.TemporaryDirectory() as tmp:
            stl = Path(tmp) / "groove.stl"
            write_stl(stl, facets)
            report = analyze_islands(stl)

        self.assertTrue(report["ok"])
        self.assertEqual(report["island_count"], 0)

    def test_tiny_nub_is_reported_but_tolerated(self):
        from bambu.mesh import analyze_islands

        # A small dome nub just in front of a wall (glasses-ring bottom
        # class): the wall within drag distance rescues it - reported, not
        # blocking.
        nub = octahedron(0, 0.9, 40.0, 0.7)
        wall = [
            ((-3, 1.8, 36), (3, 1.8, 36), (0, 1.8, 38.9)),
            ((-3, 1.8, 38.9), (3, 1.8, 38.9), (0, 1.8, 44)),
        ]
        with tempfile.TemporaryDirectory() as tmp:
            stl = Path(tmp) / "nub.stl"
            write_stl(stl, nub + wall)
            report = analyze_islands(stl)

        self.assertTrue(report["ok"])
        self.assertGreaterEqual(report["island_count"], 1)
        self.assertFalse(any(i["blocking"] for i in report["islands"]))

    def test_plate_touching_minima_are_exempt(self):
        from bambu.mesh import analyze_islands

        with tempfile.TemporaryDirectory() as tmp:
            stl = Path(tmp) / "grounded.stl"
            write_stl(stl, octahedron(0, 0, 0.5, 0.6))
            report = analyze_islands(stl)

        self.assertTrue(report["ok"])
        self.assertEqual(report["island_count"], 0)


class SharedParserTests(unittest.TestCase):
    def test_watertight_and_normals_from_shared_parser(self):
        from bambu.mesh import inspect_mesh, load_binary_stl

        with tempfile.TemporaryDirectory() as tmp:
            stl = Path(tmp) / "octa.stl"
            write_stl(stl, octahedron(0, 0, 10, 2.0))
            report = inspect_mesh(stl)
            mesh = load_binary_stl(stl)

        self.assertTrue(report["watertight_manifold"])
        self.assertEqual(report["vertices"], 6)
        total_area = sum(mesh.facet_geometry(t)[0] for t in mesh.triangles)
        # Octahedron surface = 2*sqrt(3)*a^2 with edge a = r*sqrt(2).
        self.assertAlmostEqual(total_area, 2 * math.sqrt(3) * 8.0, delta=0.01)


if __name__ == "__main__":
    unittest.main()
