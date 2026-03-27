import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

import main
from knowledge_base import KnowledgeBaseError, KnowledgeBaseWarmupResult, reset_cache
from runtime_state import KnowledgeBaseWarmupSnapshot
from rules import analyze


class ApiContractTests(unittest.TestCase):
    def setUp(self) -> None:
        reset_cache()
        self.runtime_state = main.get_runtime_state()
        self.original_state = (
            self.runtime_state.startup_state,
            self.runtime_state.knowledge_base_loaded,
            dict(self.runtime_state.warmup_meta),
            dict(self.runtime_state.warmup_counts),
            self.runtime_state.warmup_error,
        )

    def tearDown(self) -> None:
        self.runtime_state.startup_state = self.original_state[0]
        self.runtime_state.knowledge_base_loaded = self.original_state[1]
        self.runtime_state.warmup_meta = self.original_state[2]
        self.runtime_state.warmup_counts = self.original_state[3]
        self.runtime_state.warmup_error = self.original_state[4]

    def _mark_ready(self) -> None:
        self.runtime_state.mark_ready(
            KnowledgeBaseWarmupSnapshot(
                counts={"products": 1, "standards": 1},
                meta={"version": "test-catalog"},
            )
        )

    def _mark_not_ready(self, message: str = "warming up") -> None:
        self.runtime_state.mark_failed(message)

    def test_health_live(self) -> None:
        with TestClient(main.app) as client:
            response = client.get("/health/live")

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertTrue(body["ok"])
        self.assertIn("version", body)

    def test_health_ready_when_ready(self) -> None:
        with TestClient(main.app) as client:
            self._mark_ready()
            response = client.get("/health/ready")

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertTrue(body["ok"])
        self.assertEqual(body["startup_state"], "ready")
        self.assertEqual(body["catalog_version"], "test-catalog")
        self.assertTrue(body["knowledge_base_loaded"])
        self.assertIn("engine_version", body)

    def test_health_ready_when_not_ready(self) -> None:
        with TestClient(main.app) as client:
            self._mark_not_ready("catalog failed")
            response = client.get("/health/ready")

        self.assertEqual(response.status_code, 503)
        body = response.json()
        self.assertFalse(body["ok"])
        self.assertEqual(body["startup_state"], "failed")
        self.assertFalse(body["knowledge_base_loaded"])

    def test_analyze_returns_503_when_not_ready(self) -> None:
        with TestClient(main.app) as client:
            self._mark_not_ready("catalog failed")
            response = client.post("/analyze", json={"description": "smart speaker"})

        self.assertEqual(response.status_code, 503)
        body = response.json()
        self.assertFalse(body["ok"])
        self.assertEqual(body["error"]["code"], "knowledge_base_not_ready")

    def test_degraded_mode_response_when_standards_fail(self) -> None:
        with patch("rules.find_applicable_items", side_effect=RuntimeError("boom")):
            result = analyze("smart speaker with wifi and bluetooth")

        self.assertTrue(result.degraded_mode)
        self.assertIn("standards_enrichment_failed", result.degraded_reasons)
        self.assertEqual(result.product_type, "smart_speaker")
        self.assertEqual(result.api_version, "1.0")
        self.assertTrue(result.warnings)

    def test_stable_response_shape_for_ambiguous_query(self) -> None:
        payload = analyze("generic industrial tool").model_dump()

        for key in (
            "api_version",
            "engine_version",
            "catalog_version",
            "analysis_audit",
            "hero_summary",
            "confidence_panel",
            "input_gaps_panel",
            "route_context",
            "classification_summary",
            "primary_uncertainties",
            "degraded_mode",
            "degraded_reasons",
        ):
            self.assertIn(key, payload)
        self.assertIn("normalized_description", payload)
        self.assertIn("triggered_routes", payload)
        self.assertIn("next_actions", payload)

    def test_stable_response_shape_for_confident_query(self) -> None:
        payload = analyze("smart speaker with wifi and bluetooth").model_dump()

        self.assertEqual(payload["product_type"], "smart_speaker")
        self.assertIn("analysis_audit", payload)
        self.assertIn("route_context", payload)
        self.assertIn("known_facts", payload)
        self.assertIn("classification_summary", payload)
        self.assertIn("api_version", payload)
        self.assertIn("catalog_version", payload)

    def test_admin_reload_success_payload(self) -> None:
        warmup = KnowledgeBaseWarmupResult(
            counts={"products": 1, "standards": 2},
            meta={"version": "reload-catalog"},
            duration_ms=7,
        )
        with TestClient(main.app) as client:
            with patch.dict("os.environ", {"REGCHECK_ADMIN_RELOAD_TOKEN": "secret"}):
                with patch("main.reset_cache"):
                    with patch("main.warmup_knowledge_base", return_value=warmup):
                        response = client.post("/admin/reload", headers={"X-Admin-Token": "secret"})

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertTrue(body["ok"])
        self.assertTrue(body["knowledge_base_loaded"])
        self.assertEqual(body["catalog_version"], "reload-catalog")
        self.assertEqual(body["startup_state"], "ready")

    def test_admin_reload_failure_payload(self) -> None:
        with TestClient(main.app) as client:
            with patch.dict("os.environ", {"REGCHECK_ADMIN_RELOAD_TOKEN": "secret"}):
                with patch("main.reset_cache"):
                    with patch("main.warmup_knowledge_base", side_effect=KnowledgeBaseError("reload failed")):
                        response = client.post("/admin/reload", headers={"X-Admin-Token": "secret"})

        self.assertEqual(response.status_code, 503)
        body = response.json()
        self.assertFalse(body["ok"])
        self.assertEqual(body["error"]["code"], "knowledge_base_reload_failed")

    def test_analysis_response_includes_version_fields(self) -> None:
        result = analyze("smart speaker with wifi and bluetooth")

        self.assertEqual(result.api_version, "1.0")
        self.assertEqual(result.engine_version, "2.0")
        self.assertTrue(result.catalog_version)

    def test_shadow_diff_present_when_enabled(self) -> None:
        with patch("rules.ENABLE_ENGINE_V2_SHADOW", True):
            result = analyze("smart speaker with wifi and bluetooth")

        self.assertIsInstance(result.analysis_audit.shadow_diff, list)


if __name__ == "__main__":
    unittest.main()
