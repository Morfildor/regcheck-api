from __future__ import annotations

from . import traits as _traits
from .matching import (
    ProductMatchingSnapshot,
    _select_matched_products,
    _shortlist_product_matchers_v2,
    build_product_matching_snapshot,
)
from .normalization import normalize
from .scoring import ENGINE_VERSION
from .traits import _known_trait_ids, extract_traits, extract_traits_v1, extract_traits_v2, reset_classifier_cache

TRAIT_IDS_CACHE: set[str] | None


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
