from __future__ import annotations

from .base import family_case, subtype_case

GROUP = "office_peripherals"

CASES = (
    family_case(GROUP, "all_in_one_pc_touch", "all in one pc with touchscreen display", "personal_computing_device", tags=("boundary",)),
    subtype_case(GROUP, "conference_speakerphone", "conference speakerphone with local usb and bluetooth", "conference_speakerphone"),
    subtype_case(GROUP, "desktop_pc_tower", "desktop pc tower with ethernet and hdmi", "desktop_pc"),
    subtype_case(GROUP, "digital_signage_player_retail", "digital signage player for retail display", "digital_signage_player", forbidden_subtypes=("smart_display",)),
    family_case(GROUP, "document_camera_classroom", "document camera for classroom presentation", "creator_office_device", tags=("boundary",)),
    subtype_case(GROUP, "document_scanner_a4", "a4 document scanner with usb", "document_scanner", forbidden_subtypes=("office_printer",)),
    family_case(GROUP, "kvm_switch_dual_monitor", "kvm switch for dual monitor desktop setup", "office_avict_peripheral", tags=("boundary",)),
    subtype_case(GROUP, "mini_pc_compact", "mini pc with ethernet and hdmi", "mini_pc"),
    subtype_case(GROUP, "office_monitor", "27 inch computer monitor with displayport", "monitor"),
    subtype_case(GROUP, "office_printer_laser", "laser office printer with wifi", "office_printer", forbidden_subtypes=("document_scanner",)),
    subtype_case(GROUP, "presentation_clicker", "wireless presentation clicker with laser pointer", "presentation_clicker"),
    subtype_case(GROUP, "usb_c_dock_for_monitor", "usb c dock for monitor", "docking_station", forbidden_subtypes=("monitor",)),
    subtype_case(
        GROUP,
        "usb_c_monitor_dock",
        "usb c monitor dock with ethernet and usb ports",
        "docking_station",
        forbidden_subtypes=("monitor", "all_in_one_pc"),
        tags=("contrastive", "accessory", "relation"),
    ),
    family_case(
        GROUP,
        "monitor_arm_with_usb_hub",
        "monitor arm with integrated usb hub",
        "office_avict_peripheral",
        forbidden_subtypes=("docking_station", "monitor", "usb_hub"),
        tags=("accessory", "boundary", "relation"),
    ),
    subtype_case(GROUP, "thin_client_terminal", "mini pc thin client terminal", "thin_client", forbidden_subtypes=("desktop_pc",)),
    subtype_case(GROUP, "wireless_microphone_receiver", "wireless microphone receiver", "wireless_microphone_receiver"),
)
