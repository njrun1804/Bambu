import unittest


class ContextTests(unittest.TestCase):
    def test_context_view_exposes_a1_mini_constraints_and_material_state(self):
        from bambu.context import context_view

        view = context_view()

        self.assertEqual(view["printer"]["model"], "Bambu Lab A1 mini")
        self.assertEqual(view["printer"]["build_volume_mm"], [180, 180, 180])
        self.assertEqual(view["printer"]["nozzle_mm"], 0.4)
        self.assertEqual(view["printer"]["printer_contact_policy"], "manual_only")
        self.assertIn("Bambu PLA Basic", [item["name"] for item in view["materials"]])
        petg = next(item for item in view["materials"] if item["name"] == "Bambu PETG HF")
        self.assertTrue(petg["requires_dryness_tracking"])
        self.assertEqual(view["plate"]["name"], "Bambu Dual-Texture PEI Plate")

    def test_rules_view_names_backend_and_artifact_policy(self):
        from bambu.context import rules_view

        rules = rules_view()

        self.assertEqual(rules["cad_backends"]["serious"], "build123d")
        self.assertEqual(rules["cad_backends"]["simple_public"], "openscad")
        self.assertEqual(rules["slicing"]["primary"], "bambu-studio")
        self.assertEqual(rules["slicing"]["backup"], "orcaslicer")
        self.assertIn("stl", rules["artifacts"]["generated_extensions"])
        self.assertEqual(rules["printer_contact"], "manual_only")


if __name__ == "__main__":
    unittest.main()
