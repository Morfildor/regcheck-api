from __future__ import annotations

import unittest

from app.services.classifier.matcher_v3 import run_matcher_v3
from app.services.classifier.normalization import normalize
from app.services.routing_v3 import build_classifier_evidence, decide_route_policy
from app.services.rules.routing import _prepare_analysis


class V3AdapterTests(unittest.TestCase):
    def test_matcher_v3_preserves_current_matcher_outcome_shape(self) -> None:
        outcome = run_matcher_v3(normalize("smart lock with wifi and bluetooth"), {"wifi", "bluetooth", "radio"})

        self.assertEqual(outcome.product_type, "smart_lock")
        self.assertEqual(outcome.product_match_stage, "subtype")
        self.assertTrue(any(diag.startswith("matcher_v3_phases=") for diag in outcome.diagnostics))

    def test_routing_v3_decision_tracks_primary_route(self) -> None:
        prepared = _prepare_analysis("smart lock with wifi and bluetooth", "", "standard")
        evidence = build_classifier_evidence(prepared)
        decision = decide_route_policy(prepared, ["RED", "GPSR"])

        self.assertEqual(evidence.product_type, "smart_lock")
        self.assertEqual(decision.primary_route_family, "building_hardware")
        self.assertIn("RED", decision.directive_overlays)
        self.assertEqual(decision.primary_standard_code, "EN 14846")


if __name__ == "__main__":
    unittest.main()
