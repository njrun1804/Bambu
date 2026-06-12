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

    def test_world_cup_v2_source_defines_exportable_model(self):
        from bambu.cad import load_build123d_model

        model = load_build123d_model(Path("projects/world-cup-neighbors/source/model.py"))

        box = model.bounding_box()
        self.assertLessEqual(float(box.size.X), 130.0)
        self.assertLessEqual(float(box.size.Y), 75.0)
        self.assertLessEqual(float(box.size.Z), 85.0)

    def test_world_cup_v3_source_compiles_from_structured_specs(self):
        from bambu.cad import export_build123d_project, load_build123d_model
        from importlib.util import module_from_spec, spec_from_file_location

        source = Path("projects/world-cup-neighbors/source/v3/model.py")
        model = load_build123d_model(source)

        box = model.bounding_box()
        self.assertLessEqual(float(box.size.X), 125.1)
        self.assertLessEqual(float(box.size.Y), 70.1)
        self.assertLessEqual(float(box.size.Z), 70.1)

        result = export_build123d_project(
            "projects/world-cup-neighbors",
            output_dir=Path("outputs"),
            source_file=source,
            output_slug="world-cup-neighbors-v3",
        )

        self.assertEqual(result["project_slug"], "world-cup-neighbors-v3")
        self.assertTrue(result["step"].endswith("world-cup-neighbors-v3.step"))
        self.assertTrue(result["stl"].endswith("world-cup-neighbors-v3.stl"))
        self.assertTrue(result["fits_a1_mini"])

        module_spec = spec_from_file_location("world_cup_neighbors_v3_components_test", source.parent / "components.py")
        self.assertIsNotNone(module_spec)
        self.assertIsNotNone(module_spec.loader)
        components = module_from_spec(module_spec)
        module_spec.loader.exec_module(components)
        specs = components.load_specs()

        self.assertEqual(specs["design"]["revision"], "v3b")
        self.assertEqual(specs["print_constraints"]["target_model"]["base_size_mm"]["z"], 12)
        dan, carrie = specs["people"]["people"]
        self.assertEqual(components.character_metrics(dan)["head_width_mm"], 24)
        self.assertEqual(components.character_metrics(carrie)["head_width_mm"], 24)
        self.assertGreaterEqual(components.character_metrics(dan)["head_to_height_ratio"], 0.38)
        self.assertGreaterEqual(components.character_metrics(carrie)["head_to_height_ratio"], 0.40)

    def test_alternate_source_export_does_not_rewrite_project_artifact_manifest(self):
        from bambu.cad import export_build123d_project

        project = Path("projects/world-cup-neighbors")
        artifacts = project / "artifacts.json"
        before = artifacts.read_text()

        result = export_build123d_project(
            project,
            output_dir=Path("outputs"),
            source_file=project / "source" / "v3" / "model.py",
            output_slug="world-cup-neighbors-v3",
        )

        self.assertEqual(artifacts.read_text(), before)
        self.assertEqual(result["artifacts"], {"artifacts": []})


if __name__ == "__main__":
    unittest.main()
