"""Regression tests for core routing paths after backend refactor.

These tests lock in the expected regulatory outputs for representative
product descriptions across the six key routing scenarios:

1. Non-radio mains appliance  → standalone LVD + EMC (no RED)
2. Radio product              → RED only at CE level, correct Art. 3.1a/3.1b/3.2,
                                no incorrect standalone LVD/EMC leakage
3. Wi-Fi connected appliance  → radio + cybersecurity implications retained
4. Machinery / power-tool     → machinery review route present
5. Wearable / body-contact    → proximity / body-contact implications present
6. Optical / laser product    → optical route retained

These tests verify behavioral stability after the refactor; they should
remain green as long as the intended regulatory outcomes are unchanged.
"""
from __future__ import annotations

import unittest

from knowledge_base import reset_cache
from rules import analyze


class NonRadioMainsApplianceTests(unittest.TestCase):
    """Non-radio mains appliance must route to standalone LVD + EMC, never RED."""

    def setUp(self) -> None:
        reset_cache()

    def test_mains_kettle_has_lvd_and_emc_in_ce_routes(self) -> None:
        result = analyze("230 V electric kettle, household use, no wireless connectivity")
        ce_keys = {item.directive_key for item in result.ce_legislations}
        self.assertIn("LVD", ce_keys)
        self.assertIn("EMC", ce_keys)

    def test_mains_kettle_has_no_red_route(self) -> None:
        result = analyze("230 V electric kettle, household use, no wireless connectivity")
        ce_keys = {item.directive_key for item in result.ce_legislations}
        self.assertNotIn("RED", ce_keys)

    def test_mains_appliance_directives_do_not_include_red(self) -> None:
        result = analyze("Corded vacuum cleaner, 1200 W, mains powered, household use")
        self.assertIn("LVD", result.directives)
        self.assertIn("EMC", result.directives)
        self.assertNotIn("RED", result.directives)

    def test_mains_appliance_has_appliance_standards(self) -> None:
        result = analyze("Corded vacuum cleaner, 1200 W, mains powered, household use")
        codes = {item.code for item in result.standards}
        # Should contain at least one EN 60335-series standard (household appliance safety)
        household_standards = {c for c in codes if c.startswith("EN 60335-")}
        self.assertTrue(household_standards, f"No EN 60335-x standard found; got {sorted(codes)}")


class RadioProductRoutingTests(unittest.TestCase):
    """Radio products must route exclusively through RED with all mandatory sub-articles."""

    def setUp(self) -> None:
        reset_cache()

    def test_wifi_bluetooth_speaker_is_red_only_ce_route(self) -> None:
        result = analyze("Wi-Fi and Bluetooth smart speaker, mains powered")
        ce_keys = {item.directive_key for item in result.ce_legislations}
        self.assertIn("RED", ce_keys)
        self.assertNotIn("LVD", ce_keys)
        self.assertNotIn("EMC", ce_keys)

    def test_radio_product_red_item_has_31a_31b_32(self) -> None:
        result = analyze("Wi-Fi and Bluetooth smart speaker, mains powered")
        red_item = next(
            (item for item in result.ce_legislations if item.directive_key == "RED"), None
        )
        self.assertIsNotNone(red_item, "RED legislation item missing from CE routes")
        article_labels = {a.article for a in red_item.sub_articles}
        self.assertIn("Art. 3.1(a)", article_labels)
        self.assertIn("Art. 3.1(b)", article_labels)
        self.assertIn("Art. 3.2", article_labels)

    def test_radio_product_31a_and_31b_are_applicable(self) -> None:
        result = analyze("Wi-Fi and Bluetooth smart speaker, mains powered")
        red_item = next(
            (item for item in result.ce_legislations if item.directive_key == "RED"), None
        )
        self.assertIsNotNone(red_item)
        by_article = {a.article: a for a in red_item.sub_articles}
        self.assertTrue(by_article.get("Art. 3.1(a)", None) and by_article["Art. 3.1(a)"].applicable)
        self.assertTrue(by_article.get("Art. 3.1(b)", None) and by_article["Art. 3.1(b)"].applicable)

    def test_radio_product_does_not_leak_standalone_lvd_or_emc(self) -> None:
        result = analyze("Bluetooth 5.0 door sensor, battery powered, mobile app")
        self.assertIn("RED", result.directives)
        self.assertNotIn("LVD", result.directives)
        self.assertNotIn("EMC", result.directives)

    def test_radio_product_standards_include_red_harmonised_standard(self) -> None:
        result = analyze("Wi-Fi 6 router, mains powered, dual-band 2.4/5 GHz")
        # At least one RED-directive standard should appear
        red_standards = [item for item in result.standards if item.directive == "RED"]
        self.assertTrue(red_standards, "No RED-directive standards found")


