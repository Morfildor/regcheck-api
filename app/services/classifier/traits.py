from __future__ import annotations

import re
from typing import Any

from app.services.knowledge_base import get_knowledge_base_snapshot

from .matching import _hierarchical_product_match, _hierarchical_product_match_v2
from .normalization import normalize
from .scoring import (
    ELECTRONIC_SIGNAL_TRAITS,
    ENGINE_VERSION,
    POWER_TRAITS,
    RADIO_TRAITS,
    SERVICE_DEPENDENT_TRAITS,
    SMART_CONNECTED_PATTERNS,
    WIRED_NETWORK_PATTERNS,
    _contradiction_severity,
)


TRAIT_IDS_CACHE: set[str] | None = None


NEGATIONS: dict[str, list[str]] = {
    "radio": [
        r"\bno radio\b",
        r"\bwithout radio\b",
        r"\bno wireless communication\b",
        r"\bwithout wireless communication\b",
        r"\bno wireless connectivity\b",
        r"\bwithout wireless connectivity\b",
        r"\bwired only\b",
    ],
    "wifi": [r"\bno wifi\b", r"\bwithout wifi\b", r"\bnon wifi\b", r"\bwifi not present\b"],
    "bluetooth": [r"\bno bluetooth\b", r"\bwithout bluetooth\b"],
    "cloud": [r"\bno cloud\b", r"\bwithout cloud\b", r"\bcloud free\b", r"\blocal only\b", r"\blocal control only\b"],
    "internet": [
        r"\bno internet\b",
        r"\bwithout internet\b",
        r"\boffline only\b",
        r"\blocal only\b",
        r"\blocal control only\b",
    ],
    "app_control": [r"\bno app\b", r"\bwithout app\b"],
    "ota": [r"\bno ota\b", r"\bwithout ota\b", r"\bmanual update only\b"],
    "account": [
        r"\bno account\b",
        r"\bwithout account\b",
        r"\bguest only\b",
        r"\bno cloud account\b",
        r"\bno app account\b",
        r"\bno account required\b",
    ],
    "authentication": [r"\bno password\b", r"\bwithout login\b", r"\bwithout authentication\b"],
    "speaker": [r"\bnot a speaker\b", r"\bno speaker\b", r"\bwithout speaker\b"],
    "toy": [r"\bnot a toy\b", r"\bnot intended for play\b"],
    "child_targeted": [r"\bnot intended for play\b", r"\bnot designed for play\b"],
    "battery_powered": [r"\bno battery\b", r"\bwithout battery\b", r"\bbattery not included\b"],
    "electronic": [r"\bno electronics\b", r"\bwithout electronics\b", r"\bnon electronic\b", r"\bpassive accessory\b", r"\bpassive cable\b"],
    "monetary_transaction": [
        r"\bno payment\b",
        r"\bwithout payment\b",
        r"\bno purchase\b",
        r"\bwithout subscription\b",
        r"\bno wallet\b",
    ],
}
_COMPILED_NEGATIONS: dict[str, list[re.Pattern]] = {
    trait: [re.compile(p) for p in pats]
    for trait, pats in NEGATIONS.items()
}
NEGATED_TRAIT_SUPPRESSIONS: dict[str, set[str]] = {
    "radio": RADIO_TRAITS | {"radio"},
    "wifi": {"wifi", "wifi_5ghz", "wifi_6", "wifi_7", "tri_band_wifi", "mesh_network_node", "wpa3"},
    "bluetooth": {"bluetooth"},
    "cloud": {"cloud"},
    "internet": {"internet", "internet_connected"},
    "app_control": {"app_control"},
    "ota": {"ota"},
    "account": {"account"},
    "authentication": {"authentication"},
    "speaker": {"speaker", "multi_room_audio", "spatial_audio"},
    "toy": {"toy", "child_targeted"},
    "child_targeted": {"child_targeted", "toy"},
    "battery_powered": {"battery_powered", "backup_battery", "portable"},
    "electronic": {"electronic"},
    "monetary_transaction": {"monetary_transaction", "subscription_dependency"},
}

