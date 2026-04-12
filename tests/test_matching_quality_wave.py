from __future__ import annotations

import unittest

from classifier import extract_traits
from knowledge_base import reset_cache

from tests.matching_quality_fixtures import MATCHING_QUALITY_CASES, expected_case_family


class MatchingQualityWaveTests(unittest.TestCase):
    def setUp(self) -> None:
        reset_cache()

    def test_matching_quality_regressions(self) -> None:
        for case in MATCHING_QUALITY_CASES:
            with self.subTest(group=case.group, case=case.name):
                result = extract_traits(case.description)

                expected_family = expected_case_family(case)
                if expected_family is not None:
                    self.assertEqual(result["product_family"], expected_family)
                if case.expected_subtype is not None:
                    self.assertEqual(result["product_subtype"], case.expected_subtype)
                elif case.expected_stage in {"family", "ambiguous"}:
                    self.assertIsNone(result["product_subtype"])
                if case.expected_stage is not None:
                    self.assertEqual(result["product_match_stage"], case.expected_stage)
                for forbidden_subtype in case.forbidden_subtypes:
                    self.assertNotEqual(result["product_subtype"], forbidden_subtype)

    def test_matching_audit_exposes_new_pipeline_fields(self) -> None:
        dock = extract_traits("USB-C monitor dock with ethernet and USB ports")["product_match_audit"]
        family_only = extract_traits("monitor arm with integrated usb hub")["product_match_audit"]
        ambiguous = extract_traits("portable charger for ebike battery")["product_match_audit"]
        companion = extract_traits("smart lock bridge for bluetooth door lock")["product_match_audit"]
        hybrid = extract_traits("door entry panel with camera and keypad")["product_match_audit"]

        self.assertTrue(dock["shortlist_basis"])
        self.assertTrue(dock["rerank_reasons"])
        self.assertIn("docking_station", dock["top_subtype_candidates"][0]["id"])

        self.assertTrue(family_only["accessory_gate_reasons"])
        self.assertTrue(family_only["generic_alias_penalties"])
        self.assertTrue(family_only["family_level_limiter"])
        self.assertEqual(family_only["role_parse"]["primary_product_head"], "monitor arm")

        self.assertEqual(ambiguous["final_match_stage"], "family")
        self.assertIn("portable_power_charger", ambiguous["top_family_candidates"][0]["family"])
        self.assertTrue(ambiguous["role_parse"]["charged_device"])

        self.assertEqual(companion["resolved_head_candidate"], "smart lock bridge")
        self.assertTrue(companion["companion_device_decision"])
        self.assertTrue(companion["negative_guard_activations"])
        self.assertTrue(companion["rejected_confusable_candidates"])

        self.assertEqual(hybrid["resolved_head_candidate"], "entry panel with camera and keypad")
        self.assertTrue(hybrid["hybrid_detection_reason"])
        self.assertTrue(hybrid["domain_disambiguation_reason"])


if __name__ == "__main__":
    unittest.main()