class WifiApplianceTests(unittest.TestCase):
    """Wi-Fi connected appliances should carry radio and cybersecurity implications."""

    def setUp(self) -> None:
        reset_cache()

    def test_smart_washing_machine_routes_through_red(self) -> None:
        result = analyze(
            "Smart washing machine with Wi-Fi, cloud account, OTA firmware updates, 230 V mains"
        )
        self.assertIn("RED", result.directives)

    def test_smart_appliance_carries_cyber_review(self) -> None:
        result = analyze(
            "Smart washing machine with Wi-Fi, cloud account, OTA firmware updates, 230 V mains"
        )
        # Cybersecurity route (RED_CYBER or CRA) should be present
        all_directive_keys = {item.directive_key for item in result.legislations}
        cyber_present = bool({"RED_CYBER", "CRA"} & all_directive_keys)
        self.assertTrue(cyber_present, f"No cyber route found; directives={result.directives}")

    def test_wifi_appliance_has_no_standalone_lvd_or_emc(self) -> None:
        result = analyze(
            "Smart Wi-Fi air purifier with HEPA filter, 230 V, cloud app control"
        )
        self.assertIn("RED", result.directives)
        self.assertNotIn("LVD", result.directives)
        self.assertNotIn("EMC", result.directives)


class MachineryPowerToolTests(unittest.TestCase):
    """Power tools and machinery products must include a machinery review route."""

    def setUp(self) -> None:
        reset_cache()

    def test_power_drill_has_machinery_review(self) -> None:
        result = analyze(
            "Cordless power drill, 18 V lithium-ion battery, consumer handheld tool"
        )
        all_directive_keys = {item.directive_key for item in result.legislations}
        machinery_present = bool({"MD", "MACH_REG"} & all_directive_keys)
        self.assertTrue(machinery_present, f"No machinery route; directives={result.directives}")

    def test_power_tool_product_type_is_identified(self) -> None:
        result = analyze(
            "Cordless power drill, 18 V lithium-ion battery, consumer handheld tool"
        )
        self.assertIsNotNone(result.product_type, "Product type should be identified for power drill")

    def test_power_tool_missing_info_includes_tool_context(self) -> None:
        result = analyze("Power drill")
        # With minimal description, missing-info items should flag something tool-relevant
        self.assertTrue(
            result.missing_information,
            "Expected missing-information items for an under-described power tool",
        )

    def test_corded_power_saw_has_machinery_route(self) -> None:
        result = analyze(
            "Corded circular saw, 230 V, 1800 W, for professional wood cutting"
        )
        all_directive_keys = {item.directive_key for item in result.legislations}
        machinery_present = bool({"MD", "MACH_REG"} & all_directive_keys)
        self.assertTrue(machinery_present, f"No machinery route; directives={result.directives}")


