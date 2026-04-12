from __future__ import annotations

from .base import ambiguous_case, family_case, subtype_case

GROUP = "office_peripherals"

_SUBTYPE_CASES = (
    ("kiosk_display_integrated_windows_pc", "kiosk display with integrated windows pc", "all_in_one_pc", ("hybrid", "contrastive"), ("organic",)),
    ("touch_display_terminal_built_in_pc", "touch display terminal with built in pc", "all_in_one_pc", ("hybrid", "contrastive"), ("paraphrase",)),
    ("display_monitor_with_pc_built_in", "display monitor with pc built in", "all_in_one_pc", ("hybrid", "contrastive"), ("organic",)),
    ("terminal_display_with_integrated_pc", "terminal display with integrated pc", "all_in_one_pc", ("hybrid", "contrastive"), ("paraphrase",)),
    ("display_terminal_with_built_in_pc", "display terminal with built in pc", "all_in_one_pc", ("hybrid", "contrastive"), ("organic",)),
    ("windows_pc_kiosk_monitor", "kiosk display with built in windows pc", "all_in_one_pc", ("hybrid", "contrastive"), ("organic",)),
    ("all_in_one_touch_terminal", "touchscreen all in one pc terminal", "all_in_one_pc", ("hybrid",), ("organic",)),
    ("built_in_pc_display_terminal", "built in pc display terminal", "all_in_one_pc", ("hybrid",), ("paraphrase",)),
    ("integrated_windows_pc_display", "integrated windows pc display", "all_in_one_pc", ("hybrid",), ("organic",)),
    ("document_camera_for_classroom", "document camera for classroom", "document_camera", ("contrastive", "boundary"), ("organic",)),
    ("visualizer_camera_for_teacher_desk", "visualizer camera for teacher desk", "document_camera", ("contrastive", "boundary"), ("paraphrase",)),
    ("usb_c_monitor_dock", "usb c monitor dock with ethernet and usb ports", "docking_station", ("contrastive", "relation"), ("organic",)),
    ("monitor_dock_with_usb_hub", "monitor dock with usb hub and ethernet", "docking_station", ("hybrid", "contrastive"), ("paraphrase",)),
    ("display_with_usb_hub", "display with usb hub and ethernet", "usb_hub", ("hybrid", "contrastive"), ("organic",)),
    ("thin_client_terminal_display", "thin client terminal display", "thin_client", ("contrastive",), ("organic",)),
    ("kvm_switch_for_dual_monitors", "kvm switch for dual monitors", "kvm_switch", ("contrastive", "relation"), ("paraphrase",)),
    ("wireless_microphone_receiver_desktop", "wireless microphone receiver for desktop studio", "wireless_microphone_receiver", ("contrastive",), ("organic",)),
    ("baby_camera_monitor_with_screen", "baby camera monitor with screen", "baby_monitor", ("contrastive", "boundary"), ("organic",)),
    ("camera_monitor_for_baby_room", "camera monitor for baby room", "baby_monitor", ("contrastive", "boundary"), ("paraphrase",)),
)

_FAMILY_CASES = (
    ("office_display_terminal", "windows pc display terminal", "personal_computing_device", ("family_only", "boundary"), ("organic",)),
    ("monitor_arm_with_ports", "monitor arm with integrated usb hub", "office_avict_peripheral", ("family_only", "boundary", "accessory"), ("organic",)),
    ("monitor_stand_with_usb_hub", "monitor stand with built in usb hub", "office_avict_peripheral", ("family_only", "boundary", "accessory"), ("paraphrase",)),
)

_AMBIGUOUS_CASES = (
    ("smart_display_monitor", "smart display monitor", ("boundary", "contrastive"), ("adversarial",)),
    ("terminal_monitor_module", "terminal monitor module", ("boundary", "contrastive"), ("adversarial",)),
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
