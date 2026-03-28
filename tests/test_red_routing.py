"""Tests for RED vs non-radio electrical product legislation routing separation.

Verifies:
- Radio products show RED as the only top-level CE route (no standalone LVD/EMC).
- RED legislation items always carry Art. 3.1(a), 3.1(b), and 3.2 sub-articles.
- Non-radio mains appliances show separate LVD and EMC top-level routes.
- Low-voltage non-radio electronics can show EMC without RED.
- No radio product produces duplicate standalone LVD/EMC top-level routes.
"""
from __future__ import annotations

import unittest

from knowledge_base import reset_cache
from rules import analyze


class RedRoutingTests(unittest.TestCase):
    def setUp(self) -> None:
        reset_cache()

    # ------------------------------------------------------------------
    # Radio product routing
    # ------------------------------------------------------------------

    def test_wifi_bluetooth_product_shows_red_only_at_ce_top_level(self) -> None:
        result = analyze("Wi-Fi and Bluetooth smart speaker with mains power")

        ce_directive_keys = {
            item.directive_key
            for item in result.ce_legislations
        }
        self.assertIn("RED", ce_directive_keys)
        self.assertNotIn("LVD", ce_directive_keys)
        self.assertNotIn("EMC", ce_directive_keys)

    def test_radio_product_directives_list_excludes_standalone_lvd_and_emc(self) -> None:
        result = analyze("Bluetooth tracker with rechargeable battery and mobile app")

        self.assertIn("RED", result.directives)
        self.assertNotIn("LVD", result.directives)
        self.assertNotIn("EMC", result.directives)

    def test_radio_product_red_legislation_item_has_mandatory_sub_articles(self) -> None:
        result = analyze("Wi-Fi 6 mesh router with gigabit ethernet and mobile app")

        red_item = next(
            (item for item in result.ce_legislations if item.directive_key == "RED"),
            None,
        )
        self.assertIsNotNone(red_item, "RED legislation item not found in CE routes")

        article_labels = {a.article for a in red_item.sub_articles}
        self.assertIn("Art. 3.1(a)", article_labels)
        self.assertIn("Art. 3.1(b)", article_labels)
        self.assertIn("Art. 3.2", article_labels)
        self.assertIn("Art. 3.3", article_labels)

    def test_radio_product_art_31a_and_31b_are_always_applicable(self) -> None:
        result = analyze("Wi-Fi and Bluetooth smart speaker with mains power")

        red_item = next(
            (item for item in result.ce_legislations if item.directive_key == "RED"),
            None,
        )
        self.assertIsNotNone(red_item)

        by_article = {a.article: a for a in red_item.sub_articles}
        self.assertTrue(by_article["Art. 3.1(a)"].applicable)
        self.assertTrue(by_article["Art. 3.1(b)"].applicable)
        self.assertTrue(by_article["Art. 3.2"].applicable)

    def test_radio_product_art_33_is_applicable_when_connectivity_traits_present(self) -> None:
        result = analyze(
            "Smart Wi-Fi plug with cloud account, mobile app, and OTA firmware updates"
        )

        red_item = next(
            (item for item in result.ce_legislations if item.directive_key == "RED"),
            None,
        )
        self.assertIsNotNone(red_item)

        art_33 = next(a for a in red_item.sub_articles if a.article == "Art. 3.3")
        self.assertTrue(art_33.applicable)

    def test_mains_powered_wifi_product_has_safety_standards_in_standards_list(self) -> None:
        """Safety standards (e.g. EN 62368-1) must still appear even without standalone LVD."""
        # Use the same description as the existing router test that confirmed EN 62368-1
        result = analyze("wifi router with ethernet ports and external power adapter")

        standard_codes = {item.code for item in result.standards}
        self.assertIn("EN 62368-1", standard_codes)

    def test_mains_powered_wifi_product_has_emc_standards_in_standards_list(self) -> None:
        """EMC standards must still appear even without standalone EMC directive."""
        result = analyze("Wi-Fi and Bluetooth smart speaker with mains power")

        standard_codes = {item.code for item in result.standards}
        # At least one of the generic EMC or radio-EMC standards should be present
        emc_or_radio_emc = {"EN 55032", "EN 55035", "EN 301 489-1", "EN 301 489-17"}
        self.assertTrue(
            emc_or_radio_emc & standard_codes,
            f"No EMC/radio-EMC standard found. Got: {sorted(standard_codes)}",
        )

    def test_radio_product_safety_standards_are_grouped_under_red_section(self) -> None:
        """Safety and EMC standards must appear in the RED standard section, not LVD/EMC."""
        result = analyze("wifi router with ethernet ports and external power adapter")

        section_keys = {section.key for section in result.standard_sections}
        self.assertIn("RED", section_keys)
        self.assertNotIn("LVD", section_keys)

    # ------------------------------------------------------------------
    # Non-radio product routing
    # ------------------------------------------------------------------

    def test_non_radio_mains_appliance_shows_separate_lvd_route(self) -> None:
        result = analyze("mains-powered electric kettle 230V")

        ce_directive_keys = {item.directive_key for item in result.ce_legislations}
        self.assertIn("LVD", ce_directive_keys)

    def test_non_radio_mains_appliance_shows_separate_emc_route(self) -> None:
        result = analyze("mains-powered electric kettle 230V")

        ce_directive_keys = {item.directive_key for item in result.ce_legislations}
        self.assertIn("EMC", ce_directive_keys)

    def test_non_radio_mains_appliance_does_not_show_red(self) -> None:
        result = analyze("mains-powered electric kettle 230V")

        self.assertNotIn("RED", result.directives)

    def test_low_voltage_non_radio_electronic_shows_emc_not_red(self) -> None:
        # Wired-only ethernet switch: electronic, no wireless radio interface
        result = analyze("8-port gigabit wired ethernet switch with steel housing")

        self.assertNotIn("RED", result.directives)

    # ------------------------------------------------------------------
    # De-duplication: no radio product produces duplicate standalone routes
    # ------------------------------------------------------------------

    def test_no_radio_product_has_duplicate_standalone_lvd_route(self) -> None:
        descriptions = [
            "Wi-Fi and Bluetooth smart speaker with mains power",
            "Bluetooth tracker with rechargeable battery and mobile app",
            "Wi-Fi 6 mesh router with gigabit ethernet and mobile app",
            "smart refrigerator with wifi, app control, and OTA updates",
        ]
        for desc in descriptions:
            with self.subTest(description=desc):
                result = analyze(desc)
                self.assertNotIn(
                    "LVD",
                    result.directives,
                    f"LVD appeared as standalone directive for radio product: {desc}",
                )

    def test_no_radio_product_has_duplicate_standalone_emc_route(self) -> None:
        descriptions = [
            "Wi-Fi and Bluetooth smart speaker with mains power",
            "Bluetooth tracker with rechargeable battery and mobile app",
            "Wi-Fi 6 mesh router with gigabit ethernet and mobile app",
        ]
        for desc in descriptions:
            with self.subTest(description=desc):
                result = analyze(desc)
                self.assertNotIn(
                    "EMC",
                    result.directives,
                    f"EMC appeared as standalone directive for radio product: {desc}",
                )


if __name__ == "__main__":
    unittest.main()
