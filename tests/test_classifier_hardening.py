from __future__ import annotations

import unittest

from classifier import extract_traits
from knowledge_base import reset_cache
from rules import analyze


class ClassifierHardeningTests(unittest.TestCase):
    def setUp(self) -> None:
        reset_cache()

    def test_wireless_text_beats_default_wireless_suppression(self) -> None:
        result = extract_traits("smart speaker with wifi and bluetooth")

        self.assertEqual(result["product_type"], "smart_speaker")
        self.assertIn("wifi", result["all_traits"])
        self.assertIn("bluetooth", result["all_traits"])
        self.assertIn("radio", result["all_traits"])

    def test_product_default_wireless_traits_stay_suppressed_without_text_support(self) -> None:
        result = extract_traits("smart speaker")
        implied = {row["source"]: row for row in result["product_match_audit"]["product_implied_traits"]}

        self.assertEqual(result["product_type"], "smart_speaker")
        self.assertNotIn("wifi", result["all_traits"])
        self.assertNotIn("bluetooth", result["all_traits"])
        self.assertNotIn("radio", result["all_traits"])
        self.assertEqual(set(implied["product_core"]["suppressed_traits"]), {"bluetooth", "radio", "wifi"})

    def test_local_only_and_no_cloud_negations_are_explicitly_audited(self) -> None:
        result = extract_traits("smart door lock with no cloud and local control only")
        negation_reasons = {row["reason"] for row in result["product_match_audit"]["negation_suppressions"]}

        self.assertEqual(result["product_type"], "smart_lock")
        self.assertIn("local_only", result["all_traits"])
        self.assertNotIn("cloud", result["all_traits"])
        self.assertIn("explicit text negation for 'cloud'", negation_reasons)
        self.assertIn("explicit text negation for 'internet'", negation_reasons)

    def test_wired_only_blocks_radio_defaults(self) -> None:
        result = extract_traits("smart speaker wired only with Ethernet audio input")

        self.assertEqual(result["product_type"], "smart_speaker")
        self.assertNotIn("radio", result["all_traits"])
        self.assertNotIn("wifi", result["all_traits"])
        self.assertNotIn("bluetooth", result["all_traits"])

    def test_power_contradictions_are_stable(self) -> None:
        result = extract_traits("battery powered mains powered inspection camera")

        self.assertIn("Both battery-powered and mains-powered signals were detected.", result["contradictions"])
        self.assertEqual(result["contradiction_severity"], "high")

    def test_household_and_professional_mixed_use_is_reported(self) -> None:
        result = extract_traits("household professional coffee machine")

        self.assertIn("Both professional/commercial and household-use signals were detected.", result["contradictions"])

    def test_family_level_resolution_explains_why_subtype_was_withheld(self) -> None:
        result = extract_traits("smart speaker with screen and wifi")
        audit = result["product_match_audit"]

        self.assertEqual(result["product_match_stage"], "family")
        self.assertIsNone(result["product_subtype"])
        self.assertEqual(audit["final_match_stage"], "family")
        self.assertIn("runner-up", audit["final_match_reason"])
        self.assertTrue(audit["ambiguity_reason"])

    def test_decisive_subtype_support_is_reflected_in_audit(self) -> None:
        result = extract_traits("mesh router with tri-band Wi-Fi 6 and mobile app")
        audit = result["product_match_audit"]

        self.assertEqual(result["product_subtype"], "mesh_wifi_system")
        self.assertEqual(audit["final_match_stage"], "subtype")
        self.assertIn("decisive", audit["final_match_reason"])
        self.assertEqual(audit["top_subtype_candidates"][0]["id"], "mesh_wifi_system")

    def test_wearable_body_contact_language_stays_explicit(self) -> None:
        result = extract_traits("wearable heart-rate monitor with Bluetooth/app/body-contact")

        self.assertEqual(result["product_type"], "heart_rate_monitor")
        self.assertIn("wearable", result["all_traits"])
        self.assertIn("body_worn_or_applied", result["all_traits"])
        self.assertIn("possible_medical_boundary", result["all_traits"])

    def test_toy_language_and_not_a_toy_language_diverge_cleanly(self) -> None:
        toy = analyze("interactive toy robot for children under 14 with bluetooth")
        not_toy = analyze("child safety wearable with bluetooth, not intended for play")

        self.assertEqual(toy.product_type, "smart_toy")
        self.assertIn("TOY", toy.directives)
        self.assertNotIn("TOY", not_toy.directives)

    def test_named_classifier_products_stay_stable(self) -> None:
        cases = {
            "smart door lock with wifi bluetooth keypad and app control": "smart_lock",
            "smart speaker with wifi and bluetooth": "smart_speaker",
            "portable EV charger with mode 2 cable and in-cable protection device": "portable_ev_charger",
            "wearable heart-rate monitor with Bluetooth/app/body-contact": "heart_rate_monitor",
        }

        for description, expected in cases.items():
            with self.subTest(description=description):
                result = extract_traits(description)
                self.assertEqual(result["product_type"], expected)
                self.assertTrue(result["product_match_audit"]["top_family_candidates"])
                self.assertTrue(result["product_match_audit"]["top_subtype_candidates"])


if __name__ == "__main__":
    unittest.main()