TRAIT_PATTERNS: dict[str, list[str]] = {
    "radio": [r"\bradio\b"],
    "bluetooth": [r"\bbluetooth\b"],
    "wifi": [r"\bwifi\b", r"\bwi fi\b", r"\bwlan\b", r"\bwireless lan\b", r"\b802 11\b"],
    "wifi_5ghz": [
        r"\b5ghz\b",
        r"\b5 ghz\b",
        r"\b5ghz wifi\b",
        r"\b5 ghz wifi\b",
        r"\bdual band\b",
        r"\bdual-band\b",
        r"\btri band\b",
        r"\btri-band\b",
        r"\b802 11a\b",
        r"\b802 11ac\b",
        r"\b802 11ax\b",
        r"\b802 11be\b",
        r"\bwifi 5\b",
        r"\bwifi 6\b",
        r"\bwifi 6e\b",
        r"\bwifi 7\b",
    ],
    "wifi_6": [r"\bwifi 6\b", r"\bwifi 6e\b", r"\b802 11ax\b"],
    "wifi_7": [r"\bwifi 7\b", r"\b802 11be\b"],
    "zigbee": [r"\bzigbee\b"],
    "thread": [r"\bthread\b"],
    "matter": [r"\bmatter\b"],
    "matter_bridge": [r"\bmatter bridge\b"],
    "nfc": [r"\bnfc\b", r"\brfid\b"],
    "cellular": [r"\bcellular\b", r"\blte\b", r"\b4g\b", r"\b5g cellular\b", r"\b5g mobile\b", r"\bgsm\b", r"\bsim\b"],
    "dect": [r"\bdect\b"],
    "gsm": [r"\bgsm\b"],
    "sigfox": [r"\bsigfox\b"],
    "lte_m": [r"\blte m\b", r"\blte-m\b", r"\bnb iot\b", r"\bnb-iot\b"],
    "5g_nr": [r"\b5g nr\b", r"\bstandalone 5g\b"],
    "satellite_connectivity": [r"\bsatellite internet\b", r"\bsatellite connectivity\b", r"\bstarlink\b", r"\bvsat\b"],
    "lora": [r"\blora\b"],
    "lorawan": [r"\blorawan\b"],
    "uwb": [r"\buwb\b", r"\bultra wideband\b"],
    "wpa3": [r"\bwpa3\b"],
    "mesh_network_node": [r"\bmesh wifi\b", r"\bmesh node\b", r"\bwhole home wifi\b", r"\bmesh router\b", r"\bmesh network router\b"],
    "tri_band_wifi": [r"\btri band\b", r"\btri band wifi\b"],
    "app_control": [
        r"\bmobile app\b",
        r"\bcompanion app\b",
        r"\bsmartphone app\b",
        r"\bmobile application\b",
        r"\bapp control\b",
        r"\bapp controlled\b",
        r"\bapp enabled\b",
        r"\bapp connected\b",
        r"\bapp sync(?:ed)?\b",
        r"\bapp synced\b",
        r"\bsyncs? with (?:the )?(?:mobile )?app\b",
        r"\bsyncs? to (?:the )?(?:mobile )?app\b",
        r"\bvia (?:the )?(?:mobile )?app\b",
        r"\bapp monitoring\b",
        r"\bbluetooth app\b",
        r"\bwifi app\b",
        r"\bcontrol(?:led)? via app\b",
        r"\bworks with app\b",
        r"\bworks with alexa\b",
        r"\bgoogle home\b",
        r"\bapple home\b",
        r"\bhomekit\b",
        r"\bsmartthings\b",
        r"\btuya\b",
    ],
    "cloud": [
        r"\bcloud\b",
        r"\bcloud account\b",
        r"\bcloud account required\b",
        r"\bcloud service\b",
        r"\bcloud required\b",
        r"\brequires cloud\b",
        r"\bcloud dependent\b",
        r"\bcloud dependency\b",
        r"\bremote server\b",
        r"\bbackend api\b",
        r"\bweb service\b",
        r"\bout of home\b",
        r"\bremote monitoring\b",
        r"\bremote diagnostics\b",
    ],
    "internet": [
        r"\binternet\b",
        r"\binternet connected\b",
        r"\bonline service\b",
        r"\bremote access\b",
        r"\bweb portal\b",
        r"\biot\b",
        r"\binternet of things\b",
        r"\bconnected device\b",
        r"\bconnected product\b",
    ],
    "local_only": [r"\boffline\b", r"\bno cloud\b", r"\bno internet\b", r"\blocal only\b", r"\blan only\b"],
    "ota": [
        r"\bota\b",
        r"\bota updates?\b",
        r"\bfirmware update\b",
        r"\bfirmware updates?\b",
        r"\bover the air\b",
        r"\bremote firmware update\b",
        r"\bwireless firmware update\b",
        r"\bsecurity patch\b",
        r"\bsoftware update over\b",
        r"\bsoftware updates?\b",
        r"\bautomatic updates?\b",
        r"\bsecurity updates?\b",
        r"\bsoftware security updates?\b",
    ],
    "account": [
        r"\baccount\b",
        r"\blogin\b",
        r"\blog in\b",
        r"\bsign in\b",
        r"\buser account\b",
        r"\buser profile\b",
        r"\baccount required\b",
        r"\bcreate account\b",
        r"\bsign up\b",
    ],
    "authentication": [
        r"\bauthentication\b",
        r"\bpassword\b",
        r"\bpasscode\b",
        r"\bcredential\b",
        r"\bpin\b",
        r"\bpin code\b",
        r"\bpairing code\b",
        r"\btwo factor\b",
        r"\bmfa\b",
        r"\b2fa\b",
        r"\bpasskey\b",
    ],
    "av_ict": [
        r"\brouter\b",
        r"\bmodem\b",
        r"\bgateway\b",
        r"\bnetwork switch\b",
        r"\bethernet switch\b",
        r"\baccess point\b",
        r"\bwireless access point\b",
        r"\blaptop\b",
        r"\bnotebook\b",
        r"\bdesktop pc\b",
        r"\bpersonal computer\b",
        r"\bserver\b",
        r"\bmonitor\b",
        r"\btelevision\b",
        r"\bsmart tv\b",
        r"\btv\b",
        r"\bsmart display\b",
        r"\bdisplay hub\b",
        r"\bset top box\b",
        r"\bset-top box\b",
        r"\bstreaming device\b",
        r"\bmedia player\b",
        r"\bprojector\b",
        r"\bsmart speaker\b",
        r"\bict equipment\b",
        r"\baudio video equipment\b",
    ],
    "monetary_transaction": [
        r"\bpayment\b",
        r"\bpayments\b",
        r"\bpurchase\b",
        r"\bpurchases\b",
        r"\bcheckout\b",
        r"\bsubscription\b",
        r"\bwallet\b",
        r"\bmoney transfer\b",
        r"\bmonetary value\b",
        r"\bvirtual currency\b",
        r"\bin app purchase\b",
        r"\bplace order\b",
        r"\bpaid plan\b",
    ],
    "camera": [r"\bcamera\b"],
    "microphone": [r"\bmicrophone\b", r"\bmic\b", r"\bvoice control\b", r"\bvoice command\b"],
    "speaker": [r"\bspeaker\b", r"\baudio playback\b", r"\bsound output\b"],
    "display": [r"\bdisplay\b", r"\bscreen\b", r"\btouchscreen\b", r"\btouch screen\b", r"\bmonitor\b"],
    "display_touchscreen": [r"\btouchscreen\b", r"\btouch screen\b"],
    "e_ink_display": [r"\beink\b", r"\bepaper\b", r"\be reader\b"],
    "hdr_display": [r"\bhdr10\b", r"\bhdr10\+\b", r"\bdolby vision\b", r"\bhlg\b"],
    "high_refresh_display": [r"\b90hz\b", r"\b120hz\b", r"\b144hz\b", r"\bhigh refresh\b"],
    "screen_mirroring": [r"\bscreen mirroring\b", r"\bchromecast\b", r"\bairplay\b", r"\bmiracast\b"],
    "multi_room_audio": [r"\bmulti room audio\b", r"\bmultiroom audio\b"],
    "spatial_audio": [r"\bspatial audio\b", r"\bdolby atmos\b", r"\bdts x\b", r"\b3d audio\b"],
    "voice_assistant": [
        r"\bvoice assistant\b",
        r"\balexa\b",
        r"\bgoogle assistant\b",
        r"\bsiri\b",
        r"\bbixby\b",
        r"\bworks with alexa\b",
    ],
    "privacy_switch": [r"\bprivacy switch\b", r"\bmic mute switch\b", r"\bcamera kill switch\b"],
    "parental_controls": [r"\bparental control\b", r"\bfamily safety\b", r"\bcontent filter\b"],
    "subscription_dependency": [
        r"\bsubscription required\b",
        r"\brequires subscription\b",
        r"\bpaid subscription\b",
        r"\bsubscription plan\b",
        r"\bservice plan\b",
    ],
    "laser": [r"\blaser\b", r"\blidar\b", r"\blaser scanner\b", r"\brangefinder\b"],
    "location": [r"\bgps\b", r"\bgnss\b", r"\bgeolocation\b", r"\blocation tracking\b"],
    "battery_powered": [
        r"\bbattery powered\b",
        r"\bbattery operated\b",
        r"\brechargeable battery\b",
        r"\brechargeable\b",
        r"\bcordless\b",
        r"\bli ion\b",
        r"\bli-ion\b",
        r"\blithium ion\b",
        r"\blithium\b",
        r"\blithium battery\b",
        r"\bbattery pack\b",
        r"\bbattery cell\b",
        r"\bbattery powered device\b",
        r"\bon battery\b",
    ],
    "external_psu": [
        r"\bexternal psu\b",
        r"\bexternal power supply\b",
        r"\bpower adapter\b",
        r"\bac adapter\b",
        r"\bdc adapter\b",
        r"\bpower brick\b",
        r"\bwall wart\b",
        r"\bplug pack\b",
        r"\bmains adapter\b",
    ],
    "usb_powered": [r"\busb powered\b", r"\busb c powered\b", r"\bpowered by usb\b", r"\btype c powered\b"],
    "usb_pd": [r"\busb pd\b", r"\bpower delivery\b", r"\busb power delivery\b"],
    "poe_powered": [r"\bpoe powered\b", r"\bpoe\b", r"\b802 3af\b", r"\b802 3at\b", r"\b802 3bt\b"],
    "poe_supply": [r"\bpoe injector\b", r"\bpoe switch\b", r"\bpower sourcing equipment\b"],
    "wireless_charging_tx": [r"\bwireless charger\b", r"\bcharging pad\b", r"\bcharging stand\b"],
    "wireless_charging_rx": [r"\bsupports wireless charging\b", r"\bwireless charging receiver\b"],
    "backup_battery": [r"\bbackup battery\b", r"\bbattery backup\b"],
    "energy_monitoring": [r"\benergy monitoring\b", r"\bpower monitoring\b", r"\benergy meter\b", r"\bpower consumption\b"],
    "smart_grid_ready": [r"\bsmart grid\b", r"\bdemand response\b", r"\bdynamic load management\b"],
    "mains_powered": [r"\bmains\b", r"\b230v\b", r"\b220v\b", r"\b240v\b", r"\bac power\b", r"\bplug in\b", r"\bplugged in\b"],
    "professional": [
        r"\bprofessional\b",
        r"\bprofessional use\b",
        r"\bfor professional use\b",
        r"\bcommercial\b",
        r"\bcommercial use\b",
        r"\bindustrial\b",
        r"\bindustrial use\b",
        r"\bwarehouse\b",
        r"\benterprise\b",
        r"\bcatering\b",
        r"\bhoreca\b",
    ],
    "consumer": [r"\bconsumer\b", r"\bconsumer use\b", r"\bdomestic\b", r"\bhousehold\b", r"\bhome use\b", r"\bpersonal use\b"],
    "household": [r"\bhousehold\b", r"\bdomestic\b", r"\bhome use\b"],
    "indoor_use": [r"\bindoor\b", r"\bindoor use\b", r"\bindoors\b"],
    "outdoor_use": [r"\boutdoor\b", r"\bgarden\b", r"\blawn\b"],
    "fixed_installation": [r"\bbuilt in\b", r"\bfixed\b", r"\bwall mounted\b", r"\bceiling mounted\b", r"\bpermanently installed\b"],
    "wall_mount": [r"\bwall mounted\b", r"\bwall mount\b"],
    "ceiling_mount": [r"\bceiling mounted\b", r"\bceiling mount\b"],
    "rack_mount": [r"\brack mount\b", r"\b19 inch rack\b"],
    "din_rail_mount": [r"\bdin rail\b"],
    "portable": [r"\bportable\b", r"\btravel\b", r"\bhandheld\b"],
    "water_contact": [
        r"\bwater tank\b",
        r"\bwater reservoir\b",
        r"\bwater path\b",
        r"\bliquid handling\b",
        r"\bsteam\b",
        r"\brinse\b",
        r"\bwet use\b",
        r"\bimmersion\b",
    ],
    "heating": [r"\bheating\b", r"\bheater\b", r"\bhot\b", r"\bboil\b", r"\bbrew\b", r"\bsteam\b"],
    "cooling": [r"\bcooling\b", r"\brefrigerat\b", r"\bfreezer\b", r"\bice\b", r"\bchill\b"],
    "motorized": [
        r"\bmotor\b",
        r"\bfan\b",
        r"\bpump\b",
        r"\bcompressor\b",
        r"\bmotor drive\b",
        r"\bdrive unit\b",
        r"\bgear drive\b",
        r"\bchain drive\b",
        r"\bbelt drive\b",
        r"\bpower tool\b",
        r"\bdrill\b",
        r"\bsaw\b",
        r"\bgrinder\b",
        r"\bsander\b",
        r"\bimpact driver\b",
        r"\brotary hammer\b",
    ],
    "remote_control": [r"\bremote control\b", r"\bremote start\b", r"\bremote operation\b"],
    "remote_management": [
        r"\bremote management\b",
        r"\bdevice management\b",
        r"\bremote provisioning\b",
        r"\bfleet management\b",
        r"\bremote diagnostics\b",
    ],
    "secure_boot": [r"\bsecure boot\b"],
    "hardware_security_element": [r"\bsecurity element\b", r"\btpm\b", r"\bhsm\b", r"\bsecure enclave\b"],
    "ai_related": [r"\bai\b", r"\bmachine learning\b", r"\bneural\b", r"\bllm\b"],
    "personal_data_likely": [
        r"\bpersonal data\b",
        r"\buser data\b",
        r"\bprofile\b",
        r"\bprivacy\b",
    ],
    "food_contact": [
        r"\bfood contact\b",
        r"\bfood safe\b",
        r"\bfood grade\b",
        r"\bfood prep\b",
        r"\bfood processing\b",
        r"\bfood processor\b",
        r"\bfood handling\b",
        r"\bbeverage dispenser\b",
        r"\bdrink dispenser\b",
        r"\bdrinking water\b",
        r"\bbrew path\b",
        r"\bcook\b",
        r"\bwater tank\b",
    ],
    "wet_environment": [r"\bwet environment\b", r"\bbathroom\b", r"\bshower\b", r"\bsplash\b"],
    "wearable": [
        r"\bwearable\b",
        r"\bfitness tracker\b",
        r"\bsmart band\b",
        r"\bsmart watch\b",
        r"\bsmartwatch\b",
        r"\bactivity tracker\b",
        r"\bfitness watch\b",
        r"\bhealth watch\b",
        r"\bsmart ring\b",
        r"\bwrist worn\b",
        r"\bwristband\b",
        r"\bbody worn\b",
    ],
    "body_worn_or_applied": [
        r"\bbody worn\b",
        r"\bbody worn use\b",
        r"\bbody contact\b",
        r"\bskin contact\b",
        r"\bon body\b",
        r"\bon skin\b",
        r"\bchest strap\b",
        r"\bwrist worn\b",
        r"\bwristband\b",
        r"\barmband\b",
        r"\bfinger worn\b",
        r"\bwearable patch\b",
        r"\bsensor patch\b",
        r"\bclip on body\b",
    ],
    "hair_care": [r"\bhair care\b", r"\bhair trimmer\b", r"\bhair clipper\b", r"\bbeard trimmer\b", r"\bclipper\b"],
    "oral_care": [r"\boral care\b", r"\btoothbrush\b", r"\bdental flosser\b", r"\bwater flosser\b"],
    "personal_care": [r"\bpersonal care\b", r"\bgrooming\b", r"\bbeauty device\b", r"\btrimmer\b", r"\bshaver\b", r"\bepilator\b"],
    "biometric": [
        r"\bbiometric\b",
        r"\bphysiological\b",
        r"\bheart rate\b",
        r"\bpulse\b",
        r"\bspo2\b",
        r"\boxygen saturation\b",
        r"\bblood oxygen\b",
        r"\becg\b",
        r"\bekg\b",
    ],
    "health_related": [
        r"\bhealth monitor\b",
        r"\bwellness monitor\b",
        r"\bwellness device\b",
        r"\bconnected health device\b",
        r"\bhealth device\b",
        r"\bhealth tracking\b",
        r"\bphysiological monitoring\b",
        r"\bbiometric monitoring\b",
        r"\bheart rate monitor\b",
        r"\bpulse monitor\b",
        r"\bpulse oximeter\b",
        r"\bspo2 monitor\b",
        r"\becg monitor\b",
        r"\bekg monitor\b",
        r"\bblood oxygen monitor\b",
    ],
    "medical_context": [
        r"\bmedical use\b",
        r"\bpatient use\b",
        r"\bpatient monitoring\b",
        r"\bclinical use\b",
        r"\bclinical setting\b",
        r"\bhospital use\b",
        r"\bhealthcare use\b",
    ],
    "medical_claims": [
        r"\bdiagnos(?:e|is|tic)\b",
        r"\btreat(?:ment|s|ing)?\b",
        r"\btherap(?:y|eutic)\b",
        r"\bdisease monitoring\b",
        r"\bmedical claims?\b",
        r"\bmedical grade\b",
    ],
    "possible_medical_boundary": [
        r"\bdiagnos(?:e|is|tic)\b",
        r"\btreat(?:ment|s|ing)?\b",
        r"\bdisease monitoring\b",
        r"\bpatient monitoring\b",
        r"\bclinical use\b",
        r"\bmedical claims?\b",
        r"\bmedical grade\b",
        r"\bphysiological monitoring\b",
        r"\bheart rate monitor\b",
        r"\bpulse oximeter\b",
        r"\becg monitor\b",
        r"\bekg monitor\b",
        r"\bwellness monitor\b",
    ],
    "child_targeted": [r"\bchild targeted\b", r"\bfor children\b", r"\bkids mode\b"],
    "ambient_light_sensor": [r"\bambient light sensor\b", r"\blight sensor\b", r"\bauto brightness\b"],
    "occupancy_detection": [r"\boccupancy detection\b", r"\boccupancy sensor\b", r"\bpresence detection\b"],
    "gas_detection": [r"\bgas detection\b", r"\bgas detector\b", r"\blpg detector\b", r"\bnatural gas detector\b"],
    "flood_detection": [r"\bflood detection\b", r"\bwater leak\b", r"\bleak sensor\b"],
    "door_window_sensor": [r"\bdoor sensor\b", r"\bwindow sensor\b", r"\bcontact sensor\b"],
    "strobe_output": [r"\bstrobe\b", r"\bvisual alarm\b", r"\bflashing alarm\b"],
}
_COMPILED_TRAIT_PATTERNS: dict[str, list[re.Pattern]] = {
    trait: [re.compile(p) for p in pats]
    for trait, pats in TRAIT_PATTERNS.items()
}
_COMPILED_SMART_CONNECTED = [re.compile(p) for p in SMART_CONNECTED_PATTERNS]
_COMPILED_WIRED_NETWORK = [re.compile(p) for p in WIRED_NETWORK_PATTERNS]
WIRELESS_MENTION_PATTERNS = [
    r"\bwi[ -]?fi\b",
    r"\bwlan\b",
    r"\bbluetooth\b",
    r"\bble\b",
    r"\bzigbee\b",
    r"\bthread\b",
    r"\bmatter\b",
    r"\bnfc\b",
    r"\brfid\b",
    r"\bcellular\b",
    r"\blte\b",
    r"\b4g\b",
    r"\b5g\b",
    r"\bgsm\b",
    r"\bdect\b",
    r"\buwb\b",
    r"\blora\b",
    r"\blorawan\b",
    r"\bsigfox\b",
    r"\bsatellite connectivity\b",
    r"\bradio\b",
    r"\brf\b",
    r"\bwireless\b",
]
_COMPILED_WIRELESS_MENTIONS = [re.compile(p) for p in WIRELESS_MENTION_PATTERNS]
_COMPILED_ELECTRICAL_CUES = [
    re.compile(r"\belectric(?:al)?\b"),
    re.compile(r"\belectronic\b"),
    re.compile(r"\bpowered\b"),
    re.compile(r"\bvoltage\b"),
    re.compile(r"\bcharger\b"),
    re.compile(r"\badapter\b"),
    re.compile(r"\bplug\b"),
    re.compile(r"\bsocket\b"),
    re.compile(r"\bdevice\b"),
    re.compile(r"\bequipment\b"),
    re.compile(r"\bappliance\b"),
]
_COMPILED_ELECTRONIC_CUES = [
    re.compile(r"\belectronic\b"),
    re.compile(r"\bdigital\b"),
    re.compile(r"\bfirmware\b"),
    re.compile(r"\bsoftware\b"),
    re.compile(r"\bpcb\b"),
    re.compile(r"\bcircuit\b"),
    re.compile(r"\bsensor\b"),
    re.compile(r"\bsmart\b"),
    re.compile(r"\bconnected\b"),
]
_COMPILED_LOCAL_ONLY_CUES = [
    re.compile(r"\blocal only\b"),
    re.compile(r"\boffline only\b"),
    re.compile(r"\blan only\b"),
]
_COMPILED_CONSUMERISH_CUES = [
    re.compile(r"\bhousehold\b"),
    re.compile(r"\bconsumer\b"),
    re.compile(r"\bdomestic\b"),
    re.compile(r"\bappliance\b"),
    re.compile(r"\bhome device\b"),
    re.compile(r"\bpersonal care\b"),
    re.compile(r"\bwearable\b"),
    re.compile(r"\bwellness\b"),
]


