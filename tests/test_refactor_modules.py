from __future__ import annotations

import unittest

from app.domain.catalog_types import (
    GenreCatalogRow,
    LegislationCatalogRow,
    ProductCatalogRow,
    StandardCatalogRow,
    TraitCatalogRow,
)
from app.domain.models import (
    KnownFactItem,
    KnowledgeBaseMeta,
    LegislationItem,
    LegislationSection,
    MetadataOptionsResponse,
    MetadataStandardsResponse,
    ProductMatchAudit,
    RiskSummary,
    RouteContext,
    StandardItem,
    StandardMatchAudit,
)
from app.services.classifier import extract_traits, normalize
from app.services.knowledge_base.metadata import _build_metadata_options_payload, _build_metadata_standards_payload
from app.services.rules.facts import _build_known_facts, _missing_information
from app.services.rules.result_builder import (
    _build_analysis_result,
    _build_standard_sections,
    _standard_item_from_row,
)
from app.services.rules.risk import _current_risk, _future_risk
from app.services.rules.routing import (
    RoutePlan,
    _apply_post_selection_gates_v1,
    _build_route_plan,
    _route_product_row,
    _route_selection_traits,
)
from app.services.standards_engine.gating import _trait_gate_details
from app.services.standards_engine.scoring import _score_standard_v2
from app.services.standards_engine.service import find_applicable_items


