from __future__ import annotations

from contextlib import redirect_stdout
import io
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

from knowledge_base import KnowledgeBaseError, get_knowledge_base_snapshot, reset_cache, warmup_knowledge_base
from scripts import catalog_audit

from app.services.knowledge_base.product_normalization import normalize_product_row
from app.services.knowledge_base.taxonomy import resolve_product_taxonomy, validate_product_taxonomy_row
from app.services.rules.route_anchors import resolve_route_anchor


class TaxonomyGovernanceTests(unittest.TestCase):
    def setUp(self) -> None:
        reset_cache()

    def test_resolve_product_taxonomy_requires_explicit_compatibility_for_unknown_products(self) -> None:
        strict = resolve_product_taxonomy(
            product_id="legacy_unknown_device",
            declared_family=None,
            declared_subfamily=None,
            allow_legacy_fallback=False,
        )
        self.assertIsNone(strict.family)
        self.assertIsNone(strict.subfamily)
        self.assertEqual(strict.family_source, "missing")
        self.assertEqual(strict.subfamily_source, "missing")
        self.assertFalse(strict.compatibility_fallback_used)

        compatibility = resolve_product_taxonomy(
            product_id="legacy_unknown_device",
            declared_family=None,
            declared_subfamily=None,
            allow_legacy_fallback=True,
        )
        self.assertEqual(compatibility.family, "legacy_unknown_device")
        self.assertEqual(compatibility.subfamily, "legacy_unknown_device")
        self.assertEqual(compatibility.family_source, "compatibility_product_id")
        self.assertEqual(compatibility.subfamily_source, "compatibility_product_id")
        self.assertTrue(compatibility.compatibility_fallback_used)
        self.assertIn("compatibility_family_fallback", compatibility.issues)
        self.assertIn("compatibility_subfamily_fallback", compatibility.issues)

    def test_normalization_preserves_declared_taxonomy_and_route_anchor(self) -> None:
        normalized = normalize_product_row(
            {
                "id": "smart_lock",
                "label": "Smart lock",
                "aliases": ["smart lock"],
                "genres": ["building_hardware_lock"],
                "product_family": "building_hardware_lock",
                "product_subfamily": "smart_lock",
                "route_anchor": "building_access",
                "route_family": "building_hardware",
                "implied_traits": ["consumer", "electrical", "electronic", "bluetooth"],
                "likely_standards": ["EN 14846"],
            },
            allow_legacy_family_fallback=False,
        )

        self.assertEqual(normalized["product_family"], "building_hardware_lock")
        self.assertEqual(normalized["product_subfamily"], "smart_lock")
        self.assertEqual(normalized["route_anchor"], "building_access")
        self.assertEqual(normalized["route_family"], "building_hardware")
        self.assertEqual(normalized["family_resolution_source"], "declared")
        self.assertEqual(normalized["subfamily_resolution_source"], "declared")
        self.assertEqual(normalized["route_anchor_source"], "declared")
        self.assertFalse(normalized["compatibility_fallback_used"])

    def test_normalization_marks_compatibility_fallback_debt_for_legacy_products(self) -> None:
        normalized = normalize_product_row(
            {
                "id": "legacy_unknown_device",
                "label": "Legacy unknown device",
                "aliases": ["legacy unknown device"],
                "genres": ["av_ict_device"],
                "implied_traits": ["consumer", "electrical", "electronic", "av_ict"],
                "likely_standards": ["EN 62368-1"],
            },
            allow_legacy_family_fallback=True,
        )

        self.assertEqual(normalized["product_family"], "legacy_unknown_device")
        self.assertEqual(normalized["product_subfamily"], "legacy_unknown_device")
        self.assertEqual(normalized["family_resolution_source"], "compatibility_product_id")
        self.assertEqual(normalized["subfamily_resolution_source"], "compatibility_product_id")
        self.assertTrue(normalized["compatibility_fallback_used"])
        self.assertIn("compatibility_fallback", normalized["inference_debt_flags"])
        self.assertEqual(normalized["route_anchor_source"], "scored")

    def test_route_anchor_scoring_exposes_boundary_reasons_for_ups(self) -> None:
        products = {row["id"]: row.as_legacy_dict() for row in get_knowledge_base_snapshot().products}
        decision = resolve_route_anchor(products["ups"])

        self.assertEqual(decision.anchor, "power_system_boundary")
        self.assertEqual(decision.route_family, "power_system_boundary")
        self.assertEqual(decision.source, "declared")
        self.assertEqual(decision.boundary_decision.boundary_class, "power_system")
        self.assertEqual(decision.boundary_decision.confidence_cap, "low")
        self.assertTrue(decision.boundary_decision.concise_reason)
        self.assertIn("boundary prefers power_system_boundary", decision.reasons)

    def test_validate_product_taxonomy_row_rejects_disallowed_route_anchor(self) -> None:
        with self.assertRaisesRegex(KnowledgeBaseError, "is not allowed for taxonomy family"):
            validate_product_taxonomy_row(
                {
                    "id": "smart_lock",
                    "label": "Smart lock",
                    "product_family": "building_hardware_lock",
                    "product_subfamily": "smart_lock",
                    "route_anchor": "avict_core",
                    "route_family": "av_ict",
                }
            )

    def test_taxonomy_validation_rejects_unknown_required_trait_in_config(self) -> None:
        source_dir = Path(__file__).resolve().parents[1] / "data"
        with tempfile.TemporaryDirectory() as tmpdir:
            temp_data_dir = Path(tmpdir) / "data"
            shutil.copytree(source_dir, temp_data_dir)
            families_path = temp_data_dir / "taxonomy" / "families.yaml"
            original = families_path.read_text(encoding="utf-8")
            families_path.write_text(
                original.replace("  - safety_function", "  - invented_required_trait", 1),
                encoding="utf-8",
            )

            with patch.dict("os.environ", {"REGCHECK_DATA_DIR": str(temp_data_dir)}):
                reset_cache()
                with self.assertRaisesRegex(KnowledgeBaseError, "invented_required_trait"):
                    warmup_knowledge_base(refresh_paths=True)