def _has_any_compiled(text: str, patterns: list[re.Pattern]) -> bool:
    return any(p.search(text) for p in patterns)


def _trait_is_negated(text: str, trait: str) -> bool:
    return _has_any_compiled(text, _COMPILED_NEGATIONS.get(trait, []))


def _add_regex_trait(text: str, explicit_traits: set[str]) -> None:
    for trait, patterns in _COMPILED_TRAIT_PATTERNS.items():
        if _trait_is_negated(text, trait):
            continue
        if _has_any_compiled(text, patterns):
            explicit_traits.add(trait)

    if RADIO_TRAITS & explicit_traits:
        explicit_traits.add("radio")
    if "wifi_5ghz" in explicit_traits:
        explicit_traits.add("wifi")

    if "cloud" in explicit_traits and "local_only" not in explicit_traits:
        explicit_traits.add("internet")
    if "ota" in explicit_traits and not _trait_is_negated(text, "internet"):
        explicit_traits.add("internet")
    if ("account" in explicit_traits or "authentication" in explicit_traits) and (
        {"cloud", "ota", "app_control", "wifi", "cellular", "internet"} & explicit_traits
    ):
        explicit_traits.add("internet")
    if "wearable" in explicit_traits:
        explicit_traits.add("body_worn_or_applied")
    if "biometric" in explicit_traits:
        explicit_traits.update({"health_related", "personal_data_likely"})
    if {"medical_context", "possible_medical_boundary", "medical_claims"} & explicit_traits:
        explicit_traits.add("health_related")
    if {"account", "authentication", "camera", "microphone", "location", "biometric"} & explicit_traits:
        explicit_traits.add("personal_data_likely")
    if "health_related" in explicit_traits and (
        {"app_control", "cloud", "account", "authentication", "data_storage", "wifi", "bluetooth", "internet"} & explicit_traits
    ):
        explicit_traits.add("personal_data_likely")


