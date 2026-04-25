import importlib
import json
from pathlib import Path
import shutil
import tempfile
import threading
import time
import unittest
from unittest.mock import MagicMock, patch

import main
from scripts import catalog_audit
from app.domain.models import AnalysisResult, MetadataOptionsResponse, MetadataStandardsResponse
from app.services.classifier.matching_runtime import _compile_alias, _compile_phrase
from app.services.classifier.traits import extract_traits_v2_typed
from app.services.rules.contracts import ClassifierTraitsSnapshot
from knowledge_base import KnowledgeBaseError, KnowledgeBaseWarmupResult, load_genres, load_legislations, load_products, load_standards, load_traits, reset_cache, warmup_knowledge_base
from rules import analyze
from runtime_state import AppRuntimeState, KnowledgeBaseWarmupSnapshot


def _stable_snapshot_projection(result: AnalysisResult) -> dict[str, object]:
    return {
        "product_type": result.product_type,
        "product_family": result.product_family,
        "product_subtype": result.product_subtype,
        "product_match_stage": result.product_match_stage,
        "product_match_confidence": result.product_match_confidence,
        "classification_is_ambiguous": result.classification_is_ambiguous,
        "classification_confidence_below_threshold": result.classification_confidence_below_threshold,
        "directives": result.directives,
        "ce_legislation_keys": [item.directive_key for item in result.ce_legislations],
        "non_ce_obligation_keys": [item.directive_key for item in result.non_ce_obligations],
        "primary_route_standard_code": result.primary_route_standard_code,
        "primary_route_reason": result.primary_route_reason,
        "route_context": {
            "scope_route": result.route_context.scope_route,
            "primary_route_family": result.route_context.primary_route_family,
            "primary_route_standard_code": result.route_context.primary_route_standard_code,
            "route_confidence": result.route_context.route_confidence,
            "overlay_routes": result.route_context.overlay_routes,
            "context_tags": result.route_context.context_tags,
        },
        "standard_codes": [item.code for item in result.standards],
        "review_codes": [item.code for item in result.review_items],
        "standard_section_keys": [section.key for section in result.standard_sections],
        "missing_information_keys": [item.key for item in result.missing_information_items],
        "decision_trace_steps": [entry.step for entry in result.analysis_audit.decision_trace],
    }


