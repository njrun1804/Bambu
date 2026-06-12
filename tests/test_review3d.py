import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


class Review3dTests(unittest.TestCase):
    def test_detect_freecad_finds_app_bundle_console_environment(self):
        from bambu.review3d import detect_freecad

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "FreeCAD.app" / "Contents"
            binary = root / "MacOS" / "FreeCAD"
            binary.parent.mkdir(parents=True)
            binary.write_text("#!/bin/sh\n")

            result = detect_freecad([Path(tmp) / "FreeCAD.app"])

        self.assertTrue(result.available)
        self.assertEqual(result.binary, binary)
        self.assertEqual(result.command[:2], [str(binary), "-c"])
        self.assertIn("FREECAD_USER_HOME", result.env)
        self.assertNotIn("OPENAI_API_KEY", result.env)

    def test_parse_freecad_inspection_json_from_noisy_output(self):
        from bambu.review3d import parse_freecad_json

        payload = {"available": True, "shape_count": 1, "solid_count": 1}
        output = "FreeCAD banner\nFREECAD_REVIEW_JSON_BEGIN\n" + json.dumps(payload) + "\nFREECAD_REVIEW_JSON_END\n"

        self.assertEqual(parse_freecad_json(output), payload)

    def test_freecad_warning_exit_keeps_written_report(self):
        from bambu.review3d import FreeCADInstall, inspect_step_with_freecad

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            step = root / "model.step"
            step.write_text("ISO-10303-21;")
            output = root / "review.json"
            script = root / "freecad_review.py"
            script.write_text("# fake")
            output.write_text(
                json.dumps(
                    {
                        "available": True,
                        "ok": False,
                        "is_valid": True,
                        "is_closed": True,
                        "warnings": ["geometry check error"],
                    }
                )
            )
            freecad = FreeCADInstall(
                available=True,
                app=None,
                binary=root / "FreeCAD",
                env={},
            )

            with patch("subprocess.run") as run:
                run.return_value.returncode = 2
                run.return_value.stdout = ""
                run.return_value.stderr = "BOP check found self-intersection"
                report = inspect_step_with_freecad(step, output, freecad=freecad, script=script)

        self.assertEqual(report["warnings"], ["geometry check error"])
        self.assertEqual(report["freecad_returncode"], 2)
        self.assertTrue(report["is_valid"])
        self.assertTrue(report["is_closed"])

    def test_blender_preview_command_is_read_only_and_writes_ignored_outputs(self):
        from bambu.review3d import build_blender_preview_command

        command = build_blender_preview_command(
            blender="/opt/homebrew/bin/blender",
            stl=Path("outputs/world-cup-neighbors.stl"),
            output_dir=Path("outputs/review/world-cup-neighbors"),
        )

        self.assertEqual(command[0], "/opt/homebrew/bin/blender")
        self.assertIn("--background", command)
        self.assertIn("outputs/world-cup-neighbors.stl", command[-1])
        self.assertIn("outputs/review/world-cup-neighbors", command[-1])

    def test_review_project_report_never_contacts_printer(self):
        from bambu.review3d import FreeCADInstall, review_project_3d

        freecad = FreeCADInstall(
            available=False,
            app=None,
            binary=None,
            env={},
            reason="not installed",
        )

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project = root / "projects" / "demo"
            project.mkdir(parents=True)
            outputs = root / "outputs"
            outputs.mkdir()

            with patch("bambu.review3d.export_build123d_project") as export, patch(
                "bambu.review3d.sync_project_artifacts"
            ) as sync, patch("bambu.review3d.detect_freecad", return_value=freecad), patch(
                "bambu.review3d.detect_blender", return_value=None
            ):
                export.return_value = {
                    "project_slug": "demo",
                    "step": str(outputs / "demo.step"),
                    "stl": str(outputs / "demo.stl"),
                    "bounding_box_mm": [10.0, 20.0, 30.0],
                    "fits_a1_mini": True,
                }
                sync.return_value = {"artifacts": []}
                report = review_project_3d(project, outputs_root=outputs, render=False)

        self.assertEqual(report["manual_boundary"], "No printer contact. Review CAD, previews, slicer settings, and supports manually.")
        self.assertFalse(report["printer_contact"])
        self.assertEqual(report["freecad"]["available"], False)

    def test_review_project_can_target_v3_source_and_output_slug(self):
        from bambu.review3d import FreeCADInstall, review_project_3d

        freecad = FreeCADInstall(
            available=False,
            app=None,
            binary=None,
            env={},
            reason="not installed",
        )

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project = root / "projects" / "demo"
            project.mkdir(parents=True)
            source = project / "source" / "v3" / "model.py"
            source.parent.mkdir(parents=True)
            source.write_text("from build123d import Box\nmodel = Box(1, 1, 1)\n")
            outputs = root / "outputs"
            outputs.mkdir()

            with patch("bambu.review3d.export_build123d_project") as export, patch(
                "bambu.review3d.sync_project_artifacts"
            ) as sync, patch("bambu.review3d.detect_freecad", return_value=freecad), patch(
                "bambu.review3d.detect_blender", return_value=None
            ):
                export.return_value = {
                    "project_slug": "demo-v3",
                    "step": str(outputs / "demo-v3.step"),
                    "stl": str(outputs / "demo-v3.stl"),
                    "bounding_box_mm": [10.0, 20.0, 30.0],
                    "fits_a1_mini": True,
                }
                sync.return_value = {"artifacts": []}
                report = review_project_3d(
                    project,
                    outputs_root=outputs,
                    render=False,
                    source_file=source,
                    output_slug="demo-v3",
                )

        export.assert_called_once_with(project, output_dir=outputs, source_file=source, output_slug="demo-v3")
        self.assertEqual(report["project"], "demo-v3")


if __name__ == "__main__":
    unittest.main()