class RefactorModuleTests(unittest.TestCase):
    def test_route_selection_traits_suppresses_unbacked_sensitive_traits(self) -> None:
        route_traits, suppressed = _route_selection_traits(
            traits={"radio", "wifi", "cloud"},
            confirmed_traits=set(),
            state_map={
                "text_explicit": {},
                "text_inferred": {},
                "product_core": {},
                "product_default": {},
                "engine_derived": {},
            },
            product_genres=set(),
        )

        self.assertEqual(route_traits, set())
        self.assertEqual(suppressed, ["cloud", "radio", "wifi"])

    def test_build_route_plan_uses_typed_product_rows(self) -> None:
        row = _route_product_row("smart_lock", {"smart_lock"})

        self.assertIsInstance(row, ProductCatalogRow)
        self.assertEqual(row.id, "smart_lock")

        route_plan = _build_route_plan(
            traits_data={"product_match_confidence": "high"},
            traits={"radio", "wifi"},
            matched_products={"smart_lock"},
            product_type="smart_lock",
        )

        self.assertEqual(route_plan.primary_route_family, "building_hardware")
        self.assertEqual(route_plan.primary_standard_code, "EN 14846")
        self.assertEqual(route_plan.scope_route, "appliance")

    def test_build_known_facts_extracts_explicit_wireless_features(self) -> None:
        facts = _build_known_facts("Bluetooth smart lock with Wi-Fi and cloud account required")
        fact_keys = {item.key for item in facts}

        self.assertIn("connectivity.bluetooth", fact_keys)
        self.assertIn("connectivity.wifi", fact_keys)
        self.assertIn("service.cloud_account_required", fact_keys)
        self.assertNotIn("connectivity.no_radio", fact_keys)

    def test_missing_information_assembles_route_specific_questions(self) -> None:
        items = _missing_information(
            {"radio", "wifi", "app_control", "cloud"},
            {"smart_lock"},
            "smart lock with app control and wifi",
            product_type="smart_lock",
            route_plan=RoutePlan(primary_route_family="building_hardware"),
        )
        keys = [item.key for item in items]

        self.assertIn("smart_lock_installation", keys)
        self.assertIn("cloud_dependency", keys)
        self.assertIn("radio_rf_detail", keys)

    def test_risk_helpers_raise_current_and_future_connected_risk(self) -> None:
        current = _current_risk(
            product_confidence="medium",
            contradiction_severity="none",
            review_items=[],
            missing_items=[],
        )
        future = _future_risk(["CRA"], {"cloud", "ota"})

        self.assertEqual(current, "LOW")
        self.assertEqual(future, "HIGH")

    def test_trait_gate_details_accepts_typed_standard_rows(self) -> None:
        row = StandardCatalogRow.model_validate(
            {
                "code": "EN TEST 1",
                "title": "Typed test route",
                "category": "safety",
                "applies_if_all": ["radio"],
                "applies_if_any": ["wifi", "bluetooth"],
                "required_fact_basis": "confirmed",
            }
        )

        gate = _trait_gate_details(
            row,
            traits={"radio", "wifi"},
            confirmed_traits={"radio", "wifi"},
            allow_soft_any_miss=False,
        )

        self.assertTrue(gate["passes"])
        self.assertEqual(gate["fact_basis"], "confirmed")
        self.assertEqual(gate["matched_traits_all"], ["radio"])
        self.assertEqual(gate["matched_traits_any"], ["wifi"])

    def test_score_standard_v2_rewards_product_preference_and_context(self) -> None:
        row = StandardCatalogRow.model_validate(
            {
                "code": "EN 14846",
                "title": "Locks and latches",
                "category": "safety",
                "harmonization_status": "harmonized",
                "selection_priority": 3,
            }
        )
        gate = _trait_gate_details(
            row,
            traits=set(),
            confirmed_traits=set(),
            allow_soft_any_miss=False,
        )

        base_score = _score_standard_v2(row, gate, None, False, [], set())
        boosted_score = _score_standard_v2(
            row,
            gate,
            "primary_product",
            True,
            ["smart lock"],
            {"primary:building_hardware"},
        )

        self.assertGreater(boosted_score, base_score)

    def test_find_applicable_items_returns_typed_standard_rows(self) -> None:
        traits_data = extract_traits("smart lock with wifi and bluetooth")
        standards = find_applicable_items(
            traits=set(traits_data["all_traits"]),
            directives=["RED", "EMC", "GPSR"],
            product_type=traits_data["product_type"],
            matched_products=traits_data["routing_matched_products"],
            product_genres=traits_data["product_genres"],
            preferred_standard_codes=traits_data["preferred_standard_codes"],
            explicit_traits=set(traits_data["explicit_traits"]),
            confirmed_traits=set(traits_data["confirmed_traits"]),
            normalized_text=normalize("smart lock with wifi and bluetooth"),
            context_tags={"scope:appliance", "primary:building_hardware"},
            allowed_directives={"RED", "EMC", "GPSR"},
            selection_context={
                "scope_route": "appliance",
                "primary_route_family": "building_hardware",
            },
        )

        self.assertTrue(standards["standards"])
        self.assertTrue(all(isinstance(row, StandardCatalogRow) for row in standards["standards"]))

    def test_standard_item_from_row_accepts_typed_standard_catalog_row(self) -> None:
        row = StandardCatalogRow.model_validate(
            {
                "code": "EN 14846",
                "title": "Locks and latches",
                "category": "safety",
                "directives": ["RED"],
                "harmonization_status": "harmonized",
            }
        )
        legislation = LegislationItem(
            code="RED",
            title="Radio Equipment Directive",
            family="radio",
            directive_key="RED",
            bucket="ce",
        )

        item = _standard_item_from_row(row, {"RED": legislation}, {"radio"})

        self.assertIsInstance(item, StandardItem)
        self.assertEqual(item.code, "EN 14846")
        self.assertEqual(item.directive, "RED")

    def test_metadata_payload_helpers_accept_typed_catalog_rows(self) -> None:
        meta = KnowledgeBaseMeta(
            traits=1,
            genres=1,
            products=1,
            legislations=1,
            standards=1,
            version="test-version",
        )
        traits = (TraitCatalogRow(id="wifi", label="Wi-Fi", description="Wireless networking"),)
        genres = (
            GenreCatalogRow(
                id="smart_home_iot",
                label="Smart home",
                keywords=["smart home"],
                traits=["wifi"],
            ),
        )
        products = (
            ProductCatalogRow(
                id="smart_lock",
                label="Smart lock",
                product_family="smart_access_device",
                product_subfamily="smart_lock",
                genres=["smart_home_iot"],
                aliases=["smart lock"],
            ),
        )
        legislations = (
            LegislationCatalogRow(
                code="RED",
                title="Radio Equipment Directive",
                family="radio",
                directive_key="RED",
                bucket="ce",
            ),
        )
        standards = (
            StandardCatalogRow(
                code="EN 14846",
                title="Locks and latches",
                category="safety",
                directives=["RED"],
                harmonization_status="harmonized",
            ),
        )

        options_payload = _build_metadata_options_payload(traits, genres, products, legislations, meta)
        standards_payload = _build_metadata_standards_payload(standards, meta)

        self.assertIsInstance(options_payload, MetadataOptionsResponse)
        self.assertEqual(options_payload.knowledge_base_meta.version, "test-version")
        self.assertEqual(options_payload.products[0].id, "smart_lock")
        self.assertIsInstance(standards_payload, MetadataStandardsResponse)
        self.assertEqual(standards_payload.standards[0].directive, "RED")

    def test_apply_post_selection_gates_v1_returns_typed_standard_rows(self) -> None:
        row = StandardCatalogRow.model_validate(
            {
                "code": "EN 62311",
                "title": "EMF assessment",
                "category": "emf",
                "directives": ["LVD"],
                "score": 100,
                "item_type": "standard",
            }
        )

        gated_rows = _apply_post_selection_gates_v1(
            [row],
            traits={"radio", "electrical"},
            matched_products=set(),
            diagnostics=[],
            allowed_directives={"RED", "LVD"},
            product_type="smart_lock",
            confirmed_traits={"radio", "electrical"},
            description="radio-enabled smart lock",
        )

        self.assertEqual(len(gated_rows), 1)
        self.assertIsInstance(gated_rows[0], StandardCatalogRow)
        self.assertEqual(gated_rows[0].get("directive"), "RED")
        self.assertEqual(gated_rows[0].get("legislation_key"), "RED")

    def test_build_analysis_result_preserves_route_context_fields(self) -> None:
        legislation = LegislationItem(
            code="RED",
            title="Radio Equipment Directive",
            family="radio",
            directive_key="RED",
            bucket="ce",
        )
        legislation_sections = [
            LegislationSection(
                key="ce",
                title="CE routes",
                count=1,
                items=[legislation],
            )
        ]
        standard = StandardItem(
            code="EN 14846",
            title="Locks and latches",
            directive="RED",
            directives=["RED"],
            category="safety",
            harmonization_status="harmonized",
        )
        standard_sections = _build_standard_sections([standard])
        route_context = RouteContext(
            scope_route="appliance",
            scope_reasons=["primary_route_family=building_hardware"],
            context_tags=["primary:building_hardware"],
            primary_route_family="building_hardware",
            primary_route_standard_code="EN 14846",
            primary_route_reason="Smart lock maps to EN 14846 as the primary route.",
            overlay_routes=["RED"],
            route_confidence="high",
        )

        result = _build_analysis_result(
            description="smart lock with wifi",
            depth="standard",
            normalized_description="smart lock with wifi",
            traits_data={
                "product_type": "smart_lock",
                "product_family": "smart_access_device",
                "product_subtype": "smart_lock",
                "product_match_stage": "subtype",
                "product_match_confidence": "high",
                "explicit_traits": ["radio", "wifi"],
                "confirmed_traits": ["radio", "wifi"],
                "inferred_traits": [],
                "functional_classes": ["home_device"],
                "confirmed_functional_classes": ["home_device"],
                "product_candidates": [],
                "contradictions": [],
                "contradiction_severity": "none",
            },
            diagnostics=["primary_route_standard=EN 14846"],
            matched_products={"smart_lock"},
            routing_matched_products={"smart_lock"},
            product_genres={"smart_home_iot"},
            likely_standards={"EN 14846"},
            trait_set={"radio", "wifi"},
            confirmed_traits={"radio", "wifi"},
            detected_directives=["RED"],
            forced_directives=[],
            legislation_items=[legislation],
            legislation_sections=legislation_sections,
            standard_items=[standard],
            review_items=[],
            missing_items=[],
            standard_sections=standard_sections,
            risk_reasons=[],
            risk_summary=RiskSummary(),
            summary="Primary route assembled.",
            findings=[],
            known_facts=[KnownFactItem(key="connectivity.wifi", label="Wi-Fi", value="explicit", source="parsed")],
            trait_evidence=[],
            product_match_audit=ProductMatchAudit(engine_version="2.0", normalized_text="smart lock with wifi"),
            standard_match_audit=StandardMatchAudit(engine_version="2.0"),
            route_context=route_context,
            overall_risk="LOW",
            current_risk="LOW",
            future_risk="LOW",
            degraded_reasons=[],
            warnings=[],
        )

        self.assertEqual(result.primary_route_standard_code, "EN 14846")
        self.assertEqual(result.route_context.primary_route_standard_code, "EN 14846")
        self.assertEqual(result.summary, "Primary route assembled.")
        self.assertIsNotNone(result.catalog_version)


if __name__ == "__main__":
    unittest.main()
