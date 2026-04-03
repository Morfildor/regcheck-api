from __future__ import annotations

from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass, replace

from app.domain.models import ConfidenceLevel, ProductMatchStage

from .confusable_domains import DomainDisambiguationContext, apply_domain_role_matrices
from .matching_legacy import _select_matched_products
from .matching_runtime import (
    CompiledAlias,
    CompiledPhrase,
    CompiledProductMatcher,
    ProductMatchingSnapshot,
    _compiled_phrase_hits,
    _product_matching_snapshot,
    _shortlist_product_matchers_v2,
    build_product_matching_snapshot,
    reset_matching_cache,
)
from .models import ClassifierMatchAudit, ClassifierMatchOutcome, FamilySeedCandidate, SubtypeCandidate
from .normalization import normalize
from .relation_parsing import ProductRoleParse, parse_product_roles
from .scoring import (
    ENGINE_VERSION,
    _context_bonus,
    _matching_clues,
    _string_list,
    _trait_overlap_score,
)
from .signal_config import get_classifier_signal_snapshot


@dataclass(frozen=True, slots=True)
class MatchingTextContext:
    text: str
    signal_traits: frozenset[str]
    text_terms: frozenset[str]
    cue_hits: frozenset[str]
    role_parse: ProductRoleParse

    def has(self, *cue_names: str) -> bool:
        return any(cue_name in self.cue_hits for cue_name in cue_names)

    def hit_names(self, *cue_names: str) -> list[str]:
        return [cue_name.replace("_", " ") for cue_name in cue_names if cue_name in self.cue_hits]

    @property
    def accessory_like(self) -> bool:
        return bool(self.has(*ACCESSORY_CUE_NAMES) or self.text_terms & ACCESSORY_TERMS)

    @property
    def connected_context(self) -> bool:
        return bool(self.signal_traits & {"account", "app_control", "authentication", "bluetooth", "cloud", "ota", "radio", "wifi", "zigbee"})

    @property
    def wired_context(self) -> bool:
        return bool(self.signal_traits & {"display", "ethernet", "hdmi_interface", "office_peripheral", "usb_hub_function", "wired_networking"})

    @property
    def installation_context(self) -> bool:
        return bool(self.signal_traits & {"building_access", "fixed_installation", "smart_building"})


@dataclass(frozen=True, slots=True)
class RolePack:
    positive_cues: tuple[str, ...] = ()
    negative_cues: tuple[str, ...] = ()
    accessory_role: bool = False
    group: str | None = None


ACCESSORY_CUE_NAMES = (
    "adapter_cable_role",
    "backup_unit_role",
    "dock_role",
    "gateway_module_role",
    "hub_role",
    "mount_attachment_role",
    "receiver_role",
    "terminal_role",
)
ACCESSORY_TERMS = frozenset(
    {
        "accessory",
        "adapter",
        "arm",
        "backup",
        "bracket",
        "cable",
        "controller",
        "dock",
        "gateway",
        "hub",
        "injector",
        "keypad",
        "module",
        "mount",
        "panel",
        "reader",
        "receiver",
        "stand",
        "station",
        "terminal",
        "transmitter",
        "ups",
    }
)
HIGH_RISK_GENERIC_TERMS = frozenset(
    {
        "adapter",
        "alarm",
        "camera",
        "charger",
        "controller",
        "display",
        "gateway",
        "hub",
        "module",
        "monitor",
        "panel",
        "player",
        "receiver",
        "switch",
        "terminal",
    }
)
SECONDARY_ROLE_BASE_PENALTIES: dict[str, int] = {
    "target_device": 18,
    "controlled_device": 20,
    "charged_device": 20,
    "powered_device": 20,
    "host_device": 16,
    "mounted_on_or_for": 16,
    "integrated_feature": 16,
}
PRIMARY_ROLE_HEAD_BOOSTS: dict[str, frozenset[str]] = {
    "target_device": frozenset({"adapter", "module", "panel", "reader", "receiver", "terminal", "transmitter"}),
    "controlled_device": frozenset({"controller", "keypad", "panel"}),
    "charged_device": frozenset({"charger", "cradle", "dock"}),
    "powered_device": frozenset({"backup", "injector", "supply", "ups"}),
    "host_device": frozenset({"dock", "gateway", "hub"}),
}
PRIMARY_ROLE_MISMATCH_PENALTIES: dict[str, int] = {
    "target_device": 12,
    "controlled_device": 16,
    "charged_device": 24,
    "powered_device": 18,
    "host_device": 16,
}
RELATION_ROLE_REQUIRED_CUES: dict[str, frozenset[str]] = {
    "charged_device": frozenset({"battery_charger_role"}),
    "powered_device": frozenset({"backup_unit_role", "external_psu_role", "poe_injector_role"}),
    "host_device": frozenset({"dock_role", "gateway_module_role", "hub_role"}),
    "target_device": frozenset({"adapter_cable_role", "receiver_role", "terminal_role"}),
}