class BackendHardeningTests(unittest.TestCase):
    def setUp(self) -> None:
        reset_cache()

    def test_reload_lock_serializes_concurrent_reloads(self) -> None:
        runtime_state = main.get_runtime_state()
        runtime_state.mark_ready(KnowledgeBaseWarmupSnapshot(counts={"products": 1}, meta={"version": "baseline"}))

        started = threading.Barrier(2)
        counters_lock = threading.Lock()
        active = 0
        max_active = 0
        calls = 0
        results: list[dict[str, object]] = []

        def fake_warmup(*, refresh_paths: bool = False) -> KnowledgeBaseWarmupResult:
            nonlocal active, max_active, calls
            with counters_lock:
                calls += 1
                active += 1
                max_active = max(max_active, active)
            time.sleep(0.05)
            with counters_lock:
                active -= 1
            return KnowledgeBaseWarmupResult(
                counts={"products": 1, "standards": 1},
                meta={"version": f"reload-{calls}"},
                duration_ms=5,
            )

        def invoke_reload() -> None:
            started.wait()
            results.append(main.admin_reload(None))

        threads = [threading.Thread(target=invoke_reload) for _ in range(2)]
        with patch("app.main.warmup_knowledge_base", side_effect=fake_warmup):
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join()

        self.assertEqual(max_active, 1)
        self.assertEqual(calls, 2)
        self.assertEqual(len(results), 2)
        self.assertTrue(all(item["ok"] for item in results))

    def test_runtime_state_transitions_preserve_reload_snapshot(self) -> None:
        runtime_state = AppRuntimeState()
        runtime_state.mark_warming("warming_up")
        self.assertFalse(runtime_state.snapshot().is_ready)

        runtime_state.mark_ready(KnowledgeBaseWarmupSnapshot(counts={"products": 2}, meta={"version": "initial"}))
        self.assertTrue(runtime_state.snapshot().is_ready)

        runtime_state.mark_warming("reloading", preserve_snapshot=True)
        reloading = runtime_state.snapshot()
        self.assertEqual(reloading.startup_state, "reloading")
        self.assertTrue(reloading.is_ready)
        self.assertEqual(reloading.catalog_version, "initial")

        runtime_state.mark_reload_failed("reload failed")
        recovered = runtime_state.snapshot()
        self.assertEqual(recovered.startup_state, "ready")
        self.assertTrue(recovered.is_ready)
        self.assertEqual(recovered.catalog_version, "initial")
        self.assertEqual(recovered.last_reload_error, "reload failed")

    def test_metadata_payloads_validate_against_response_models(self) -> None:
        runtime_state = main.get_runtime_state()
        runtime_state.mark_ready(KnowledgeBaseWarmupSnapshot(counts={}, meta={"version": "test-catalog"}))

        options = MetadataOptionsResponse.model_validate(main.metadata_options())
        standards = MetadataStandardsResponse.model_validate(main.metadata_standards())

        self.assertTrue(options.products)
        self.assertTrue(standards.standards)
        self.assertEqual(options.knowledge_base_meta.version, main.metadata_options()["knowledge_base_meta"]["version"])

    def test_package_import_stability(self) -> None:
        modules = [
            "main",
            "knowledge_base",
            "classifier",
            "standards_engine",
            "rules",
            "models",
            "runtime_state",
            "app.main",
            "app.services.routing",
            "app.services.result_builder",
            "app.services.classifier.normalization",
            "app.services.classifier.traits",
            "app.services.standards_engine.gating",
            "app.services.rules.legacy",
        ]
        loaded = {name: importlib.import_module(name) for name in modules}

        self.assertTrue(hasattr(loaded["main"], "app"))
        self.assertTrue(hasattr(loaded["rules"], "analyze"))
        self.assertTrue(hasattr(loaded["classifier"], "extract_traits"))
        self.assertTrue(hasattr(loaded["app.services.result_builder"], "build_analysis_result"))

    def test_controlled_degraded_mode_uses_standardized_reason_and_warning(self) -> None:
        with patch("app.services.rules.service._build_summary", side_effect=TypeError("boom")):
            result = analyze("smart speaker with wifi and bluetooth")

        self.assertTrue(result.degraded_mode)
        self.assertIn("summary_failed", result.degraded_reasons)
        self.assertIn("The narrative summary could not be assembled; returning a compact fallback summary.", result.warnings)
        self.assertIn("legislation routes", result.summary)

    def test_typed_catalog_validation_surfaces_knowledge_base_error(self) -> None:
        source_dir = Path(__file__).resolve().parents[1] / "data"
        with tempfile.TemporaryDirectory() as tmpdir:
            temp_data_dir = Path(tmpdir) / "data"
            shutil.copytree(source_dir, temp_data_dir)
            products_path = temp_data_dir / "products" / "household_wave3.yaml"
            original = products_path.read_text(encoding="utf-8")
            products_path.write_text(
                original.replace("supporting_standard_codes:\n  - EN 60335-1", "supporting_standard_codes: invalid", 1),
                encoding="utf-8",
            )

            with patch.dict("os.environ", {"REGCHECK_DATA_DIR": str(temp_data_dir)}):
                reset_cache()
                with self.assertRaisesRegex(KnowledgeBaseError, "supporting_standard_codes"):
                    warmup_knowledge_base(refresh_paths=True)

    def test_classifier_signal_validation_surfaces_knowledge_base_error(self) -> None:
        source_dir = Path(__file__).resolve().parents[1] / "data"
        with tempfile.TemporaryDirectory() as tmpdir:
            temp_data_dir = Path(tmpdir) / "data"
            shutil.copytree(source_dir, temp_data_dir)
            signals_path = temp_data_dir / "classifier_signals" / "connectivity.yaml"
            original = signals_path.read_text(encoding="utf-8")
            signals_path.write_text(
                original.replace(
                    "    radio:\n    - \\bradio\\b",
                    "    radio:\n    - \\bradio\\b\n    invented_signal_trait:\n    - \\binvented signal\\b",
                    1,
                ),
                encoding="utf-8",
            )

            with patch.dict("os.environ", {"REGCHECK_DATA_DIR": str(temp_data_dir)}):
                reset_cache()
                with self.assertRaisesRegex(KnowledgeBaseError, "invented_signal_trait"):
                    warmup_knowledge_base(refresh_paths=True)

    def test_catalog_audit_validate_mode_succeeds(self) -> None:
        self.assertEqual(catalog_audit.run("validate", minimum_aliases=4, broad_alias_threshold=3), 0)

    def test_api_snapshots_remain_stable_for_representative_products(self) -> None:
        snapshot_dir = Path(__file__).resolve().parent / "snapshots"
        cases = {
            "smart_speaker": "smart speaker with wifi and bluetooth",
            "generic_industrial_tool": "generic industrial tool",
            "uv_nail_lamp": "uv nail lamp for gel polish",
            "ups_battery_backup": "ups battery backup unit for office server",
        }

        for name, description in cases.items():
            with self.subTest(snapshot=name):
                current = _stable_snapshot_projection(analyze(description))
                expected = json.loads((snapshot_dir / f"{name}.json").read_text(encoding="utf-8"))
                self.assertEqual(current, expected)