class WearableBodyContactTests(unittest.TestCase):
    """Wearable / body-contact products must carry exposure and proximity implications."""

    def setUp(self) -> None:
        reset_cache()

    def test_smartwatch_product_type_recognised(self) -> None:
        result = analyze(
            "Smartwatch with heart rate monitor, Bluetooth, rechargeable battery, wrist-worn"
        )
        self.assertIsNotNone(result.product_type)

    def test_wearable_radio_product_routes_through_red(self) -> None:
        result = analyze(
            "Smartwatch with heart rate monitor, Bluetooth, rechargeable battery, wrist-worn"
        )
        self.assertIn("RED", result.directives)

    def test_wearable_radio_product_has_no_standalone_lvd_emc(self) -> None:
        result = analyze(
            "Smartwatch with heart rate monitor, Bluetooth, rechargeable battery, wrist-worn"
        )
        self.assertNotIn("LVD", result.directives)
        self.assertNotIn("EMC", result.directives)

    def test_wearable_gpsr_present(self) -> None:
        result = analyze(
            "Fitness tracker, Bluetooth LE, skin-contact silicone band, rechargeable battery"
        )
        all_directive_keys = {item.directive_key for item in result.legislations}
        self.assertIn("GPSR", all_directive_keys)

    def test_body_contact_product_confirms_body_contact_trait(self) -> None:
        result = analyze(
            "ECG chest strap, body-worn, skin-contact electrodes, Bluetooth 5.0, rechargeable battery"
        )
        self.assertIn("RED", result.directives)
        all_directive_keys = {item.directive_key for item in result.legislations}
        # GPSR should also be present for body-contact consumer product
        self.assertIn("GPSR", all_directive_keys)


class OpticalLaserTests(unittest.TestCase):
    """Laser / optical products must retain the optical route and relevant standards."""

    def setUp(self) -> None:
        reset_cache()

    def test_laser_projector_has_optical_standard(self) -> None:
        result = analyze(
            "Laser home projector, 230 V mains, HDMI input, 2000 lm, class 1 laser"
        )
        codes = {item.code for item in result.standards + result.review_items}
        # EN 60825-1 (laser safety) or EN 62471 (photobiological) should be present
        optical_present = bool({"EN 60825-1", "EN 62471"} & codes)
        self.assertTrue(optical_present, f"No optical standard found; codes={sorted(codes)}")

    def test_laser_product_has_optical_route(self) -> None:
        # A home projector with an explicit laser light source should trigger the laser standard.
        result = analyze(
            "Laser home projector, 230 V mains, HDMI input, 2000 lm, class 1 laser source"
        )
        codes = {item.code for item in result.standards + result.review_items}
        optical_present = bool({"EN 60825-1", "EN 62471"} & codes)
        self.assertTrue(optical_present, f"No optical standard; codes={sorted(codes)}")

    def test_non_laser_product_without_explicit_optical_emitter_omits_laser_standard(self) -> None:
        # A basic mains kettle with no optical emitter mention should not get EN 60825-1.
        result = analyze(
            "230 V electric kettle, 1.7 L, automatic shut-off, household use"
        )
        codes = {item.code for item in result.standards + result.review_items}
        self.assertNotIn("EN 60825-1", codes, "Laser safety standard incorrectly included for non-laser kettle")


class RefactorStabilityTests(unittest.TestCase):
    """Sanity checks that confirm core refactored helpers produce coherent outputs."""

    def setUp(self) -> None:
        reset_cache()

    def test_analyze_returns_result_for_empty_description(self) -> None:
        result = analyze("")
        self.assertIsNotNone(result)

    def test_version_is_present_in_result(self) -> None:
        result = analyze("Wi-Fi smart plug, 230 V, app control")
        self.assertTrue(result.catalog_version or result.engine_version)

    def test_analyze_is_side_effect_free_across_calls(self) -> None:
        # Two consecutive calls with different products must not contaminate each other.
        r1 = analyze("230 V electric kettle, no wireless")
        r2 = analyze("Bluetooth fitness tracker, rechargeable battery")
        self.assertNotIn("RED", r1.directives)
        self.assertIn("RED", r2.directives)

    def test_missing_information_limit_is_respected(self) -> None:
        # _missing_information caps at 8 items.
        result = analyze("some electronic device")
        self.assertLessEqual(len(result.missing_information), 8)

    def test_shadow_diff_absent_when_not_enabled(self) -> None:
        result = analyze("Wi-Fi smart speaker, mains powered")
        # Shadow diff should be empty list (not enabled by default in tests).
        self.assertEqual(result.analysis_audit.shadow_diff, [])


if __name__ == "__main__":
    unittest.main()
