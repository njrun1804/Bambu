import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


ARCHIVE = "projects/_archive/world-cup-neighbors"


class DesignPipelineTests(unittest.TestCase):
    def test_world_cup_v3_specs_are_agentic_and_a1_mini_specific(self):
        from bambu.design_pipeline import load_design_spec, validate_design_spec

        spec = load_design_spec(ARCHIVE, revision="v3")
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
        self.assertIn("face_closeup", " ".join(report["errors"]))

    def test_design_check_cli_prints_agent_next_actions_and_json(self):
        from bambu.cli import main
        import io
        import json

        with tempfile.TemporaryDirectory() as tmp:
            json_path = Path(tmp) / "report.json"
            output = io.StringIO()
            with patch("sys.stdout", output):
                exit_code = main(
                    [
                        "design-check",
                        ARCHIVE,
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

    def test_world_cup_v4_specs_pass_with_authored_cad_contract(self):
        from bambu.design_pipeline import load_design_spec, validate_design_spec

        spec = load_design_spec(ARCHIVE, revision="v4")
        report = validate_design_spec(spec)

        self.assertTrue(report["ok"], report["errors"])
        self.assertIsNone(report["archetype"])
        self.assertFalse(any("chair" in error for error in report["errors"]))
        self.assertEqual(report["design"]["source_of_truth"], "authored_cad_with_spec_gates")
        self.assertIn("Dan", report["people"])
        self.assertIn("Carrie", report["people"])
        carrie = spec["files"]["people"]["people"][1]
        self.assertEqual(carrie["clothing"]["number"], "9")

    def test_best_buds_v1_specs_pass_archetype_gates(self):
        from bambu.design_pipeline import load_design_spec, validate_design_spec

        spec = load_design_spec("projects/best-buds-chair", revision="v1")
        report = validate_design_spec(spec)

        self.assertTrue(report["ok"], report["errors"])
        self.assertEqual(spec["lane"], "hybrid")
        self.assertEqual(report["archetype"], "seated_diorama")
        self.assertTrue(report["gates"]["concept_sheet_hybrid"])
        self.assertIn("woman", report["people_ids"])
        self.assertIn("dog", report["people_ids"])


if __name__ == "__main__":
    unittest.main()
