import unittest
import runpy
from pathlib import Path

import yaml


class SeatedDioramaTests(unittest.TestCase):
    def test_rect_glasses_are_wide_low_frames(self):
        from bambu.cad.heads import open_rect_glasses_frame

        frame = open_rect_glasses_frame()
        box = frame.bounding_box()
        self.assertGreaterEqual(float(box.size.X), 17.0)
        self.assertLessEqual(float(box.size.Y), 5.2)

    def test_dog_geometry_is_single_solid(self):
        from bambu.cad.animals import validate_dog_geometry

        validate_dog_geometry()

    def test_dog_closeup_targets_current_dog_head(self):
        params = runpy.run_path("projects/best-buds-chair/source/v1/model.py")["PARAMS"]

        views = yaml.safe_load(Path("projects/best-buds-chair/designs/v1/views.yaml").read_text())["views"]
        dog_view = next(view for view in views if view["name"] == "face_closeup_dog")
        target = dog_view["target"]
        dog = params["dog"]
        base_z = params["base"]["z"]
        self.assertEqual(target[0], dog["cx"])
        self.assertLess(target[1], dog["cy"])
        self.assertGreaterEqual(target[1], dog["cy"] - dog["head_r"])
        self.assertAlmostEqual(target[2], base_z + 16.0, delta=3.0)

    def test_seated_diorama_builds_single_solid(self):
        from bambu.cad.archetypes.seated_diorama import build_seated_diorama

        scene = build_seated_diorama()
        self.assertEqual(len(scene.solids()), 1)

    def test_best_buds_model_exports_bounding_box(self):
        from bambu.cad import load_build123d_model

        model = load_build123d_model("projects/best-buds-chair/source/v1/model.py")
        box = model.bounding_box()
        self.assertLessEqual(float(box.size.X), 125)
        self.assertLessEqual(float(box.size.Y), 70)
        self.assertLessEqual(float(box.size.Z), 70)


if __name__ == "__main__":
    unittest.main()
