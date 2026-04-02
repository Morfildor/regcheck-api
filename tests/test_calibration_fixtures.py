import unittest

from app.domain.models import AnalysisResult
from knowledge_base import reset_cache
from rules import analyze
from tests.calibration_fixtures import CALIBRATION_CASES, CalibrationCase


TRACE_STEP_ORDER = [
    "classification",
    "traits",
    "assumptions",
    "missing_facts",
    "legislation",
    "standards",
    "rejections",
]


class CalibrationFixtureTests(unittest.TestCase):
    def setUp(self) -> None:
        reset_cache()

    def _assert_membership(self, actual: set[str], include: tuple[str, ...], exclude: tuple[str, ...], *, label: str) -> None:
        for item in include:
            self.assertIn(item, actual, f"expected {label} {item!r} to be present")
        for item in exclude:
            self.assertNotIn(item, actual, f"expected {label} {item!r} to be absent")

    def _assert_trace_structure(self, result: AnalysisResult) -> None:
        trace = result.analysis_audit.decision_trace
        self.assertEqual([entry.step for entry in trace], TRACE_STEP_ORDER)
        for entry in trace:
            self.assertTrue(entry.summary.strip())
            self.assertIsInstance(entry.items, list)

    def _assert_route_integrity(self, result: AnalysisResult) -> None:
        ce_keys = [item.directive_key for item in result.ce_legislations]
        standard_codes = [item.code for item in result.standards]
        review_codes = [item.code for item in result.review_items]

        self.assertEqual(len(ce_keys), len(set(ce_keys)))
        self.assertEqual(len(standard_codes), len(set(standard_codes)))
        self.assertEqual(len(review_codes), len(set(review_codes)))
        self.assertFalse(set(standard_codes) & set(review_codes))

        if "RED" in ce_keys:
            self.assertNotIn("LVD", ce_keys)
            self.assertNotIn("EMC", ce_keys)
            red_route = next(item for item in result.ce_legislations if item.directive_key == "RED")
            applicable_articles = [article.article for article in red_route.sub_articles if article.applicable]
            self.assertEqual(applicable_articles[:3], ["Art. 3.1(a)", "Art. 3.1(b)", "Art. 3.2"])

    def _assert_primary_route(self, result: AnalysisResult, case: CalibrationCase) -> None:
        self.assertEqual(result.route_context.scope_route, case.expected_scope_route)
        self.assertEqual(result.route_context.primary_route_family, case.expected_primary_route_family)
        self.assertEqual(result.primary_route_standard_code, case.expected_primary_route_standard)
        self.assertEqual(result.route_context.primary_route_standard_code, case.expected_primary_route_standard)
        self.assertTrue(result.primary_route_reason)

        standard_codes = [item.code for item in result.standards]
        review_codes = [item.code for item in result.review_items]

        if case.expected_primary_route_standard in standard_codes:
            self.assertEqual(standard_codes[0], case.expected_primary_route_standard)
        if case.expected_primary_route_standard in review_codes:
            self.assertEqual(review_codes[0], case.expected_primary_route_standard)

    def test_calibration_fixtures_cover_representative_routes(self) -> None:
        for case in CALIBRATION_CASES:
            with self.subTest(case=case.name):
                reset_cache()
                result = analyze(case.description)

                directives = set(result.directives)
                ce_keys = {item.directive_key for item in result.ce_legislations}
                standard_codes = {item.code for item in result.standards}
                review_codes = {item.code for item in result.review_items}
                missing_keys = {item.key for item in result.missing_information_items}

                self._assert_membership(directives, case.directives_include, case.directives_exclude, label="directive")
                self._assert_membership(ce_keys, case.ce_include, case.ce_exclude, label="CE legislation")
                self._assert_membership(standard_codes, case.standards_include, case.standards_exclude, label="standard")
                self._assert_membership(review_codes, case.review_include, case.review_exclude, label="review item")
                self._assert_membership(missing_keys, case.missing_include, case.missing_exclude, label="missing-information key")

                self._assert_trace_structure(result)
                self._assert_route_integrity(result)

                if case.assert_primary_route:
                    self._assert_primary_route(result, case)
                else:
                    self.assertEqual(result.route_context.scope_route, case.expected_scope_route)

                if case.assert_product_type:
                    self.assertEqual(result.product_type, case.expected_product_type)


if __name__ == "__main__":
    unittest.main()
