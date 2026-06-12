"""Binary-STL analysis core: the authoritative print-path geometry gates.

Everything here judges the tessellated mesh that actually gets sliced, not
CAD intent. Three independent gates, one shared parser:

- ``inspect_mesh``: watertight/manifold check - every edge of every
  non-degenerate facet shared by exactly two facets.
- ``analyze_overhangs``: connected patches of downward-facing area steeper
  than the printable limit, split into sloped droop risk (gated) and
  flat bridging area (slicers handle with bridging moves).
- ``analyze_islands``: regions that START printing in mid-air. This is
  reachability, not slope - a mitten dome 2 mm above the base passes every
  overhang check and still prints as spaghetti. Bambu Studio's
  "floating regions" warning catches these; so does this gate.
"""

from __future__ import annotations

import math
import struct
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class StlMesh:
    """Parsed binary STL with deduplicated vertices.

    ``triangles`` holds vertex-id triples into ``points``; stored facet
    normals are ignored - analyses recompute normals from the winding.
    """

    path: str
    facet_count: int
    points: list[tuple[float, float, float]]
    triangles: list[tuple[int, int, int]]

    def facet_geometry(self, tri: tuple[int, int, int]):
        """Return (area, unit_normal, centroid) for one triangle."""

        a, b, c = (self.points[i] for i in tri)
        ux, uy, uz = b[0] - a[0], b[1] - a[1], b[2] - a[2]
        vx, vy, vz = c[0] - a[0], c[1] - a[1], c[2] - a[2]
        nx, ny, nz = uy * vz - uz * vy, uz * vx - ux * vz, ux * vy - uy * vx
        norm = math.sqrt(nx * nx + ny * ny + nz * nz)
        centroid = ((a[0] + b[0] + c[0]) / 3, (a[1] + b[1] + c[1]) / 3, (a[2] + b[2] + c[2]) / 3)
        if norm <= 1e-12:
            return 0.0, (0.0, 0.0, 0.0), centroid
        return norm / 2.0, (nx / norm, ny / norm, nz / norm), centroid


def load_binary_stl(stl_path: Path | str) -> StlMesh:
    path = Path(stl_path)
    with open(path, "rb") as handle:
        handle.read(80)
        (facet_count,) = struct.unpack("<I", handle.read(4))
        data = handle.read()

    record = struct.Struct("<12fH")
    vertex_ids: dict[tuple[float, float, float], int] = {}
    points: list[tuple[float, float, float]] = []
    triangles: list[tuple[int, int, int]] = []
    offset = 0
    for _ in range(facet_count):
        values = record.unpack_from(data, offset)
        offset += record.size
        ids = []
        for start in (3, 6, 9):
            vertex = values[start : start + 3]
            existing = vertex_ids.get(vertex)
            if existing is None:
                existing = len(points)
                vertex_ids[vertex] = existing
                points.append(vertex)
            ids.append(existing)
        triangles.append(tuple(ids))
    return StlMesh(path=str(path), facet_count=facet_count, points=points, triangles=triangles)


def inspect_mesh(stl_path: Path | str) -> dict[str, Any]:
    """Watertight/manifold check. Zero-area facets are counted but tolerated;
    slicers discard them."""

    if not Path(stl_path).exists():
        return {"available": False, "reason": f"STL not found: {stl_path}", "watertight_manifold": False}

    mesh = load_binary_stl(stl_path)
    edges: dict[tuple[int, int], int] = defaultdict(int)
    degenerate = 0
    for tri in mesh.triangles:
        if len(set(tri)) < 3:
            degenerate += 1
            continue
        for u, v in ((tri[0], tri[1]), (tri[1], tri[2]), (tri[2], tri[0])):
            edges[(min(u, v), max(u, v))] += 1

    open_edges = sum(1 for count in edges.values() if count == 1)
    non_manifold = sum(1 for count in edges.values() if count > 2)
    return {
        "available": True,
        "facets": mesh.facet_count,
        "vertices": len(mesh.points),
        "degenerate_facets": degenerate,
        "open_edges": open_edges,
        "non_manifold_edges": non_manifold,
        "watertight_manifold": open_edges == 0 and non_manifold == 0,
    }


