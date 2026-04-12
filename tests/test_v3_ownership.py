from __future__ import annotations

import unittest

from app.services.classifier.matcher_v3 import run_matcher_v3
from app.services.classifier.matching import _hierarchical_product_match_v2
from app.services.classifier.normalization import normalize
from app.services.routing_v3 import build_route_context, decide_route_policy
from app.services.standards_engine import find_applicable_items
from app.services.standards_v3 import run_standards_policy, select_applicable_items_v3
from app.services.rules.facts import _build_known_facts, _missing_information
from app.services.rules.result_builder import _build_standard_sections, _sort_standard_items, _standard_item_from_row
from app.services.rules.routing import _prepare_analysis, _select_legislation_routes, _standard_context


class V3OwnershipTests(unittest.TestCase):
    DESCRIPTION = "smart lock with wifi and bluetooth"

    def _prepared(self):
        return _prepare_analysis(self.DESCRIPTION, "", "standard")

    def test_matching_module_is_a_compatibility_facade_over_matcher_v3(self) -> None:
        normalized = normalize(self.DESCRIPTION)
        direct = run_matcher_v3(normalized, {"wifi", "bluetooth", "radio"})
        compatibility = _hierarchical_product_match_v2(normalized, {"wifi", "bluetooth", "radio"})

        self.assertEqual(compatibility.product_type, direct.product_type)
        self.assertEqual(compatibility.product_match_stage, direct.product_match_stage)
        self.assertEqual(compatibility.audit.final_match_reason, direct.audit.final_match_reason)

    def test_routing_v3_builds_route_context_for_the_production_path(self) -> None:
        prepared = self._prepared()
        routes = _select_legislation_routes(prepared, None)
        context = _standard_context(
            prepared.route_traits,
            prepared.routing_matched_products,
            prepared.routing_product_type,
            prepared.confirmed_traits,
            self.DESCRIPTION,
            prepared.route_plan,
        )
        policy = decide_route_policy(prepared, routes.detected_directives)
        route_context = build_route_context(
            context,
            _build_known_facts(self.DESCRIPTION),
            policy,
            [directive for directive in routes.detected_directives if directive == "RED"],
        )

        self.assertEqual(route_context.primary_route_family, "building_hardware")
        self.assertEqual(route_context.primary_route_standard_code, "EN 14846")
        self.assertIn("RED", route_context.overlay_routes)
        self.assertEqual(route_context.route_confidence, "high")

    def test_standards_engine_v2_compatibility_entrypoint_delegates_to_standards_v3(self) -> None:
        prepared = self._prepared()
        routes = _select_legislation_routes(prepared, None)
        context = _standard_context(
            prepared.route_traits,
            prepared.routing_matched_products,
            prepared.routing_product_type,
            prepared.confirmed_traits,
            self.DESCRIPTION,
            prepared.route_plan,
        )

        v3_items = select_applicable_items_v3(
            traits=prepared.route_traits,
            directives=list(routes.allowed_directives),
            product_type=prepared.routing_product_type,
            matched_products=sorted(prepared.routing_matched_products),
            product_genres=sorted(prepared.product_genres),
            preferred_standard_codes=sorted(prepared.likely_standards),
            explicit_traits=set(prepared.traits_data.explicit_traits),
            confirmed_traits=prepared.confirmed_traits,
            normalized_text=normalize(self.DESCRIPTION),
            context_tags=context.context_tags,
            allowed_directives=routes.allowed_directives,
            selection_context=context,
        )
        compatibility_items = find_applicable_items(
            traits=prepared.route_traits,
            directives=list(routes.allowed_directives),
            product_type=prepared.routing_product_type,
            matched_products=sorted(prepared.routing_matched_products),
            product_genres=sorted(prepared.product_genres),
            preferred_standard_codes=sorted(prepared.likely_standards),
            explicit_traits=set(prepared.traits_data.explicit_traits),
            confirmed_traits=prepared.confirmed_traits,
            normalized_text=normalize(self.DESCRIPTION),
            context_tags=context.context_tags,
            allowed_directives=routes.allowed_directives,
            selection_context=context,
        )

        self.assertEqual(
            [row.code for row in compatibility_items["standards"]],
            [row.code for row in v3_items["standards"]],
        )
        self.assertEqual(
            [row.code for row in compatibility_items["review_items"]],
            [row.code for row in v3_items["review_items"]],
        )

    def test_run_standards_policy_uses_v3_selection_policy(self) -> None:
        prepared = self._prepared()
        routes = _select_legislation_routes(prepared, None)
        context = _standard_context(
            prepared.route_traits,
            prepared.routing_matched_products,
            prepared.routing_product_type,
            prepared.confirmed_traits,
            self.DESCRIPTION,
            prepared.route_plan,
        )
        selection = run_standards_policy(
            prepared=prepared,
            routes=routes,
            description=self.DESCRIPTION,
            context=context,
            missing_items=_missing_information(
                prepared.route_traits,
                prepared.routing_matched_products,
                self.DESCRIPTION,
                product_type=prepared.product_type,
                product_match_stage=prepared.product_match_stage,
                route_plan=prepared.route_plan,
            ),
            standard_sections=_build_standard_sections(
                [],
                primary_standard_code=prepared.route_plan.primary_standard_code,
                supporting_standard_codes=prepared.route_plan.supporting_standard_codes,
            ),
            standard_item_from_row=_standard_item_from_row,
            sort_standard_items=_sort_standard_items,
        )

        self.assertIn("EN 14846", selection.policy.eligibility_codes)
        self.assertEqual(selection.context.primary_route_family, "building_hardware")
        self.assertIn("EN 14846", {item.code for item in selection.standard_items})


if __name__ == "__main__":
    unittest.main()
