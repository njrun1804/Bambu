import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


class CliTests(unittest.TestCase):
    def test_doctor_prints_tool_status_and_next_step(self):
        from bambu.cli import main

        output = io.StringIO()
        with patch("sys.stdout", output):
            exit_code = main(["doctor"])

        self.assertEqual(exit_code, 0)
        text = output.getvalue()
        self.assertIn("Bambu preflight", text)
        self.assertIn("OpenSCAD", text)
        self.assertIn("Next", text)

    def test_make_figurines_writes_scad_file(self):
        from bambu.cli import main

        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "neighbors.scad"
            exit_code = main(["make-figurines", "--output", str(out)])

            self.assertEqual(exit_code, 0)
            scad = out.read_text()

        self.assertIn("World Cup neighbors", scad)
        self.assertIn("Brazil-inspired", scad)
        self.assertIn("figurine", scad)

    def test_slice_plan_prints_command(self):
        from bambu.cli import main

        fake_report = {
            "bambu_studio": type(
                "Tool",
                (),
                {"available": True, "path": "/Applications/BambuStudio.app/Contents/MacOS/BambuStudio"},
            )(),
            "orcaslicer": type("Tool", (), {"available": False, "path": None})(),
        }
        output = io.StringIO()
        with patch("sys.stdout", output), patch("bambu.cli.detect_tools", return_value=fake_report):
            exit_code = main(
                [
                    "slice-plan",
                    "outputs/world-cup-neighbors.stl",
                    "--output",
                    "outputs/world-cup-neighbors.gcode.3mf",
                ]
            )

        self.assertEqual(exit_code, 0)
        text = output.getvalue()
        self.assertIn("/Applications/BambuStudio.app/Contents/MacOS/BambuStudio", text)
        self.assertIn("--export-3mf", text)
        self.assertIn("Review supports", text)

    def test_create_project_command_writes_manifest(self):
        from bambu.cli import main

        with tempfile.TemporaryDirectory() as tmp:
            output = io.StringIO()
            with patch("sys.stdout", output):
                exit_code = main(
                    [
                        "create-project",
                        "Cable clip",
                        "--root",
                        tmp,
                        "--lane",
                        "build123d",
                        "--material",
                        "Bambu PLA Basic",
                        "--plate-side",
                        "textured",
                    ]
                )

            self.assertEqual(exit_code, 0)
            self.assertTrue((Path(tmp) / "cable-clip" / "project.yaml").exists())
            self.assertIn("Next safe action", output.getvalue())

    def test_record_print_result_command_writes_feedback(self):
        from bambu.cli import main
        from bambu.projects import create_project

        with tempfile.TemporaryDirectory() as tmp:
            create_project("Cable clip", root=Path(tmp))
            output = io.StringIO()
            with patch("sys.stdout", output):
                exit_code = main(
                    [
                        "record-print-result",
                        str(Path(tmp) / "cable-clip"),
                        "--outcome",
                        "failed",
                        "--failure-mode",
                        "too_tight",
                        "--notes",
                        "Clip gap too small.",
                        "--next-revision",
                        "Increase gap.",
                    ]
                )

            self.assertEqual(exit_code, 0)
            self.assertTrue((Path(tmp) / "cable-clip" / "reviews" / "004-print-feedback.md").exists())
            self.assertIn("Recorded print result", output.getvalue())


if __name__ == "__main__":
    unittest.main()