def _infer_baseline_traits(text: str, explicit_traits: set[str]) -> set[str]:
    inferred: set[str] = set()

    electrical_signals = POWER_TRAITS | {
        "av_ict",
        "heating",
        "motorized",
        "radio",
        "camera",
        "display",
        "microphone",
        "speaker",
    }
    electronic_signals = ELECTRONIC_SIGNAL_TRAITS | {"radio", "electronic"}

    if (electrical_signals & explicit_traits) or _has_any_compiled(text, _COMPILED_ELECTRICAL_CUES):
        inferred.add("electrical")
    if (electronic_signals & explicit_traits) or _has_any_compiled(text, _COMPILED_ELECTRONIC_CUES):
        inferred.add("electronic")
    if "electronic" in inferred and not ({"electrical"} & (explicit_traits | inferred)):
        inferred.add("electrical")

    if "wifi" in explicit_traits and ({"cloud", "ota"} & explicit_traits):
        inferred.add("internet")
    if "cellular" in explicit_traits:
        inferred.add("internet")
    if "battery_powered" in explicit_traits and "portable" not in explicit_traits:
        inferred.add("portable")
    if "food_contact" in explicit_traits and "consumer" not in explicit_traits:
        inferred.add("consumer")
    if "wearable" in explicit_traits and "body_worn_or_applied" not in explicit_traits:
        inferred.add("body_worn_or_applied")
    if "biometric" in explicit_traits and "health_related" not in explicit_traits:
        inferred.add("health_related")
    if "health_related" in explicit_traits and (
        {"app_control", "cloud", "account", "authentication", "data_storage", "wifi", "bluetooth", "internet"} & explicit_traits
    ):
        inferred.add("personal_data_likely")

    return inferred


