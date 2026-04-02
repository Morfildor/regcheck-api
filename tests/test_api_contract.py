import unittest
from pathlib import Path
import shutil
import tempfile
from unittest.mock import patch

from fastapi.testclient import TestClient

import main
from knowledge_base import (
    KnowledgeBaseError,
    KnowledgeBaseWarmupResult,
    load_meta,
    load_metadata_payload,
    reset_cache,
    warmup_knowledge_base,
)
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
            self.runtime_state.last_reload_error,
            self.runtime_state.ready_timestamp,
            self.runtime_state.last_reload_timestamp,
        )

    def tearDown(self) -> None:
        self.runtime_state.startup_state = self.original_state[0]
        self.runtime_state.knowledge_base_loaded = self.original_state[1]
        self.runtime_state.warmup_meta = self.original_state[2]
        self.runtime_state.warmup_counts = self.original_state[3]
        self.runtime_state.warmup_error = self.original_state[4]
        self.runtime_state.last_reload_error = self.original_state[5]
        self.runtime_state.ready_timestamp = self.original_state[6]
        self.runtime_state.last_reload_timestamp = self.original_state[7]

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

    def test_validation_errors_use_normalized_error_response(self) -> None:
        with TestClient(main.app) as client:
            response = client.post("/analyze", json={"description": "   "}, headers={"X-Request-Id": "req-123"})

        self.assertEqual(response.status_code, 422)
        body = response.json()
        self.assertFalse(body["ok"])
        self.assertEqual(body["error"]["code"], "request_validation_failed")
        self.assertEqual(body["error"]["request_id"], "req-123")
        self.assertIn("description", body["error"]["message"])
        self.assertNotIn("detail", body)

    def test_validation_errors_generate_request_id_when_missing(self) -> None:
        with TestClient(main.app) as client:
            response = client.post("/analyze", json={"description": "   "})

        self.assertEqual(response.status_code, 422)
        body = response.json()
        self.assertTrue(body["error"]["request_id"])
        self.assertEqual(body["error"]["request_id"], response.headers["X-Request-Id"])

    def test_degraded_mode_response_when_standards_fail(self) -> None:
        with patch("app.services.rules.service.find_applicable_items", side_effect=RuntimeError("boom")):
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
            "primary_route_standard_code",
            "primary_route_reason",
            "overlay_routes",
            "route_confidence",
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
        self.assertIn("primary_route_standard_code", payload)
        self.assertIn("overlay_routes", payload)
        self.assertIn("route_confidence", payload)
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
                    with patch("app.main.warmup_knowledge_base", return_value=warmup):
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
                    with patch("app.main.warmup_knowledge_base", side_effect=KnowledgeBaseError("reload failed")):
                        response = client.post("/admin/reload", headers={"X-Admin-Token": "secret"})

        self.assertEqual(response.status_code, 503)
        body = response.json()
        self.assertFalse(body["ok"])
        self.assertEqual(body["error"]["code"], "knowledge_base_reload_failed")

    def test_startup_warmup_success_marks_runtime_ready(self) -> None:
        warmup = KnowledgeBaseWarmupResult(
            counts={"products": 1, "standards": 2},
            meta={"version": "startup-catalog"},
            duration_ms=5,
        )
        with patch("app.main.warmup_knowledge_base", return_value=warmup):
            with TestClient(main.app):
                runtime_state = main.get_runtime_state()
                self.assertTrue(runtime_state.is_ready)
                self.assertEqual(runtime_state.catalog_version, "startup-catalog")
                self.assertTrue(runtime_state.knowledge_base_loaded)

    def test_reload_failure_preserves_prior_healthy_runtime_state(self) -> None:
        with TestClient(main.app) as client:
            self.runtime_state.mark_ready(
                KnowledgeBaseWarmupSnapshot(
                    counts={"products": 3, "standards": 4},
                    meta={"version": "healthy-catalog"},
                )
            )
            with patch.dict("os.environ", {"REGCHECK_ADMIN_RELOAD_TOKEN": "secret"}):
                with patch("app.main.warmup_knowledge_base", side_effect=KnowledgeBaseError("reload failed")):
                    response = client.post("/admin/reload", headers={"X-Admin-Token": "secret"})

        self.assertEqual(response.status_code, 503)
        self.assertTrue(self.runtime_state.is_ready)
        self.assertEqual(self.runtime_state.startup_state, "ready")
        self.assertEqual(self.runtime_state.catalog_version, "healthy-catalog")
        self.assertEqual(self.runtime_state.last_reload_error, "reload failed")

    def test_admin_reload_forbidden_without_matching_token(self) -> None:
        with TestClient(main.app) as client:
            with patch.dict("os.environ", {"REGCHECK_ADMIN_RELOAD_TOKEN": "secret"}):
                response = client.post("/admin/reload")

        self.assertEqual(response.status_code, 403)
        body = response.json()
        self.assertFalse(body["ok"])
        self.assertEqual(body["error"]["code"], "forbidden")

    def test_admin_reload_disabled_when_env_token_missing(self) -> None:
        with TestClient(main.app) as client:
            with patch.dict("os.environ", {"REGCHECK_ADMIN_RELOAD_TOKEN": ""}):
                response = client.post("/admin/reload")

        self.assertEqual(response.status_code, 503)
        body = response.json()
        self.assertFalse(body["ok"])
        self.assertEqual(body["error"]["code"], "admin_reload_disabled")

    def test_metadata_endpoints_work_when_ready(self) -> None:
        with TestClient(main.app) as client:
            self._mark_ready()
            options = client.get("/metadata/options")
            standards = client.get("/metadata/standards")

        self.assertEqual(options.status_code, 200)
        self.assertEqual(standards.status_code, 200)
        self.assertIn("knowledge_base_meta", options.json())
        self.assertIn("knowledge_base_meta", standards.json())
        self.assertTrue(options.json()["products"])
        self.assertTrue(standards.json()["standards"])

    def test_analysis_response_includes_version_fields(self) -> None:
        result = analyze("smart speaker with wifi and bluetooth")

        self.assertEqual(result.api_version, "1.0")
        self.assertEqual(result.engine_version, "2.0")
        self.assertTrue(result.catalog_version)

    def test_catalog_version_changes_when_yaml_content_changes(self) -> None:
        source_dir = Path(main.__file__).resolve().parent / "data"
        with tempfile.TemporaryDirectory() as tmpdir:
            temp_data_dir = Path(tmpdir) / "data"
            shutil.copytree(source_dir, temp_data_dir)
            with patch.dict("os.environ", {"REGCHECK_DATA_DIR": str(temp_data_dir)}):
                reset_cache()
                version_before = load_meta()["version"]
                products_path = temp_data_dir / "products.yaml"
                products_path.write_text(products_path.read_text(encoding="utf-8") + "\n# test catalog change\n", encoding="utf-8")
                reset_cache()
                version_after = load_meta()["version"]

        reset_cache()
        self.assertNotEqual(version_before, version_after)

    def test_failed_warmup_keeps_last_known_good_snapshot_active(self) -> None:
        source_dir = Path(main.__file__).resolve().parent / "data"
        with tempfile.TemporaryDirectory() as tmpdir:
            temp_data_dir = Path(tmpdir) / "data"
            shutil.copytree(source_dir, temp_data_dir)
            with patch.dict("os.environ", {"REGCHECK_DATA_DIR": str(temp_data_dir)}):
                reset_cache()
                warmup_knowledge_base(refresh_paths=True)
                version_before = load_meta()["version"]
                products_path = temp_data_dir / "products.yaml"
                products_path.write_text("products: [\n  invalid", encoding="utf-8")

                with self.assertRaises(KnowledgeBaseError):
                    warmup_knowledge_base(refresh_paths=True)

                self.assertEqual(load_meta()["version"], version_before)

    def test_metadata_payload_cache_refreshes_on_successful_reload(self) -> None:
        source_dir = Path(main.__file__).resolve().parent / "data"
        with tempfile.TemporaryDirectory() as tmpdir:
            temp_data_dir = Path(tmpdir) / "data"
            shutil.copytree(source_dir, temp_data_dir)
            with patch.dict("os.environ", {"REGCHECK_DATA_DIR": str(temp_data_dir)}):
                reset_cache()
                warmup_knowledge_base(refresh_paths=True)
                options_before = load_metadata_payload("options")
                version_before = options_before["knowledge_base_meta"]["version"]
                products_path = temp_data_dir / "products.yaml"
                products_path.write_text(
                    products_path.read_text(encoding="utf-8") + "\n# metadata cache refresh\n",
                    encoding="utf-8",
                )

                warmup_knowledge_base(refresh_paths=True)
                options_after = load_metadata_payload("options")

        reset_cache()
        self.assertNotEqual(version_before, options_after["knowledge_base_meta"]["version"])
        self.assertIsNot(options_before, options_after)

    def test_shadow_diff_present_when_enabled(self) -> None:
        with patch("app.services.rules.service._shadow_enabled", return_value=True):
            result = analyze("smart speaker with wifi and bluetooth")

        self.assertIsInstance(result.analysis_audit.shadow_diff, list)


if __name__ == "__main__":
    unittest.main()
