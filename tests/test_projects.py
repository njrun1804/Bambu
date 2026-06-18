import json
import tempfile
import unittest
from pathlib import Path

import yaml


class ProjectTests(unittest.TestCase):
    def test_create_project_writes_manifest_and_safe_folders(self):
        from bambu.projects import create_project, load_project, validate_project

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project = create_project(
                "Shelf bracket",
                root=root,
                lane="build123d",
                privacy="private",
                material="Bambu PETG HF",
                plate_side="textured",
            )

            project_dir = root / "shelf-bracket"
            manifest = project_dir / "project.yaml"
            self.assertTrue(manifest.exists())
            self.assertTrue((project_dir / "designs" / "v1").is_dir())
            self.assertTrue((project_dir / "references").is_dir())
            self.assertIn("slug: shelf-bracket", manifest.read_text())
            self.assertEqual(project["source_files"], ["source/v1/model.py"])

            loaded = load_project(manifest)
            self.assertEqual(loaded["slug"], "shelf-bracket")
            self.assertEqual(loaded["lane"], "build123d")
            self.assertEqual(loaded["material"]["name"], "Bambu PETG HF")
            self.assertTrue(loaded["material"]["requires_dryness_tracking"])
            self.assertEqual(validate_project(loaded), [])

    def test_validate_project_reports_missing_design_gate_fields(self):
        from bambu.projects import validate_project

        errors = validate_project({"slug": "bad"})

        self.assertIn("intent is required", errors)
        self.assertIn("lane must be one of build123d, openscad, figurine, hybrid", errors)
        self.assertIn("material.name is required", errors)

    def test_write_artifact_manifest_records_hashes(self):
        from bambu.projects import write_artifact_manifest

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            artifact = root / "part.stl"
            artifact.write_text("solid test")
            result = write_artifact_manifest(root / "artifacts.json", project_slug="part", revision="v001", paths=[artifact])
            data = json.loads((root / "artifacts.json").read_text())

        self.assertEqual(result["project_slug"], "part")
        self.assertEqual(data["artifacts"][0]["path"], "part.stl")
        self.assertEqual(len(data["artifacts"][0]["sha256"]), 64)

    def test_record_print_result_writes_revision_feedback(self):
        from bambu.projects import create_project, record_print_result

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            create_project("Pegboard hook", root=root, lane="build123d", material="Bambu PETG HF")
            result = record_print_result(
                root / "pegboard-hook",
                outcome="failed",
                failure_mode="warped_corner",
                measurements={"slot_width_mm": {"expected": 6.0, "actual": 5.6}},
                material_state={"opened_date": "2026-06-12", "dryness": "unknown"},
                notes="Corner lifted on textured plate.",
                next_revision="Add brim and increase slot width by 0.4 mm.",
            )
            measurement = root / "pegboard-hook" / "measurements" / "v1.yaml"
            review = root / "pegboard-hook" / "reviews" / "001-print-feedback-v1.md"

            self.assertTrue(measurement.exists())
            self.assertTrue(review.exists())
            self.assertEqual(result["outcome"], "failed")
            self.assertIn("warped_corner", review.read_text())
            self.assertIn("slot_width_mm", yaml.safe_load(measurement.read_text())["measurements"])

    def test_sync_project_artifacts_hashes_and_classifies_generated_outputs(self):
        from bambu.projects import create_project, sync_project_artifacts

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            projects_root = root / "projects"
            outputs = root / "outputs"
            outputs.mkdir()
            create_project("Widget", root=projects_root)
            for name in (
                "widget.step",
                "widget.stl",
                "widget-preview.png",
                "widget-project.3mf",
                "widget.gcode.3mf",
            ):
                (outputs / name).write_text(name)

            result = sync_project_artifacts(projects_root / "widget", outputs_root=outputs)
            data = json.loads((projects_root / "widget" / "artifacts.json").read_text())

        kinds = {entry["kind"] for entry in data["artifacts"]}
        self.assertEqual(result["project_slug"], "widget")
        self.assertIn("cad_step", kinds)
        self.assertIn("mesh_stl", kinds)
        self.assertIn("preview_png", kinds)
        self.assertIn("project_3mf", kinds)
        self.assertIn("sliced_gcode_3mf", kinds)
        self.assertTrue(all(len(entry["sha256"]) == 64 for entry in data["artifacts"]))


if __name__ == "__main__":
    unittest.main()
