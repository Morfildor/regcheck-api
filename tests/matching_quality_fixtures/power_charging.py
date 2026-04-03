from __future__ import annotations

from .base import ambiguous_case, family_case, subtype_case

GROUP = "power_charging"

CASES = (
    subtype_case(GROUP, "battery_charger_desktop", "desktop battery charger with charging cradle", "battery_charger"),
    subtype_case(GROUP, "external_power_supply_adapter", "24v external power supply adapter for monitor", "external_power_supply"),
    family_case(GROUP, "home_battery_system", "home battery system with inverter and backup power", "energy_power_system", tags=("boundary",)),
    family_case(GROUP, "industrial_charger", "industrial battery charger for forklift packs", "portable_power_charger", tags=("boundary",)),
    subtype_case(GROUP, "portable_power_station", "portable power station with ac outlet and battery pack", "portable_power_station"),
    subtype_case(GROUP, "power_bank_usb_c", "usb c power bank with fast charging", "power_bank"),
    subtype_case(GROUP, "smart_power_strip", "smart power strip with wifi outlets", "smart_power_strip"),
    subtype_case(GROUP, "travel_adapter_charger", "travel adapter charger with usb c pd", "travel_adapter_charger"),
    family_case(GROUP, "usb_charging_hub", "usb charging station with pd charger", "portable_power_charger", tags=("boundary",)),
    subtype_case(GROUP, "usb_wall_charger_pd", "65w usb c wall charger with power delivery", "usb_wall_charger"),
    subtype_case(GROUP, "wireless_charger_magnetic", "wireless charging pad with magnetic alignment", "wireless_charger"),
    family_case(GROUP, "ups_battery_backup", "ups battery backup unit for office server", "energy_power_system", tags=("boundary",)),
    family_case(
        GROUP,
        "portable_charger_for_ebike_battery",
        "portable charger for ebike battery",
        "portable_power_charger",
        forbidden_subtypes=("power_bank", "electric_bicycle"),
        tags=("relation", "family_only"),
    ),
    family_case(
        GROUP,
        "ups_battery_backup_for_router_nas",
        "ups battery backup for router and nas",
        "energy_power_system",
        forbidden_subtypes=("router", "network_attached_storage"),
        tags=("relation", "boundary"),
    ),
    ambiguous_case(
        GROUP,
        "solar_gate_controller",
        "controller for solar gate",
        tags=("contrastive", "relation"),
    ),
)
