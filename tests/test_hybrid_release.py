import struct
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


def _write_watertight_tetrahedron(stl: Path) -> None:
    vertices = [(0, 0, 0), (1, 0, 0), (0, 1, 0), (0, 0, 1)]
    facets = [(0, 2, 1), (0, 1, 3), (1, 2, 3), (0, 3, 2)]
    with open(stl, "wb") as handle:
        handle.write(b"\0" * 80)
        handle.write(struct.pack("<I", len(facets)))
        for a, b, c in facets:
            handle.write(struct.pack("<3f", 0, 0, 0))
            for idx in (a, b, c):
                handle.write(struct.pack("<3f", *vertices[idx]))
            handle.write(struct.pack("<H", 0))


class HybridReleaseTests(unittest.TestCase):
    def test_review_project_3d_accepts_fused_stl_path(self):
        from bambu.review3d import review_project_3d

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project = root / "projects" / "demo"
            project.mkdir(parents=True)
            (project / "project.yaml").write_text(
                "slug: demo\ncurrent_revision: v1\nprinter:\n  build_volume_mm: [180,180,180]\n"
            )
            outputs = root / "outputs"
            outputs.mkdir()
            stl = outputs / "demo-v1-fused.stl"
            _write_watertight_tetrahedron(stl)

            with patch("bambu.review3d.detect_blender", return_value=None):
                report = review_project_3d(
                    project,
                    outputs_root=outputs,
                    render=False,
                    stl_path=stl,
                    skip_export=True,
                    skip_freecad=True,
                    revision="v1",
                )

        self.assertEqual(report["stl"], str(stl))
        self.assertTrue(report["freecad"].get("skipped") or report["source"] == "fused_stl")
        self.assertTrue(report["mesh"].get("watertight_manifold"))

    def test_release_check_cli_skips_freecad_with_stl(self):
        from bambu.cli import main
        import io

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project = root / "projects" / "demo"
            design = project / "designs" / "v1"
            design.mkdir(parents=True)
            (project / "project.yaml").write_text("slug: demo\ncurrent_revision: v1\n")
            outputs = root / "outputs"
            outputs.mkdir()
            stl = outputs / "fused.stl"
            _write_watertight_tetrahedron(stl)

            output = io.StringIO()
            with patch("bambu.review3d.review_project_3d") as review, patch(
                "bambu.cli.validate_design_spec", return_value={"ok": True, "errors": []}
            ):
                review.return_value = {
                    "step": None,
                    "stl": str(stl),
                    "fits_a1_mini": True,
                    "freecad": {"skipped": True, "reason": "fused STL path"},
                    "mesh": {"watertight_manifold": True, "open_edges": 0, "non_manifold_edges": 0},
                    "overhangs": {"ok": True},
                    "islands": {"ok": True},
                    "blender": {"paths": []},
                    "bounding_box_mm": [1, 1, 1],
                    "manual_boundary": "test",
                }
                with patch("sys.stdout", output):
                    code = main(
                        [
                            "release-check",
                            str(project),
                            "--revision",
                            "v1",
                            "--stl",
                            str(stl),
                            "--skip-export",
                            "--skip-freecad",
                            "--no-render",
                        ]
                    )

        self.assertEqual(code, 0)
        review.assert_called_once()
        self.assertTrue(review.call_args.kwargs.get("skip_freecad"))


    def test_mcp_release_check_accepts_stl_flag(self):
        from bambu.mcp_server import bambu_release_check

        with patch("bambu.review3d.review_project_3d") as review:
            review.return_value = {
                "fits_a1_mini": True,
                "freecad": {"skipped": True},
                "mesh": {"watertight_manifold": True},
                "overhangs": {"ok": True},
                "islands": {"ok": True},
                "blender": {"paths": []},
            }
            with patch("bambu.mcp_server.validate_design_spec", return_value={"ok": True}):
                with patch("bambu.mcp_server.load_design_spec", return_value={"files": {}}):
                    with patch("bambu.review3d.load_review_views", return_value=[]):
                        result = bambu_release_check(
                            "projects/best-buds-chair",
                            revision="v1",
                            stl="outputs/gift-v1-fused.stl",
                            skip_export=True,
                            skip_freecad=True,
                            no_render=True,
                        )
        self.assertTrue(result["gates"]["freecad"])
        self.assertTrue(result["ok"])


if __name__ == "__main__":
    unittest.main()
