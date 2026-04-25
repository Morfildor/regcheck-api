"""Catalog integrity tests for the product/standard mapping invariants.

These tests guard the invariant that every product `likely_standards` entry
either points to a valid standard whose `applies_if_products` includes the
product, or that the standard explicitly opts in via the new
`allow_preferred_product_fallback: true` metadata field.
"""

from __future__ import annotations

import unittest

from app.services.knowledge_base import get_knowledge_base_snapshot, reset_cache
from app.services.knowledge_base.validator import collect_product_standard_integrity_issues


class CatalogStandardIntegrityTests(unittest.TestCase):
    def setUp(self) -> None:
        reset_cache()

    def test_no_product_likely_standards_mismatches(self) -> None:
        snapshot = get_knowledge_base_snapshot()
        products = [row.as_legacy_dict() for row in snapshot.products]
        standards = [row.as_legacy_dict() for row in snapshot.standards]
        issues = collect_product_standard_integrity_issues(products, standards)
        self.assertEqual(
            issues,
            [],
            msg="Product/standard catalog integrity issues found:\n" + "\n".join(issues),
        )

    def test_collector_reports_missing_membership(self) -> None:
        products = [
            {
                "id": "fake_product",
                "label": "Fake",
                "aliases": ["fake"],
                "likely_standards": ["EN 60335-2-13"],
            }
        ]
        standards = [
            {
                "code": "EN 60335-2-13",
                "title": "Deep fryers",
                "category": "safety",
                "applies_if_products": ["deep_fryer"],
            }
        ]
        issues = collect_product_standard_integrity_issues(products, standards)
        self.assertEqual(len(issues), 1)
        self.assertIn("fake_product", issues[0])
        self.assertIn("EN 60335-2-13", issues[0])

    def test_collector_accepts_explicit_fallback_optin(self) -> None:
        products = [
            {
                "id": "boundary_product",
                "label": "Boundary",
                "aliases": ["boundary"],
                "likely_standards": ["EN 60335-2-XX"],
            }
        ]
        standards = [
            {
                "code": "EN 60335-2-XX",
                "title": "Generic",
                "category": "safety",
                "applies_if_products": ["other_product"],
                "allow_preferred_product_fallback": True,
            }
        ]
        issues = collect_product_standard_integrity_issues(products, standards)
        self.assertEqual(issues, [])

    def test_collector_reports_unknown_standard_reference(self) -> None:
        products = [
            {
                "id": "fake_product",
                "label": "Fake",
                "aliases": ["fake"],
                "likely_standards": ["EN 99999-99-99"],
            }
        ]
        standards: list[dict] = []
        issues = collect_product_standard_integrity_issues(products, standards)
        self.assertEqual(len(issues), 1)
        self.assertIn("does not match any standard code", issues[0])


if __name__ == "__main__":
    unittest.main()
