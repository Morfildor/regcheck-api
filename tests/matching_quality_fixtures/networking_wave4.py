from __future__ import annotations

from .base import family_case, subtype_case

GROUP = "networking"

_SUBTYPE_CASES = (
    ("ceiling_wireless_access_point_poe_injector", "ceiling wireless access point with poe injector", "wireless_access_point", ("relation",), ("adversarial",)),
    ("small_office_router_dual_band", "small office router with dual band wifi", "router", ("boundary",), ("paraphrase",)),
    ("mesh_wifi_kit_whole_home", "mesh wifi kit for whole home coverage", "mesh_wifi_system", ("boundary",), ("organic",)),
    ("plug_in_wifi_repeater_extender", "plug in wifi repeater extender", "wifi_extender", ("boundary",), ("organic",)),
    ("iot_gateway_modbus_sensors", "iot gateway for modbus sensors", "iot_gateway", ("relation",), ("adversarial",)),
    ("din_rail_smart_relay_app_control", "din rail smart relay with app control", "smart_relay", ("boundary",), ("paraphrase",)),
    ("matter_smart_wall_switch_lighting", "matter smart wall switch for lighting", "smart_switch", ("relation",), ("adversarial",)),
    ("docsis_cable_modem_broadband", "docsis cable modem for broadband", "modem", ("boundary",), ("paraphrase",)),
    ("ceiling_mount_access_point_wifi6", "ceiling mount access point wifi 6", "wireless_access_point", ("boundary",), ("paraphrase",)),
    ("poe_injector_ceiling_camera_ap", "poe injector for ceiling camera access point", "poe_injector", ("relation", "accessory"), ("adversarial",)),
    ("dect_phone_base_station_voip", "dect phone base station for voip desk", "voip_dect_phone", ("relation",), ("organic",)),
    ("lora_gateway_ethernet_backhaul", "lora gateway with ethernet backhaul", "lora_gateway", ("boundary",), ("paraphrase",)),
    ("bluetooth_tracker_tag_luggage", "bluetooth tracker tag for luggage", "bluetooth_tracker", ("boundary",), ("organic",)),
    ("five_g_cpe_gateway_wifi6", "5g cpe gateway with wifi 6", "5g_home_gateway", ("boundary",), ("paraphrase",)),
)

_FAMILY_CASES = (
    ("poe_switch_security_cameras", "poe switch for security cameras", "networking_device", ("contrastive", "boundary"), ("adversarial",)),
    ("poe_switch_camera_uplinks", "poe switch for cameras with uplink ports", "networking_device", ("contrastive", "boundary"), ("organic",)),
    ("managed_poe_switch_ip_cameras", "managed poe switch for ip cameras", "networking_device", ("contrastive", "boundary"), ("adversarial",)),
    ("network_switch_with_poe_injector", "network switch with poe injector", "networking_device", ("contrastive", "boundary"), ("adversarial",)),
    ("ceiling_access_point_powered_by_injector", "ceiling access point powered by poe injector", "networking_device", ("contrastive", "boundary"), ("organic",)),
    ("satellite_internet_terminal_cabin", "satellite internet terminal for remote cabin", "networking_device", ("boundary",), ("organic",)),
)

CASES = tuple(
    subtype_case(GROUP, name, description, expected_subtype, tags=tags, modes=modes)
    for name, description, expected_subtype, tags, modes in _SUBTYPE_CASES
) + tuple(
    family_case(GROUP, name, description, expected_family, tags=tags, modes=modes)
    for name, description, expected_family, tags, modes in _FAMILY_CASES
)

