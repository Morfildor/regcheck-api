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
        self.assertEqual(result.primary_route_standard_code, "EN IEC 61851-1")
        standard_codes = {item.code for item in result.standards}
        review_codes = {item.code for item in result.review_items}

        self.assertIn("EN IEC 61851-1", standard_codes)
        self.assertIn("EN IEC 61851-21-2", standard_codes)
        self.assertIn("EN 62196-2", review_codes)
        self.assertIn("IEC 62752", review_codes)
        self.assertNotIn("EN 62368-1", standard_codes | review_codes)

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
        self.assertEqual(result.primary_route_standard_code, "EN 62841-1")
        md_section = next(section for section in result.standards_by_directive if section.directive_key == "MD")
        self.assertIn("EN 62841-1", {item.code for item in md_section.items})

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
        self.assertEqual(result.primary_route_standard_code, "EN 62841-2-1")
        md_section = next(section for section in result.standards_by_directive if section.directive_key == "MD")
        md_codes = {item.code for item in md_section.items}
        self.assertIn("EN 62841-1", md_codes)
        self.assertIn("EN 62841-2-1", md_codes)
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

    def test_small_smart_products_keep_62368_review_even_with_appliance_adjacent_traits(self) -> None:
        for description in [
            "smart air sensor",
            "smart radiator valve",
            "smart irrigation controller",
            "smart water bottle",
        ]:
            with self.subTest(description=description):
                result = analyze(description)
                review_codes = {item.code for item in result.review_items}
                self.assertIn("EN 62368-1", review_codes)

    def test_small_smart_products_do_not_assume_radio_without_wireless_text(self) -> None:
        for description in [
            "smart air sensor",
            "smart smoke alarm",
        ]:
            with self.subTest(description=description):
                result = analyze(description)
                self.assertNotIn("radio", result.all_traits)
                self.assertNotIn("wifi", result.all_traits)
                self.assertNotIn("RED", result.directives)
                self.assertIn("connectivity.no_radio", result.known_fact_keys)

    def test_smart_insole_prefers_av_ict_routes_after_catalog_merge(self) -> None:
        result = analyze("smart insole with bluetooth app")

        standard_codes = {item.code for item in result.standards}
        all_codes = standard_codes | {item.code for item in result.review_items}

        self.assertEqual(result.product_type, "smart_insole")
        self.assertIn("av_ict_device", result.analysis_audit.product_genres)
        self.assertIn("scope:av_ict", result.route_context.context_tags)
        self.assertIn("EN 62368-1", standard_codes)
        self.assertIn("EN 55032", standard_codes)
        self.assertIn("EN 55035", standard_codes)
        self.assertNotIn("EN 55014-1", all_codes)
        self.assertNotIn("EN 55014-2", all_codes)

    def test_smart_posture_corrector_prefers_av_ict_routes_after_catalog_merge(self) -> None:
        result = analyze("smart posture corrector with bluetooth app")

        standard_codes = {item.code for item in result.standards}
        all_codes = standard_codes | {item.code for item in result.review_items}

        self.assertEqual(result.product_type, "smart_posture_corrector")
        self.assertIn("av_ict_device", result.analysis_audit.product_genres)
        self.assertIn("scope:av_ict", result.route_context.context_tags)
        self.assertIn("EN 62368-1", standard_codes)
        self.assertIn("EN 55032", standard_codes)
        self.assertIn("EN 55035", standard_codes)
        self.assertNotIn("EN 55014-1", all_codes)
        self.assertNotIn("EN 55014-2", all_codes)

    def test_digital_stethoscope_promotes_primary_av_ict_routes_after_catalog_merge(self) -> None:
        result = analyze("digital stethoscope with bluetooth app")

        standard_codes = {item.code for item in result.standards}

        self.assertEqual(result.product_type, "digital_stethoscope")
        self.assertIn("av_ict_device", result.analysis_audit.product_genres)
        self.assertIn("scope:av_ict", result.route_context.context_tags)
        self.assertIn("EN 62368-1", standard_codes)
        self.assertIn("EN 55032", standard_codes)
        self.assertIn("EN 55035", standard_codes)

    def test_smart_glucose_meter_promotes_primary_av_ict_routes_after_catalog_merge(self) -> None:
        result = analyze("smart glucose meter with bluetooth app")

        standard_codes = {item.code for item in result.standards}

        self.assertEqual(result.product_type, "smart_glucose_meter")
        self.assertIn("av_ict_device", result.analysis_audit.product_genres)
        self.assertIn("scope:av_ict", result.route_context.context_tags)
        self.assertIn("EN 62368-1", standard_codes)
        self.assertIn("EN 55032", standard_codes)
        self.assertIn("EN 55035", standard_codes)

    def test_smart_door_lock_prefers_building_hardware_route(self) -> None:
        result = analyze("smart door lock with wifi bluetooth keypad and app control")

        all_codes = {item.code for item in result.standards} | {item.code for item in result.review_items}
        self.assertEqual(result.product_type, "smart_lock")
        self.assertEqual(result.primary_route_standard_code, "EN 14846")
        self.assertNotIn("smart_speaker", {item.id for item in result.product_candidates})
        self.assertIn("EN 14846", all_codes)
        self.assertNotIn("EN 62368-1", all_codes)

    def test_smart_led_bulb_prefers_lighting_route(self) -> None:
        result = analyze("smart LED bulb with wifi app control and voice assistant integration")

        all_codes = {item.code for item in result.standards} | {item.code for item in result.review_items}
        self.assertEqual(result.product_type, "smart_led_bulb")
        self.assertEqual(result.primary_route_standard_code, "EN IEC 62560")
        self.assertNotIn("smart_speaker", {item.id for item in result.product_candidates})
        self.assertNotIn("home_projector", {item.id for item in result.product_candidates})
        self.assertIn("EN IEC 62560", all_codes)
        self.assertNotIn("EN 62368-1", all_codes)

    def test_smart_refrigerator_prefers_refrigerator_route(self) -> None:
        result = analyze("smart refrigerator with touchscreen display and internal camera")

        self.assertEqual(result.product_type, "refrigerator_freezer")
        self.assertEqual(result.primary_route_standard_code, "EN 60335-2-24")
        self.assertIn("EN 60335-2-24", {item.code for item in result.standards})

    def test_poe_injector_beats_downstream_camera_context(self) -> None:
        result = analyze("poe injector for ip camera installation")

        self.assertEqual(result.product_type, "poe_injector")
        self.assertEqual(result.product_match_stage, "subtype")
        self.assertEqual(result.primary_route_standard_code, "EN 62368-1")
        self.assertNotIn("RED", result.directives)

    def test_water_dispenser_stays_family_level_pending_boundary_review(self) -> None:
        result = analyze("water dispenser with chilled water")

        self.assertEqual(result.product_type, "water_dispenser")
        self.assertEqual(result.product_match_stage, "family")
        self.assertEqual(result.route_context.route_confidence, "medium")
        self.assertIn("Water dispenser / cooler review", {item.code for item in result.review_items})

    def test_uv_nail_lamp_prefers_boundary_review_over_false_precision(self) -> None:
        result = analyze("uv nail lamp for gel polish")

        review_codes = {item.code for item in result.review_items}
        risk_keys = {item.key for item in result.risk_reasons}

        self.assertEqual(result.product_type, "uv_nail_lamp")
        self.assertEqual(result.product_match_stage, "family")
        self.assertEqual(result.route_context.route_confidence, "low")
        self.assertIn("UV / irradiation application review", review_codes)
        self.assertIn("Biocompatibility / skin-contact review", review_codes)
        self.assertIn("Confirm whether the optical output is ordinary illumination only or is intended for UV/IR exposure, sanitizing, disinfection, or treatment.", result.suggested_questions)
        self.assertIn(
            "Confirm whether the product remains in cosmetic or wellness scope, or whether it is marketed for therapy, treatment, stimulation, or other medical-adjacent outcomes.",
            result.suggested_questions,
        )
        self.assertIn("uv_irradiation_boundary", risk_keys)
        self.assertIn("body_treatment_boundary", risk_keys)

    def test_ups_requests_energy_system_review_questions(self) -> None:
        result = analyze("ups battery backup unit for office server")

        review_codes = {item.code for item in result.review_items}
        risk_keys = {item.key for item in result.risk_reasons}

        self.assertEqual(result.product_type, "ups")
        self.assertEqual(result.product_match_stage, "family")
        self.assertEqual(result.route_context.route_confidence, "medium")
        self.assertIn("Energy storage / inverter system review", review_codes)
        self.assertIn(
            "Confirm whether the product is a standalone consumer device or part of a wider inverter, storage, metering, or fixed-installation energy system.",
            result.suggested_questions,
        )
        self.assertIn("energy_system_boundary", risk_keys)

    def test_solar_charge_controller_stays_boundary_reviewed(self) -> None:
        result = analyze("solar charge controller for off-grid battery bank")

        risk_keys = {item.key for item in result.risk_reasons}

        self.assertEqual(result.product_type, "solar_charge_controller")
        self.assertEqual(result.product_match_stage, "family")
        self.assertEqual(result.route_context.route_confidence, "low")
        self.assertIn("Charger / external PSU review", {item.code for item in result.review_items})
        self.assertIn(
            "Confirm whether the product is sold as a consumer end product or as a fixed-installation, panel, cabinet, or professional building-system component.",
            result.suggested_questions,
        )
        self.assertIn("energy_system_boundary", risk_keys)
        self.assertIn("industrial_installation_boundary", risk_keys)

    def test_bottle_sterilizer_no_longer_falls_into_toy_routes(self) -> None:
        result = analyze("bottle sterilizer for baby feeding accessories")

        self.assertEqual(result.product_type, "bottle_sterilizer")
        self.assertNotIn("TOY", result.directives)
        self.assertIn("Sterilization / hygiene appliance review", {item.code for item in result.review_items})

    def test_air_purifier_prefers_air_cleaning_route(self) -> None:
        result = analyze("connected air purifier with app control and HEPA filter")

        self.assertEqual(result.product_type, "air_purifier")
        self.assertEqual(result.primary_route_standard_code, "EN 60335-2-65")
        self.assertIn("EN 60335-2-65", {item.code for item in result.standards})

    def test_robot_vacuum_prefers_vacuum_route(self) -> None:
        result = analyze("robot vacuum with docking station and wifi")

        all_codes = {item.code for item in result.standards} | {item.code for item in result.review_items}
        self.assertEqual(result.product_type, "robot_vacuum")
        self.assertEqual(result.primary_route_standard_code, "EN 60335-2-2")
        self.assertIn("EN 60335-2-2", all_codes)
        self.assertNotIn("EN 62368-1", all_codes)

    def test_smartwatch_keeps_wearable_avict_primary_route(self) -> None:
        result = analyze("smart watch with bluetooth and app")

        self.assertEqual(result.product_type, "smartwatch")
        self.assertEqual(result.primary_route_standard_code, "EN 62368-1")
        self.assertIn("EN 62368-1", {item.code for item in result.standards})

    def test_cordless_drill_without_radio_stays_on_machinery_route(self) -> None:
        result = analyze("cordless drill with rechargeable battery and no wireless communication")

        self.assertEqual(result.product_type, "cordless_power_drill")
        self.assertEqual(result.primary_route_standard_code, "EN 62841-2-1")
        self.assertNotIn("RED", result.directives)
        self.assertNotIn("radio", result.all_traits)
        self.assertIn("EN 62841-2-1", {item.code for item in result.standards})

    def test_smart_smoke_and_co_alarm_prefers_alarm_route(self) -> None:
        result = analyze("smart smoke and carbon monoxide alarm with wifi app control")

        standard_codes = {item.code for item in result.standards}
        self.assertEqual(result.product_type, "smart_smoke_co_alarm")
        self.assertEqual(result.primary_route_standard_code, "EN 14604")
        self.assertIn("EN 14604", standard_codes)
        self.assertIn("EN 50291-1", standard_codes)
        self.assertNotIn("EN 62368-1", standard_codes | {item.code for item in result.review_items})

    def test_smart_thermostat_prefers_control_route(self) -> None:
        result = analyze("smart thermostat with voice assistant integration and local control only")

        all_codes = {item.code for item in result.standards} | {item.code for item in result.review_items}
        self.assertEqual(result.product_type, "smart_thermostat")
        self.assertEqual(result.primary_route_standard_code, "EN 60730-2-9")
        self.assertIn("EN 60730-2-9", all_codes)
        self.assertNotIn("EN 62368-1", all_codes)

    def test_toy_like_child_play_product_uses_toy_route(self) -> None:
        result = analyze("interactive toy robot for children under 14 with bluetooth")

        self.assertEqual(result.product_type, "smart_toy")
        self.assertEqual(result.primary_route_standard_code, "EN 62115")
        self.assertIn("TOY", result.directives)
        self.assertIn("EN 62115", {item.code for item in result.review_items})

    def test_child_related_non_play_safety_product_does_not_use_toy_route(self) -> None:
        result = analyze("baby monitor with wifi camera and app control")

        self.assertEqual(result.product_type, "baby_monitor")
        self.assertNotIn("TOY", result.directives)

    def test_explicit_negations_change_routing_signals(self) -> None:
        smart_lock = analyze("smart door lock with no cloud and local control only")
        smart_bulb = analyze("smart LED bulb, not a speaker, with no projection functions")
        child_safety = analyze("child safety wearable with bluetooth, not intended for play")

        self.assertEqual(smart_lock.product_type, "smart_lock")
        self.assertNotIn("cloud", smart_lock.all_traits)
        self.assertEqual(smart_bulb.product_type, "smart_led_bulb")
        self.assertNotIn("EN 62368-1", {item.code for item in smart_bulb.standards} | {item.code for item in smart_bulb.review_items})
        self.assertNotIn("TOY", child_safety.directives)


if __name__ == "__main__":
    unittest.main()
