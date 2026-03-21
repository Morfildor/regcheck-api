import unittest
from datetime import date
from unittest.mock import patch

from fastapi import HTTPException
import classifier
from classifier import _select_matched_products, extract_traits
from knowledge_base import reset_cache
import main
from models import ProductInput
from models import LegislationItem
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

    def test_analyze_preserves_preferred_standard_review_fallback(self) -> None:
        fake_traits = {
            "product_type": "smart_speaker",
            "matched_products": ["smart_speaker"],
            "confirmed_products": [],
            "preferred_standard_codes": ["EN 62368-1"],
            "product_match_confidence": "medium",
            "product_candidates": [
                {
                    "id": "smart_speaker",
                    "label": "Smart speaker",
                    "score": 140,
                    "confidence": "medium",
                    "reasons": ["synthetic fixture"],
                    "likely_standards": ["EN 62368-1"],
                }
            ],
            "functional_classes": ["home_device"],
            "confirmed_functional_classes": [],
            "explicit_traits": ["electrical", "electronic", "mains_powered"],
            "confirmed_traits": ["electrical", "electronic", "mains_powered"],
            "inferred_traits": [],
            "all_traits": ["electrical", "electronic", "mains_powered"],
            "contradictions": [],
            "contradiction_severity": "none",
            "diagnostics": [],
        }

        with patch("rules.extract_traits", return_value=fake_traits):
            result = analyze("synthetic")

        review_item = next(item for item in result.review_items if item.code == "EN 62368-1")

        self.assertEqual(review_item.match_basis, "preferred_product")
        self.assertIsNotNone(review_item.reason)
        self.assertEqual(review_item.fact_basis, "confirmed")

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

    def test_analyze_surfaces_ai_act_in_future_regimes(self) -> None:
        result = analyze("AI-enabled smart camera with wifi")

        future_keys = {item.directive_key for item in result.future_regimes}
        self.assertIn("AI_Act", future_keys)

    def test_analyze_includes_informational_legislation_without_crashing(self) -> None:
        result = analyze("mains-powered toaster")

        info_codes = {item.code for item in result.informational_items}
        self.assertIn("2017/1357", info_codes)

        section_keys = {section["key"] for section in result.legislation_sections}
        self.assertIn("informational", section_keys)

    def test_future_only_review_items_do_not_raise_current_risk(self) -> None:
        fake_traits = {
            "product_type": "synthetic_product",
            "matched_products": [],
            "confirmed_products": [],
            "preferred_standard_codes": [],
            "product_match_confidence": "high",
            "product_candidates": [],
            "functional_classes": [],
            "confirmed_functional_classes": [],
            "explicit_traits": ["ai_related"],
            "confirmed_traits": ["ai_related"],
            "inferred_traits": [],
            "all_traits": ["ai_related"],
            "contradictions": [],
            "contradiction_severity": "none",
            "diagnostics": [],
        }
        future_legislation = LegislationItem(
            code="2024/1689",
            title="Artificial Intelligence Act",
            family="AI regulation",
            directive_key="AI_Act",
            bucket="future",
            timing_status="future",
            applicability="conditional",
        )
        future_review_row = {
            "code": "AI Act review",
            "title": "AI Act assessment required",
            "directive": "AI_Act",
            "directives": ["AI_Act"],
            "legislation_key": "AI_Act",
            "category": "ai",
            "item_type": "review",
            "score": 80,
            "confidence": "medium",
            "harmonization_status": "review",
            "reason": "synthetic future-only review item",
        }

        with patch("rules.extract_traits", return_value=fake_traits):
            with patch("rules._build_legislation_sections", return_value=([future_legislation], [], ["AI_Act"])):
                with patch(
                    "rules.find_applicable_items",
                    return_value={"standards": [], "review_items": [future_review_row], "rejections": []},
                ):
                    with patch("rules._apply_post_selection_gates", side_effect=lambda rows, *_, **__: rows):
                        with patch("rules._missing_information", return_value=[]):
                            result = analyze("synthetic")

        self.assertEqual(result.current_compliance_risk, "LOW")
        self.assertEqual(result.future_watchlist_risk, "MEDIUM")
        self.assertEqual(result.overall_risk, "MEDIUM")
        self.assertEqual(result.stats.current_review_items_count, 0)
        self.assertEqual(result.stats.future_review_items_count, 1)

    def test_router_routes_to_en_62368_and_not_en_60335(self) -> None:
        result = analyze("wifi router with ethernet ports and external power adapter")

        standard_codes = {item.code for item in result.standards}

        self.assertIn("EN 62368-1", standard_codes)
        self.assertNotIn("EN 60335-1", standard_codes)

    def test_connected_appliance_keeps_en_60335_and_drops_en_62368(self) -> None:
        result = analyze(
            "connected espresso machine with wifi app control cloud account OTA updates and display"
        )

        standard_codes = {item.code for item in result.standards}

        self.assertIn("EN 60335-1", standard_codes)
        self.assertIn("EN 60335-2-15", standard_codes)
        self.assertNotIn("EN 62368-1", standard_codes)

    def test_smart_speaker_routes_to_av_ict_and_not_household_appliance_safety(self) -> None:
        result = analyze("smart speaker with wifi and bluetooth")

        standard_codes = {item.code for item in result.standards}

        self.assertIn("EN 62368-1", standard_codes)
        self.assertNotIn("EN 60335-1", standard_codes)
        self.assertIn("EN 55032", standard_codes)
        self.assertIn("EN 55035", standard_codes)
        self.assertNotIn("EN 55014-1", standard_codes)

    def test_laptop_keeps_red_emf_routes_but_drops_optical_noise_and_generic_battery_review(self) -> None:
        result = analyze(
            "Laptop notebook computer with integrated Wi-Fi and Bluetooth, rechargeable lithium battery, display, USB-C charger."
        )

        standard_codes = {item.code for item in result.standards}
        review_codes = {item.code for item in result.review_items}

        self.assertIn("EN 62368-1", standard_codes)
        self.assertIn("EN 62311", standard_codes)
        self.assertIn("EN 62479", standard_codes)
        self.assertIn("EN 62133-2", standard_codes)
        self.assertNotIn("EN 60825-1", standard_codes)
        self.assertNotIn("EN 62471", standard_codes)
        self.assertNotIn("Battery safety review", review_codes)

    def test_laser_projector_keeps_laser_and_photobiological_routes(self) -> None:
        result = analyze("Laser projector with Wi-Fi and Bluetooth")

        standard_codes = {item.code for item in result.standards}

        self.assertIn("EN 62368-1", standard_codes)
        self.assertIn("EN 60825-1", standard_codes)
        self.assertIn("EN 62471", standard_codes)

    def test_cellular_handheld_routes_to_specific_red_emf_standards_not_en_62479(self) -> None:
        result = analyze("Handheld LTE scanner with display, rechargeable battery, and Wi-Fi")

        standard_codes = {item.code for item in result.standards}

        self.assertTrue(any(code.startswith("EN 62209") for code in standard_codes))
        self.assertTrue(any(code in standard_codes for code in {"EN 50566", "EN 50663", "EN 50665", "EN 62311"}))
        self.assertNotIn("EN 62479", standard_codes)


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
