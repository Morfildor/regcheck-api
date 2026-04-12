from __future__ import annotations

import json
import unittest

from app.services.rules.legacy import analyze_v1
from rules import analyze

from .benchmark_cases import ADVERSARIAL_CASES, BLIND_HOLDOUT_CASES, CURATED_MATCH_CASES, BenchmarkCase


def _projection(case: BenchmarkCase) -> dict[str, object]:
    result = analyze(case.description)
    return {
        "product_type": result.product_type,
        "product_match_stage": result.product_match_stage,
        "primary_route_standard_code": result.primary_route_standard_code,
        "route_family": result.route_context.primary_route_family,
        "directives": result.directives,
        "standards": [item.code for item in result.standards],
        "review_items": [item.code for item in result.review_items],
        "audit_selected": [item.code for item in result.standard_match_audit.selected],
        "audit_review": [item.code for item in result.standard_match_audit.review],
    }


def _shadow_projection(description: str) -> dict[str, object]:
    before = analyze_v1(description=description)
    after = analyze(description)
    return {
        "product": {"before": before.product_type, "after": after.product_type},
        "directives": {"before": before.directives, "after": after.directives},
        "standards": {"before": [item.code for item in before.standards], "after": [item.code for item in after.standards]},
    }


class BenchmarkSuiteTests(unittest.TestCase):
    def test_curated_match_cases(self) -> None:
        for case in CURATED_MATCH_CASES:
            with self.subTest(case=case.key):
                projection = _projection(case)
                self.assertEqual(projection["product_type"], case.expected_product)
                self.assertEqual(projection["product_match_stage"], case.expected_stage)
                self.assertEqual(projection["primary_route_standard_code"], case.expected_primary_standard)
                for directive in case.required_directives:
                    self.assertIn(directive, projection["directives"])

    def test_blind_holdout_cases(self) -> None:
        for case in BLIND_HOLDOUT_CASES:
            with self.subTest(case=case.key):
                projection = _projection(case)
                self.assertEqual(projection["product_type"], case.expected_product)
                if case.expected_stage:
                    self.assertEqual(projection["product_match_stage"], case.expected_stage)

    def test_adversarial_cases(self) -> None:
        for case in ADVERSARIAL_CASES:
            with self.subTest(case=case.key):
                projection = _projection(case)
                self.assertEqual(projection["product_match_stage"], case.expected_stage)
                if case.expected_product is None:
                    self.assertIsNone(projection["product_type"])
                else:
                    self.assertEqual(projection["product_type"], case.expected_product)

    def test_audit_payload_stability(self) -> None:
        projection = _projection(CURATED_MATCH_CASES[0])
        self.assertIn("audit_selected", projection)
        self.assertIn("audit_review", projection)
        self.assertIsInstance(projection["audit_selected"], list)
        self.assertIsInstance(projection["audit_review"], list)

    def test_shadow_diff_projection_is_serializable(self) -> None:
        payload = _shadow_projection("smart lock with wifi and bluetooth")
        rendered = json.dumps(payload, sort_keys=True)
        self.assertIn("product", rendered)
        self.assertIn("directives", rendered)
        self.assertIn("standards", rendered)
