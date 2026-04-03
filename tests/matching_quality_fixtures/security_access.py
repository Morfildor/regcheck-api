from __future__ import annotations

from .base import family_case, subtype_case

GROUP = "security_access"

CASES = (
    subtype_case(GROUP, "access_reader_rfid", "access reader with rfid badge support", "access_reader"),
    family_case(GROUP, "action_camera_4k", "action camera with 4k recording", "av_ict_device", tags=("boundary",)),
    subtype_case(GROUP, "alarm_keypad_panel_home", "home alarm keypad with display", "alarm_keypad_panel"),
    subtype_case(GROUP, "baby_monitor_video", "baby monitor with camera display and audio", "baby_monitor"),
    subtype_case(GROUP, "garage_door_drive", "garage door opener drive with remote control", "garage_door_drive"),
    family_case(GROUP, "ip_camera_poe", "ip camera with poe and motion detection", "smart_home_security", tags=("boundary",)),
    subtype_case(GROUP, "ip_intercom_access", "ip intercom with access control and camera", "ip_intercom"),
    subtype_case(GROUP, "nvr_dvr_recorder", "network video recorder with poe ports and storage", "nvr_dvr_recorder"),
    subtype_case(GROUP, "occupancy_sensor_ceiling", "occupancy sensor with wired ethernet only", "occupancy_sensor"),
    subtype_case(GROUP, "security_hub_alarm", "smart security alarm hub with app and siren", "security_hub"),
    subtype_case(GROUP, "smart_button_remote", "smart button remote for panic or scene control", "smart_button_remote"),
    family_case(GROUP, "smart_doorbell_wifi", "smart doorbell with wifi and camera", "smart_home_security", tags=("boundary",)),
    subtype_case(GROUP, "smart_lock_wifi_keypad", "smart door lock with wifi bluetooth keypad and app control", "smart_lock"),
    subtype_case(GROUP, "smart_security_camera", "smart security camera with battery and wifi", "smart_security_camera"),
    subtype_case(GROUP, "smart_smoke_co_alarm", "smart smoke co alarm with wifi and app", "smart_smoke_co_alarm", tags=("boundary",)),
    subtype_case(GROUP, "smart_sensor_node", "smart sensor node with humidity and motion sensing", "smart_sensor_node"),
    subtype_case(GROUP, "smoke_co_alarm", "smoke co alarm with battery backup", "smoke_co_alarm", tags=("boundary",)),
    family_case(GROUP, "video_doorbell", "video doorbell with wifi and camera", "smart_home_security", tags=("boundary",)),
    subtype_case(
        GROUP,
        "controller_for_garage_door",
        "controller for garage door opener",
        "garage_door_controller",
        forbidden_subtypes=("garage_door_drive",),
        tags=("relation", "contrastive"),
    ),
)
