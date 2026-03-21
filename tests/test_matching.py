import unittest
from datetime import date
from unittest.mock import patch

from fastapi import HTTPException
import classifier
from classifier import _select_matched_products, extract_traits
from knowledge_base import reset_cache
import main
from models import ProductInput
from rules import _pick_legislations, analyze
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

    def test_reset_cache_clears_classifier_trait_cache(self) -> None:
        classifier._known_trait_ids()

        self.assertIsNotNone(classifier.TRAIT_IDS_CACHE)

        reset_cache()

        self.assertIsNone(classifier.TRAIT_IDS_CACHE)

    def test_multi_directive_standard_is_preserved_in_analysis_output(self) -> None:
        result = analyze("bluetooth tracker with mobile app and battery")
        en_301_489_1 = next(item for item in result.standards if item.code == "EN 301 489-1")

        self.assertEqual(set(en_301_489_1.directives), {"RED", "EMC"})

        section_keys = {
            section["key"]
            for section in result.standard_sections
            if any(row["code"] == "EN 301 489-1" for row in section["items"])
        }
        self.assertTrue({"RED", "EMC"}.issubset(section_keys))

    def test_pick_legislations_uses_current_date_per_call(self) -> None:
        with patch("rules._current_date", return_value=date(2026, 3, 21)):
            future_rows = _pick_legislations({"ai_related"}, set(), None)
        with patch("rules._current_date", return_value=date(2026, 8, 3)):
            current_rows = _pick_legislations({"ai_related"}, set(), None)

        future_ai_act = next(row for row in future_rows if row["directive_key"] == "AI_Act")
        current_ai_act = next(row for row in current_rows if row["directive_key"] == "AI_Act")

        self.assertEqual(future_ai_act["timing_status"], "future")
        self.assertEqual(current_ai_act["timing_status"], "current")

    def test_admin_reload_is_disabled_without_token(self) -> None:
        with self.assertRaises(HTTPException) as ctx:
            main._require_admin_reload_token()

        self.assertEqual(ctx.exception.status_code, 503)
        self.assertIn("disabled", ctx.exception.detail)

    def test_admin_reload_accepts_valid_token(self) -> None:
        with patch.dict("os.environ", {"REGCHECK_ADMIN_RELOAD_TOKEN": "secret"}):
            main._require_admin_reload_token("secret")
            response = main.admin_reload(None)

        self.assertTrue(response["ok"])

    def test_analyze_hides_internal_exceptions(self) -> None:
        with patch.dict(main._kb_status, {"ok": True, "error": None, "counts": {}}):
            with patch("main.analyze", side_effect=RuntimeError("boom")):
                with patch.object(main.logger, "exception"):
                    with self.assertRaises(HTTPException) as ctx:
                        main.run_analysis(ProductInput(description="test product"))

        self.assertEqual(ctx.exception.status_code, 500)
        self.assertEqual(ctx.exception.detail, "Analysis failed")


if __name__ == "__main__":
    unittest.main()
