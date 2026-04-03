from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class MatchingQualityCase:
    name: str
    description: str
    expected_family: str | None = None
    expected_subtype: str | None = None
    expected_stage: str | None = None
    forbidden_subtypes: tuple[str, ...] = ()


MATCHING_QUALITY_CASES: tuple[MatchingQualityCase, ...] = (
    MatchingQualityCase(
        name="usb_c_monitor_dock",
        description="USB-C monitor dock with ethernet and USB ports",
        expected_family="office_avict_peripheral",
        expected_subtype="docking_station",
        expected_stage="subtype",
        forbidden_subtypes=("monitor", "all_in_one_pc"),
    ),
    MatchingQualityCase(
        name="monitor_arm_with_usb_hub",
        description="monitor arm with integrated usb hub",
        expected_family="office_avict_peripheral",
        expected_stage="family",
        forbidden_subtypes=("docking_station", "monitor", "usb_hub"),
    ),
    MatchingQualityCase(
        name="portable_charger_for_ebike_battery",
        description="portable charger for ebike battery",
        expected_stage="ambiguous",
        forbidden_subtypes=("power_bank",),
    ),
    MatchingQualityCase(
        name="alarm_keypad_panel",
        description="home alarm keypad with keypad and display",
        expected_family="smart_home_security",
        expected_subtype="alarm_keypad_panel",
        expected_stage="subtype",
    ),
    MatchingQualityCase(
        name="wireless_microphone_receiver",
        description="wireless microphone receiver",
        expected_family="creator_office_device",
        expected_subtype="wireless_microphone_receiver",
        expected_stage="subtype",
    ),
    MatchingQualityCase(
        name="digital_signage_player",
        description="digital signage player for retail display",
        expected_family="personal_computing_device",
        expected_subtype="digital_signage_player",
        expected_stage="subtype",
        forbidden_subtypes=("smart_display",),
    ),
    MatchingQualityCase(
        name="thin_client_terminal",
        description="mini pc thin client terminal",
        expected_family="personal_computing_device",
        expected_subtype="thin_client",
        expected_stage="subtype",
        forbidden_subtypes=("desktop_pc",),
    ),
    MatchingQualityCase(
        name="smart_home_panel",
        description="wall mounted home automation panel with touchscreen",
        expected_family="smart_home_control_device",
        expected_subtype="smart_home_panel",
        expected_stage="subtype",
    ),
    MatchingQualityCase(
        name="smart_display",
        description="smart home hub display with screen and speaker",
        expected_family="smart_assistant_device",
        expected_subtype="smart_display",
        expected_stage="subtype",
    ),
    MatchingQualityCase(
        name="office_printer",
        description="home office inkjet printer with wifi",
        expected_family="office_imaging",
        expected_subtype="office_printer",
        expected_stage="subtype",
        forbidden_subtypes=("document_scanner",),
    ),
    MatchingQualityCase(
        name="document_scanner",
        description="A4 document scanner with USB",
        expected_family="office_imaging",
        expected_subtype="document_scanner",
        expected_stage="subtype",
        forbidden_subtypes=("office_printer",),
    ),
    MatchingQualityCase(
        name="ev_connector_accessory",
        description="type 2 vehicle connector tethered charging cable accessory",
        expected_family="ev_charging_equipment",
        expected_subtype="ev_connector_accessory",
        expected_stage="subtype",
        forbidden_subtypes=("portable_ev_charger",),
    ),
    MatchingQualityCase(
        name="portable_ev_charger",
        description="portable EV charger with mode 2 cable and in-cable protection device",
        expected_family="ev_charging_equipment",
        expected_subtype="portable_ev_charger",
        expected_stage="subtype",
        forbidden_subtypes=("ev_connector_accessory",),
    ),
    MatchingQualityCase(
        name="poe_injector",
        description="power over ethernet injector midspan adapter",
        expected_family="networking_device",
        expected_subtype="poe_injector",
        expected_stage="subtype",
        forbidden_subtypes=("network_switch",),
    ),
)
