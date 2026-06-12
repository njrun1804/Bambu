import tempfile
import unittest
from pathlib import Path


class CadTests(unittest.TestCase):
    def test_export_build123d_model_writes_step_stl_and_bounding_box(self):
        from bambu.cad import export_build123d_project
        from bambu.projects import create_project

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            create_project("Calibration block", root=root)
            project_dir = root / "calibration-block"
            source = project_dir / "source" / "model.py"
            source.write_text(
                "\n".join(
                    [
                        "from build123d import Box",
                        "model = Box(10, 20, 5)",
                    ]
                )
            )

            result = export_build123d_project(project_dir, output_dir=root / "outputs")

            self.assertTrue(Path(result["step"]).exists())
            self.assertTrue(Path(result["stl"]).exists())
            self.assertEqual(result["bounding_box_mm"], [10.0, 20.0, 5.0])
            self.assertTrue(result["fits_a1_mini"])
            self.assertIn("cad_step", {entry["kind"] for entry in result["artifacts"]["artifacts"]})

    def test_export_build123d_project_rejects_missing_model_symbol(self):
        from bambu.cad import export_build123d_project
        from bambu.projects import create_project

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            create_project("Empty", root=root)
            project_dir = root / "empty"
            (project_dir / "source" / "model.py").write_text("value = 1\n")

            with self.assertRaises(ValueError) as error:
                export_build123d_project(project_dir, output_dir=root / "outputs")

        self.assertIn("model", str(error.exception))


if __name__ == "__main__":
    unittest.main()