def analyze_overhangs(
    stl_path: Path | str,
    *,
    max_overhang_deg: float = 45.0,
    z_floor_mm: float = 0.6,
    patch_budget_mm2: float = 120.0,
) -> dict[str, Any]:
    """Cluster downward-facing area steeper than the printable overhang.

    What fails on FDM is a LARGE connected steep patch, not total ledge area:
    raised lettering undersides, brow ledges, and mitten bottoms are a couple
    of square millimetres each and print fine, while a broad under-chin span
    droops. Flagged facets are union-found into patches via shared vertices
    and the gate judges the largest SLOPED patch; flat-down area spanning
    between supports is bridging, which slicers print with bridging moves.
    Plate-touching facets are exempt.
    """

    if not Path(stl_path).exists():
        return {"available": False, "reason": f"STL not found: {stl_path}", "ok": False}

    mesh = load_binary_stl(stl_path)
    nz_limit = -math.cos(math.radians(max_overhang_deg))
    bridge_nz = -0.985  # within ~10 deg of straight down: slicers bridge these
    worst_nz = 0.0
    flagged: list[tuple[float, tuple[int, int, int], tuple[float, float, float], bool]] = []
    for tri in mesh.triangles:
        if max(mesh.points[i][2] for i in tri) <= z_floor_mm:
            continue
        area, normal, centroid = mesh.facet_geometry(tri)
        if area <= 0.0 or normal[2] >= nz_limit:
            continue
        worst_nz = min(worst_nz, normal[2])
        flagged.append((area, tri, centroid, normal[2] <= bridge_nz))

    parent = list(range(len(mesh.points)))

    def find(i: int) -> int:
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    for _, tri, _, _ in flagged:
        a = find(tri[0])
        for other in tri[1:]:
            parent[find(other)] = a

    patches: dict[int, dict[str, Any]] = {}
    for area, tri, centroid, is_bridge in flagged:
        patch = patches.setdefault(find(tri[0]), {"area": 0.0, "steep": 0.0, "bridge": 0.0, "centroid": centroid})
        patch["area"] += area
        patch["bridge" if is_bridge else "steep"] += area

    ranked = sorted(patches.values(), key=lambda p: -p["steep"])
    largest_steep = ranked[0]["steep"] if ranked else 0.0
    return {
        "available": True,
        "facets": mesh.facet_count,
        "max_overhang_deg": max_overhang_deg,
        "flagged_area_mm2": round(sum(p["area"] for p in ranked), 1),
        "bridge_area_mm2": round(sum(p["bridge"] for p in ranked), 1),
        "patch_count": len(ranked),
        "largest_steep_patch_mm2": round(largest_steep, 1),
        "patch_budget_mm2": patch_budget_mm2,
        "worst_normal_z": round(worst_nz, 3),
        "top_patches": [
            {
                "steep_mm2": round(p["steep"], 1),
                "bridge_mm2": round(p["bridge"], 1),
                "near": [round(c, 1) for c in p["centroid"]],
            }
            for p in ranked[:6]
        ],
        "ok": largest_steep <= patch_budget_mm2,
    }


def _dist2d_point_triangle(point: tuple[float, float], tri: list[tuple[float, float]]) -> float:
    """Distance from a 2D point to a triangle's XY projection.

    Near-vertical wall facets project to slivers; the segment fallback keeps
    the measurement honest regardless of tessellation density.
    """

    px, py = point

    def seg_dist(a, b) -> float:
        ax, ay = a
        bx, by = b
        dx, dy = bx - ax, by - ay
        length2 = dx * dx + dy * dy
        if length2 <= 1e-18:
            return math.hypot(px - ax, py - ay)
        t = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / length2))
        return math.hypot(px - (ax + t * dx), py - (ay + t * dy))

    # Inside test via signs of cross products.
    signs = []
    for i in range(3):
        ax, ay = tri[i]
        bx, by = tri[(i + 1) % 3]
        signs.append((bx - ax) * (py - ay) - (by - ay) * (px - ax))
    if all(v >= 0 for v in signs) or all(v <= 0 for v in signs):
        return 0.0
    return min(seg_dist(tri[i], tri[(i + 1) % 3]) for i in range(3))