PRODUCT_ROLE_PACKS: dict[str, RolePack] = {
    "monitor": RolePack(("display_surface_role", "monitor_specific_role"), ("dock_role", "hub_role", "mount_attachment_role", "network_port_role"), False, "office_display_and_dock"),
    "docking_station": RolePack(("computer_role", "dock_role", "network_port_role", "usb_peripheral_role"), ("display_surface_role", "mount_attachment_role"), True, "office_display_and_dock"),
    "usb_hub": RolePack(("hub_role", "usb_peripheral_role"), ("display_surface_role", "mount_attachment_role"), True, "office_display_and_dock"),
    "all_in_one_pc": RolePack(("all_in_one_role", "computer_role", "display_surface_role"), ("dock_role", "hub_role", "mount_attachment_role"), False, "office_display_and_dock"),
    "power_bank": RolePack(("portable_power_role", "power_bank_role"), ("battery_charger_role", "ebike_role", "ev_charger_role", "external_psu_role"), False, "power_roles"),
    "battery_charger": RolePack(("battery_charger_role",), ("ev_connector_role", "external_psu_role", "power_bank_role"), False, "power_roles"),
    "external_power_supply": RolePack(("external_psu_role",), ("battery_charger_role", "portable_power_role"), True, "power_roles"),
    "portable_ev_charger": RolePack(("ev_charger_role", "portable_power_role"), ("ev_connector_role",), True, "power_roles"),
    "ev_connector_accessory": RolePack(("adapter_cable_role", "ev_connector_role"), ("ev_charger_role",), True, "power_roles"),
    "security_hub": RolePack(("gateway_module_role", "security_alarm_role"), ("display_surface_role",), True, "smart_display_and_panel"),
    "smart_home_panel": RolePack(("keypad_panel_role", "panel_role", "smart_home_panel_role"), ("smart_speaker_role",), True, "smart_display_and_panel"),
    "smart_display": RolePack(("display_surface_role", "smart_display_role"), ("keypad_panel_role", "security_alarm_role"), False, "smart_display_and_panel"),
    "smart_speaker": RolePack(("smart_speaker_role",), ("display_surface_role",), False, "smart_display_and_panel"),
    "alarm_keypad_panel": RolePack(("keypad_panel_role", "panel_role", "security_alarm_role"), ("smart_speaker_role",), True, "smart_display_and_panel"),
    "wireless_microphone_receiver": RolePack(("microphone_receiver_role", "receiver_role", "wireless_audio_role"), ("audio_receiver_role",), True, "audio_receivers"),
    "digital_signage_player": RolePack(("player_role", "retail_role", "signage_role"), ("smart_display_role",), False, "computing_terminals"),
    "desktop_pc": RolePack(("computer_role",), ("player_role", "signage_role", "terminal_role", "thin_client_role"), False, "computing_terminals"),
    "mini_pc": RolePack(("computer_role", "mini_pc_role"), ("player_role", "signage_role"), False, "computing_terminals"),
    "thin_client": RolePack(("computer_role", "terminal_role", "thin_client_role"), ("player_role", "signage_role"), True, "computing_terminals"),
    "network_switch": RolePack(("network_switch_role",), ("poe_injector_role",), True, "network_edge_power"),
    "poe_injector": RolePack(("poe_injector_role",), ("network_switch_role",), True, "network_edge_power"),
    "office_printer": RolePack(("printer_role",), ("scanner_role",), False, "office_imaging"),
    "document_scanner": RolePack(("scanner_role",), ("printer_role",), False, "office_imaging"),
    "multifunction_printer": RolePack(("multifunction_role", "printer_role", "scanner_role"), (), False, "office_imaging"),
}
FAMILY_ROLE_PACKS: dict[str, RolePack] = {
    "office_avict_peripheral": RolePack(("dock_role", "hub_role", "mount_attachment_role", "usb_peripheral_role"), (), True),
    "portable_power_charger": RolePack(("battery_charger_role", "external_psu_role", "portable_power_role"), (), True),
    "networking_device": RolePack(("gateway_module_role", "network_switch_role", "receiver_role"), (), True),
}
CONFUSABLE_RERANK_RULES: dict[str, dict[str, dict[str, int]]] = {
    "office_display_and_dock": {
        "computer_role": {"all_in_one_pc": 12, "docking_station": 8, "monitor": -6},
        "display_surface_role": {"all_in_one_pc": 10, "monitor": 16, "docking_station": -10, "usb_hub": -8},
        "dock_role": {"docking_station": 18, "monitor": -18, "usb_hub": 8},
        "hub_role": {"docking_station": 8, "monitor": -16, "usb_hub": 16},
        "mount_attachment_role": {"all_in_one_pc": -12, "docking_station": -12, "monitor": -22, "usb_hub": -8},
        "network_port_role": {"docking_station": 12, "monitor": -14, "usb_hub": 8},
    },
    "power_roles": {
        "battery_charger_role": {"battery_charger": 18, "external_power_supply": -10, "power_bank": -22},
        "ebike_role": {"battery_charger": 10, "power_bank": -18},
        "ev_charger_role": {"ev_connector_accessory": -18, "portable_ev_charger": 20, "power_bank": -24},
        "ev_connector_role": {"battery_charger": -10, "ev_connector_accessory": 18, "portable_ev_charger": -16},
        "external_psu_role": {"battery_charger": -10, "external_power_supply": 18, "power_bank": -12},
        "portable_power_role": {"battery_charger": -10, "portable_ev_charger": 8, "power_bank": 16},
    },
    "smart_display_and_panel": {
        "display_surface_role": {"security_hub": -10, "smart_display": 14, "smart_speaker": -12},
        "keypad_panel_role": {"alarm_keypad_panel": 20, "security_hub": 10, "smart_display": -12},
        "security_alarm_role": {"alarm_keypad_panel": 16, "security_hub": 14, "smart_display": -14},
        "smart_display_role": {"alarm_keypad_panel": -10, "smart_display": 16, "smart_home_panel": -6, "smart_speaker": -8},
        "smart_speaker_role": {"smart_display": -8, "smart_speaker": 18},
    },
    "audio_receivers": {
        "audio_receiver_role": {"wireless_microphone_receiver": -14},
        "microphone_receiver_role": {"wireless_microphone_receiver": 20},
        "wireless_audio_role": {"wireless_microphone_receiver": 12},
    },
    "computing_terminals": {
        "all_in_one_role": {"all_in_one_pc": 18},
        "computer_role": {"desktop_pc": 8, "mini_pc": 10, "thin_client": 10},
        "mini_pc_role": {"desktop_pc": -10, "mini_pc": 18, "thin_client": 6},
        "player_role": {"desktop_pc": -14, "digital_signage_player": 18, "mini_pc": -8, "thin_client": -8},
        "retail_role": {"desktop_pc": -10, "digital_signage_player": 14, "thin_client": 6},
        "signage_role": {"desktop_pc": -16, "digital_signage_player": 18, "mini_pc": -10, "thin_client": -6},
        "terminal_role": {"desktop_pc": -10, "digital_signage_player": 8, "mini_pc": -6, "thin_client": 18},
        "thin_client_role": {"desktop_pc": -14, "mini_pc": 6, "thin_client": 18},
    },
    "network_edge_power": {
        "network_switch_role": {"network_switch": 18, "poe_injector": -16},
        "poe_injector_role": {"network_switch": -16, "poe_injector": 18},
    },
    "office_imaging": {
        "multifunction_role": {"document_scanner": 6, "multifunction_printer": 18, "office_printer": 6},
        "printer_role": {"document_scanner": -14, "multifunction_printer": 10, "office_printer": 18},
        "scanner_role": {"document_scanner": 18, "multifunction_printer": 10, "office_printer": -14},
    },
}


def _build_matching_context(text: str, signal_traits: set[str], role_parse: ProductRoleParse) -> MatchingTextContext:
    cue_hits = {
        cue_name
        for cue_name, patterns in get_classifier_signal_snapshot().compiled_cue_groups.items()
        if any(pattern.search(text) for pattern in patterns)
    }
    return MatchingTextContext(
        text=text,
        signal_traits=frozenset(signal_traits),
        text_terms=frozenset(text.split()),
        cue_hits=frozenset(cue_hits),
        role_parse=role_parse,
    )


def _compiled_alias_score(text: str, alias: CompiledAlias) -> int:
    score = 0
    if alias.exact_pattern.search(text):
        score = 100 + len(alias.normalized) * 3 + len(alias.normalized.split()) * 22
        if alias.normalized == text:
            score += 80
    elif alias.gap_pattern is not None and alias.gap_pattern.search(text):
        score = 42 + len(alias.normalized.split()) * 12
    if score <= 0:
        return 0
    if alias.generic_terms:
        score -= 28 if len(alias.token_terms) == 1 else 8
    return max(score, 0)


def _best_alias_match_v2(text: str, compiled: CompiledProductMatcher) -> tuple[CompiledAlias | None, int, list[str]]:
    best_alias: CompiledAlias | None = None
    best_score = 0
    best_reasons: list[str] = []

    for alias in compiled.aliases:
        score = _compiled_alias_score(text, alias)
        if score <= 0:
            continue
        reasons = [f"matched {alias.field.replace('_', ' ')[:-1]} '{alias.raw}'"]
        if alias.specificity_bonus:
            score += alias.specificity_bonus
            reasons.append(f"alias specificity {alias.specificity_bonus:+d}")
        if alias.field_bonus:
            score += alias.field_bonus
            reasons.append(f"{alias.field} bonus {alias.field_bonus:+d}")
        if alias.generic_terms:
            reasons.append("generic alias term matched")
        if best_alias is None or score > best_score:
            best_alias = alias
            best_score = score
            best_reasons = reasons

    return best_alias, best_score, best_reasons


