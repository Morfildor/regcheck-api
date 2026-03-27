import unittest

from knowledge_base import reset_cache
from rules import analyze


class MatchingRegressionTests(unittest.TestCase):
    def setUp(self) -> None:
        reset_cache()

    def test_battery_oral_hygiene_surfaces_household_safety_reviews_without_lvd(self) -> None:
        result = analyze("battery-powered oral hygiene appliance")

        self.assertNotIn("LVD", result.directives)
        review_codes = {item.code for item in result.review_items}
        self.assertIn("EN 60335-1", review_codes)
        self.assertIn("EN 60335-2-52", review_codes)

    def test_electric_tooth_brush_normalizes_to_oral_hygiene_route(self) -> None:
        result = analyze("electric tooth brush")

        self.assertEqual(result.product_type, "oral_hygiene_appliance")
        review_codes = {item.code for item in result.review_items}
        self.assertIn("EN 60335-1", review_codes)
        self.assertIn("EN 60335-2-52", review_codes)

    def test_smart_toothbrush_stays_on_oral_hygiene_route(self) -> None:
        result = analyze("smart toothbrush with bluetooth and app control")

        self.assertIn(result.product_type, {"battery_powered_oral_hygiene", "oral_hygiene_appliance"})
        self.assertNotEqual(result.product_type, "home_projector")
        codes = {item.code for item in result.standards + result.review_items}
        self.assertIn("EN 60335-2-52", codes)
        self.assertNotIn("EN 62368-1", codes)

    def test_dental_flosser_prefers_oral_hygiene_over_battery_charger(self) -> None:
        result = analyze("electric dental flosser with rechargeable battery, charging dock, bathroom use, app connectivity, bluetooth radio")

        self.assertIn(result.product_type, {"battery_powered_oral_hygiene", "oral_hygiene_appliance"})
        self.assertNotEqual(result.product_type, "battery_charger")
        codes = {item.code for item in result.standards} | {item.code for item in result.review_items}
        self.assertIn("EN 60335-2-52", codes)

    def test_robot_lawn_mower_aliases_share_the_same_safety_route(self) -> None:
        robot = analyze("robot lawn mower")
        robotic = analyze("robotic lawn mower")

        self.assertEqual(robot.product_type, "robotic_lawn_mower")
        self.assertEqual(robotic.product_type, "robotic_lawn_mower")
        self.assertIn("EN 50636-2-107", {item.code for item in robot.standards})
        self.assertIn("EN 50636-2-107", {item.code for item in robotic.standards})
        self.assertIn("EN 60335-2-107", {item.code for item in robot.review_items})

    def test_battery_av_ict_product_keeps_62368_as_review_when_lvd_is_absent(self) -> None:
        result = analyze("Digital audio player / DAC")

        self.assertNotIn("LVD", result.directives)
        self.assertIn("EN 62368-1", {item.code for item in result.review_items})

    def test_smart_watch_prefers_av_ict_routes_over_appliance_emc(self) -> None:
        result = analyze("smart watch")

        standard_codes = {item.code for item in result.standards}
        review_codes = {item.code for item in result.review_items}
        all_codes = standard_codes | review_codes

        self.assertIn("EN 55032", standard_codes)
        self.assertIn("EN 55035", standard_codes)
        self.assertIn("EN 62368-1", standard_codes)
        self.assertNotIn("EN 55014-1", all_codes)
        self.assertNotIn("EN 55014-2", all_codes)

    def test_fitness_tracker_prefers_av_ict_routes_over_appliance_emc(self) -> None:
        result = analyze("fitness tracker")

        standard_codes = {item.code for item in result.standards}
        review_codes = {item.code for item in result.review_items}
        all_codes = standard_codes | review_codes

        self.assertIn("EN 55032", standard_codes)
        self.assertIn("EN 55035", standard_codes)
        self.assertIn("EN 62368-1", standard_codes)
        self.assertNotIn("EN 55014-1", all_codes)
        self.assertNotIn("EN 55014-2", all_codes)

    def test_smart_ring_prefers_av_ict_routes_over_appliance_emc(self) -> None:
        result = analyze("smart ring")

        standard_codes = {item.code for item in result.standards}
        review_codes = {item.code for item in result.review_items}
        all_codes = standard_codes | review_codes

        self.assertIn("EN 55032", standard_codes)
        self.assertIn("EN 55035", standard_codes)
        self.assertIn("EN 62368-1", standard_codes)
        self.assertNotIn("EN 55014-1", all_codes)
        self.assertNotIn("EN 55014-2", all_codes)

    def test_hair_dryer_no_longer_selects_conflicting_part2_routes(self) -> None:
        result = analyze("hair dryer")

        codes = {item.code for item in result.standards} | {item.code for item in result.review_items}
        self.assertIn("EN 60335-1", {item.code for item in result.standards})
        self.assertIn("EN 60335-2-23", {item.code for item in result.standards})
        self.assertNotIn("EN 60335-2-45", codes)

    def test_curling_iron_reaches_the_hair_care_part2_route(self) -> None:
        result = analyze("curling iron")

        self.assertIn("EN 60335-1", {item.code for item in result.standards})
        self.assertIn("EN 60335-2-23", {item.code for item in result.standards})

    def test_family_level_projector_keeps_62368_route(self) -> None:
        result = analyze("portable projector")

        standard_codes = {item.code for item in result.standards}
        self.assertIn("EN 62368-1", standard_codes)
        self.assertIn("EN 55032", standard_codes)
        self.assertIn("EN 55035", standard_codes)

    def test_plain_home_cinema_projector_does_not_surface_radio_or_cyber_routes_without_connectivity_text(self) -> None:
        result = analyze("video projector for home cinema")

        all_codes = {item.code for item in result.standards} | {item.code for item in result.review_items}

        self.assertNotIn("RED", result.directives)
        self.assertNotIn("RED_CYBER", result.directives)
        self.assertNotIn("CRA", result.directives)
        self.assertNotIn("EN 300 328", all_codes)
        self.assertNotIn("EN 301 489-1", all_codes)
        self.assertNotIn("EN 301 489-17", all_codes)
        self.assertNotIn("EN 301 893", all_codes)
        self.assertNotIn("EN 18031-1", all_codes)
        self.assertNotIn("CRA review", all_codes)
        self.assertNotIn("cyber:connected_radio", result.route_context.context_tags)

    def test_ambiguous_security_camera_still_surfaces_62368_review(self) -> None:
        result = analyze("security camera")

        codes = {item.code for item in result.standards} | {item.code for item in result.review_items}
        self.assertIn("EN 62368-1", codes)

    def test_video_doorbell_family_match_prefers_av_ict_route(self) -> None:
        result = analyze("video doorbell")

        standard_codes = {item.code for item in result.standards}
        all_codes = standard_codes | {item.code for item in result.review_items}

        self.assertEqual(result.product_match_stage, "family")
        self.assertIn("EN 62368-1", standard_codes)
        self.assertIn("EN 55032", standard_codes)
        self.assertIn("EN 55035", standard_codes)
        self.assertNotIn("EN 55014-1", all_codes)
        self.assertNotIn("EN 55014-2", all_codes)

    def test_smart_doorbell_prefers_av_ict_routes_over_appliance_emc(self) -> None:
        result = analyze("smart doorbell")

        standard_codes = {item.code for item in result.standards}
        all_codes = standard_codes | {item.code for item in result.review_items}

        self.assertIn("EN 62368-1", standard_codes)
        self.assertIn("EN 55032", standard_codes)
        self.assertIn("EN 55035", standard_codes)
        self.assertNotIn("EN 55014-1", all_codes)
        self.assertNotIn("EN 55014-2", all_codes)

    def test_portable_ev_charger_alias_surfaces_mode_2_review_routes(self) -> None:
        result = analyze("portable EV charger with mode 2 cable and in-cable protection device")

        self.assertEqual(result.product_type, "portable_ev_charger")
        review_codes = {item.code for item in result.review_items}

        self.assertIn("IEC 61851-1", review_codes)
        self.assertIn("IEC 61851-21-2", review_codes)
        self.assertIn("IEC 62196-2", review_codes)
        self.assertIn("IEC 62752", review_codes)

    def test_granny_charger_alias_beats_generic_battery_charger(self) -> None:
        result = analyze("granny charger for electric car")

        self.assertEqual(result.product_type, "portable_ev_charger")
        self.assertIn("IEC 62752", {item.code for item in result.review_items})

    def test_micromobility_products_surface_traction_battery_review_route(self) -> None:
        result = analyze("electric scooter with bluetooth app")

        self.assertEqual(result.product_type, "electric_scooter")
        self.assertIn("EN 50604-1", {item.code for item in result.review_items})

    def test_industrial_power_tool_prefers_tool_taxonomy_over_unrelated_appliances(self) -> None:
        result = analyze("industrial power tool")

        self.assertEqual(result.product_type, "industrial_power_tool")
        self.assertEqual(result.product_family, "industrial_power_equipment")
        self.assertFalse(result.classification_is_ambiguous)
        self.assertFalse(result.classification_confidence_below_threshold)
        self.assertNotIn("electric_fish_stunner", {item.id for item in result.product_candidates})
        self.assertNotIn("bain_marie", {item.id for item in result.product_candidates})
        md_section = next(section for section in result.standards_by_directive if section.directive_key == "MD")
        self.assertIn("Power tool safety review", {item.code for item in md_section.items})

    def test_generic_industrial_tool_falls_back_to_ambiguous_match(self) -> None:
        result = analyze("generic industrial tool")

        self.assertIsNone(result.product_type)
        self.assertTrue(result.classification_is_ambiguous)
        self.assertTrue(result.classification_confidence_below_threshold)
        self.assertEqual(result.product_candidates, [])
        self.assertIn("Confirm whether the product is mains-powered, battery-powered, or both.", result.suggested_questions)

    def test_professional_electric_drill_routes_to_industrial_power_drill(self) -> None:
        result = analyze("professional electric drill")

        self.assertEqual(result.product_type, "corded_power_drill")
        self.assertFalse(result.classification_is_ambiguous)
        md_section = next(section for section in result.standards_by_directive if section.directive_key == "MD")
        md_codes = {item.code for item in md_section.items}
        self.assertIn("Power tool safety review", md_codes)
        self.assertTrue(any(item.triggered_by_directive == "MD" for item in md_section.items))

    def test_cordless_screwdriver_prefers_power_tool_route_over_oral_hygiene(self) -> None:
        result = analyze("cordless screwdriver")

        self.assertEqual(result.product_type, "cordless_screwdriver")
        self.assertEqual(result.product_family, "industrial_power_equipment")
        self.assertFalse(result.classification_is_ambiguous)
        self.assertNotIn("battery_powered_oral_hygiene", {item.id for item in result.product_candidates})
        self.assertIn("Power tool safety review", {item.code for item in result.review_items})

    def test_angle_grinder_surfaces_power_tool_review_route(self) -> None:
        result = analyze("angle grinder")

        self.assertEqual(result.product_type, "angle_grinder")
        self.assertFalse(result.classification_is_ambiguous)
        self.assertIn("Power tool safety review", {item.code for item in result.review_items})

    def test_rotary_hammer_drill_resolves_to_rotary_hammer_route(self) -> None:
        result = analyze("rotary hammer drill")

        self.assertEqual(result.product_type, "rotary_hammer")
        self.assertFalse(result.classification_is_ambiguous)
        self.assertIn("Power tool safety review", {item.code for item in result.review_items})

    def test_industrial_air_compressor_generates_pressure_specific_follow_ups(self) -> None:
        result = analyze("industrial air compressor")

        self.assertEqual(result.product_type, "industrial_air_compressor")
        self.assertIn("Confirm the compressor maximum working pressure and receiver volume.", result.suggested_questions)
        self.assertIn(
            "Confirm whether the compressor is oil-free or lubricated, and whether it is continuous-duty or intermittent-duty.",
            result.suggested_questions,
        )
        self.assertIn("high_energy", {item.key for item in result.risk_reasons})

    def test_connected_products_return_storage_and_update_questions(self) -> None:
        result = analyze("smart security camera with wifi and app control")

        self.assertIn(
            "Confirm whether the product stores user, event, diagnostic, or media data locally, in the cloud, or not at all.",
            result.suggested_questions,
        )
        self.assertIn(
            "Confirm whether firmware or software updates are supported, and whether they are OTA, app-driven, local-only, or unavailable.",
            result.suggested_questions,
        )


if __name__ == "__main__":
    unittest.main()
