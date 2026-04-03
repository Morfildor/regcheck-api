from __future__ import annotations

from .base import subtype_case

GROUP = "climate_water"

CASES = (
    subtype_case(GROUP, "air_cleaner_uv", "room air cleaner unit with washable prefilter", "air_cleaner"),
    subtype_case(GROUP, "air_purifier_hepa", "air purifier with hepa filter and app", "air_purifier"),
    subtype_case(GROUP, "fan_pedestal", "pedestal fan with oscillation", "fan"),
    subtype_case(GROUP, "fan_heater_portable", "portable fan heater with ceramic element", "fan_heater"),
    subtype_case(GROUP, "heat_pump_domestic", "domestic heat pump for space heating", "heat_pump"),
    subtype_case(GROUP, "humidifier_ultrasonic", "ultrasonic humidifier with mist output control", "humidifier"),
    subtype_case(GROUP, "hvac_humidifier_duct", "duct mounted hvac humidifier for whole home system", "hvac_humidifier"),
    subtype_case(GROUP, "immersion_heater_water", "immersion heater for water tank", "immersion_heater"),
    subtype_case(GROUP, "portable_air_conditioner_wifi", "portable air conditioner with wifi app", "portable_air_conditioner"),
    subtype_case(GROUP, "room_dehumidifier_tank", "room dehumidifier with condensate tank", "room_dehumidifier"),
    subtype_case(GROUP, "room_heater_ceramic", "ceramic room heater with thermostat", "room_heater"),
    subtype_case(GROUP, "smart_air_quality_monitor", "smart air quality monitor with co2 and pm sensors", "smart_air_quality_monitor"),
    subtype_case(GROUP, "smart_radiator_valve", "smart radiator valve with zigbee and app control", "smart_radiator_valve"),
)
