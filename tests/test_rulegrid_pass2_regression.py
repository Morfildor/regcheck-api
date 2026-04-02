from __future__ import annotations

import unittest

from rules import analyze


def _standard_codes(result: object) -> set[str]:
    return {item.code for item in result.standards}


def _review_codes(result: object) -> set[str]:
    return {item.code for item in result.review_items}


def _missing_keys(result: object) -> set[str]:
    return {item.key for item in result.missing_information_items}


def _finding_articles(result: object) -> set[str]:
    return {item.article for item in result.findings}


class RuleGridPass2RegressionTests(unittest.TestCase):
    def test_non_radio_mains_appliance_contract_fields(self) -> None:
        result = analyze("mains-powered toaster", depth="deep")

        self.assertIn("LVD", result.directives)
        self.assertIn("EMC", result.directives)
        self.assertNotIn("RED", result.directives)
        self.assertEqual(result.primary_route_standard_code, "EN 60335-2-9")
        self.assertEqual(result.route_context.scope_route, "appliance")
        self.assertEqual(result.route_context.primary_route_family, "household_appliance")
        self.assertTrue({"EN 60335-2-9", "EN 60335-1", "EN 62233"} <= _standard_codes(result))
        self.assertIn("EN 50564", _review_codes(result))
        self.assertEqual(_missing_keys(result), set())
        self.assertEqual(result.current_compliance_risk, "MEDIUM")
        self.assertEqual(_finding_articles(result), {"Informational notice", "Legislation route", "Standard review", "Standard route"})

    def test_radio_connected_appliance_contract_fields(self) -> None:
        result = analyze("smart refrigerator with wifi, app control, and OTA updates", depth="deep")

        self.assertTrue({"RED", "RED_CYBER", "CRA", "ESPR"} <= set(result.directives))
        self.assertEqual(result.primary_route_standard_code, "EN 60335-2-24")
        self.assertEqual(result.route_context.scope_route, "appliance")
        self.assertEqual(result.route_context.primary_route_family, "household_appliance")
        self.assertTrue({"EN 60335-2-24", "EN 301 893", "EN 18031-1"} <= _standard_codes(result))
        self.assertIn("CRA review", _review_codes(result))
        self.assertTrue({"refrigerator_use_class", "radio_rf_detail", "cloud_dependency"} <= _missing_keys(result))
        self.assertEqual(result.overall_risk, "HIGH")
        self.assertIn("primary:household_appliance", result.analysis_audit.context_tags)

    def test_smart_lock_output_parity_guardrails(self) -> None:
        result = analyze("bluetooth smart lock with Wi-Fi and cloud account required", depth="deep")

        self.assertTrue({"RED", "RED_CYBER", "GDPR", "CRA"} <= set(result.directives))
        self.assertEqual(result.primary_route_standard_code, "EN 14846")
        self.assertEqual(result.route_context.primary_route_family, "building_hardware")
        self.assertEqual(result.route_context.scope_route, "appliance")
        self.assertTrue({"EN 14846", "EN 12209", "EN 301 489-1"} <= _standard_codes(result))
        self.assertTrue({"GDPR review", "CRA review"} <= _review_codes(result))
        self.assertTrue({"smart_lock_installation", "radio_rf_detail", "battery_capacity"} <= _missing_keys(result))
        self.assertTrue({"Legislation route", "Missing information", "Standard review", "Standard route"} <= _finding_articles(result))
        self.assertEqual(result.analysis_audit.depth, "deep")

    def test_ev_charger_route_and_missing_info_guardrails(self) -> None:
        result = analyze("smart ev charger wallbox with wifi, bluetooth and mobile app", depth="deep")

        self.assertTrue({"RED", "RED_CYBER", "CRA"} <= set(result.directives))
        self.assertEqual(result.primary_route_standard_code, "EN IEC 61851-1")
        self.assertEqual(result.route_context.primary_route_family, "ev_charging")
        self.assertEqual(result.route_context.scope_route, "appliance")
        self.assertTrue({"EN IEC 61851-1", "EN IEC 61851-21-2", "EN 301 489-1"} <= _standard_codes(result))
        self.assertIn("EN 62196-2", _review_codes(result))
        self.assertTrue({"ev_mode", "ev_ac_dc", "ev_connector_type"} <= _missing_keys(result))
        self.assertEqual(result.overall_risk, "HIGH")
        self.assertIn("primary:ev_charging", result.standard_match_audit.context_tags)

    def test_toy_like_product_keeps_toy_route_and_connected_overlays(self) -> None:
        result = analyze("smart toy robot for children with wifi and microphone", depth="deep")

        self.assertTrue({"TOY", "RED", "RED_CYBER"} <= set(result.directives))
        self.assertEqual(result.primary_route_standard_code, "EN 62115")
        self.assertEqual(result.route_context.scope_route, "toy")
        self.assertEqual(result.route_context.primary_route_family, "toy")
        self.assertIn("EN 62115", _review_codes(result))
        self.assertIn("EN 71 review", _review_codes(result))
        self.assertTrue({"power_source", "radio_rf_detail"} <= _missing_keys(result))
        self.assertEqual(result.current_compliance_risk, "HIGH")

    def test_medical_adjacent_wearable_keeps_boundary_reviews(self) -> None:
        result = analyze("wearable heart-rate monitor with Bluetooth/app/body-contact", depth="deep")

        self.assertIn("MDR", result.directives)
        self.assertEqual(result.primary_route_standard_code, "EN 62368-1")
        self.assertEqual(result.route_context.scope_route, "av_ict")
        self.assertEqual(result.route_context.primary_route_family, "av_ict_wearable")
        self.assertTrue({"EN 62368-1", "EN 62209-1528", "EN 18031-2"} <= _standard_codes(result))
        self.assertTrue({"MDR borderline review", "Biocompatibility / skin-contact review"} <= _review_codes(result))
        self.assertTrue({"medical_wellness_boundary", "radio_rf_detail"} <= _missing_keys(result))
        self.assertIn("boundary:medical_wellness", result.route_context.context_tags)
        self.assertIn("contact:skin", result.route_context.context_tags)


if __name__ == "__main__":
    unittest.main()