def _infer_connected_traits(text: str, signal_traits: set[str]) -> set[str]:
    inferred: set[str] = set()

    local_only = "local_only" in signal_traits or _has_any_compiled(text, _COMPILED_LOCAL_ONLY_CUES)
    smartish = _has_any_compiled(text, _COMPILED_SMART_CONNECTED)
    consumerish = bool({"consumer", "household", "personal_care", "wearable", "pet_use"} & signal_traits) or _has_any_compiled(
        text, _COMPILED_CONSUMERISH_CUES
    )
    voiceish = "voice_assistant" in signal_traits

    if voiceish:
        inferred.add("app_control")

    if "subscription_dependency" in signal_traits:
        inferred.add("monetary_transaction")

    if local_only:
        if {"wifi", "bluetooth", "zigbee", "thread", "matter", "cellular"} & signal_traits:
            inferred.add("radio")
        return inferred

    if "ota" in signal_traits:
        inferred.update({"internet", "internet_connected"})

    if smartish or voiceish:
        inferred.add("app_control")

    if {"cloud", "account", "authentication", "remote_management", "subscription_dependency"} & signal_traits:
        inferred.update({"internet", "internet_connected"})
        if {"cloud", "remote_management", "subscription_dependency"} & signal_traits and consumerish:
            inferred.add("cloud")

    if "cloud" in signal_traits:
        inferred.update({"internet", "internet_connected"})

    if {"wifi", "cloud", "internet", "ota"} & (signal_traits | inferred):
        inferred.add("internet_connected")
    if {"account", "authentication"} & (signal_traits | inferred):
        inferred.add("personal_data_likely")

    return inferred


def _has_wireless_mention(text: str, matched_aliases: list[str] | None = None) -> bool:
    candidates = [text]
    candidates.extend(alias for alias in (matched_aliases or []) if isinstance(alias, str) and alias)
    return any(_has_any_compiled(candidate, _COMPILED_WIRELESS_MENTIONS) for candidate in candidates)


def _suppress_unmentioned_product_wireless_traits(
    text: str,
    traits: set[str],
    explicit_traits: set[str],
    matched_aliases: list[str] | None = None,
) -> set[str]:
    if explicit_traits & (RADIO_TRAITS | {"radio"}):
        return set(traits)
    if _has_wireless_mention(text, matched_aliases):
        return set(traits)
    return set(traits) - (RADIO_TRAITS | {"radio"})


def _suppressed_traits_for_negations(negations: list[str]) -> set[str]:
    suppressed: set[str] = set()
    for trait in negations:
        suppressed.update(NEGATED_TRAIT_SUPPRESSIONS.get(trait, {trait}))
    return suppressed


def _apply_explicit_trait_negations(traits: set[str], negations: list[str]) -> set[str]:
    if not traits or not negations:
        return set(traits)
    return set(traits) - _suppressed_traits_for_negations(negations)


def _expand_related_traits(traits: set[str]) -> set[str]:
    expanded = set(traits)

    if expanded & RADIO_TRAITS:
        expanded.add("radio")
    if "wearable" in expanded:
        expanded.add("body_worn_or_applied")
    if expanded & {"wifi_5ghz", "wifi_6", "wifi_7", "tri_band_wifi", "mesh_network_node", "wpa3"}:
        expanded.add("wifi")
    if expanded & {"wifi_6", "wifi_7", "tri_band_wifi"}:
        expanded.add("wifi_5ghz")
    if expanded & {"gsm", "lte_m", "5g_nr"}:
        expanded.add("cellular")
    if "lorawan" in expanded:
        expanded.add("lora")
    if expanded & {"display_touchscreen", "e_ink_display", "hdr_display", "high_refresh_display"}:
        expanded.add("display")
    if "privacy_switch" in expanded:
        expanded.update({"microphone", "personal_data_likely"})
    if expanded & {"biometric"}:
        expanded.update({"health_related", "personal_data_likely"})
    if expanded & {"medical_context", "medical_claims", "possible_medical_boundary"}:
        expanded.add("health_related")
    if expanded & {"parental_controls", "subscription_dependency"}:
        expanded.add("account")
    if "subscription_dependency" in expanded:
        expanded.add("monetary_transaction")
    if "matter_bridge" in expanded:
        expanded.add("matter")
    if expanded & {"internet", "internet_connected"}:
        expanded.update({"internet", "internet_connected"})
    if "health_related" in expanded and (
        {"app_control", "cloud", "account", "authentication", "data_storage", "wifi", "bluetooth", "internet", "location"} & expanded
    ):
        expanded.add("personal_data_likely")
    if expanded & {
        "wireless_charging_rx",
        "wireless_charging_tx",
        "usb_pd",
        "poe_powered",
        "poe_supply",
        "backup_battery",
        "energy_monitoring",
        "smart_grid_ready",
        "vehicle_supply",
        "ev_charging",
        "solar_powered",
    }:
        expanded.add("electrical")
    if expanded & {
        "camera",
        "display",
        "microphone",
        "speaker",
        "data_storage",
        "screen_mirroring",
        "multi_room_audio",
        "spatial_audio",
        "voice_assistant",
        "parental_controls",
        "subscription_dependency",
        "secure_boot",
        "hardware_security_element",
        "remote_management",
        "matter_bridge",
        "e_ink_display",
        "hdr_display",
        "high_refresh_display",
        "display_touchscreen",
    }:
        expanded.add("av_ict")
    if expanded & {
        "camera",
        "display",
        "microphone",
        "speaker",
        "data_storage",
        "screen_mirroring",
        "multi_room_audio",
        "spatial_audio",
        "voice_assistant",
        "privacy_switch",
        "parental_controls",
        "subscription_dependency",
        "secure_boot",
        "hardware_security_element",
        "remote_management",
        "matter_bridge",
        "poe_powered",
        "poe_supply",
        "wireless_charging_rx",
        "wireless_charging_tx",
        "usb_pd",
        "energy_monitoring",
        "smart_grid_ready",
        "backup_battery",
        "ambient_light_sensor",
        "occupancy_detection",
        "gas_detection",
        "flood_detection",
        "door_window_sensor",
        "strobe_output",
    }:
        expanded.add("electronic")

    return expanded

