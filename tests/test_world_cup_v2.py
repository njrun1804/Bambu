import json
import unittest
from pathlib import Path

import yaml


class WorldCupV2Tests(unittest.TestCase):
    def test_project_manifest_tracks_current_revision_and_loop_position(self):
        project = yaml.safe_load(Path("projects/world-cup-neighbors/project.yaml").read_text())

        self.assertEqual(project["lane"], "build123d")
        self.assertEqual(project["current_revision"], "v4.1")
        self.assertIn("source/v4/model.py", project["source_files"])
        self.assertIn("source/model.py", project["source_files"])
        self.assertIn("record-print-result", project["next_safe_action"])
        self.assertIn("docs/learning/README.md", project["next_safe_action"])
        self.assertEqual(project["design_revisions"]["v3"]["status"], "superseded")
        self.assertIn("printed", project["design_revisions"]["v4"]["status"])

    def test_v2_learning_docs_exist_and_capture_print_lessons(self):
        source_readme = Path("projects/world-cup-neighbors/source/README.md").read_text()
        review = Path("projects/world-cup-neighbors/reviews/005-v2-build123d-design-notes.md").read_text()
        learning = Path("docs/learning/build123d-figurine-workflow.md").read_text()
        root_readme = Path("README.md").read_text()

        for text in (source_readme, review, learning, root_readme):
            self.assertIn("build123d", text)

        self.assertIn("goal backdrop", source_readme)
        self.assertIn("low-relief soccer ball", review)
        self.assertIn("support", learning)
        self.assertIn("World Cup neighbors v2", root_readme)

    def test_artifact_manifest_records_v2_build123d_outputs(self):
        artifacts = json.loads(Path("projects/world-cup-neighbors/artifacts.json").read_text())

        self.assertEqual(artifacts["revision"], "v002")
        kinds = {entry["kind"] for entry in artifacts["artifacts"]}
        paths = {entry["path"] for entry in artifacts["artifacts"]}

        self.assertIn("cad_step", kinds)
        self.assertIn("mesh_stl", kinds)
        self.assertIn("outputs/world-cup-neighbors.step", paths)
        self.assertIn("outputs/world-cup-neighbors.stl", paths)


if __name__ == "__main__":
    unittest.main()
