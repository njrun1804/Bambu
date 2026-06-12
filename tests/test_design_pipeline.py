import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


class DesignPipelineTests(unittest.TestCase):
    def test_world_cup_v3_specs_are_agentic_and_a1_mini_specific(self):
        from bambu.design_pipeline import load_design_spec, validate_design_spec

        spec = load_design_spec("projects/world-cup-neighbors", revision="v3")
        report = validate_design_spec(spec)

        self.assertTrue(report["ok"], report["errors"])
        self.assertEqual(report["printer"]["model"], "Bambu Lab A1 mini")
        self.assertFalse(report["printer_contact_allowed"])
        self.assertEqual(report["design"]["source_of_truth"], "structured_specs")
        self.assertIn("Dan", report["people"])
        self.assertIn("Carrie", report["people"])
        self.assertIn("FreeCAD", report["required_review_tools"])
        self.assertIn("Blender", report["required_review_tools"])
        self.assertIn("Bambu Studio", report["manual_review_tools"])
        self.assertIn("generate build123d components from designs/v3/*.yaml", report["next_agent_actions"])
        concept_sheet = Path(spec["project_path"]) / spec["files"]["design"]["reference_inputs"]["concept_sheet"]["path"]
        self.assertTrue(concept_sheet.exists())

    def test_world_cup_v3b_specs_prioritize_single_color_readability(self):
        import yaml

        project = Path("projects/world-cup-neighbors")
        design = yaml.safe_load((project / "designs" / "v3" / "design.yaml").read_text())
        people = yaml.safe_load((project / "designs" / "v3" / "people.yaml").read_text())
        constraints = yaml.safe_load((project / "designs" / "v3" / "print_constraints.yaml").read_text())
        acceptance = yaml.safe_load((project / "designs" / "v3" / "visual_acceptance.yaml").read_text())
        manifest = yaml.safe_load((project / "references" / "manifest.yaml").read_text())

        self.assertEqual(design["revision"], "v3b")
        self.assertEqual(design["intent"]["color_policy"], "monochrome_green_final")
        self.assertIn("no paint required", design["intent"]["first_pass_goal"])
        self.assertEqual(constraints["target_model"]["base_size_mm"]["z"], 12)

        references = {entry["id"]: entry for entry in manifest["references"]}
        self.assertTrue((project / references["v3b_colored_visual_target"]["suggested_path"]).exists())
        self.assertTrue((project / references["v3b_green_review_target"]["suggested_path"]).exists())

        dan, carrie = people["people"]
        self.assertEqual(dan["target_height_mm"], 56)
        self.assertEqual(carrie["target_height_mm"], 52)
        self.assertEqual(dan["head"]["width_mm"], 24)
        self.assertEqual(carrie["head"]["width_mm"], 24)
        self.assertGreaterEqual(dan["head"]["height_ratio_min"], 0.38)
        self.assertGreaterEqual(carrie["head"]["height_ratio_min"], 0.40)
        self.assertEqual(dan["clothing"]["accent_strategy"], "geometry_relief_only_no_paint_required")
        self.assertEqual(carrie["clothing"]["accent_strategy"], "geometry_relief_only_no_paint_required")
        self.assertEqual(acceptance["acceptance_thresholds"]["single_color_legibility"], "required_without_paint")

    def test_design_validation_reports_missing_agentic_gates(self):
        from bambu.design_pipeline import load_design_spec, validate_design_spec

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            design_dir = root / "designs" / "v3"
            design_dir.mkdir(parents=True)
            (design_dir / "design.yaml").write_text("design_id: broken\n")
            spec = load_design_spec(root, revision="v3")
            report = validate_design_spec(spec)

        self.assertFalse(report["ok"])
        self.assertIn("design.intent is required", report["errors"])
        self.assertIn("print_constraints.printer.model must be Bambu Lab A1 mini", report["errors"])
        self.assertIn("visual_acceptance.required_views must include face_closeup", report["errors"])

    def test_design_check_cli_prints_agent_next_actions_and_json(self):
        from bambu.cli import main

        with tempfile.TemporaryDirectory() as tmp:
            json_path = Path(tmp) / "report.json"
            output = io.StringIO()
            with patch("sys.stdout", output):
                exit_code = main(
                    [
                        "design-check",
                        "projects/world-cup-neighbors",
                        "--revision",
                        "v3",
                        "--json",
                        str(json_path),
                    ]
                )
            report = json.loads(json_path.read_text())

        self.assertEqual(exit_code, 0)
        text = output.getvalue()
        self.assertIn("Agentic design check", text)
        self.assertIn("Bambu Lab A1 mini", text)
        self.assertIn("Next agent actions", text)
        self.assertTrue(report["ok"])
        self.assertFalse(report["printer_contact_allowed"])


if __name__ == "__main__":
    unittest.main()
