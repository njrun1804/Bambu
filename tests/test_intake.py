import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from bambu.intake import (
    load_intake_prompt,
    persist_reference_photo,
    resolve_photo_path,
    run_intake,
)


class IntakeTests(unittest.TestCase):
    def test_run_intake_scaffolds_project_and_copies_photo(self):
        from bambu.intake import run_intake

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "projects"
            photo = Path(tmp) / "patio.jpg"
            photo.write_bytes(b"fake jpeg")
            result = run_intake(
                photo,
                intent="Woman with dog on patio chair",
                slug="test-intake",
                root=root,
                archetype="seated_diorama",
            )

            project = root / "test-intake"
            self.assertTrue(project.exists())
            self.assertTrue((project / "references" / "intake.yaml").exists())
            self.assertTrue((project / "designs" / "v1" / "design.yaml").exists())
            self.assertTrue((project / "photos" / "reference" / "patio.jpg").exists())
            self.assertEqual(result["archetype"], "seated_diorama")
            self.assertIn("design-check", result["agent_prompt"])

    def test_classify_archetype_from_intent(self):
        from bambu.intake import classify_archetype_from_intent

        self.assertEqual(
            classify_archetype_from_intent("Woman with dog on patio chair diorama"),
            "seated_diorama",
        )
        self.assertEqual(
            classify_archetype_from_intent("Standing soccer figurines with goal"),
            "seated_diorama",
        )

    def test_run_intake_rejects_existing_project(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "projects"
            photo = Path(tmp) / "patio.jpg"
            photo.write_bytes(b"fake jpeg")
            run_intake(
                photo,
                intent="Woman with dog on patio chair",
                slug="test-intake",
                root=root,
            )

            with self.assertRaises(FileExistsError):
                run_intake(
                    photo,
                    intent="Another intent",
                    slug="test-intake",
                    root=root,
                )

    def test_run_intake_rejects_unsupported_archetype(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "projects"
            photo = Path(tmp) / "patio.jpg"
            photo.write_bytes(b"fake jpeg")

            with self.assertRaises(ValueError) as error:
                run_intake(
                    photo,
                    intent="Standing soccer figurines with goal",
                    slug="standing-test",
                    root=root,
                    archetype="standing_figurines",
                )

            self.assertIn("no spec templates", str(error.exception))

    def test_run_intake_accepts_intent_with_literal_braces(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "projects"
            photo = Path(tmp) / "patio.jpg"
            photo.write_bytes(b"fake jpeg")

            result = run_intake(
                photo,
                intent="Gift {name} on patio chair",
                slug="brace-test",
                root=root,
            )

            self.assertIn("Gift {name} on patio chair", result["agent_prompt"])

    def test_load_intake_prompt_preserves_literal_braces_in_intent(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "projects"
            photo = Path(tmp) / "patio.jpg"
            photo.write_bytes(b"fake jpeg")
            run_intake(
                photo,
                intent="Gift for name on patio chair",
                slug="prompt-test",
                root=root,
            )
            intake_yaml = root / "prompt-test" / "references" / "intake.yaml"
            intake_yaml.write_text(
                intake_yaml.read_text().replace(
                    "Gift for name on patio chair",
                    "Gift {name} on patio chair",
                )
            )

            prompt = load_intake_prompt(root / "prompt-test")

            self.assertIn("Gift {name} on patio chair", prompt)

    def test_resolve_photo_path_rejects_clear_right_pair_for_seated_diorama(self):
        wrong = Path("private/references/clear-right-pair.jpg")
        if not wrong.exists():
            self.skipTest("clear-right-pair fixture missing")
        with self.assertRaises(ValueError) as error:
            resolve_photo_path(wrong, slug="best-buds-chair", archetype="seated_diorama")
        self.assertIn("clear-right-pair", str(error.exception))

    def test_resolve_photo_path_rejects_renamed_marina_copy(self):
        with tempfile.TemporaryDirectory() as tmp:
            forbidden = Path(tmp) / "clear-right-pair.jpg"
            marina_bytes = b"the-exact-marina-couple-bytes"
            forbidden.write_bytes(marina_bytes)
            renamed = Path(tmp) / "patio-reference.jpg"
            renamed.write_bytes(marina_bytes)

            with patch("bambu.intake.FORBIDDEN_DEFAULT_REFERENCES", (forbidden,)):
                with self.assertRaises(ValueError) as error:
                    resolve_photo_path(
                        renamed, slug="best-buds-chair", archetype="seated_diorama"
                    )
            self.assertIn("byte-identical", str(error.exception))

    def test_resolve_photo_path_uses_explicit_existing_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            photo = Path(tmp) / "patio.jpg"
            photo.write_bytes(b"fake jpeg")
            resolved = resolve_photo_path(photo, slug="test", archetype="seated_diorama")
            self.assertEqual(resolved, photo.resolve())

    def test_resolve_photo_path_uses_cursor_upload_sentinel(self):
        with tempfile.TemporaryDirectory() as tmp:
            cache = Path(tmp) / "ws" / "images"
            cache.mkdir(parents=True)
            upload = cache / "chat-upload.png"
            upload.write_bytes(b"png")

            with patch("bambu.intake.CURSOR_WORKSPACE_STORAGE", Path(tmp) / "ws"):
                with patch("bambu.intake.find_cursor_upload_photos", return_value=[upload]):
                    resolved = resolve_photo_path("@cursor", slug="best-buds-chair")
            self.assertEqual(resolved, upload)

    def test_persist_reference_photo_writes_jpeg(self):
        from PIL import Image

        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            source = Path(tmp) / "3BE8F09C-8766-4010-8E7C-D2A5155E8940_1_105_c.jpg"
            Image.new("RGB", (2, 2), color="red").save(source, "JPEG")
            dest = persist_reference_photo(source, project, slug="best-buds-chair")
            self.assertEqual(dest, project / "photos" / "reference" / "best-buds-chair-reference.jpg")
            self.assertTrue(dest.exists())
            self.assertGreater(dest.stat().st_size, 0)


if __name__ == "__main__":
    unittest.main()
