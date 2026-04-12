from __future__ import annotations

from .base import ambiguous_case, subtype_case

GROUP = "household_core"

_SUBTYPE_CASES = (
    ("portable_induction_hot_plate", "portable induction hot plate", "induction_hot_plate", ("contrastive",), ("organic",)),
    ("countertop_induction_cooker_single_plate", "countertop induction cooker single plate", "induction_hot_plate", ("contrastive",), ("paraphrase",)),
    ("single_zone_induction_hot_plate", "single zone induction hot plate", "induction_hot_plate", ("contrastive",), ("organic",)),
    ("compact_induction_cooker", "compact induction cooker", "induction_hot_plate", ("contrastive",), ("organic",)),
    ("portable_induction_cooker", "portable induction cooker", "induction_hot_plate", ("contrastive",), ("paraphrase",)),
    ("countertop_induction_hob", "countertop induction hob", "induction_hot_plate", ("contrastive",), ("organic",)),
    ("single_plate_induction_hob", "single plate induction cooker", "induction_hot_plate", ("contrastive",), ("paraphrase",)),
    ("desktop_induction_hotplate", "desktop induction cooker hot plate", "induction_hot_plate", ("contrastive",), ("organic",)),
    ("compact_countertop_induction_burner", "countertop induction hot plate burner", "induction_hot_plate", ("contrastive",), ("organic",)),
    ("portable_countertop_induction_cooker", "portable countertop induction cooker", "induction_hot_plate", ("contrastive",), ("organic",)),
    ("portable_single_zone_induction_cooker", "portable single zone induction cooker", "induction_hot_plate", ("contrastive",), ("paraphrase",)),
    ("portable_hot_plate_cooker", "portable hot plate cooker", "induction_hot_plate", ("contrastive",), ("organic",)),
)

_AMBIGUOUS_CASES = (
    ("countertop_cooking_device", "countertop cooking device", ("boundary", "contrastive"), ("adversarial",)),
    ("single_plate_cooker", "single plate cooker", ("boundary", "contrastive"), ("adversarial",)),
    ("compact_countertop_cooker", "compact countertop cooker", ("boundary", "contrastive"), ("adversarial",)),
    ("portable_cooker_module", "portable cooker module", ("boundary", "contrastive"), ("adversarial",)),
    ("single_plate_appliance", "single plate appliance", ("boundary", "contrastive"), ("adversarial",)),
    ("compact_hot_unit", "compact hot unit", ("boundary", "contrastive"), ("adversarial",)),
)

CASES = tuple(
    subtype_case(GROUP, name, description, expected_subtype, tags=tags, modes=modes)
    for name, description, expected_subtype, tags, modes in _SUBTYPE_CASES
) + tuple(
    ambiguous_case(GROUP, name, description, tags=tags, modes=modes)
    for name, description, tags, modes in _AMBIGUOUS_CASES
)
