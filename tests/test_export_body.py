import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


class ExportBodyTests(unittest.TestCase):
    def test_body_model_exports_single_solid(self):
        from bambu.cad import load_build123d_model

        body = load_build123d_model("projects/best-buds-chair/source/v1/model.py", model_symbol="body_model")
        self.assertEqual(len(body.solids()), 1)

    def test_full_model_and_body_model_differ_in_height(self):
        from bambu.cad import load_build123d_model

        full = load_build123d_model("projects/best-buds-chair/source/v1/model.py", model_symbol="model")
        body = load_build123d_model("projects/best-buds-chair/source/v1/model.py", model_symbol="body_model")
        self.assertLess(float(body.bounding_box().size.Z), float(full.bounding_box().size.Z))

    def test_build_seated_diorama_include_heads_flag(self):
        from bambu.cad.archetypes.seated_diorama import build_seated_diorama

        body = build_seated_diorama({"include_heads": False})
        full = build_seated_diorama({"include_heads": True})
        self.assertEqual(len(body.solids()), 1)
        self.assertEqual(len(full.solids()), 1)

    def test_export_body_uses_body_model_symbol(self):
        from bambu.cad import export_build123d_project

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project = root / "demo"
            (project / "source" / "v1").mkdir(parents=True)
            (project / "project.yaml").write_text(
                "slug: demo\ncurrent_revision: v1\nprinter:\n  build_volume_mm: [180,180,180]\n"
            )
            (project / "source" / "v1" / "model.py").write_text(
                "from bambu.cad.archetypes.seated_diorama import build_seated_diorama\n"
                "body_model = build_seated_diorama({'include_heads': False})\n"
            )
            with patch("bambu.cad._build123d_exporters") as exporters, patch(
                "bambu.cad.sync_project_artifacts", return_value={"artifacts": []}
            ), patch("bambu.cad.load_build123d_model") as load:
                exporters.return_value = (lambda *a, **k: None, lambda *a, **k: None)
                from bambu.cad.archetypes.seated_diorama import build_seated_diorama

                load.return_value = build_seated_diorama({"include_heads": False})
                result = export_build123d_project(
                    project,
                    output_dir=root / "outputs",
                    revision="v1",
                    body_only=True,
                )
                load.assert_called_once()
                self.assertEqual(load.call_args.kwargs["model_symbol"], "body_model")

        self.assertIn("demo-v1-body", result["step"])


if __name__ == "__main__":
    unittest.main()