class BackendHardeningNewGuaranteesTests(unittest.TestCase):
    """Tests for guarantees introduced in the performance + architecture hardening pass."""

    def setUp(self) -> None:
        reset_cache()

    # ------------------------------------------------------------------ #
    # A: Shadow diff — normal analyze() must NOT invoke v1 engine inline  #
    # ------------------------------------------------------------------ #

    def test_analyze_does_not_invoke_v1_shadow_inline_when_shadow_enabled(self) -> None:
        """Even when _shadow_enabled() returns True, analyze_v1 must not be called inline."""
        with patch("app.services.rules.service._shadow_enabled", return_value=True):
            with patch("app.services.rules.legacy.analyze_v1", wraps=None) as mock_v1:
                # wraps=None means the mock returns a MagicMock; we just want call tracking
                mock_v1.side_effect = AssertionError("analyze_v1 must not be called inline")
                result = analyze("smart speaker with wifi and bluetooth")

        # Should succeed — no AssertionError
        self.assertIsNotNone(result)
        self.assertEqual(result.product_type, "smart_speaker")

    def test_shadow_diff_field_is_always_a_list(self) -> None:
        """analysis_audit.shadow_diff must always be a list (empty is acceptable)."""
        for shadow_on in (False, True):
            with self.subTest(shadow_enabled=shadow_on):
                with patch("app.services.rules.service._shadow_enabled", return_value=shadow_on):
                    result = analyze("smart speaker with wifi and bluetooth")
                self.assertIsInstance(result.analysis_audit.shadow_diff, list)

    # ------------------------------------------------------------------  #
    # B: Lazy payload generation — shapes must match typed catalog rows    #
    # ------------------------------------------------------------------  #

    def test_lazy_load_traits_returns_list_of_dicts(self) -> None:
        rows = load_traits()
        self.assertIsInstance(rows, list)
        self.assertTrue(rows)
        self.assertIn("id", rows[0])

    def test_lazy_load_products_returns_list_of_dicts(self) -> None:
        rows = load_products()
        self.assertIsInstance(rows, list)
        self.assertTrue(rows)
        self.assertIn("id", rows[0])

    def test_lazy_load_standards_returns_list_of_dicts(self) -> None:
        rows = load_standards()
        self.assertIsInstance(rows, list)
        self.assertTrue(rows)
        self.assertIn("code", rows[0])

    def test_lazy_load_genres_returns_list_of_dicts(self) -> None:
        rows = load_genres()
        self.assertIsInstance(rows, list)
        self.assertTrue(rows)

    def test_lazy_load_legislations_returns_list_of_dicts(self) -> None:
        rows = load_legislations()
        self.assertIsInstance(rows, list)
        self.assertTrue(rows)

    def test_lazy_payloads_are_stable_across_repeated_calls(self) -> None:
        traits_first = load_traits()
        traits_second = load_traits()
        # Same list object (cached) or equal contents
        self.assertEqual(traits_first, traits_second)

    # ------------------------------------------------------------------ #
    # C: Compile cache — caching must not alter matcher results            #
    # ------------------------------------------------------------------ #

    def test_compile_phrase_returns_same_object_on_repeated_call(self) -> None:
        phrase_a = _compile_phrase("smart speaker")
        phrase_b = _compile_phrase("smart speaker")
        self.assertIs(phrase_a, phrase_b)  # LRU cache hit → identical object

    def test_compile_alias_returns_same_object_on_repeated_call(self) -> None:
        alias_a = _compile_alias("smart lock", "aliases", 5)
        alias_b = _compile_alias("smart lock", "aliases", 5)
        self.assertIs(alias_a, alias_b)

    def test_compile_phrase_cache_hit_does_not_change_pattern_behaviour(self) -> None:
        phrase = _compile_phrase("wifi router")
        self.assertIsNotNone(phrase)
        assert phrase is not None
        self.assertIsNotNone(phrase.pattern.search("dual-band wifi router for home"))
        self.assertIsNone(phrase.pattern.search("bluetooth speaker"))

    def test_compile_alias_none_for_empty_string(self) -> None:
        # Empty strings should still return None (normalise produces empty)
        result = _compile_alias("", "aliases", 0)
        self.assertIsNone(result)

    # ------------------------------------------------------------------ #
    # D: Typed classifier output — extract_traits_v2_typed contract        #
    # ------------------------------------------------------------------ #

    def test_extract_traits_v2_typed_returns_classifier_traits_snapshot(self) -> None:
        snapshot = extract_traits_v2_typed("smart speaker with wifi and bluetooth")
        self.assertIsInstance(snapshot, ClassifierTraitsSnapshot)

    def test_extract_traits_v2_typed_product_type_matches_dict_path(self) -> None:
        from classifier import extract_traits
        typed = extract_traits_v2_typed("smart speaker with wifi and bluetooth")
        legacy = extract_traits("smart speaker with wifi and bluetooth")

        self.assertEqual(typed.product_type, legacy.get("product_type"))
        self.assertEqual(typed.product_match_stage, legacy.get("product_match_stage"))

    def test_extract_traits_v2_typed_confirmed_traits_populated(self) -> None:
        snapshot = extract_traits_v2_typed("smart lock with wifi and bluetooth")
        self.assertIsInstance(snapshot.confirmed_traits, list)
        self.assertIsInstance(snapshot.explicit_traits, list)
        self.assertIsInstance(snapshot.product_candidates, list)

    def test_extract_traits_v2_typed_flows_through_pipeline_without_error(self) -> None:
        """Typed snapshot from extract_traits_v2_typed must produce a valid analysis result."""
        from app.services.rules.routing import _prepare_analysis, _select_legislation_routes

        prepared = _prepare_analysis("smart speaker with wifi and bluetooth", "", "standard")
        routes = _select_legislation_routes(prepared, None)

        self.assertIsInstance(prepared.traits_data, ClassifierTraitsSnapshot)
        self.assertIn("RED", routes.detected_directives)


if __name__ == "__main__":
    unittest.main()
