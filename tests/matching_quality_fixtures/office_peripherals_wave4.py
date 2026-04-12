from __future__ import annotations

from .base import family_case, subtype_case

GROUP = "office_peripherals"

_SUBTYPE_CASES = (
    ("document_camera_visualizer_classroom", "document camera visualizer for classroom", "document_camera", ("contrastive",), ("adversarial",)),
    ("classroom_visualizer_projector_camera", "classroom visualizer projector camera", "document_camera", ("contrastive",), ("adversarial",)),
    ("document_visualizer_hdmi", "document visualizer with hdmi out", "document_camera", ("boundary",), ("paraphrase",)),
    ("wireless_receiver_stage_microphones", "wireless receiver for stage microphones", "wireless_microphone_receiver", ("contrastive",), ("adversarial",)),
    ("stage_microphone_receiver_rack", "stage microphone receiver with rack ears", "wireless_microphone_receiver", ("boundary",), ("paraphrase",)),
    ("kvm_switch_dual_monitors", "kvm switch for dual monitors", "kvm_switch", ("contrastive",), ("adversarial",)),
    ("remote_clicker_for_slides", "remote clicker for slides", "presentation_clicker", ("boundary",), ("paraphrase",)),
    ("presentation_remote_clicker_laser", "presentation remote clicker with laser", "presentation_clicker", ("boundary",), ("organic",)),
    ("slide_clicker_usb_receiver", "slide clicker usb receiver", "presentation_clicker", ("accessory",), ("organic",)),
    ("conference_speakerphone_zoom_room", "conference speakerphone for zoom room", "conference_speakerphone", ("boundary",), ("paraphrase",)),
    ("mini_pc_thin_client_terminal", "mini pc thin client terminal", "thin_client", ("contrastive",), ("adversarial",)),
    ("thin_client_terminal_mini_desktop", "thin client terminal mini desktop", "thin_client", ("contrastive",), ("organic",)),
    ("retail_signage_media_box_player", "retail signage media box player", "digital_signage_player", ("boundary",), ("paraphrase",)),
    ("document_scanner_small_office", "small office document scanner feeder", "document_scanner", ("boundary",), ("organic",)),
    ("office_printer_wifi_copy", "office laser printer wifi copy", "office_printer", ("boundary",), ("organic",)),
    ("desktop_pc_multiple_hdmi", "desktop pc tower with multiple hdmi ports", "desktop_pc", ("boundary",), ("paraphrase",)),
    ("usb_c_monitor_dock_ethernet_charging", "usb c monitor dock with ethernet and charging", "docking_station", ("relation",), ("paraphrase",)),
    ("all_in_one_desktop_display_pc", "all in one desktop display pc", "all_in_one_pc", ("boundary", "hybrid"), ("adversarial",)),
)

_FAMILY_CASES = (
    ("keyboard_video_mouse_switch_two_pcs", "keyboard video mouse switch for two pcs", "office_avict_peripheral", ("contrastive", "boundary"), ("adversarial",)),
    ("monitor_arm_built_in_usb_hub", "monitor arm with built in usb hub", "office_avict_peripheral", ("accessory", "boundary"), ("organic",)),
    ("usb_hub_built_into_monitor_stand", "usb hub built into monitor stand", "office_avict_peripheral", ("accessory", "boundary"), ("adversarial",)),
)

CASES = tuple(
    subtype_case(GROUP, name, description, expected_subtype, tags=tags, modes=modes)
    for name, description, expected_subtype, tags, modes in _SUBTYPE_CASES
) + tuple(
    family_case(GROUP, name, description, expected_family, tags=tags, modes=modes)
    for name, description, expected_family, tags, modes in _FAMILY_CASES
)