def analyze_islands(
    stl_path: Path | str,
    *,
    z_floor_mm: float = 0.7,
    tie_mm: float = 0.02,
    slab_mm: float = 0.45,
    support_radius_mm: float = 1.2,
    support_band_mm: float = 1.0,
) -> dict[str, Any]:
    """Find regions that start printing in mid-air.

    Reachability, not slope: a mitten dome 2.4 mm above the base passes every
    overhang check and still prints as spaghetti.

    1. Candidate starts are LOCAL-MINIMUM CLUSTERS of the surface: vertices
       whose neighbours are all at-or-above them, grouped across ``tie_mm``
       z-jitter (sphere poles are points; prism bottoms and flat undersides
       are lines/faces). Upward-facing clusters are groove/pocket floors,
       supported by design.
    2. Each cluster's first printed layer is judged by SLAB CONNECTIVITY:
       flood the mesh facets intersecting [z0, z0+slab] from the cluster.
       If that connected component reaches below z0, the start is anchored
       to standing material (goal crossbar onto posts, glasses prism into
       the face wall, lettering into the base face): not an island.
    3. Remaining islands are BLOCKING unless other slab material sits within
       ``support_radius_mm`` in XY (a nub one nozzle-drag from a wall is
       rescued within a layer or two; report it, tolerate it).
    """

    if not Path(stl_path).exists():
        return {"available": False, "reason": f"STL not found: {stl_path}", "ok": False}

    mesh = load_binary_stl(stl_path)
    neighbours: dict[int, set[int]] = defaultdict(set)
    vertex_facets: dict[int, list[int]] = defaultdict(list)
    for f_idx, tri in enumerate(mesh.triangles):
        for a in tri:
            vertex_facets[a].append(f_idx)
            for b in tri:
                if a != b:
                    neighbours[a].add(b)

    def z(i: int) -> float:
        return mesh.points[i][2]

    # 1. Local-minimum clusters with downward orientation. The flood is
    # bounded by an ABSOLUTE band above the seed z: chaining ties edge-by-edge
    # crawls up finely tessellated spheres (pole rings rise ~0.02 mm) until a
    # descending edge falsely disqualifies the cluster.
    clusters: list[set[int]] = []
    visited: set[int] = set()
    for vertex in sorted(neighbours, key=z):
        if vertex in visited or z(vertex) <= z_floor_mm:
            continue
        if any(z(n) < z(vertex) - 1e-6 for n in neighbours[vertex]):
            continue
        z0 = z(vertex)
        cluster = {vertex}
        stack = [vertex]
        while stack:
            u = stack.pop()
            for n in neighbours[u]:
                if n not in cluster and z(n) <= z0 + tie_mm:
                    cluster.add(n)
                    stack.append(n)
        visited |= cluster
        if any(z(n) < z0 - 1e-6 for v in cluster for n in neighbours[v]):
            continue  # a downhill escape: ledge on a slope, not a minimum
        normal_z = 0.0
        for f_idx in {f for v in cluster for f in vertex_facets[v]}:
            area, normal, _ = mesh.facet_geometry(mesh.triangles[f_idx])
            normal_z += normal[2] * area
        if normal_z >= 0.0:
            continue
        clusters.append(cluster)

    # 2/3. Slab connectivity and drag-distance rescue per cluster.
    islands = []
    for cluster in clusters:
        z0 = min(z(v) for v in cluster)
        slab_facets = [
            f_idx
            for f_idx, tri in enumerate(mesh.triangles)
            if min(z(i) for i in tri) <= z0 + slab_mm and max(z(i) for i in tri) >= z0 - tie_mm
        ]
        slab_adjacency: dict[int, set[int]] = defaultdict(set)
        for f_idx in slab_facets:
            tri = mesh.triangles[f_idx]
            for a in tri:
                for b in tri:
                    if a != b:
                        slab_adjacency[a].add(b)
        component = set(v for v in cluster if v in slab_adjacency)
        stack = list(component)
        while stack:
            u = stack.pop()
            for n in slab_adjacency[u]:
                if n not in component:
                    component.add(n)
                    stack.append(n)
        if any(z(v) < z0 - tie_mm - 1e-9 for v in component):
            continue  # anchored: the first layer connects to standing material

        seed_xy = [(mesh.points[v][0], mesh.points[v][1]) for v in cluster]
        rescued = False
        for f_idx in slab_facets:
            tri = mesh.triangles[f_idx]
            if all(v in component for v in tri):
                continue
            if min(z(i) for i in tri) > z0 + slab_mm or max(z(i) for i in tri) < z0 - support_band_mm:
                continue
            tri_xy = [(mesh.points[i][0], mesh.points[i][1]) for i in tri]
            if any(_dist2d_point_triangle(p, tri_xy) <= support_radius_mm for p in seed_xy):
                rescued = True
                break
        sx, sy = seed_xy[0]
        islands.append(
            {
                "seed": [round(sx, 1), round(sy, 1), round(z0, 1)],
                "cluster_vertices": len(cluster),
                "rescued_nearby": rescued,
                "blocking": not rescued,
            }
        )

    islands.sort(key=lambda i: (i["rescued_nearby"], i["seed"][2]))
    blocking = [i for i in islands if i["blocking"]]
    return {
        "available": True,
        "facets": mesh.facet_count,
        "slab_mm": slab_mm,
        "support_radius_mm": support_radius_mm,
        "support_band_mm": support_band_mm,
        "island_count": len(islands),
        "blocking_count": len(blocking),
        "islands": islands[:10],
        "ok": not blocking,
    }
