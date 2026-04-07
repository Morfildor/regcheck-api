from __future__ import annotations

from contextlib import redirect_stdout
import io
import json
import unittest

from knowledge_base import get_knowledge_base_snapshot, reset_cache
from rules import analyze
from scripts import catalog_audit
from app.services.rules.route_anchors import family_from_standard_code, normalized_standard_codes
from standards_engine import find_applicable_items


class CatalogNormalizationSnapshotTests(unittest.TestCase):
    def setUp(self) -> None:
        reset_cache()

    def _products_by_id(self) -> dict[str, dict[str, object]]:
        return {row["id"]: row.as_legacy_dict() for row in get_knowledge_base_snapshot().products}

    def test_normalized_snapshot_eliminates_unknown_and_unanchored_buckets(self) -> None:
        products = [row.as_legacy_dict() for row in get_knowledge_base_snapshot().products]

        self.assertFalse(
            [
                row["id"]
                for row in products
                if str(row.get("product_family") or "").strip() in {"", "unknown"}
            ]
        )
        self.assertFalse(
            [
                row["id"]
                for row in products
                if str(row.get("product_subfamily") or "").strip() in {"", "unknown"}
            ]
        )
        self.assertFalse(
            [
                row["id"]
                for row in products
                if str(row.get("route_family") or "").strip() in {"", "unanchored"}
            ]
        )
        self.assertFalse([row["id"] for row in products if not str(row.get("route_anchor") or "").strip()])
        self.assertFalse([row["id"] for row in products if not row.get("genres")])

    def test_representative_products_have_governed_structure(self) -> None:
        products = self._products_by_id()
        cases = {
            "air_fryer": {
                "product_family": "countertop_cooking_appliance",
                "product_subfamily": "air_fryer",
                "route_anchor": "household_core",
                "route_family": "household_appliance",
            },
            "bluetooth_speaker": {
                "product_family": "home_entertainment_device",
                "product_subfamily": "bluetooth_speaker",
                "route_anchor": "avict_connected",
                "route_family": "av_ict",
            },
            "smart_pet_feeder": {
                "product_family": "pet_technology",
                "product_subfamily": "smart_pet_feeder",
                "route_anchor": "household_connected",
                "route_family": "household_appliance",
            },
            "smart_led_bulb": {
                "product_family": "smart_lighting",
                "product_subfamily": "smart_led_bulb",
                "route_anchor": "lighting_connected",
                "route_family": "lighting_device",
            },
            "wireless_charger": {
                "product_family": "portable_power_charger",
                "product_subfamily": "wireless_charger",
                "route_anchor": "avict_core",
                "route_family": "av_ict",
            },
            "ev_charger_home": {
                "product_family": "ev_charging_equipment",
                "product_subfamily": "ev_charger_home",
                "route_anchor": "ev_charging",
                "route_family": "ev_charging",
            },
            "ev_connector_accessory": {
                "product_family": "ev_charging_equipment",
                "product_subfamily": "ev_connector_accessory",
                "route_anchor": "ev_connector_accessory",
                "route_family": "ev_connector_accessory",
            },
            "smart_smoke_co_alarm": {
                "product_family": "life_safety_alarm",
                "product_subfamily": "smart_smoke_co_alarm",
                "route_anchor": "life_safety_alarm",
                "route_family": "life_safety_alarm",
            },
            "smart_lock": {
                "product_family": "building_hardware_lock",
                "product_subfamily": "smart_lock",
                "route_anchor": "building_access",
                "route_family": "building_hardware",
            },
            "smart_meter_gateway": {
                "product_family": "energy_power_system",
                "product_subfamily": "smart_meter_gateway",
                "route_anchor": "power_system_boundary",
                "route_family": "power_system_boundary",
            },
            "solar_charge_controller": {
                "product_family": "energy_power_system",
                "product_subfamily": "solar_charge_controller",
                "route_anchor": "power_system_boundary",
                "route_family": "power_system_boundary",
            },
            "fence_energizer": {
                "product_family": "specialty_electrical_device",
                "product_subfamily": "fence_energizer",
                "route_anchor": "specialty_electrical_boundary",
                "route_family": "specialty_electrical_boundary",
            },
        }

        for product_id, expected in cases.items():
            with self.subTest(product_id=product_id):
                row = products[product_id]
                self.assertTrue(row["genres"])
                for key, value in expected.items():
                    self.assertEqual(row.get(key), value)

    def test_boundary_products_keep_explicit_family_level_discipline(self) -> None:
        products = self._products_by_id()
        boundary_ids = {
            "ems_tens_device": "medical_wellness_boundary",
            "uv_nail_lamp": "lighting_core",
            "bench_saw": "machinery_tool",
            "smart_meter_gateway": "power_system_boundary",
            "solar_charge_controller": "power_system_boundary",
            "solar_inverter_gateway": "power_system_boundary",
            "fence_energizer": "specialty_electrical_boundary",
            "water_dispenser": "household_core",
        }

        for product_id, anchor in boundary_ids.items():
            with self.subTest(product_id=product_id):
                row = products[product_id]
                self.assertEqual(row.get("route_anchor"), anchor)
                self.assertEqual(row.get("max_match_stage"), "family")
                self.assertIn(row.get("route_confidence_cap"), {"low", "medium"})
                self.assertTrue(str(row.get("family_level_reason") or "").strip())
                self.assertTrue(row.get("boundary_tags"))


