from __future__ import annotations

from .base import family_case, subtype_case

GROUP = "power_charging"

_SUBTYPE_CASES = (
    ("portable_power_station_camping_fridge", "portable power station for camping fridge", "portable_power_station", ("boundary",), ("adversarial",)),
    ("power_station_ac_socket_usbc", "power station with ac socket and usb c", "portable_power_station", ("boundary",), ("paraphrase",)),
    ("multi_port_charger_power_delivery", "multi port charger with power delivery", "usb_charging_hub", ("boundary",), ("adversarial",)),
    ("usb_c_wall_charger_pd65w", "usb c wall charger with power delivery 65w", "usb_wall_charger", ("boundary",), ("paraphrase",)),
    ("usb_power_adapter_wall_charger", "usb power adapter wall charger", "usb_wall_charger", ("boundary",), ("organic",)),
    ("external_power_supply_monitor", "24v external power supply adapter for monitor", "external_power_supply", ("relation",), ("paraphrase",)),
    ("external_psu_brick_display", "external power supply brick for display", "external_power_supply", ("relation",), ("organic",)),
    ("forklift_charger_traction_battery", "forklift charger for traction battery packs", "industrial_charger", ("boundary",), ("adversarial",)),
    ("industrial_charger_traction_packs", "industrial battery charger for traction packs", "industrial_charger", ("boundary",), ("paraphrase",)),
    ("power_bank_phone_laptop", "rechargeable power bank for phone and laptop", "power_bank", ("boundary",), ("organic",)),
    ("battery_charger_cradle_tool_pack", "battery charger cradle for tool pack", "battery_charger", ("relation",), ("paraphrase",)),
    ("travel_adapter_global_plugs", "travel adapter charger for global plugs", "travel_adapter_charger", ("boundary",), ("organic",)),
)

_FAMILY_CASES = (
    ("battery_backup_for_nas", "battery backup for nas", "energy_power_system", ("contrastive", "family_only"), ("adversarial",)),
    ("ups_backup_unit_for_router", "ups backup unit for router", "energy_power_system", ("contrastive", "family_only"), ("adversarial",)),
    ("ups_backup_modem_nas", "ups battery backup for modem and nas", "energy_power_system", ("relation", "family_only"), ("paraphrase",)),
    ("desktop_ups_network_rack", "desktop ups for network rack", "energy_power_system", ("boundary", "family_only"), ("organic",)),
    ("portable_charger_ebike_battery", "portable charger for ebike battery", "portable_power_charger", ("relation", "family_only"), ("adversarial",)),
    ("backup_power_unit_router", "backup power unit for router", "energy_power_system", ("relation", "family_only"), ("organic",)),
    ("home_battery_system_inverter_backup", "home battery system with inverter backup", "energy_power_system", ("boundary", "family_only"), ("paraphrase",)),
    ("uninterruptible_power_supply_nas_server", "uninterruptible power supply for nas server", "energy_power_system", ("boundary", "family_only"), ("paraphrase",)),
)

CASES = tuple(
    subtype_case(GROUP, name, description, expected_subtype, tags=tags, modes=modes)
    for name, description, expected_subtype, tags, modes in _SUBTYPE_CASES
) + tuple(
    family_case(GROUP, name, description, expected_family, tags=tags, modes=modes)
    for name, description, expected_family, tags, modes in _FAMILY_CASES
)

