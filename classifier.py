from __future__ import annotations

from app.services import classifier as _classifier
from app.services.classifier import traits as _traits

ENGINE_VERSION = _classifier.ENGINE_VERSION
ProductMatchingSnapshot = _classifier.ProductMatchingSnapshot
build_product_matching_snapshot = _classifier.build_product_matching_snapshot
extract_traits = _classifier.extract_traits
extract_traits_v1 = _classifier.extract_traits_v1
extract_traits_v2 = _classifier.extract_traits_v2
normalize = _classifier.normalize
_select_matched_products = _classifier._select_matched_products
_shortlist_product_matchers_v2 = _classifier._shortlist_product_matchers_v2
TRAIT_IDS_CACHE: set[str] | None


def _known_trait_ids() -> set[str]:
    return _classifier._known_trait_ids()


def reset_classifier_cache() -> None:
    _classifier.reset_classifier_cache()


def __getattr__(name: str):
    if name == "TRAIT_IDS_CACHE":
        return _traits.TRAIT_IDS_CACHE
    raise AttributeError(name)


__all__ = [
    "ENGINE_VERSION",
    "ProductMatchingSnapshot",
    "TRAIT_IDS_CACHE",
    "_known_trait_ids",
    "_select_matched_products",
    "_shortlist_product_matchers_v2",
    "build_product_matching_snapshot",
    "extract_traits",
    "extract_traits_v1",
    "extract_traits_v2",
    "normalize",
    "reset_classifier_cache",
]
