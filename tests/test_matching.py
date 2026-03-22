import unittest
from datetime import date
from unittest.mock import patch

from fastapi import HTTPException
import classifier
from classifier import _select_matched_products, extract_traits
from knowledge_base import (
    _validate_products,
    _validate_standard_metadata,
    load_products,
    load_standards,
    load_traits,
    reset_cache,
)
import main
from models import ProductInput
from models import LegislationItem
from rules import _pick_legislations, analyze
from standards_engine import _keyword_hits, find_applicable_items


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
        self.assertEqual(result["product_family"], "smart_assistant_device")
        self.assertEqual(result["product_subtype"], "smart_speaker")
        self.assertEqual(result["product_match_stage"], "subtype")
        self.assertIn("EN 62368-1", result["preferred_standard_codes"])

    def test_product_implied_wireless_traits_expand_to_radio(self) -> None:
        result = extract_traits("smart smoke alarm")

        self.assertEqual(result["product_type"], "smart_smoke_co_alarm")
        self.assertIn("radio", result["all_traits"])
        self.assertIn("wifi", result["all_traits"])

    def test_product_match_exposes_safe_genres(self) -> None:
        result = extract_traits("connected espresso machine with wifi app control cloud account OTA updates and display")

        self.assertEqual(result["product_type"], "coffee_machine")
        self.assertIn("household_appliance", result["product_genres"])
        self.assertIn("kitchen_food_appliance", result["product_genres"])

    def test_new_feature_traits_are_detected_from_text(self) -> None:
        result = extract_traits("Wi-Fi 7 mesh router with WPA3 and voice assistant support")

        for trait in ("wifi", "wifi_7", "mesh_network_node", "wpa3", "voice_assistant", "radio"):
            self.assertIn(trait, result["all_traits"])

    def test_smart_display_beats_speaker_when_display_clues_are_present(self) -> None:
        result = extract_traits("smart display with screen camera speaker and wifi")

        self.assertEqual(result["product_family"], "smart_assistant_device")
        self.assertEqual(result["product_subtype"], "smart_display")
        self.assertEqual(result["product_match_stage"], "subtype")
        self.assertEqual(result["product_type"], "smart_display")

    def test_smart_speaker_with_screen_stays_at_family_stage(self) -> None:
        result = extract_traits("smart speaker with screen and wifi")

        self.assertEqual(result["product_family"], "smart_assistant_device")
        self.assertIsNone(result["product_subtype"])
        self.assertEqual(result["product_match_stage"], "family")
        self.assertIn("smart_speaker", result["matched_products"])
        self.assertIn("smart_display", result["matched_products"])
        self.assertEqual(result["preferred_standard_codes"], ["EN 62368-1"])
        self.assertEqual(result["contradiction_severity"], "none")

    def test_mesh_router_beats_plain_router(self) -> None:
        result = extract_traits("mesh router with tri-band Wi-Fi 6 and mobile app")

        self.assertEqual(result["product_family"], "wifi_networking")
        self.assertEqual(result["product_subtype"], "mesh_wifi_system")
        self.assertEqual(result["product_match_stage"], "subtype")

    def test_wireless_access_point_beats_router_when_ap_clues_are_present(self) -> None:
        result = extract_traits("wireless access point with PoE and dual-band wifi")

        self.assertEqual(result["product_family"], "wifi_networking")
        self.assertEqual(result["product_subtype"], "wireless_access_point")
        self.assertEqual(result["product_match_stage"], "subtype")

    def test_air_purifier_beats_air_cleaner_with_hepa_clue(self) -> None:
        result = extract_traits("HEPA air purifier with wifi")

        self.assertEqual(result["product_family"], "air_treatment_cleaner")
        self.assertEqual(result["product_subtype"], "air_purifier")

    def test_fan_heater_beats_fan_with_heater_clue(self) -> None:
        result = extract_traits("fan heater for indoor room heating")

        self.assertEqual(result["product_family"], "indoor_air_mover")
        self.assertEqual(result["product_subtype"], "fan_heater")
        self.assertEqual(result["product_match_stage"], "subtype")

    def test_home_projector_beats_generic_projector_with_home_cinema_clues(self) -> None:
        result = extract_traits("laser projector with wifi bluetooth and home cinema apps")

        self.assertEqual(result["product_family"], "projector_device")
        self.assertEqual(result["product_subtype"], "home_projector")
        self.assertEqual(result["product_match_stage"], "subtype")

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

    def test_genre_gated_standard_uses_direct_genre_context(self) -> None:
        items = find_applicable_items(
            traits={"consumer", "electrical", "electronic", "battery_powered"},
            directives=["GPSR"],
            product_genres=["micromobility"],
        )

        review_codes = {row["code"] for row in items["review_items"]}
        self.assertIn("EN 17128", review_codes)

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
        self.assertEqual(section_keys, {"RED"})

    def test_analyze_keeps_genre_gated_iot_review_routes(self) -> None:
        result = analyze("consumer iot smart plug with app control")

        review_codes = {item.code for item in result.review_items}
        self.assertIn("EN 303 645 review", review_codes)

    def test_keyword_matching_handles_reordered_phrase_tokens(self) -> None:
        standard = next(row for row in load_standards() if row["code"] == "EN 62368-1")
        hits = _keyword_hits(standard, classifier.normalize("ict audio video equipment with display"))

        self.assertIn("audio/video, ict", hits)

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

    def test_informational_legislation_does_not_create_lvd_route_for_battery_only_household_product(self) -> None:
        result = analyze("battery-powered oral hygiene appliance")

        self.assertNotIn("LVD", result.directives)
        self.assertFalse(any(item.directive_key == "LVD" and item.bucket != "informational" for item in result.legislations))
        self.assertFalse(any(item.code.startswith("EN 60335-") for item in result.standards + result.review_items))

    def test_offline_electronic_appliance_does_not_get_cra_watchlist(self) -> None:
        result = analyze("electric kettle")

        self.assertNotIn("CRA", result.directives)
        self.assertNotIn("CRA", {item.directive_key for item in result.future_regimes})

    def test_engine_derived_handheld_trait_is_confirmed_when_stated_in_text(self) -> None:
        result = analyze("Handheld LTE scanner with display, rechargeable battery, and Wi-Fi")

        self.assertIn("handheld", result.all_traits)
        self.assertIn("handheld", result.confirmed_traits)

    def test_ev_charger_catalog_links_resolve_and_surface_review_route(self) -> None:
        standards = load_standards()
        products = load_products()

        product = next(row for row in products if row["id"] == "ev_charger_home")
        known_refs = {row["code"] for row in standards} | {
            row["standard_family"] for row in standards if row.get("standard_family")
        }

        for reference in product["likely_standards"]:
            self.assertIn(reference, known_refs)

        result = analyze("smart ev charger wallbox with wifi, bluetooth and mobile app")
        review_codes = {item.code for item in result.review_items}
        self.assertIn("IEC 61851-1", review_codes)

    def test_all_product_likely_standards_resolve_to_known_codes_or_families(self) -> None:
        standards = load_standards()
        known_refs = {row["code"] for row in standards} | {
            row["standard_family"] for row in standards if row.get("standard_family")
        }

        unresolved = [
            (product["id"], reference)
            for product in load_products()
            for reference in product.get("likely_standards", [])
            if reference not in known_refs
        ]

        self.assertEqual(unresolved, [])

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
                            result = analyze("synthetic", depth="deep")

        self.assertEqual(result.current_compliance_risk, "LOW")
        self.assertEqual(result.future_watchlist_risk, "MEDIUM")
        self.assertEqual(result.overall_risk, "MEDIUM")
        self.assertEqual(result.stats.current_review_items_count, 0)
        self.assertEqual(result.stats.future_review_items_count, 1)
        self.assertTrue(any(item.article == "Future standard review" for item in result.findings))

    def test_analyze_populates_actionable_findings(self) -> None:
        result = analyze("bluetooth tracker with mobile app and battery", depth="standard")

        self.assertTrue(result.findings)
        self.assertTrue(any(item.article == "Legislation route" for item in result.findings))
        self.assertTrue(any(item.article == "Standard route" for item in result.findings))
        self.assertTrue(any(item.directive == "INPUT" for item in result.findings))

    def test_analysis_depth_changes_findings_and_question_volume(self) -> None:
        description = "AI-enabled smart camera with wifi, cloud account, OTA updates, and mobile app control"

        quick = analyze(description, depth="quick")
        deep = analyze(description, depth="deep")

        self.assertLess(len(quick.findings), len(deep.findings))
        self.assertLess(len(quick.suggested_questions), len(deep.suggested_questions))
        self.assertFalse(any(item.directive == "AI_Act" for item in quick.findings))
        self.assertTrue(any(item.directive == "AI_Act" for item in deep.findings))
        self.assertEqual(quick.analysis_audit["depth"], "quick")
        self.assertEqual(deep.analysis_audit["depth"], "deep")
        self.assertEqual(quick.hero_summary["depth"], "quick")
        self.assertEqual(deep.hero_summary["depth"], "deep")

    def test_family_stage_product_match_does_not_inject_subtype_specific_fan_standard(self) -> None:
        result = analyze("smart speaker with screen and wifi")

        self.assertEqual(result.product_match_stage, "family")
        self.assertIsNone(result.product_subtype)
        self.assertEqual(result.product_family, "smart_assistant_device")
        standard_codes = {item.code for item in result.standards}
        self.assertIn("EN 62368-1", standard_codes)

    def test_fan_heater_route_prefers_fan_heater_standard_not_fan_standard(self) -> None:
        result = analyze("fan heater with app control and wifi")

        standard_codes = {item.code for item in result.standards}

        self.assertIn("EN 60335-2-30", standard_codes)
        self.assertNotIn("EN 60335-2-80", standard_codes)

    def test_mesh_router_route_keeps_connected_networking_traits(self) -> None:
        result = analyze("mesh router with tri-band Wi-Fi 6 and mobile app")

        self.assertEqual(result.product_subtype, "mesh_wifi_system")
        self.assertIn("CRA", result.directives)
        self.assertIn("cloud", result.all_traits)
        self.assertIn("ota", result.all_traits)

    def test_home_projector_route_keeps_home_projector_traits(self) -> None:
        result = analyze("laser projector with wifi bluetooth and home cinema apps")

        self.assertEqual(result.product_subtype, "home_projector")
        standard_codes = {item.code for item in result.standards}

        self.assertIn("EN 60825-1", standard_codes)
        self.assertIn("EN 62471", standard_codes)
        self.assertIn("RED", result.directives)

    def test_router_routes_to_en_62368_and_not_en_60335(self) -> None:
        result = analyze("wifi router with ethernet ports and external power adapter")

        standard_codes = {item.code for item in result.standards}

        self.assertIn("EN 62368-1", standard_codes)
        self.assertNotIn("EN 60335-1", standard_codes)

    def test_connected_appliance_keeps_en_60335_and_drops_en_62368(self) -> None:
        result = analyze("connected espresso machine with wifi app control cloud account OTA updates and display")

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

    def test_video_doorbell_promotes_en_62368_from_explicit_av_ict_signals(self) -> None:
        result = analyze("video doorbell with wifi and camera")

        standard_codes = {item.code for item in result.standards}
        review_codes = {item.code for item in result.review_items}

        self.assertIn("EN 62368-1", standard_codes)
        self.assertNotIn("EN 62368-1", review_codes)

    def test_cellular_handheld_routes_to_specific_red_emf_standards_not_en_62479(self) -> None:
        result = analyze("Handheld LTE scanner with display, rechargeable battery, and Wi-Fi")

        standard_codes = {item.code for item in result.standards}

        self.assertTrue(any(code.startswith("EN 62209") for code in standard_codes))
        self.assertTrue(any(code in standard_codes for code in {"EN 50566", "EN 50663", "EN 50665", "EN 62311"}))
        self.assertNotIn("EN 62479", standard_codes)

    def test_alias_free_voice_assistant_description_can_retrieve_family(self) -> None:
        result = extract_traits("voice controlled assistant device with speaker microphone and wifi")

        self.assertEqual(result["product_family"], "smart_assistant_device")
        self.assertIn(result["product_match_stage"], {"family", "subtype"})

    def test_service_traits_from_product_match_stay_unconfirmed_without_text(self) -> None:
        result = extract_traits("smart speaker with wifi and bluetooth")

        self.assertIn("cloud", result["all_traits"])
        self.assertNotIn("cloud", result["confirmed_traits"])
        self.assertNotIn("account", result["confirmed_traits"])
        self.assertNotIn("authentication", result["confirmed_traits"])

    def test_analysis_exposes_trait_and_standard_audits(self) -> None:
        result = analyze("smart speaker with wifi and bluetooth")

        self.assertEqual(result.engine_version, "2.0")
        self.assertTrue(result.trait_evidence)
        self.assertIsNotNone(result.product_match_audit)
        self.assertIsNotNone(result.standard_match_audit)
        self.assertTrue(result.standard_match_audit.selected)
        self.assertEqual(result.product_match_audit.engine_version, "2.0")
        self.assertIn("scope:av_ict", result.standard_match_audit.context_tags)

    def test_metadata_endpoints_expose_v2_fields(self) -> None:
        with patch.dict(main._kb_status, {"ok": True, "error": None, "counts": {}}):
            options = main.metadata_options()
            standards = main.metadata_standards()

        product_row = next(row for row in options["products"] if row["id"] == "smart_speaker")
        genre_row = next(row for row in options["genres"] if row["id"] == "smart_home_iot")
        standard_row = next(row for row in standards["standards"] if row["code"] == "EN 62368-1")

        self.assertIn("product_family", product_row)
        self.assertIn("genres", product_row)
        self.assertIn("family_keywords", product_row)
        self.assertIn("core_traits", product_row)
        self.assertIn("default_traits", product_row)
        self.assertIn("id", genre_row)
        self.assertIn("likely_standards", genre_row)
        self.assertIn("selection_group", standard_row)
        self.assertIn("selection_priority", standard_row)
        self.assertIn("required_fact_basis", standard_row)
        self.assertIn("applies_if_genres", standard_row)

    def test_product_schema_validation_requires_family_for_confusable_products(self) -> None:
        trait_ids = {row["id"] for row in load_traits()}
        with self.assertRaisesRegex(Exception, "confusable_with"):
            _validate_products(
                {
                    "products": [
                        {
                            "id": "broken",
                            "label": "Broken",
                            "aliases": ["broken"],
                            "confusable_with": ["other"],
                            "implied_traits": ["electrical"],
                            "functional_classes": [],
                            "likely_standards": [],
                        },
                        {
                            "id": "other",
                            "label": "Other",
                            "aliases": ["other"],
                            "implied_traits": ["electrical"],
                            "functional_classes": [],
                            "likely_standards": [],
                        },
                    ]
                },
                trait_ids,
            )

    def test_standard_schema_validation_rejects_invalid_required_fact_basis(self) -> None:
        with self.assertRaisesRegex(Exception, "required_fact_basis"):
            _validate_standard_metadata("TEST", {"required_fact_basis": "unsupported"})

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