def _compiled_clue_score(text: str, compiled: CompiledProductMatcher) -> tuple[int, list[str], list[str], list[str], bool]:
    required_hits = _compiled_phrase_hits(text, compiled.required_clues)
    preferred_hits = _compiled_phrase_hits(text, compiled.preferred_clues)
    exclude_hits = _compiled_phrase_hits(text, compiled.exclude_clues)
    score = len(required_hits) * 28 + len(preferred_hits) * 16 - len(exclude_hits) * 36
    reasons = [f"required clue '{clue}'" for clue in required_hits]
    reasons.extend(f"preferred clue '{clue}'" for clue in preferred_hits)
    reasons.extend(f"exclude clue '{clue}'" for clue in exclude_hits)
    if compiled.required_clues and not required_hits:
        score -= 20
        reasons.append("missing required subtype clues")
    decisive = bool(required_hits or len(preferred_hits) >= 2)
    return score, reasons, required_hits + preferred_hits, exclude_hits, decisive


def _route_anchor_bonus(compiled: CompiledProductMatcher, context: MatchingTextContext) -> tuple[int, list[str]]:
    if not compiled.route_anchor:
        return 0, []
    score = 0
    reasons: list[str] = []
    if compiled.route_anchor.endswith("_connected") and context.connected_context:
        score += 12
        reasons.append(f"route anchor {compiled.route_anchor} fits connected context")
    if compiled.route_anchor.endswith("_core") and context.wired_context:
        score += 6
        reasons.append(f"route anchor {compiled.route_anchor} fits wired or local context")
    if compiled.route_anchor.startswith("ev_") and context.has("ev_charger_role", "ev_connector_role"):
        score += 10
        reasons.append(f"route anchor {compiled.route_anchor} fits EV context")
    if "building" in compiled.route_anchor and context.installation_context:
        score += 8
        reasons.append(f"route anchor {compiled.route_anchor} fits installation context")
    if compiled.route_anchor == "life_safety_alarm" and context.has("keypad_panel_role", "security_alarm_role"):
        score += 10
        reasons.append("alarm route anchor fits safety or keypad context")
    return score, reasons


def _family_prior_bonus(compiled: CompiledProductMatcher, context: MatchingTextContext, shortlist_score: int) -> tuple[int, list[str]]:
    score = min(shortlist_score, 24)
    reasons = [f"shortlist prior +{min(shortlist_score, 24)}"] if shortlist_score else []
    family_required = set(compiled.family_required_traits)
    if family_required:
        if family_required <= context.signal_traits:
            score += 12
            reasons.append("family required traits fit")
        elif not family_required & context.signal_traits:
            score -= 12
            reasons.append("family required traits absent")
    shortlist_hits = len(compiled.shortlist_traits & context.signal_traits)
    if shortlist_hits:
        score += min(shortlist_hits, 4) * 3
        reasons.append(f"family prior traits x{min(shortlist_hits, 4)}")
    if context.has("computer_role") and compiled.family == "personal_computing_device":
        score += 8
        reasons.append("computing context fits family prior")
    if context.has("retail_role", "signage_role") and compiled.family in {"creator_office_device", "personal_computing_device"}:
        score += 6
        reasons.append("retail or signage context fits family prior")
    return score, reasons


def _build_product_candidate_v2(
    context: MatchingTextContext,
    compiled: CompiledProductMatcher,
    shortlist_score: int,
    shortlist_reasons: tuple[str, ...],
) -> SubtypeCandidate | None:
    product = compiled.product
    blocked_phrases = _matching_clues(context.text, _string_list(product.get("not_when_text_contains")))
    forbidden_traits = set(_string_list(product.get("forbidden_traits")))
    if forbidden_traits & context.signal_traits:
        return None

    matched_alias, alias_score, alias_reasons = _best_alias_match_v2(context.text, compiled)
    family_keyword_hits = _compiled_phrase_hits(context.text, compiled.family_keywords)
    clue_score, clue_reasons, positive_clues, negative_clues, decisive = _compiled_clue_score(context.text, compiled)
    core_traits = set(compiled.core_traits)
    default_traits = set(compiled.default_traits)
    family_traits = set(compiled.family_traits) or core_traits
    family_overlap = _trait_overlap_score(set(context.signal_traits), family_traits, weight=4)
    core_overlap = _trait_overlap_score(set(context.signal_traits), core_traits, weight=6)
    default_overlap = _trait_overlap_score(set(context.signal_traits), default_traits, weight=3)
    bonus, bonus_reasons = _context_bonus(context.text, product, set(context.signal_traits))
    route_bonus, route_reasons = _route_anchor_bonus(compiled, context)
    family_prior_bonus, family_prior_reasons = _family_prior_bonus(compiled, context, shortlist_score)

    score = alias_score + clue_score + family_overlap + core_overlap + default_overlap + bonus + route_bonus + family_prior_bonus
    score += len(family_keyword_hits) * 18
    direct_signal_count = int(matched_alias is not None) + len(positive_clues) + len(family_keyword_hits)

    score_boost_traits = set(_string_list(product.get("score_boost_if_traits")))
    score_penalty_traits = set(_string_list(product.get("score_penalty_if_traits")))
    boost_hits = sorted(score_boost_traits & context.signal_traits)
    penalty_hits = sorted(score_penalty_traits & context.signal_traits)
    required_any_traits = set(_string_list(product.get("required_any_traits")))
    required_any_missing = bool(required_any_traits and not (required_any_traits & context.signal_traits))
    score += len(boost_hits) * 8
    score -= len(penalty_hits) * 18
    score -= len(blocked_phrases) * 60
    if required_any_missing:
        score -= 18

    minimum_match_score = int(product.get("minimum_match_score", 0) or 0)
    if direct_signal_count == 0:
        return None
    if required_any_missing and matched_alias is None:
        return None
    if score < minimum_match_score:
        return None

    reasons = list(alias_reasons)
    reasons.extend(f"family keyword '{hit}'" for hit in family_keyword_hits)
    reasons.extend(clue_reasons)
    if family_overlap:
        reasons.append(f"family trait overlap +{family_overlap}")
    if core_overlap:
        reasons.append(f"product core overlap +{core_overlap}")
    if default_overlap:
        reasons.append(f"product default overlap +{default_overlap}")
    reasons.extend(f"blocked phrase '{phrase}'" for phrase in blocked_phrases)
    reasons.extend(f"metadata boost '{trait}'" for trait in boost_hits)
    reasons.extend(f"metadata penalty '{trait}'" for trait in penalty_hits)
    if required_any_missing:
        reasons.append("missing required routing traits")
    reasons.extend(route_reasons)
    reasons.extend(family_prior_reasons)
    reasons.extend(bonus_reasons)

    return SubtypeCandidate(
        id=product["id"],
        label=product.get("label", product["id"]),
        family=compiled.family,
        subtype=compiled.subtype,
        genres=tuple(_string_list(product.get("genres"))),
        product=product,
        matched_alias=matched_alias.raw if matched_alias else None,
        matched_alias_field=matched_alias.field if matched_alias else None,
        matched_alias_generic_terms=tuple(sorted(matched_alias.generic_terms)) if matched_alias else (),
        alias_hits=(matched_alias.raw,) if matched_alias else (),
        family_keyword_hits=tuple(family_keyword_hits),
        positive_clues=tuple(positive_clues),
        negative_clues=tuple(negative_clues),
        decisive=decisive or bool(matched_alias and alias_score >= 115 and not matched_alias.generic_terms) or bool(family_keyword_hits),
        score=score,
        direct_signal_count=direct_signal_count,
        reasons=tuple(reasons),
        core_traits=tuple(sorted(core_traits)),
        default_traits=tuple(sorted(default_traits)),
        family_traits=tuple(sorted(family_traits)),
        subtype_traits=tuple(_string_list(product.get("subtype_traits")) or _string_list(product.get("implied_traits"))),
        functional_classes=tuple(_string_list(product.get("functional_classes"))),
        likely_standards=tuple(_string_list(product.get("likely_standards"))),
        confusable_with=tuple(_string_list(product.get("confusable_with"))),
        route_anchor=compiled.route_anchor,
        max_match_stage=compiled.max_match_stage,
        boundary_tags=compiled.boundary_tags,
        head_phrases=tuple(phrase.normalized for phrase in compiled.head_phrases),
        head_terms=tuple(sorted(compiled.head_terms)),
        shortlist_reasons=shortlist_reasons,
    )


