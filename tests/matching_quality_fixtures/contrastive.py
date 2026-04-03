from __future__ import annotations

from .base import family_case, subtype_case

GROUP = "contrastive_relations"

CASES = (
    subtype_case(GROUP, "alarm_keypad", "alarm keypad with chime", "alarm_keypad_panel", tags=("contrastive",)),
    subtype_case(GROUP, "baby_monitor_display", "baby monitor display with camera feed", "baby_monitor", tags=("contrastive",)),
    subtype_case(GROUP, "ebike_with_charger_pair", "ebike with charger", "electric_bicycle", tags=("contrastive", "relation")),
    subtype_case(GROUP, "poe_injector_for_switch", "poe injector for switch", "poe_injector", forbidden_subtypes=("network_switch",), tags=("contrastive", "relation")),
    subtype_case(GROUP, "usb_c_dock_for_monitor_pair", "usb c dock for monitor", "docking_station", tags=("contrastive", "relation")),
    subtype_case(GROUP, "wireless_mic_receiver_pair", "wireless microphone receiver", "wireless_microphone_receiver", tags=("contrastive",)),
    subtype_case(GROUP, "charger_for_ebike_battery_pair", "charger for ebike battery", "battery_charger", forbidden_subtypes=("electric_bicycle", "power_bank"), tags=("contrastive", "relation")),
    family_case(GROUP, "monitor_arm_with_usb_hub_pair", "monitor arm with integrated usb hub", "office_avict_peripheral", forbidden_subtypes=("monitor", "usb_hub"), tags=("contrastive", "relation")),
    family_case(GROUP, "network_switch_with_injector_pair", "network switch with poe injector", "networking_device", forbidden_subtypes=("poe_injector",), tags=("contrastive", "relation")),
    family_case(GROUP, "usb_c_monitor_dock_pair", "usb c monitor dock", "office_avict_peripheral", forbidden_subtypes=("monitor",), tags=("contrastive", "relation")),
)