class CatalogAuditGovernanceTests(unittest.TestCase):
    def setUp(self) -> None:
        reset_cache()

    def test_catalog_audit_taxonomy_json_exposes_governance_sections(self) -> None:
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            exit_code = catalog_audit.run(
                "taxonomy",
                minimum_aliases=4,
                broad_alias_threshold=3,
                by_file=True,
                json_output=True,
            )

        self.assertEqual(exit_code, 0)
        payload = json.loads(buffer.getvalue())
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["command"], "taxonomy")
        self.assertEqual(payload["taxonomy"]["inferred_families"], [])
        self.assertEqual(payload["taxonomy"]["inferred_subfamilies"], [])
        self.assertEqual(payload["taxonomy"]["weak_family_support"], [])
        self.assertIn("taxonomy_cluster_mismatches", payload["by_file"])

    def test_catalog_audit_route_governance_json_exposes_family_distribution(self) -> None:
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            exit_code = catalog_audit.run(
                "route-governance",
                minimum_aliases=4,
                broad_alias_threshold=3,
                by_family=True,
                json_output=True,
            )

        self.assertEqual(exit_code, 0)
        payload = json.loads(buffer.getvalue())
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["command"], "route-governance")
        self.assertEqual(payload["route_governance"]["inferred_route_anchors"], [])
        self.assertTrue(
            any(row.startswith("life_safety_alarm:") for row in payload["route_governance"]["by_family"])
        )

    def test_catalog_audit_inference_debt_json_reports_family_level_only_rows(self) -> None:
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            exit_code = catalog_audit.run(
                "inference-debt",
                minimum_aliases=4,
                broad_alias_threshold=3,
                by_file=True,
                json_output=True,
            )

        self.assertEqual(exit_code, 0)
        payload = json.loads(buffer.getvalue())
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["command"], "inference-debt")
        self.assertEqual(payload["inference_debt"]["compatibility_fallbacks"], [])
        self.assertIn("ups: family_level_only", payload["inference_debt"]["family_level_only"])
        self.assertIn("inference_debt_rows", payload["by_file"])


if __name__ == "__main__":
    unittest.main()