def _candidate_role_pack(candidate: SubtypeCandidate | FamilySeedCandidate) -> RolePack:
    subtype_candidate = candidate.representative if isinstance(candidate, FamilySeedCandidate) else candidate
    return PRODUCT_ROLE_PACKS.get(subtype_candidate.id) or FAMILY_ROLE_PACKS.get(subtype_candidate.family) or RolePack()


def _group_for_candidate(candidate: SubtypeCandidate) -> str | None:
    return _candidate_role_pack(candidate).group


def _candidate_phrase_support(candidate: SubtypeCandidate, phrase: str | None) -> int:
    if not phrase:
        return 0
    normalized_phrase = normalize(phrase)
    if not normalized_phrase:
        return 0
    candidate_phrases = set(candidate.head_phrases)
    candidate_terms = set(candidate.head_terms)
    phrase_terms = set(normalized_phrase.split())
    if normalized_phrase in candidate_phrases:
        return 3
    phrase_tail = normalized_phrase.split()[-1]
    if phrase_tail in candidate_terms:
        return 2
    if candidate_terms & phrase_terms:
        return 1
    return 0


def _candidate_matches_secondary_role(candidate: SubtypeCandidate, context: MatchingTextContext) -> bool:
    parse = context.role_parse
    for role_name in SECONDARY_ROLE_BASE_PENALTIES:
        if any(_candidate_phrase_support(candidate, phrase) >= 2 for phrase in parse.role_values(role_name)):
            return True
    return False


def _alias_only_matches_secondary_role(candidate: SubtypeCandidate, context: MatchingTextContext) -> bool:
    matched_alias = normalize(candidate.matched_alias or "")
    if not matched_alias:
        return False
    if _candidate_phrase_support(candidate, context.role_parse.primary_product_phrase) > 0:
        return False
    return any(
        matched_alias in normalize(phrase)
        for role_name in SECONDARY_ROLE_BASE_PENALTIES
        for phrase in context.role_parse.role_values(role_name)
    )


def _role_parse_adjustment(candidate: SubtypeCandidate, context: MatchingTextContext) -> tuple[int, list[str]]:
    parse = context.role_parse
    if parse.primary_product_phrase is None and parse.primary_product_head is None:
        return 0, []

    score = 0
    reasons: list[str] = []
    pack = _candidate_role_pack(candidate)
    primary_phrase_support = _candidate_phrase_support(candidate, parse.primary_product_phrase)
    primary_head_support = _candidate_phrase_support(candidate, parse.primary_product_head)
    primary_head_term_support = _candidate_phrase_support(candidate, parse.primary_product_head_term)
    primary_support = max(primary_phrase_support, primary_head_support, primary_head_term_support)

    if primary_support:
        delta = 8 + primary_support * 6
        if parse.primary_is_accessory and pack.accessory_role:
            delta += 6
            reasons.append(f"{candidate.id}: accessory-dominant wording aligned with the primary head")
        if parse.primary_head_source == "catalog_head_phrase":
            delta += 2
        score += delta
        reasons.append(f"{candidate.id}: primary head '{parse.primary_product_head}' aligned with the candidate")
    elif candidate.matched_alias_generic_terms and parse.primary_product_head:
        score -= 10
        reasons.append(f"{candidate.id}: generic role alias lacked primary-head alignment")

    if parse.primary_is_accessory and not pack.accessory_role and primary_support == 0:
        score -= 12
        reasons.append(f"{candidate.id}: accessory-dominant wording conflicted with a standalone main-device reading")

    for role_name, boosted_heads in PRIMARY_ROLE_HEAD_BOOSTS.items():
        if not parse.role_values(role_name):
            continue
        matching_heads = sorted(set(candidate.head_terms) & set(boosted_heads))
        if not matching_heads:
            continue
        delta = 10 + len(matching_heads) * 3
        if primary_support:
            delta += 4
        score += delta
        reasons.append(
            f"{candidate.id}: {role_name.replace('_', ' ')} relation reinforced primary-role wording"
        )

    for role_name in ("target_device", "controlled_device", "charged_device", "powered_device", "host_device"):
        if not parse.role_values(role_name) or role_name not in PRIMARY_ROLE_HEAD_BOOSTS:
            continue
        if set(candidate.head_terms) & set(PRIMARY_ROLE_HEAD_BOOSTS[role_name]):
            continue
        penalty = PRIMARY_ROLE_MISMATCH_PENALTIES.get(role_name, 12)
        if primary_support >= 2:
            score -= penalty
            reasons.append(
                f"{candidate.id}: {role_name.replace('_', ' ')} wording weakened a mismatched primary-role interpretation"
            )
        elif primary_support == 0:
            score -= max(8, penalty - 8)
            reasons.append(
                f"{candidate.id}: {role_name.replace('_', ' ')} mention remained secondary to the detected primary head"
            )

    for role_name, base_penalty in SECONDARY_ROLE_BASE_PENALTIES.items():
        for phrase in parse.role_values(role_name):
            support = _candidate_phrase_support(candidate, phrase)
            if support <= 0:
                continue
            penalty = base_penalty + (support - 1) * 4
            if pack.accessory_role and primary_support:
                penalty = max(6, penalty - 6)
            score -= penalty
            reasons.append(
                f"{candidate.id}: {role_name.replace('_', ' ')} mention '{phrase}' stayed secondary"
            )

    if parse.primary_head_conflict and candidate.matched_alias_generic_terms and primary_support == 0:
        score -= 8
        reasons.append(f"{candidate.id}: competing primary-head candidates kept generic role evidence ambiguous")

    return score, reasons


