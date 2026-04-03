from __future__ import annotations

from .base import family_case, subtype_case

GROUP = "networking"

CASES = (
    subtype_case(GROUP, "five_g_home_gateway", "5g home gateway with wifi 6 and ethernet", "5g_home_gateway"),
    subtype_case(GROUP, "bluetooth_tracker_tag", "bluetooth tracker tag for keys", "bluetooth_tracker"),
    subtype_case(GROUP, "iot_gateway_modbus", "iot gateway with modbus and ethernet", "iot_gateway"),
    subtype_case(GROUP, "lora_gateway_industrial", "lora gateway with ethernet backhaul", "lora_gateway"),
    subtype_case(GROUP, "mesh_wifi_system", "mesh router system with tri band wifi 6", "mesh_wifi_system"),
    subtype_case(GROUP, "modem_cable", "cable modem with docsis and ethernet", "modem"),
    family_case(GROUP, "network_switch_managed", "managed network switch with 8 ethernet ports", "networking_device", forbidden_subtypes=("poe_injector",), tags=("boundary",)),
    subtype_case(GROUP, "poe_injector_midspan", "power over ethernet injector midspan adapter", "poe_injector", forbidden_subtypes=("network_switch",), tags=("accessory",)),
    subtype_case(GROUP, "poe_injector_for_access_point", "poe injector for ceiling access point", "poe_injector", forbidden_subtypes=("wireless_access_point",), tags=("relation", "accessory")),
    subtype_case(GROUP, "router_dual_band", "dual band wifi router with app control", "router"),
    family_case(GROUP, "satellite_terminal_remote", "vsat satellite terminal", "networking_device", tags=("boundary",)),
    subtype_case(GROUP, "smart_relay_din", "smart relay for din rail automation", "smart_relay"),
    subtype_case(GROUP, "smart_switch_matter", "smart wall switch with matter and thread", "smart_switch"),
    subtype_case(GROUP, "voip_dect_phone", "voip dect phone with base station", "voip_dect_phone"),
    subtype_case(GROUP, "wifi_extender_dual_band", "wifi range extender with dual band support", "wifi_extender"),
    subtype_case(GROUP, "wireless_access_point_ceiling", "ceiling wireless access point with poe", "wireless_access_point"),
    family_case(
        GROUP,
        "network_switch_with_poe_injector",
        "network switch with poe injector",
        "networking_device",
        forbidden_subtypes=("poe_injector",),
        tags=("contrastive", "relation", "boundary"),
    ),
)