def _empty_trait_state_map() -> dict[str, dict[str, list[str]]]:
    return {
        "text_explicit": {},
        "text_inferred": {},
        "product_core": {},
        "product_default": {},
        "engine_derived": {},
    }


def _record_trait_state(
    state_map: dict[str, dict[str, list[str]]],
    state: str,
    traits: set[str] | list[str],
    evidence: str,
) -> None:
    for trait in traits:
        state_map.setdefault(state, {}).setdefault(trait, [])
        if evidence not in state_map[state][trait]:
            state_map[state][trait].append(evidence)


def _trait_evidence_items(
    state_map: dict[str, dict[str, list[str]]],
    confirmed_traits: set[str],
) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    fact_basis_by_state = {
        "text_explicit": "confirmed",
        "product_core": "confirmed",
        "text_inferred": "inferred",
        "product_default": "inferred",
        "engine_derived": "inferred",
    }
    for state in ("text_explicit", "text_inferred", "product_core", "product_default", "engine_derived"):
        for trait in sorted(state_map.get(state, {})):
            items.append(
                {
                    "trait": trait,
                    "state": state,
                    "fact_basis": fact_basis_by_state[state],
                    "confirmed": trait in confirmed_traits,
                    "evidence": list(state_map[state][trait]),
                }
            )
    return items


def _collect_text_trait_signals(text: str) -> tuple[set[str], set[str], dict[str, dict[str, list[str]]], list[str]]:
    explicit_direct: set[str] = set()
    negations = sorted(trait for trait in _COMPILED_NEGATIONS if _trait_is_negated(text, trait))
    state_map = _empty_trait_state_map()

    for trait, patterns in _COMPILED_TRAIT_PATTERNS.items():
        if trait in negations:
            continue
        if _has_any_compiled(text, patterns):
            explicit_direct.add(trait)
            _record_trait_state(state_map, "text_explicit", {trait}, f"text:{trait}")

    explicit_traits = _expand_related_traits(explicit_direct)
    derived_explicit = explicit_traits - explicit_direct
    if derived_explicit:
        _record_trait_state(state_map, "text_explicit", derived_explicit, "text:derived")

    inferred_traits = _expand_related_traits(_infer_baseline_traits(text, explicit_traits))
    if inferred_traits:
        _record_trait_state(state_map, "text_inferred", inferred_traits, "text:baseline_inference")

    connected_inferred = _expand_related_traits(_infer_connected_traits(text, explicit_traits | inferred_traits)) - explicit_traits - inferred_traits
    if connected_inferred:
        inferred_traits |= connected_inferred
        _record_trait_state(state_map, "text_inferred", connected_inferred, "text:connected_inference")

    return explicit_traits, inferred_traits, state_map, negations

def _apply_product_trait_signals(
    text: str,
    match: dict,
    explicit_traits: set[str],
    inferred_traits: set[str],
    negations: list[str],
    state_map: dict,
) -> tuple[set[str], set[str], set[str]]:
    """Expand and filter product-level core/default traits, record them in state_map.

    Returns (product_core_traits, product_default_traits, product_genres).
    """
    product_match_stage = match["product_match_stage"]
    product_match_confidence = str(match.get("product_match_confidence") or "low")
    matched_aliases = [
        candidate.get("matched_alias")
        for candidate in match["product_candidates"]
        if candidate.get("matched_alias")
    ]
    product_core_traits = _suppress_unmentioned_product_wireless_traits(
        text,
        _expand_related_traits(set(match.get("product_core_traits") or set())),
        explicit_traits,
        matched_aliases,
    )
    product_default_traits = _suppress_unmentioned_product_wireless_traits(
        text,
        _expand_related_traits(set(match.get("product_default_traits") or set())),
        explicit_traits,
        matched_aliases,
    )
    product_core_traits = _apply_explicit_trait_negations(product_core_traits, negations)
    product_default_traits = _apply_explicit_trait_negations(product_default_traits, negations)
    product_genres = {item for item in (match.get("product_genres") or set()) if isinstance(item, str) and item}

    if product_match_stage == "ambiguous" and product_match_confidence == "low":
        product_core_traits = set()
        product_default_traits = set()
        product_genres = set()

    if product_core_traits:
        product_evidence = (
            f"product:{match['product_subtype']}"
            if product_match_stage == "subtype" and match.get("product_subtype")
            else f"family:{match['product_family']}"
        )
        _record_trait_state(state_map, "product_core", product_core_traits, product_evidence)
    if product_default_traits:
        product_evidence = (
            f"product_default:{match['product_subtype']}"
            if product_match_stage == "subtype" and match.get("product_subtype")
            else f"family_default:{match['product_family']}"
        )
        _record_trait_state(state_map, "product_default", product_default_traits, product_evidence)

    return product_core_traits, product_default_traits, product_genres


def _compute_confirmed_traits(
    explicit_traits: set[str],
    product_core_traits: set[str],
    product_default_traits: set[str],
    product_match_stage: str,
    product_family_confidence: str,
    product_subtype_confidence: str,
    product_candidates: list[dict],
) -> set[str]:
    """Build the confirmed traits set from explicit signals and product match quality."""
    confirmed = set(explicit_traits)
    top_candidate = product_candidates[0] if product_candidates else {}

    decisive_medium = (
        product_match_stage == "subtype"
        and product_subtype_confidence == "medium"
        and bool(top_candidate.get("matched_alias") or top_candidate.get("positive_clues"))
    )
    decisive_subtype = (
        product_match_stage == "subtype"
        and bool(
            top_candidate.get("matched_alias")
            or top_candidate.get("positive_clues")
            or top_candidate.get("family_keyword_hits")
        )
    )
    # Promote product-core traits to confirmed when match is sufficiently confident.
    if product_family_confidence == "high":
        confirmed.update(product_core_traits - SERVICE_DEPENDENT_TRAITS)
    if product_match_stage == "subtype" and (product_subtype_confidence == "high" or decisive_medium or decisive_subtype):
        confirmed.update(product_core_traits - SERVICE_DEPENDENT_TRAITS)

    # Corroborated defaults: product default traits that are also explicit in text.
    corroborated_default = {trait for trait in product_default_traits if trait in explicit_traits}
    confirmed.update(corroborated_default - SERVICE_DEPENDENT_TRAITS)

    return confirmed


def _detect_trait_contradictions(
    explicit_traits: set[str],
    text: str,
    match_contradictions: list[str],
) -> list[str]:
    """Collect trait-level signal contradictions from both product matching and text signals."""
    contradictions = list(match_contradictions)
    if "battery_powered" in explicit_traits and "mains_powered" in explicit_traits:
        contradictions.append("Both battery-powered and mains-powered signals were detected.")
    if "cloud" in explicit_traits and "local_only" in explicit_traits:
        contradictions.append("Both cloud-connected and local-only signals were detected.")
    if "professional" in explicit_traits and "household" in explicit_traits:
        contradictions.append("Both professional/commercial and household-use signals were detected.")
    if "wifi" in explicit_traits and _trait_is_negated(text, "internet") and {"cloud", "ota", "account"} & explicit_traits:
        contradictions.append("Wi-Fi is present while the text also says no internet, but cloud or OTA features were also detected.")
    return contradictions