def _generic_alias_penalty(candidate: SubtypeCandidate, context: MatchingTextContext) -> tuple[int, list[str]]:
    if not candidate.matched_alias_generic_terms:
        return 0, []
    positive_support = len(candidate.positive_clues) + len(candidate.family_keyword_hits)
    pack = _candidate_role_pack(candidate)
    positive_hits = len(set(pack.positive_cues) & set(context.cue_hits))
    negative_hits = len(set(pack.negative_cues) & set(context.cue_hits))
    alias_token_count = len((candidate.matched_alias or "").split())
    total_penalty = 0
    reasons: list[str] = []

    for term in candidate.matched_alias_generic_terms:
        penalty = 10
        if term in HIGH_RISK_GENERIC_TERMS:
            penalty += 8
        if positive_support == 0:
            penalty += 8
        if positive_hits == 0:
            penalty += 8
        if negative_hits:
            penalty += negative_hits * 8
        if any(context.role_parse.role_values(role_name) for role_name in SECONDARY_ROLE_BASE_PENALTIES):
            penalty += 10
        if alias_token_count >= 2:
            penalty = max(4, penalty // 2)
        if candidate.matched_alias_field == "strong_aliases":
            penalty -= 4
        if candidate.direct_signal_count >= 3 or positive_hits:
            penalty -= 6
        penalty = max(penalty, 0)
        if penalty:
            total_penalty += penalty
            reasons.append(f"{candidate.id}: generic alias '{term}' lacked decisive supporting context")

    return -total_penalty, reasons


def _accessory_gate_adjustment(candidate: SubtypeCandidate, context: MatchingTextContext) -> tuple[int, list[str]]:
    if not context.accessory_like:
        return 0, []
    pack = _candidate_role_pack(candidate)
    positive_hits = set(pack.positive_cues) & set(context.cue_hits)
    negative_hits = set(pack.negative_cues) & set(context.cue_hits)
    reasons: list[str] = []
    score = 0

    if pack.accessory_role:
        if positive_hits:
            score += 6 + len(positive_hits) * 3
            reasons.append(f"{candidate.id}: accessory role fits {', '.join(sorted(positive_hits))}")
        if candidate.matched_alias_generic_terms and context.has("mount_attachment_role") and candidate.id in {"docking_station", "usb_hub"}:
            score -= 6
            reasons.append(f"{candidate.id}: attachment wording weakens subtype precision")
        return score, reasons

    if positive_hits:
        return 0, []

    score -= 18
    reasons.append(f"{candidate.id}: accessory-like description conflicts with a main-device interpretation")
    if negative_hits:
        score -= len(negative_hits) * 4
        reasons.append(f"{candidate.id}: stronger accessory cues outweighed its device role")
    return score, reasons


def _filter_candidates(candidates: Sequence[SubtypeCandidate], context: MatchingTextContext) -> tuple[list[SubtypeCandidate], list[str]]:
    kept: list[SubtypeCandidate] = []
    filtered_out: list[str] = []

    for candidate in candidates:
        pack = _candidate_role_pack(candidate)
        positive_hits = set(pack.positive_cues) & set(context.cue_hits)
        negative_hits = set(pack.negative_cues) & set(context.cue_hits)
        generic_only = bool(candidate.matched_alias_generic_terms and not candidate.positive_clues and not candidate.family_keyword_hits)
        family_required_traits = set(_string_list(candidate.product.get("family_required_traits")))

        if candidate.negative_clues and not candidate.positive_clues and candidate.matched_alias is None:
            filtered_out.append(f"{candidate.id}: excluded because only negative clues matched")
            continue
        if candidate.negative_clues and candidate.matched_alias_generic_terms:
            pack = _candidate_role_pack(candidate)
            for role_name, required_cues in RELATION_ROLE_REQUIRED_CUES.items():
                if context.role_parse.role_values(role_name) and not (required_cues & set(pack.positive_cues)):
                    filtered_out.append(
                        f"{candidate.id}: filtered because relation wording conflicted with its generic role alias"
                    )
                    break
            else:
                primary_support = max(
                    _candidate_phrase_support(candidate, context.role_parse.primary_product_phrase),
                    _candidate_phrase_support(candidate, context.role_parse.primary_product_head),
                    _candidate_phrase_support(candidate, context.role_parse.primary_product_head_term),
                )
                if primary_support:
                    kept.append(candidate)
                    continue
                if context.role_parse.primary_is_accessory and pack.accessory_role:
                    kept.append(candidate)
                    continue
                filtered_out.append(f"{candidate.id}: filtered because negative clues outweighed a generic role alias")
                continue
            continue
        if _alias_only_matches_secondary_role(candidate, context):
            filtered_out.append(f"{candidate.id}: filtered because its alias appeared only inside a secondary role phrase")
            continue
        if (
            family_required_traits
            and not (family_required_traits & context.signal_traits)
            and generic_only
            and not (candidate.matched_alias_field == "strong_aliases" and len((candidate.matched_alias or "").split()) >= 2)
        ):
            filtered_out.append(f"{candidate.id}: filtered because family-required trait context was absent")
            continue
        if generic_only and negative_hits and not positive_hits:
            filtered_out.append(f"{candidate.id}: filtered because generic alias overlap conflicted with stronger role cues")
            continue
        if generic_only and _candidate_matches_secondary_role(candidate, context):
            if context.role_parse.primary_is_accessory and _candidate_role_pack(candidate).accessory_role:
                kept.append(candidate)
                continue
            filtered_out.append(f"{candidate.id}: filtered because it only lined up with a secondary role phrase")
            continue
        if candidate.max_match_stage == "family" and candidate.score < 55 and candidate.matched_alias is None and not candidate.family_keyword_hits:
            filtered_out.append(f"{candidate.id}: filtered because boundary-only evidence stayed weak")
            continue
        if candidate.score < 30:
            filtered_out.append(f"{candidate.id}: filtered because score stayed below rerank floor")
            continue
        kept.append(candidate)

    return kept, filtered_out


def _apply_group_adjustments(group: str, group_candidates: Sequence[SubtypeCandidate], context: MatchingTextContext) -> tuple[dict[str, int], list[str]]:
    rule_map = CONFUSABLE_RERANK_RULES.get(group)
    if not rule_map:
        return {}, []

    deltas: dict[str, int] = defaultdict(int)
    reasons: list[str] = []
    for cue_name, candidate_deltas in rule_map.items():
        if cue_name not in context.cue_hits:
            continue
        for candidate in group_candidates:
            delta = candidate_deltas.get(candidate.id, 0)
            if not delta:
                continue
            deltas[candidate.id] += delta
            direction = "boosted" if delta > 0 else "down-ranked"
            reasons.append(f"{candidate.id}: {direction} by {cue_name.replace('_', ' ')}")
    return dict(deltas), reasons


def _domain_disambiguation_context(context: MatchingTextContext) -> DomainDisambiguationContext:
    parse = context.role_parse
    return DomainDisambiguationContext(
        cue_hits=context.cue_hits,
        signal_traits=context.signal_traits,
        primary_head=parse.primary_product_head,
        primary_head_term=parse.primary_product_head_term,
        primary_head_quality=parse.primary_head_quality,
        primary_head_conflict=parse.primary_head_conflict,
        primary_is_accessory=parse.primary_is_accessory,
        target_device=parse.target_device,
        controlled_device=parse.controlled_device,
        charged_device=parse.charged_device,
        powered_device=parse.powered_device,
        host_device=parse.host_device,
        integrated_feature=parse.integrated_feature,
        installation_context=parse.installation_context,
    )


def _apply_domain_disambiguation(
    candidates: Sequence[SubtypeCandidate],
    context: MatchingTextContext,
) -> tuple[list[SubtypeCandidate], list[str], list[str]]:
    adjustments = apply_domain_role_matrices(candidates, _domain_disambiguation_context(context))
    if not adjustments:
        return list(candidates), [], []

    updated: list[SubtypeCandidate] = []
    domain_reasons: list[str] = []
    confusable_reasons: list[str] = []
    for candidate in candidates:
        adjustment = adjustments.get(candidate.id)
        if adjustment is None:
            updated.append(candidate)
            continue
        updated_candidate = replace(
            candidate,
            score=candidate.score + adjustment.delta,
            reasons=candidate.reasons + adjustment.domain_role_reasons,
            rerank_reasons=candidate.rerank_reasons + adjustment.domain_role_reasons,
            domain_role_reasons=candidate.domain_role_reasons + adjustment.domain_role_reasons,
            confusable_adjustments=candidate.confusable_adjustments + adjustment.confusable_adjustments,
        )
        updated.append(updated_candidate)
        domain_reasons.extend(adjustment.domain_role_reasons)
        confusable_reasons.extend(adjustment.confusable_adjustments)
    return updated, domain_reasons, confusable_reasons


def _rerank_candidates(
    candidates: Sequence[SubtypeCandidate],
    context: MatchingTextContext,
) -> tuple[list[SubtypeCandidate], list[str], list[str], list[str], list[str]]:
    updated: dict[str, SubtypeCandidate] = {candidate.id: candidate for candidate in candidates}
    rerank_reasons: list[str] = []
    accessory_reasons: list[str] = []
    generic_penalties: list[str] = []
    confusable_domain_reasons: list[str] = []

    grouped: dict[str, list[SubtypeCandidate]] = defaultdict(list)
    for candidate in candidates:
        group = _group_for_candidate(candidate)
        if group:
            grouped[group].append(candidate)

    for group, group_candidates in grouped.items():
        deltas, reasons = _apply_group_adjustments(group, group_candidates, context)
        for candidate_id, delta in deltas.items():
            current = updated[candidate_id]
            updated[candidate_id] = replace(
                current,
                score=current.score + delta,
                reasons=current.reasons + tuple(reason for reason in reasons if reason.startswith(f"{candidate_id}:")),
                rerank_reasons=current.rerank_reasons + tuple(reason for reason in reasons if reason.startswith(f"{candidate_id}:")),
                confusable_adjustments=current.confusable_adjustments + tuple(
                    reason for reason in reasons if reason.startswith(f"{candidate_id}:")
                ),
            )
        rerank_reasons.extend(reasons)
        confusable_domain_reasons.extend(reasons)

    for candidate_id, current in list(updated.items()):
        role_delta, role_notes = _role_parse_adjustment(current, context)
        if role_delta:
            current = replace(
                current,
                score=current.score + role_delta,
                reasons=current.reasons + tuple(role_notes),
                rerank_reasons=current.rerank_reasons + tuple(role_notes),
                domain_role_reasons=current.domain_role_reasons + tuple(role_notes),
            )
            updated[candidate_id] = current
            rerank_reasons.extend(role_notes)
        penalty, reasons = _generic_alias_penalty(current, context)
        if penalty:
            current = replace(
                current,
                score=current.score + penalty,
                reasons=current.reasons + tuple(reasons),
                rerank_reasons=current.rerank_reasons + tuple(reasons),
                domain_role_reasons=current.domain_role_reasons + tuple(reasons),
            )
            updated[candidate_id] = current
            generic_penalties.extend(reasons)
        accessory_delta, accessory_notes = _accessory_gate_adjustment(current, context)
        if accessory_delta:
            updated[candidate_id] = replace(
                updated[candidate_id],
                score=updated[candidate_id].score + accessory_delta,
                reasons=updated[candidate_id].reasons + tuple(accessory_notes),
                rerank_reasons=updated[candidate_id].rerank_reasons + tuple(accessory_notes),
                domain_role_reasons=updated[candidate_id].domain_role_reasons + tuple(accessory_notes),
            )
            accessory_reasons.extend(accessory_notes)

    reranked = sorted(updated.values(), key=lambda row: (-row.score, row.id))
    return reranked, rerank_reasons, accessory_reasons, generic_penalties, confusable_domain_reasons


def _candidate_confidence_v2(
    candidate: SubtypeCandidate | FamilySeedCandidate,
    next_candidate: SubtypeCandidate | FamilySeedCandidate | None = None,
) -> ConfidenceLevel:
    score = candidate.score
    gap = score - next_candidate.score if next_candidate else score
    direct_signals = candidate.direct_signal_count
    if isinstance(candidate, FamilySeedCandidate):
        candidate = candidate.representative
    generic_only = bool(candidate.matched_alias_generic_terms and not candidate.positive_clues and not candidate.family_keyword_hits)
    if generic_only:
        score -= 12
        gap -= 4
    if score >= 150 and gap >= 16 and direct_signals >= 2:
        return "high"
    if score >= 110 and gap >= 8 and direct_signals >= 1:
        return "medium"
    if score >= 90 and direct_signals >= 2:
        return "medium"
    return "low"


def _common_strings(rows: Sequence[SubtypeCandidate], field: str) -> list[str]:
    if not rows:
        return []
    common = set(getattr(rows[0], field))
    for row in rows[1:]:
        common &= set(getattr(row, field))
    return sorted(common)


def _common_sets(rows: Sequence[SubtypeCandidate], field: str) -> set[str]:
    if not rows:
        return set()
    common = set(getattr(rows[0], field))
    for row in rows[1:]:
        common &= set(getattr(row, field))
    return common


def _top_unique(items: list[str], *, limit: int = 5) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for item in items:
        if not item or item in seen:
            continue
        seen.add(item)
        ordered.append(item)
        if len(ordered) >= limit:
            break
    return ordered


def _normalized_text_summary(text: str, *, limit: int = 160) -> str:
    if len(text) <= limit:
        return text
    return text[: limit - 3].rstrip() + "..."


def _build_empty_match_outcome(text: str, role_parse: ProductRoleParse | None = None) -> ClassifierMatchOutcome:
    return ClassifierMatchOutcome(
        product_family=None,
        product_family_confidence="low",
        product_subtype=None,
        product_subtype_confidence="low",
        product_match_stage="ambiguous",
        product_type=None,
        product_match_confidence="low",
        diagnostics=[
            "product_shortlist_candidates=0",
            f"product_shortlist_catalog={len(_product_matching_snapshot().products)}",
            "product_winner=none",
        ],
        audit=ClassifierMatchAudit(
            engine_version=ENGINE_VERSION,
            normalized_text=text,
            normalized_text_summary=_normalized_text_summary(text),
            role_parse=role_parse.to_audit() if role_parse is not None else None,
        ),
    )


def _family_level_limiter(
    context: MatchingTextContext,
    top_subtype: SubtypeCandidate,
    next_subtype: SubtypeCandidate | None,
) -> str | None:
    role_parse = context.role_parse
    explicit_limit = str(top_subtype.product.get("family_level_reason") or "").strip()
    if explicit_limit and top_subtype.max_match_stage == "family":
        return explicit_limit
    alias_token_count = len((top_subtype.matched_alias or "").split())
    if role_parse.primary_head_conflict and top_subtype.matched_alias_generic_terms and alias_token_count <= 1:
        return "Primary head candidates remained in conflict, so subtype precision stays conservative."
    if role_parse.primary_is_accessory and (
        role_parse.target_device
        or role_parse.controlled_device
        or role_parse.charged_device
        or role_parse.powered_device
        or role_parse.host_device
        or role_parse.integrated_feature
        or role_parse.mounted_on_or_for
    ):
        if next_subtype and top_subtype.score - next_subtype.score < 14:
            return "Accessory-dominant wording with secondary device context capped subtype precision."
        if top_subtype.matched_alias_generic_terms and not top_subtype.positive_clues:
            return "System or boundary accessory wording capped subtype precision."
    if context.accessory_like and _candidate_role_pack(top_subtype).accessory_role:
        if top_subtype.matched_alias_generic_terms and not top_subtype.positive_clues and not top_subtype.family_keyword_hits:
            return "Accessory-like wording is present, so subtype precision stays conservative."
        if top_subtype.negative_clues and not top_subtype.positive_clues and not top_subtype.family_keyword_hits:
            return "Accessory or attachment wording conflicted with subtype-only cues, so the result stays at family level."
        if next_subtype and top_subtype.score - next_subtype.score < 12:
            return "Accessory or attachment wording keeps the family stable but leaves subtype competition unresolved."
    if (
        top_subtype.matched_alias_generic_terms
        and alias_token_count <= 1
        and not top_subtype.positive_clues
        and len(top_subtype.family_keyword_hits) < 2
    ):
        return "Subtype evidence is driven mainly by a generic alias without decisive supporting clues."
    if next_subtype and _group_for_candidate(top_subtype) and _group_for_candidate(top_subtype) == _group_for_candidate(next_subtype) and top_subtype.score - next_subtype.score < 12:
        return "Confusable subtype candidates remained close after reranking."
    return None


def _confidence_limiter(
    context: MatchingTextContext,
    top_subtype: SubtypeCandidate,
    next_subtype: SubtypeCandidate | None,
) -> str | None:
    alias_token_count = len((top_subtype.matched_alias or "").split())
    if context.role_parse.primary_head_quality == "low" and not top_subtype.decisive:
        return "head resolution stayed weak or overly modifier-driven"
    if context.role_parse.primary_head_conflict and top_subtype.matched_alias_generic_terms and alias_token_count <= 1:
        return "primary head candidates remained conflicted"
    if top_subtype.matched_alias_generic_terms and alias_token_count <= 1 and not top_subtype.positive_clues:
        return "generic alias evidence lacked decisive supporting clues"
    if next_subtype and top_subtype.score - next_subtype.score < 8:
        return "rerank margin remained narrow"
    if context.role_parse.primary_is_accessory and not top_subtype.decisive:
        return "role parsing kept secondary object mentions below the primary product"
    if context.accessory_like and not top_subtype.decisive:
        return "accessory wording reduced subtype certainty"
    return None


def _resolve_stage(
    *,
    top_family: FamilySeedCandidate,
    next_family: FamilySeedCandidate | None,
    top_subtype: SubtypeCandidate,
    next_subtype: SubtypeCandidate | None,
    family_confidence: ConfidenceLevel,
    subtype_confidence: ConfidenceLevel,
    family_level_limiter: str | None,
) -> tuple[ProductMatchStage, str, list[str], str | None]:
    contradictions: list[str] = []
    ambiguity_reason: str | None = None
    family_gap = top_family.score - next_family.score if next_family else top_family.score
    subtype_gap = top_subtype.score - next_subtype.score if next_subtype else top_subtype.score
    close_family_competition = bool(next_family and family_gap < 8 and next_family.family != top_family.family)
    close_subtype_competition = bool(next_subtype and subtype_gap < 10)

    if close_family_competition and next_family is not None:
        ambiguity_reason = (
            f"Product identification remains ambiguous between {top_family.id.replace('_', ' ')} "
            f"and {next_family.id.replace('_', ' ')}."
        )
        contradictions.append(ambiguity_reason)
        return "ambiguous", "cross-family candidates remain too close to resolve safely", contradictions, ambiguity_reason
    if family_level_limiter:
        return "family", family_level_limiter, contradictions, family_level_limiter
    if next_subtype and top_subtype.negative_clues and next_subtype.positive_clues:
        ambiguity_reason = f"Confusable subtype clues remain unresolved within family {top_family.family.replace('_', ' ')}."
        return "family", "top subtype has exclusion clues while a close runner-up has positive subtype clues", contradictions, ambiguity_reason
    if close_subtype_competition:
        ambiguity_reason = f"Subtype evidence is too close within family {top_family.family.replace('_', ' ')}."
        return "family", "family match is stable but subtype candidates remain too close to confirm", contradictions, ambiguity_reason
    if subtype_confidence == "high" or (subtype_confidence == "medium" and top_subtype.decisive):
        return "subtype", "decisive alias or clue support confirmed the subtype", contradictions, ambiguity_reason
    if family_confidence in {"high", "medium"}:
        return "family", "family evidence is strong enough, but subtype evidence is not decisive", contradictions, ambiguity_reason
    ambiguity_reason = f"Product evidence for {top_family.label} is too weak to confirm a subtype."
    return "ambiguous", "family evidence remained below the subtype confirmation threshold", contradictions, ambiguity_reason


def _shortlist_basis(shortlist_scoring: dict[str, int], shortlist_reasons: dict[str, tuple[str, ...]]) -> list[str]:
    basis: list[str] = []
    for product_id, score in sorted(shortlist_scoring.items(), key=lambda item: (-item[1], item[0]))[:5]:
        reason = shortlist_reasons.get(product_id, ())
        if reason:
            basis.append(f"{product_id}:{score}:{reason[0]}")
        else:
            basis.append(f"{product_id}:{score}")
    return basis


def _why_not_reasons(
    candidate: SubtypeCandidate,
    winner: SubtypeCandidate,
    *,
    family_level_limiter: str | None,
) -> tuple[str, ...]:
    reasons = [f"score finished {winner.score - candidate.score} behind {winner.id}"]
    if candidate.confusable_adjustments:
        reasons.append(candidate.confusable_adjustments[0])
    elif candidate.domain_role_reasons:
        reasons.append(candidate.domain_role_reasons[0])
    elif candidate.rerank_reasons:
        reasons.append(candidate.rerank_reasons[0])
    if family_level_limiter and candidate.family == winner.family:
        reasons.append(f"winner stopped at family because: {family_level_limiter}")
    return tuple(reasons[:3])


def _hierarchical_product_match_v2(text: str, signal_traits: set[str]) -> ClassifierMatchOutcome:
    role_parse = parse_product_roles(text)
    context = _build_matching_context(text, signal_traits, role_parse)
    shortlisted_matchers, shortlist_scoring, shortlist_reasons = _shortlist_product_matchers_v2(
        text,
        signal_traits,
        include_reasons=True,
    )
    generated = [
        candidate
        for matcher in shortlisted_matchers
        if (
            candidate := _build_product_candidate_v2(
                context,
                matcher,
                shortlist_scoring.get(matcher.id, 0),
                shortlist_reasons.get(matcher.id, ()),
            )
        )
        is not None
    ]
    filtered_candidates, filtered_out = _filter_candidates(generated, context)
    disambiguated_candidates, domain_role_reasons, confusable_domain_reasons = _apply_domain_disambiguation(
        filtered_candidates, context
    )
    candidates, rerank_reasons, accessory_reasons, generic_penalties, group_confusable_reasons = _rerank_candidates(
        disambiguated_candidates, context
    )
    confusable_domain_reasons = confusable_domain_reasons + group_confusable_reasons

    if not candidates:
        outcome = _build_empty_match_outcome(text, role_parse)
        outcome.audit.shortlist_basis = _shortlist_basis(shortlist_scoring, shortlist_reasons)
        outcome.audit.filtered_out = filtered_out[:8]
        return outcome

    family_map: dict[str, FamilySeedCandidate] = {}
    for candidate in candidates:
        existing = family_map.get(candidate.family)
        if existing is None or candidate.score > existing.score:
            family_map[candidate.family] = FamilySeedCandidate(candidate.family, candidate, candidate.score)

    ordered_family_candidates = sorted(family_map.values(), key=lambda row: (-row.score, row.family))
    family_candidates = [
        replace(
            row,
            confidence=_candidate_confidence_v2(row, ordered_family_candidates[idx + 1] if idx + 1 < len(ordered_family_candidates) else None),
        )
        for idx, row in enumerate(ordered_family_candidates)
    ]
    top_family = family_candidates[0]
    next_family = family_candidates[1] if len(family_candidates) > 1 else None
    family_rows = [row for row in candidates if row.family == top_family.family]
    top_subtype = family_rows[0]
    next_subtype = family_rows[1] if len(family_rows) > 1 else None
    family_confidence: ConfidenceLevel = top_family.confidence
    subtype_confidence: ConfidenceLevel = _candidate_confidence_v2(top_subtype, next_subtype)
    family_level_limiter = _family_level_limiter(context, top_subtype, next_subtype)
    confidence_limiter = _confidence_limiter(context, top_subtype, next_subtype)
    family_stage, stage_reason, contradictions, ambiguity_reason = _resolve_stage(
        top_family=top_family,
        next_family=next_family,
        top_subtype=top_subtype,
        next_subtype=next_subtype,
        family_confidence=family_confidence,
        subtype_confidence=subtype_confidence,
        family_level_limiter=family_level_limiter,
    )

    subtype_band = [row for row in family_rows if top_subtype.score - row.score <= 12][:3]
    if family_stage == "family" and next_subtype and next_subtype.id not in {row.id for row in subtype_band}:
        subtype_band = [top_subtype, next_subtype]

    common_classes = _common_strings(subtype_band, "functional_classes")
    common_standards = _common_strings(subtype_band, "likely_standards")
    common_core_traits = _common_sets(subtype_band, "core_traits")
    common_default_traits = _common_sets(subtype_band, "default_traits")
    common_genres = _common_sets(subtype_band, "genres")

    product_core_traits = set(top_subtype.core_traits)
    product_default_traits = set(top_subtype.default_traits)
    product_genres = set(top_subtype.genres)
    functional_classes = set(top_subtype.functional_classes)
    confirmed_functional_classes: set[str] = set()
    preferred_standard_codes: list[str] = []
    confirmed_products: list[str] = []
    matched_products = [row.id for row in subtype_band]
    routing_matched_products: list[str] = []
    product_subtype = top_subtype.id if family_stage == "subtype" else None
    product_type = top_subtype.id
    product_match_confidence: ConfidenceLevel = subtype_confidence

    if family_stage == "ambiguous" and next_family is not None:
        matched_products = [top_family.id, next_family.id]
        functional_classes = set()
        product_core_traits = set()
        product_default_traits = set()
        product_genres = set()
        product_match_confidence = "low"
    elif family_stage == "family":
        functional_classes = set(common_classes)
        product_core_traits = set(common_core_traits)
        product_default_traits = set(common_default_traits)
        product_genres = set(common_genres)
        preferred_standard_codes = common_standards
        product_match_confidence = "medium" if family_confidence == "high" else family_confidence
        if family_confidence == "high":
            confirmed_functional_classes.update(common_classes)
    else:
        routing_matched_products = [top_subtype.id]
        preferred_standard_codes = list(top_subtype.likely_standards)
        if subtype_confidence == "high":
            confirmed_products = [top_subtype.id]
            confirmed_functional_classes.update(top_subtype.functional_classes)
        elif common_classes:
            confirmed_functional_classes.update(common_classes)

    if confidence_limiter and product_match_confidence == "high":
        product_match_confidence = "medium"
    public_rows = family_rows[:5]
    close_family_competition = bool(next_family and top_family.score - next_family.score < 8 and next_family.family != top_family.family)
    if close_family_competition and next_family is not None and next_family.representative not in public_rows:
        public_rows = public_rows + [next_family.representative]

    product_candidates = [
        candidate.to_public_candidate(
            confidence=_candidate_confidence_v2(candidate, public_rows[idx + 1] if idx + 1 < len(public_rows) else None),
            family_score=family_map[candidate.family].score if candidate.family in family_map else candidate.score,
        )
        for idx, candidate in enumerate(public_rows[:5])
    ]
    audit_rows = subtype_band if family_stage == "family" else [top_subtype]
    alias_hits = _top_unique([hit for row in audit_rows for hit in row.alias_hits], limit=5)
    family_keyword_hits = _top_unique([hit for row in audit_rows for hit in row.family_keyword_hits], limit=5)
    clue_hits = _top_unique([hit for row in audit_rows for hit in row.positive_clues], limit=5)
    strongest_negative_clues = _top_unique([hit for row in audit_rows for hit in row.negative_clues], limit=5)
    top_family_audit = [row.to_audit_candidate() for row in family_candidates[:3]]
    top_subtype_audit = [
        row.to_audit_candidate(
            confidence=_candidate_confidence_v2(row, candidates[idx + 1] if idx + 1 < len(candidates) else None),
            why_not_reasons=() if row.id == top_subtype.id else _why_not_reasons(row, top_subtype, family_level_limiter=family_level_limiter),
            final_stop_reason=family_level_limiter if row.id == top_subtype.id else None,
        )
        for idx, row in enumerate(candidates[:5])
    ]

    diagnostics = [
        f"product_shortlist_candidates={len(shortlisted_matchers)}",
        f"product_shortlist_catalog={len(_product_matching_snapshot().products)}",
        f"product_family={top_family.family}",
        f"product_family_confidence={family_confidence}",
        f"product_subtype_candidate={top_subtype.id}",
        f"product_subtype_confidence={subtype_confidence}",
        f"product_match_stage={family_stage}",
    ]
    if top_subtype.boundary_tags:
        diagnostics.append("product_boundary_tags=" + ",".join(sorted(top_subtype.boundary_tags)))
    if family_level_limiter:
        diagnostics.append(f"product_family_limiter={family_level_limiter}")
    if confidence_limiter:
        diagnostics.append(f"product_confidence_limiter={confidence_limiter}")

    top_row_reasons = list(top_subtype.reasons[:8])
    audit = ClassifierMatchAudit(
        engine_version=ENGINE_VERSION,
        normalized_text=text,
        normalized_text_summary=_normalized_text_summary(text),
        retrieval_basis=top_row_reasons,
        shortlist_basis=_shortlist_basis(shortlist_scoring, shortlist_reasons),
        filtered_out=filtered_out[:8],
        alias_hits=alias_hits,
        matched_aliases=alias_hits,
        family_keyword_hits=family_keyword_hits,
        clue_hits=clue_hits,
        strongest_positive_clues=clue_hits,
        strongest_negative_clues=strongest_negative_clues,
        rerank_reasons=_top_unique(rerank_reasons, limit=8),
        domain_role_disambiguation_reasons=_top_unique(domain_role_reasons, limit=8),
        confusable_domain_reasons=_top_unique(confusable_domain_reasons, limit=8),
        accessory_gate_reasons=_top_unique(accessory_reasons, limit=8),
        generic_alias_penalties=_top_unique(generic_penalties, limit=8),
        top_family_candidates=top_family_audit,
        top_subtype_candidates=top_subtype_audit,
        role_parse=role_parse.to_audit(),
        final_match_stage=family_stage,
        final_match_reason=stage_reason,
        ambiguity_reason=ambiguity_reason,
        family_level_limiter=family_level_limiter,
        confidence_limiter=confidence_limiter,
    )

    return ClassifierMatchOutcome(
        product_family=top_family.family,
        product_family_confidence=family_confidence,
        product_subtype=product_subtype,
        product_subtype_confidence=subtype_confidence,
        product_match_stage=family_stage,
        product_type=product_type,
        product_match_confidence=product_match_confidence,
        product_candidates=product_candidates,
        matched_products=matched_products,
        routing_matched_products=routing_matched_products,
        confirmed_products=confirmed_products,
        product_core_traits=product_core_traits,
        product_default_traits=product_default_traits,
        product_genres=product_genres,
        preferred_standard_codes=preferred_standard_codes,
        functional_classes=functional_classes,
        confirmed_functional_classes=confirmed_functional_classes,
        diagnostics=diagnostics,
        contradictions=contradictions,
        audit=audit,
        family_seed_candidates=family_candidates,
        subtype_candidates=candidates,
    )


__all__ = [
    "CompiledAlias",
    "CompiledPhrase",
    "CompiledProductMatcher",
    "ProductMatchingSnapshot",
    "_hierarchical_product_match_v2",
    "_select_matched_products",
    "_shortlist_product_matchers_v2",
    "build_product_matching_snapshot",
    "reset_matching_cache",
]
