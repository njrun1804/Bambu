import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from zipfile import ZIP_DEFLATED, ZipFile


class McpToolTests(unittest.TestCase):
    def test_mcp_doctor_returns_structured_setup_report(self):
        from bambu.mcp_server import bambu_doctor

        report = bambu_doctor()

        self.assertIn("tools", report)
        self.assertIn("next_steps", report)
        self.assertIn("openscad", report["tools"])

    def test_mcp_generate_world_cup_figurines_writes_under_requested_path(self):
        from bambu.mcp_server import bambu_generate_world_cup_figurines

        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "figures.scad"
            result = bambu_generate_world_cup_figurines(str(output))

            self.assertTrue(output.exists())
            self.assertEqual(result["output"], str(output))
            self.assertIn("World Cup neighbors", output.read_text())

    def test_mcp_slice_plan_uses_detected_slicer_executable(self):
        from bambu.mcp_server import bambu_slice_plan

        fake_report = {
            "bambu_studio": type(
                "Tool",
                (),
                {"available": True, "path": "/Applications/BambuStudio.app/Contents/MacOS/BambuStudio"},
            )(),
            "orcaslicer": type("Tool", (), {"available": False, "path": None})(),
        }
        with patch("bambu.mcp_server.detect_tools", return_value=fake_report):
            result = bambu_slice_plan("outputs/a.stl", "outputs/a.gcode.3mf")

        self.assertEqual(result["tool"], "bambu-studio")
        self.assertEqual(result["command"][0], "/Applications/BambuStudio.app/Contents/MacOS/BambuStudio")
        self.assertIn("manual approval", " ".join(result["checklist"]).lower())

    def test_mcp_build_world_cup_prototype_delegates_pipeline(self):
        from bambu.mcp_server import bambu_build_world_cup_prototype

        with patch("bambu.mcp_server.build_world_cup_prototype") as build:
            build.return_value = {"sliced": "outputs/world-cup-neighbors.gcode.3mf"}
            result = bambu_build_world_cup_prototype("outputs", "bambu-studio")

        self.assertEqual(result["sliced"], "outputs/world-cup-neighbors.gcode.3mf")
        build.assert_called_once()

    def test_mcp_print_handoff_reports_a1_mini_readiness(self):
        from bambu.mcp_server import bambu_print_handoff

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "prototype.gcode.3mf"
            with ZipFile(path, "w", ZIP_DEFLATED) as archive:
                archive.writestr(
                    "Metadata/project_settings.config",
                    "\n".join(
                        [
                            "Bambu Lab A1 mini",
                            "0.20mm Standard @BBL A1M",
                            "Bambu PLA Basic",
                            "Textured PEI Plate",
                        ]
                    ),
                )

            result = bambu_print_handoff(str(path))

        self.assertTrue(result["ready_for_manual_review"])
        self.assertEqual(result["missing_markers"], [])
        self.assertIn("Bambu Network plug-in", " ".join(result["manual_boundary"]))

    def test_mcp_context_and_rules_views_expose_substrate(self):
        from bambu.mcp_server import bambu_context_view, bambu_rules_view

        context = bambu_context_view()
        rules = bambu_rules_view()

        self.assertEqual(context["printer"]["model"], "Bambu Lab A1 mini")
        self.assertEqual(rules["cad_backends"]["serious"], "build123d")
        self.assertEqual(rules["printer_contact"], "manual_only")

    def test_mcp_create_project_and_project_view(self):
        from bambu.mcp_server import bambu_create_project, bambu_project_view

        with tempfile.TemporaryDirectory() as tmp:
            created = bambu_create_project(
                "Cable clip",
                root=tmp,
                lane="build123d",
                privacy="private",
                material="Bambu PLA Basic",
                plate_side="textured",
            )
            view = bambu_project_view(created["project_dir"])

        self.assertEqual(created["project"]["slug"], "cable-clip")
        self.assertEqual(view["project"]["lane"], "build123d")
        self.assertEqual(view["validation_errors"], [])

    def test_mcp_record_print_result(self):
        from bambu.mcp_server import bambu_create_project, bambu_record_print_result

        with tempfile.TemporaryDirectory() as tmp:
            created = bambu_create_project("Cable clip", root=tmp)
            result = bambu_record_print_result(
                created["project_dir"],
                outcome="partial_success",
                failure_mode="too_tight",
                measurements={"clip_gap_mm": {"expected": 8, "actual": 7.4}},
                material_state={"dryness": "not_required"},
                notes="Fits but too tight.",
                next_revision="Increase clip gap.",
            )

        self.assertEqual(result["outcome"], "partial_success")
        self.assertIn("clip_gap_mm", result["measurements"])


if __name__ == "__main__":
    unittest.main()
