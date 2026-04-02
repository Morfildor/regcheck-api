from __future__ import annotations

import logging
from collections.abc import Mapping
from typing import Any

from pydantic import ValidationError

from app.core.degradation import DegradationCollector, guarded_step
from app.domain.models import KnowledgeBaseMeta, ProductMatchAudit, StandardAuditItem, StandardMatchAudit
from app.services.knowledge_base import load_meta
from app.services.standards_engine.contracts import ItemsAudit

from .contracts import ClassifierTraitsSnapshot
from .routing import ENGINE_VERSION

logger = logging.getLogger(__name__)


def _build_standard_match_audit(
    items_audit: ItemsAudit | Mapping[str, Any],
    context_tags: set[str],
) -> StandardMatchAudit:
    if isinstance(items_audit, ItemsAudit):
        selected = items_audit.selected
        review = items_audit.review
        rejected = items_audit.rejected
    else:
        selected = [StandardAuditItem.model_validate(item) for item in items_audit.get("selected", [])]
        review = [StandardAuditItem.model_validate(item) for item in items_audit.get("review", [])]
        rejected = [StandardAuditItem.model_validate(item) for item in items_audit.get("rejected", [])]
    return StandardMatchAudit(
        engine_version=ENGINE_VERSION,
        context_tags=sorted(context_tags),
        selected=selected,
        review=review,
        rejected=rejected,
    )


def _safe_product_match_audit(
    traits_data: ClassifierTraitsSnapshot | Mapping[str, Any],
    normalized_description: str,
) -> ProductMatchAudit:
    raw: Mapping[str, object] | None
    if isinstance(traits_data, ClassifierTraitsSnapshot):
        raw = traits_data.product_match_audit_payload
    else:
        payload = traits_data.get("product_match_audit") or traits_data.get("audit")
        raw = payload if isinstance(payload, Mapping) else None
    if raw is not None:
        try:
            return ProductMatchAudit.model_validate(raw)
        except (ValidationError, TypeError, ValueError):
            logger.exception("analysis_degraded step=product_match_audit")
    return ProductMatchAudit(engine_version=ENGINE_VERSION, normalized_text=normalized_description)


def _safe_knowledge_base_meta(
    degraded_reasons: list[str],
    warnings: list[str],
) -> KnowledgeBaseMeta:
    collector = DegradationCollector(degraded_reasons, warnings)
    return guarded_step(
        logger=logger,
        collector=collector,
        step="knowledge_base_meta",
        reason="knowledge_base_meta_unavailable",
        warning="Catalog metadata could not be loaded during result assembly; core analysis remains available.",
        fallback=KnowledgeBaseMeta(),
        operation=lambda: KnowledgeBaseMeta(**load_meta()),
        handled_exceptions=(ValidationError, TypeError, ValueError, RuntimeError),
    )


__all__ = [
    "_build_standard_match_audit",
    "_safe_knowledge_base_meta",
    "_safe_product_match_audit",
]
