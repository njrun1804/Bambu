import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from bambu.meshy import (
    TEST_MODE_API_KEY,
    MeshyClient,
    MeshyError,
    meshy_analyze,
    meshy_concept,
    meshy_head,
    resolve_head_crop,
)


class MeshyTests(unittest.TestCase):
    def test_client_requires_api_key(self):
        with patch.dict(os.environ, {}, clear=True):
            os.environ.pop("MESHY_API_KEY", None)
            with self.assertRaises(MeshyError):
                MeshyClient.from_env()

    def test_test_mode_key_is_recognized(self):
        client = MeshyClient(api_key=TEST_MODE_API_KEY)
        self.assertTrue(client.test_mode)

    @patch.object(MeshyClient, "_request")
    def test_balance_calls_v1_endpoint(self, request: MagicMock):
        request.return_value = {"balance": 100}
        client = MeshyClient(api_key="msy_test")
        self.assertEqual(client.balance()["balance"], 100)
        request.assert_called_with("GET", "v1/balance")

    @patch.object(MeshyClient, "poll_task")
    @patch.object(MeshyClient, "create_task")
    def test_analyze_printability_uses_print_analyze_endpoint(self, create_task: MagicMock, poll_task: MagicMock):
        create_task.return_value = "analyze-task"
        poll_task.return_value = {"status": "SUCCEEDED"}
        client = MeshyClient(api_key="msy_test")
        client.analyze_printability(input_task_id="head-task")
        create_task.assert_called_once_with("v1/print/analyze", {"input_task_id": "head-task"})
        poll_task.assert_called_once_with("v1/print/analyze", "analyze-task")

    @patch.object(MeshyClient, "poll_task")
    @patch.object(MeshyClient, "create_task")
    def test_repair_printability_uses_print_repair_endpoint(self, create_task: MagicMock, poll_task: MagicMock):
        create_task.return_value = "repair-task"
        poll_task.return_value = {"status": "SUCCEEDED"}
        client = MeshyClient(api_key="msy_test")
        client.repair_printability(input_task_id="head-task")
        create_task.assert_called_once_with("v1/print/repair", {"input_task_id": "head-task"})
        poll_task.assert_called_once_with("v1/print/repair", "repair-task")

    def test_meshy_analyze_requires_task_id(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "demo"
            (project / "mesh").mkdir(parents=True)
            with self.assertRaises(MeshyError):
                meshy_analyze(project, client=MeshyClient(api_key=TEST_MODE_API_KEY))

    @patch.object(MeshyClient, "run_figure_prototype")
    @patch.object(MeshyClient, "download_url")
    @patch.object(MeshyClient, "extract_model_urls")
    def test_meshy_concept_writes_png(self, urls, download, prototype):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "demo"
            ref = project / "photos" / "reference"
            ref.mkdir(parents=True)
            photo = ref / "patio.jpg"
            photo.write_bytes(b"jpeg")
            (project / "references").mkdir()
            (project / "references" / "intake.yaml").write_text(
                "reference_photo: photos/reference/patio.jpg\n"
            )
            prototype.return_value = {"id": "task-1", "consumed_credits": 6}
            urls.return_value = {"image_url": "https://example.com/concept.png"}
            download.side_effect = lambda url, dest: dest.write_bytes(b"png") or dest

            result = meshy_concept(project, client=MeshyClient(api_key=TEST_MODE_API_KEY))

            self.assertTrue(Path(result["concept_path"]).exists())
            self.assertIn("concept-meshy.png", result["concept_path"])

    def test_resolve_head_crop_requires_crop_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            with self.assertRaises(FileNotFoundError):
                resolve_head_crop(project, "woman")

    @patch.object(MeshyClient, "run_image_to_3d")
    @patch.object(MeshyClient, "download_url")
    @patch.object(MeshyClient, "extract_model_urls")
    def test_meshy_head_writes_stl(self, urls, download, i23d):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "demo"
            ref = project / "photos" / "reference"
            ref.mkdir(parents=True)
            (ref / "crop-woman.jpg").write_bytes(b"jpeg")
            (project / "project.yaml").write_text("slug: demo\ncurrent_revision: v1\n")
            i23d.return_value = {"id": "head-task", "consumed_credits": 20}
            urls.return_value = {"stl": "https://example.com/woman.stl"}
            download.side_effect = lambda url, dest: dest.write_bytes(b"stl") or dest

            result = meshy_head(project, subject="woman", client=MeshyClient(api_key=TEST_MODE_API_KEY))

            self.assertTrue(Path(result["stl_path"]).exists())
            self.assertIn("woman-head.stl", result["stl_path"])


if __name__ == "__main__":
    unittest.main()