class RouteNormalizationRegressionTests(unittest.TestCase):
    def setUp(self) -> None:
        reset_cache()

    def test_household_appliance_routes_to_household_anchor(self) -> None:
        result = analyze("air fryer")

        self.assertEqual(result.product_type, "air_fryer")
        self.assertEqual(result.product_family, "countertop_cooking_appliance")
        self.assertEqual(result.product_subtype, "air_fryer")
        self.assertEqual(result.product_match_stage, "subtype")
        self.assertEqual(result.route_context.primary_route_family, "household_appliance")
        self.assertEqual(result.primary_route_standard_code, "EN 60335-2-13")

    def test_avict_device_routes_to_avict_anchor(self) -> None:
        result = analyze("bluetooth speaker")

        self.assertEqual(result.product_type, "bluetooth_speaker")
        self.assertEqual(result.product_family, "home_entertainment_device")
        self.assertEqual(result.route_context.primary_route_family, "av_ict")
        self.assertEqual(result.primary_route_standard_code, "EN 62368-1")
        self.assertIn("RED", result.directives)
        self.assertNotIn("LVD", result.directives)
        self.assertNotIn("EMC", result.directives)

    def test_connected_household_appliance_keeps_household_route_with_red_overlay(self) -> None:
        result = analyze("smart pet feeder with wifi and mobile app")

        self.assertEqual(result.product_type, "smart_pet_feeder")
        self.assertEqual(result.product_family, "pet_technology")
        self.assertEqual(result.route_context.primary_route_family, "household_appliance")
        self.assertEqual(result.primary_route_standard_code, "EN 60335-1")
        self.assertIn("RED", result.directives)
        self.assertIn("RED_CYBER", result.directives)
        self.assertIn("CRA", result.directives)

    def test_lighting_product_routes_to_lighting_anchor(self) -> None:
        result = analyze("smart LED bulb with wifi app control")

        self.assertEqual(result.product_type, "smart_led_bulb")
        self.assertEqual(result.product_family, "smart_lighting")
        self.assertEqual(result.route_context.primary_route_family, "lighting_device")
        self.assertEqual(result.primary_route_standard_code, "EN IEC 62560")
        self.assertIn("RED", result.directives)

    def test_charger_distinctions_share_charger_family_without_falling_into_ev_routing(self) -> None:
        cases = {
            "external power supply": "external_power_supply",
            "usb charger": "usb_wall_charger",
            "wireless charger": "wireless_charger",
        }

        for description, product_type in cases.items():
            with self.subTest(description=description):
                result = analyze(description)
                self.assertEqual(result.product_type, product_type)
                self.assertEqual(result.product_family, "portable_power_charger")
                self.assertEqual(result.route_context.primary_route_family, "av_ict")
                self.assertEqual(result.primary_route_standard_code, "EN 62368-1")
                self.assertIn("Charger / external PSU review", {item.code for item in result.review_items})

    def test_ev_charging_distinctions_split_equipment_from_connector_accessories(self) -> None:
        cases = (
            (
                "smart ev charger wallbox with wifi app",
                "ev_charger_home",
                "ev_charging",
                "EN IEC 61851-1",
            ),
            (
                "portable ev charger",
                "portable_ev_charger",
                "ev_charging",
                "EN IEC 61851-1",
            ),
            (
                "ev charging connector cable accessory type 2",
                "ev_connector_accessory",
                "ev_connector_accessory",
                "EN 62196-2",
            ),
        )

        for description, product_type, route_family, standard_code in cases:
            with self.subTest(description=description):
                result = analyze(description)
                self.assertEqual(result.product_type, product_type)
                self.assertEqual(result.product_family, "ev_charging_equipment")
                self.assertEqual(result.route_context.primary_route_family, route_family)
                self.assertEqual(result.primary_route_standard_code, standard_code)

    def test_ev_standard_code_variants_normalize_for_routing_and_selection(self) -> None:
        self.assertEqual(
            normalized_standard_codes(["EN 61851-1", "EN IEC 61851-21-2", "EN IEC 62196-2"]),
            ["EN IEC 61851-1", "EN IEC 61851-21-2", "EN 62196-2"],
        )
        self.assertEqual(family_from_standard_code("EN 61851-1", prefer_wearable=False), "ev_charging")
        self.assertEqual(family_from_standard_code("EN IEC 62196-2", prefer_wearable=False), "ev_connector_accessory")

        items = find_applicable_items(
            traits={"electrical", "electronic", "ev_charging", "vehicle_supply"},
            directives=["LVD", "EMC", "OTHER"],
            product_type="portable_ev_charger",
            matched_products=["portable_ev_charger"],
            product_genres=["ev_charging_equipment"],
            preferred_standard_codes=["EN 61851-1", "EN 61851-21-2", "EN IEC 62196-2"],
            explicit_traits={"electrical", "electronic", "ev_charging", "vehicle_supply"},
            confirmed_traits={"electrical", "electronic", "ev_charging", "vehicle_supply"},
            normalized_text="portable ev charger mode 2 type 2 connector",
        )
        selected_codes = {row["code"] for row in items["standards"]} | {row["code"] for row in items["review_items"]}
        self.assertIn("EN IEC 61851-1", selected_codes)
        self.assertIn("EN IEC 61851-21-2", selected_codes)
        self.assertIn("EN 62196-2", selected_codes)

    def test_alarm_and_building_access_routes_are_governed(self) -> None:
        alarm = analyze("smart smoke and carbon monoxide alarm with wifi")
        self.assertEqual(alarm.product_type, "smart_smoke_co_alarm")
        self.assertEqual(alarm.product_family, "life_safety_alarm")
        self.assertEqual(alarm.route_context.primary_route_family, "life_safety_alarm")
        self.assertEqual(alarm.primary_route_standard_code, "EN 14604")

        smart_lock = analyze("smart lock with bluetooth keypad")
        self.assertEqual(smart_lock.product_type, "smart_lock")
        self.assertEqual(smart_lock.product_family, "building_hardware_lock")
        self.assertEqual(smart_lock.route_context.primary_route_family, "building_hardware")
        self.assertEqual(smart_lock.primary_route_standard_code, "EN 14846")

    def test_wellness_and_uv_boundary_products_stay_family_level_only(self) -> None:
        ems = analyze("ems tens wellness device")
        self.assertEqual(ems.product_type, "ems_tens_device")
        self.assertEqual(ems.product_family, "wellness_electrostimulation")
        self.assertIsNone(ems.product_subtype)
        self.assertEqual(ems.product_match_stage, "family")
        self.assertEqual(ems.route_context.primary_route_family, "medical_wellness_boundary")
        self.assertIsNone(ems.primary_route_standard_code)
        self.assertEqual(ems.route_context.route_confidence, "low")
        self.assertIn("MDR borderline review", {item.code for item in ems.review_items})

        uv = analyze("uv nail lamp for gel polish")
        self.assertEqual(uv.product_type, "uv_nail_lamp")
        self.assertEqual(uv.product_family, "optical_beauty_device")
        self.assertIsNone(uv.product_subtype)
        self.assertEqual(uv.product_match_stage, "family")
        self.assertEqual(uv.route_context.primary_route_family, "lighting_device")
        self.assertIsNone(uv.primary_route_standard_code)
        self.assertEqual(uv.route_context.route_confidence, "low")
        self.assertIn("EN 62471", {item.code for item in uv.review_items})

    def test_machinery_and_energy_boundary_products_keep_conservative_routes(self) -> None:
        bench_saw = analyze("bench saw")
        self.assertEqual(bench_saw.product_type, "bench_saw")
        self.assertEqual(bench_saw.product_family, "industrial_power_equipment")
        self.assertIsNone(bench_saw.product_subtype)
        self.assertEqual(bench_saw.product_match_stage, "family")
        self.assertEqual(bench_saw.route_context.primary_route_family, "machinery_power_tool")
        self.assertEqual(bench_saw.primary_route_standard_code, "Power tool safety review")
        self.assertEqual(bench_saw.route_context.route_confidence, "low")

        solar = analyze("solar charge controller for off-grid battery bank")
        self.assertEqual(solar.product_type, "solar_charge_controller")
        self.assertEqual(solar.product_family, "energy_power_system")
        self.assertIsNone(solar.product_subtype)
        self.assertEqual(solar.product_match_stage, "family")
        self.assertEqual(solar.route_context.primary_route_family, "power_system_boundary")
        self.assertIsNone(solar.primary_route_standard_code)
        self.assertEqual(solar.route_context.route_confidence, "low")
        self.assertIn("Charger / external PSU review", {item.code for item in solar.review_items})

    def test_family_level_only_household_products_do_not_overcommit_subtype(self) -> None:
        result = analyze("water dispenser with chilled water")

        self.assertEqual(result.product_type, "water_dispenser")
        self.assertEqual(result.product_family, "water_dispensing_appliance")
        self.assertIsNone(result.product_subtype)
        self.assertEqual(result.product_match_stage, "family")
        self.assertEqual(result.route_context.primary_route_family, "household_appliance")
        self.assertEqual(result.primary_route_standard_code, "EN 60335-1")
        self.assertEqual(result.route_context.route_confidence, "medium")


class CatalogAuditReportingTests(unittest.TestCase):
    def test_catalog_audit_strict_structure_passes(self) -> None:
        exit_code = catalog_audit.run(
            "report",
            minimum_aliases=4,
            broad_alias_threshold=3,
            strict_structure=True,
        )
        self.assertEqual(exit_code, 0)

    def test_catalog_audit_summary_json_exposes_normalized_metrics(self) -> None:
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            exit_code = catalog_audit.run(
                "summary",
                minimum_aliases=4,
                broad_alias_threshold=3,
                json_output=True,
            )

        self.assertEqual(exit_code, 0)
        payload = json.loads(buffer.getvalue())
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["command"], "summary")
        self.assertEqual(payload["structure"]["normalized"]["unknown_family"], 0)
        self.assertEqual(payload["structure"]["normalized"]["unanchored_route"], 0)
        self.assertEqual(payload["structure"]["normalized"]["missing_structure_products"], 0)
        self.assertIn("raw_unknown_family", payload["by_file"])
        self.assertIn("raw_unanchored_route", payload["by_file"])


if __name__ == "__main__":
    unittest.main()
