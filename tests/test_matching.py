import unittest

from classifier import _select_matched_products, extract_traits
from knowledge_base import reset_cache
from standards_engine import find_applicable_items


class MatchingTests(unittest.TestCase):
    def setUp(self) -> None:
        reset_cache()

    def test_connected_text_infers_electrical_and_electronic(self) -> None:
        result = extract_traits("bluetooth battery tracker with mobile app")

        self.assertIn("electrical", result["all_traits"])
        self.assertIn("electronic", result["all_traits"])
        self.assertIn("bluetooth", result["all_traits"])

    def test_select_matched_products_keeps_close_alternatives(self) -> None:
        candidates = [
            {"id": "smart_speaker", "score": 160, "confidence": "high"},
            {"id": "smart_display", "score": 149, "confidence": "medium"},
            {"id": "smart_plug", "score": 120, "confidence": "low"},
        ]

        self.assertEqual(_select_matched_products(candidates), ["smart_speaker", "smart_display"])

    def test_connected_product_family_adds_preferred_standards(self) -> None:
        result = extract_traits("smart speaker with wifi and bluetooth")

        self.assertEqual(result["product_type"], "smart_speaker")
        self.assertIn("EN 62368-1", result["preferred_standard_codes"])

    def test_preferred_standard_can_surface_as_review_when_feature_trigger_is_missing(self) -> None:
        items = find_applicable_items(
            traits={"electrical", "electronic"},
            directives=["LVD"],
            preferred_standard_codes=["EN 62368-1"],
        )

        review_codes = {row["code"] for row in items["review_items"]}
        standard_codes = {row["code"] for row in items["standards"]}

        self.assertIn("EN 62368-1", review_codes)
        self.assertNotIn("EN 62368-1", standard_codes)


if __name__ == "__main__":
    unittest.main()