def extract_traits_v2(description: str, category: str = "") -> dict:
    text = normalize(f"{category} {description}")
    explicit_traits, inferred_traits, state_map, negations = _collect_text_trait_signals(text)
    diagnostics: list[str] = [f"normalized_text={text}"]

    # --- Product matching ---
    match = _hierarchical_product_match_v2(text, explicit_traits | inferred_traits)
    product_candidates = match["product_candidates"]
    matched_products = match["matched_products"]
    routing_matched_products = match["routing_matched_products"]
    confirmed_products = match["confirmed_products"]
    preferred_standard_codes = match["preferred_standard_codes"]
    product_family_confidence = match["product_family_confidence"]
    product_subtype_confidence = match["product_subtype_confidence"]
    product_match_stage = match["product_match_stage"]
    weak_ambiguous_guess = (
        product_match_stage == "ambiguous"
        and str(match.get("product_match_confidence") or "low") == "low"
        and bool(product_candidates)
        and not bool(
            product_candidates[0].get("matched_alias")
            or product_candidates[0].get("family_keyword_hits")
        )
    )
    if weak_ambiguous_guess:
        product_candidates = []
        matched_products = []
        routing_matched_products = []
        confirmed_products = []
        preferred_standard_codes = []
        product_family_confidence = "low"
        product_subtype_confidence = "low"
        match["product_type"] = None
        match["product_family"] = None
        match["product_subtype"] = None
        match["product_candidates"] = []
        match["matched_products"] = []
        match["routing_matched_products"] = []
        match["confirmed_products"] = []
        match["preferred_standard_codes"] = []
        match["product_core_traits"] = set()
        match["product_default_traits"] = set()
        match["product_genres"] = set()
        diagnostics.append("product_guess_suppressed=weak_ambiguous_match")

    # Apply negations to text-level traits before using them in product trait logic.
    explicit_traits = _apply_explicit_trait_negations(explicit_traits, negations)
    inferred_traits = _apply_explicit_trait_negations(inferred_traits, negations)

    # --- Apply product-level trait signals (core / default traits from catalog) ---
    product_core_traits, product_default_traits, product_genres = _apply_product_trait_signals(
        text, match, explicit_traits, inferred_traits, negations, state_map
    )
    functional_classes = set(match["functional_classes"])
    confirmed_functional_classes = set(match["confirmed_functional_classes"])

    # --- Compute confirmed trait set ---
    confirmed_traits = _compute_confirmed_traits(
        explicit_traits, product_core_traits, product_default_traits,
        product_match_stage, product_family_confidence, product_subtype_confidence,
        product_candidates,
    )

    # --- Engine-derived connectivity inference ---
    engine_derived_traits = _expand_related_traits(
        _infer_connected_traits(text, explicit_traits | inferred_traits | product_core_traits | product_default_traits)
    ) - explicit_traits - inferred_traits
    engine_derived_traits = _apply_explicit_trait_negations(engine_derived_traits, negations)
    if engine_derived_traits:
        inferred_traits |= engine_derived_traits
        _record_trait_state(state_map, "engine_derived", engine_derived_traits, "engine:connectivity_inference")

    # --- Diagnostics: product matching ---
    diagnostics.extend(match["diagnostics"])
    if product_candidates:
        diagnostics.append(f"product_winner={product_candidates[0]['id']}")
        diagnostics.append(f"product_alias={product_candidates[0].get('matched_alias') or ''}")
    else:
        diagnostics.append("product_winner=none")

    # --- Contradiction detection ---
    contradictions = _detect_trait_contradictions(explicit_traits, text, match["contradictions"])

    # --- Final trait-set cleanup: expand and filter to known catalog traits ---
    known_traits = _known_trait_ids()
    explicit_traits = {trait for trait in _expand_related_traits(explicit_traits) if trait in known_traits}
    # If battery_powered is explicitly detected from text, suppress mains_power_likely that may
    # have been injected by a product's default traits (e.g. vacuum_cleaner implies mains_power_likely,
    # but a cordless/lithium model should not inherit that).
    if "battery_powered" in explicit_traits and "mains_powered" not in explicit_traits:
        product_default_traits = product_default_traits - {"mains_power_likely"}
    product_core_traits = _apply_explicit_trait_negations(product_core_traits, negations)
    product_default_traits = _apply_explicit_trait_negations(product_default_traits, negations)
    inferred_traits = _apply_explicit_trait_negations(inferred_traits | product_core_traits | product_default_traits, negations)
    inferred_traits = {trait for trait in _expand_related_traits(inferred_traits) if trait in known_traits}
    confirmed_traits = _apply_explicit_trait_negations(confirmed_traits, negations)
    confirmed_traits = {trait for trait in _expand_related_traits(confirmed_traits) if trait in known_traits}

    # --- Diagnostics: final trait sets ---
    diagnostics.append("matched_products=" + ",".join(matched_products))
    diagnostics.append("routing_matched_products=" + ",".join(routing_matched_products))
    diagnostics.append("confirmed_products=" + ",".join(confirmed_products))
    diagnostics.append("product_genres=" + ",".join(sorted(product_genres)))
    diagnostics.append("preferred_standard_codes=" + ",".join(preferred_standard_codes))
    diagnostics.append("explicit_traits=" + ",".join(sorted(explicit_traits)))
    diagnostics.append("confirmed_traits=" + ",".join(sorted(confirmed_traits)))
    diagnostics.append("inferred_traits=" + ",".join(sorted(inferred_traits)))
    diagnostics.append("negations=" + ",".join(negations))
    diagnostics.append("contradiction_severity=" + _contradiction_severity(contradictions))

    match["audit"]["negations"] = negations
    return {
        "product_type": match.get("product_type"),
        "product_family": match.get("product_family"),
        "product_family_confidence": product_family_confidence,
        "product_subtype": match.get("product_subtype"),
        "product_subtype_confidence": product_subtype_confidence,
        "product_match_stage": product_match_stage,
        "matched_products": matched_products,
        "routing_matched_products": routing_matched_products,
        "confirmed_products": confirmed_products,
        "product_genres": sorted(product_genres),
        "preferred_standard_codes": preferred_standard_codes,
        "product_match_confidence": match.get("product_match_confidence"),
        "product_candidates": product_candidates,
        "functional_classes": sorted(functional_classes),
        "confirmed_functional_classes": sorted(confirmed_functional_classes),
        "explicit_traits": sorted(explicit_traits),
        "confirmed_traits": sorted(confirmed_traits),
        "inferred_traits": sorted((explicit_traits | inferred_traits) - confirmed_traits),
        "all_traits": sorted(explicit_traits | inferred_traits),
        "text_explicit_traits": sorted(explicit_traits),
        "text_inferred_traits": sorted({trait for trait in state_map["text_inferred"] if trait in known_traits}),
        "product_core_traits": sorted(product_core_traits & known_traits),
        "product_default_traits": sorted(product_default_traits & known_traits),
        "contradictions": contradictions,
        "contradiction_severity": _contradiction_severity(contradictions),
        "diagnostics": diagnostics,
        "trait_state_map": state_map,
        "trait_evidence": _trait_evidence_items(state_map, confirmed_traits),
        "product_match_audit": match["audit"],
        "engine_version": ENGINE_VERSION,
    }


