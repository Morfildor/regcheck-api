from __future__ import annotations

from .base import ambiguous_case, family_case, subtype_case

GROUP = "power_charging"

_SUBTYPE_CASES = (
    ("load_balancing_meter_for_wallbox_charger", "load balancing meter for wallbox charger", "ev_energy_module", ("companion", "contrastive"), ("organic",)),
    ("load_balancing_meter", "load balancing meter", "ev_energy_module", ("companion", "contrastive"), ("paraphrase",)),
    ("din_rail_wallbox_meter_module", "din rail wallbox meter module", "ev_energy_module", ("companion", "contrastive"), ("paraphrase",)),
    ("wallbox_load_balancing_module", "wallbox load balancing module", "ev_energy_module", ("companion",), ("organic",)),
    ("wallbox_load_balancing_meter_module", "wallbox load balancing meter module", "ev_energy_module", ("companion",), ("paraphrase",)),
    ("ev_energy_meter_module", "ev energy meter module", "ev_energy_module", ("companion",), ("paraphrase",)),
    ("ev_power_meter_module", "ev power meter module", "ev_energy_module", ("companion",), ("organic",)),
    ("smart_ev_load_balancer", "smart ev load balancer din rail", "ev_energy_module", ("companion",), ("paraphrase",)),
    ("ev_load_management_module", "ev load management module", "ev_energy_module", ("companion", "relation"), ("organic",)),
    ("load_balancing_meter_wallbox_module", "wallbox load balancing meter module", "ev_energy_module", ("companion",), ("organic",)),
)

_FAMILY_CASES = (
    ("smart_meter_display_for_home_battery_system", "smart meter display for home battery system", "energy_power_system", ("family_only", "companion", "boundary"), ("organic",)),
    ("home_battery_energy_display", "home battery energy display", "energy_power_system", ("family_only", "companion", "boundary"), ("paraphrase",)),
    ("inverter_storage_display", "inverter storage display", "energy_power_system", ("family_only", "companion", "boundary"), ("organic",)),
    ("energy_monitor_gateway_for_inverter_storage", "energy monitor gateway for inverter storage", "energy_power_system", ("family_only", "companion", "boundary"), ("organic",)),
    ("smart_meter_gateway_for_distribution_board", "smart meter gateway for distribution board", "energy_power_system", ("family_only", "companion", "boundary"), ("paraphrase",)),
    ("utility_meter_gateway_module", "utility meter gateway module", "energy_power_system", ("family_only", "companion", "boundary"), ("organic",)),
    ("din_rail_energy_gateway", "din rail energy gateway", "energy_power_system", ("family_only", "companion", "boundary"), ("paraphrase",)),
    ("home_battery_gateway", "home battery gateway", "energy_power_system", ("family_only", "companion", "boundary"), ("organic",)),
    ("smart_meter_display_unit", "smart meter display unit", "energy_power_system", ("family_only", "companion", "boundary"), ("paraphrase",)),
    ("ups_companion_control_unit", "ups companion control unit", "energy_power_system", ("family_only", "companion", "boundary"), ("organic",)),
    ("ups_battery_backup_controller", "ups battery backup controller", "energy_power_system", ("family_only", "companion", "boundary"), ("organic",)),
    ("inverter_storage_gateway", "inverter storage gateway", "energy_power_system", ("family_only", "companion", "boundary"), ("paraphrase",)),
    ("energy_gateway_for_home_battery", "energy gateway for home battery system", "energy_power_system", ("family_only", "companion", "relation"), ("organic",)),
    ("smart_meter_consumer_unit", "smart meter consumer unit", "energy_power_system", ("family_only", "companion", "boundary"), ("organic",)),
    ("home_area_network_display", "home area network display", "energy_power_system", ("family_only", "companion", "boundary"), ("paraphrase",)),
    ("home_energy_monitor_unit", "home energy monitor unit", "energy_power_system", ("family_only", "boundary"), ("organic",)),
    ("charger_companion_module", "charger companion module for wallbox", "energy_power_system", ("family_only", "companion", "boundary"), ("organic",)),
    ("din_rail_energy_meter_for_ev_charger", "din rail energy meter for ev charger", "energy_power_system", ("family_only", "companion", "boundary"), ("organic",)),
)

_AMBIGUOUS_CASES = (
    ("smart_power_module", "smart power module", ("boundary", "contrastive"), ("adversarial",)),
    ("charger_meter_display", "charger meter display", ("boundary", "contrastive"), ("adversarial",)),
)

CASES = tuple(
    subtype_case(GROUP, name, description, expected_subtype, tags=tags, modes=modes)
    for name, description, expected_subtype, tags, modes in _SUBTYPE_CASES
) + tuple(
    family_case(GROUP, name, description, expected_family, tags=tags, modes=modes)
    for name, description, expected_family, tags, modes in _FAMILY_CASES
) + tuple(
    ambiguous_case(GROUP, name, description, tags=tags, modes=modes)
    for name, description, tags, modes in _AMBIGUOUS_CASES
)
