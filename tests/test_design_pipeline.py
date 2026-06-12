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