def extract_traits_v1(description: str, category: str = "") -> dict:
    text = normalize(f"{category} {description}")
    explicit_traits: set[str] = set()
    inferred_traits: set[str] = set()
    confirmed_traits: set[str] = set()
    functional_classes: set[str] = set()
    confirmed_functional_classes: set[str] = set()
    contradictions: list[str] = []
    diagnostics: list[str] = []
    negations = sorted(trait for trait in _COMPILED_NEGATIONS if _trait_is_negated(text, trait))

    _add_regex_trait(text, explicit_traits)
    explicit_traits = _expand_related_traits(explicit_traits)
    explicit_traits = _apply_explicit_trait_negations(explicit_traits, negations)
    inferred_traits.update(_infer_baseline_traits(text, explicit_traits))
    inferred_traits = _apply_explicit_trait_negations(inferred_traits, negations)
    diagnostics.append(f"normalized_text={text}")

    match = _hierarchical_product_match(text, explicit_traits | inferred_traits)
    product_type = match["product_type"]
    product_match_confidence = match["product_match_confidence"]
    product_candidates = match["product_candidates"]
    matched_products = match["matched_products"]
    routing_matched_products = match["routing_matched_products"]
    confirmed_products = match["confirmed_products"]
    preferred_standard_codes = match["preferred_standard_codes"]
    product_family = match["product_family"]
    product_family_confidence = match["product_family_confidence"]
    product_subtype = match["product_subtype"]
    product_subtype_confidence = match["product_subtype_confidence"]
    product_match_stage = match["product_match_stage"]
    matched_aliases = [candidate.get("matched_alias") for candidate in product_candidates if candidate.get("matched_alias")]

    inferred_traits.update(
        _suppress_unmentioned_product_wireless_traits(
            text,
            _expand_related_traits(set(match["family_traits"])),
            explicit_traits,
            matched_aliases,
        )
    )
    inferred_traits = _apply_explicit_trait_negations(inferred_traits, negations)
    inferred_traits.update(
        _suppress_unmentioned_product_wireless_traits(
            text,
            _expand_related_traits(set(match["subtype_traits"])),
            explicit_traits,
            matched_aliases,
        )
    )
    inferred_traits = _apply_explicit_trait_negations(inferred_traits, negations)
    functional_classes.update(match["functional_classes"])
    confirmed_functional_classes.update(match["confirmed_functional_classes"])
    if product_family_confidence == "high":
        confirmed_traits.update(
            _suppress_unmentioned_product_wireless_traits(
                text,
                _expand_related_traits(set(match["family_traits"])),
                explicit_traits,
                matched_aliases,
            )
        )
        confirmed_traits = _apply_explicit_trait_negations(confirmed_traits, negations)
    if product_match_stage == "subtype" and product_subtype_confidence == "high":
        confirmed_traits.update(
            _suppress_unmentioned_product_wireless_traits(
                text,
                _expand_related_traits(set(match["subtype_traits"])),
                explicit_traits,
                matched_aliases,
            )
        )
        confirmed_traits = _apply_explicit_trait_negations(confirmed_traits, negations)

    diagnostics.extend(match["diagnostics"])
    if product_candidates:
        diagnostics.append(f"product_winner={product_candidates[0]['id']}")
        diagnostics.append(f"product_alias={product_candidates[0].get('matched_alias') or ''}")
    else:
        diagnostics.append("product_winner=none")

    contradictions.extend(match["contradictions"])

    if "battery_powered" in explicit_traits and "mains_powered" in explicit_traits:
        contradictions.append("Both battery-powered and mains-powered signals were detected.")
    if "cloud" in explicit_traits and "local_only" in explicit_traits:
        contradictions.append("Both cloud-connected and local-only signals were detected.")
    if "professional" in explicit_traits and "household" in explicit_traits:
        contradictions.append("Both professional/commercial and household-use signals were detected.")
    if "wifi" in explicit_traits and _trait_is_negated(text, "internet") and {"cloud", "ota", "account"} & explicit_traits:
        contradictions.append("Wi-Fi is present while the text also says no internet, but cloud or OTA features were also detected.")

    known_traits = _known_trait_ids()
    explicit_traits = _apply_explicit_trait_negations(_expand_related_traits(explicit_traits), negations)
    inferred_traits = _apply_explicit_trait_negations(_expand_related_traits(inferred_traits), negations)
    confirmed_traits = _apply_explicit_trait_negations(_expand_related_traits(confirmed_traits), negations)
    explicit_traits = {t for t in explicit_traits if t in known_traits}
    inferred_traits = {t for t in inferred_traits if t in known_traits}
    confirmed_traits = {t for t in (confirmed_traits | explicit_traits) if t in known_traits}

    diagnostics.append("matched_products=" + ",".join(matched_products))
    diagnostics.append("routing_matched_products=" + ",".join(routing_matched_products))
    diagnostics.append("confirmed_products=" + ",".join(confirmed_products))
    diagnostics.append("preferred_standard_codes=" + ",".join(preferred_standard_codes))
    diagnostics.append("explicit_traits=" + ",".join(sorted(explicit_traits)))
    diagnostics.append("confirmed_traits=" + ",".join(sorted(confirmed_traits)))
    diagnostics.append("inferred_traits=" + ",".join(sorted(inferred_traits)))
    diagnostics.append("negations=" + ",".join(negations))
    diagnostics.append("contradiction_severity=" + _contradiction_severity(contradictions))

    return {
        "product_type": product_type,
        "product_family": product_family,
        "product_family_confidence": product_family_confidence,
        "product_subtype": product_subtype,
        "product_subtype_confidence": product_subtype_confidence,
        "product_match_stage": product_match_stage,
        "matched_products": matched_products,
        "routing_matched_products": routing_matched_products,
        "confirmed_products": confirmed_products,
        "preferred_standard_codes": preferred_standard_codes,
        "product_match_confidence": product_match_confidence,
        "product_candidates": product_candidates,
        "functional_classes": sorted(functional_classes),
        "confirmed_functional_classes": sorted(confirmed_functional_classes),
        "explicit_traits": sorted(explicit_traits),
        "confirmed_traits": sorted(confirmed_traits),
        "inferred_traits": sorted(inferred_traits),
        "all_traits": sorted(explicit_traits | inferred_traits),
        "contradictions": contradictions,
        "contradiction_severity": _contradiction_severity(contradictions),
        "diagnostics": diagnostics,
    }


def extract_traits(description: str, category: str = "") -> dict:
    return extract_traits_v2(description=description, category=category)


def _known_trait_ids() -> set[str]:
    global TRAIT_IDS_CACHE
    if TRAIT_IDS_CACHE is None:
        TRAIT_IDS_CACHE = {row["id"] for row in get_knowledge_base_snapshot().traits}
    return TRAIT_IDS_CACHE


def reset_classifier_cache() -> None:
    global TRAIT_IDS_CACHE
    TRAIT_IDS_CACHE = None
    from .matching import reset_matching_cache
    from .scoring import reset_scoring_cache
    reset_matching_cache()
    reset_scoring_cache()


__all__ = [
    "TRAIT_IDS_CACHE",
    "_known_trait_ids",
    "extract_traits",
    "extract_traits_v1",
    "extract_traits_v2",
    "reset_classifier_cache",
]
