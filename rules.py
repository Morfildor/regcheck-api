from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable

from models import AnalysisResult, FactModel, FeatureEvidence, Finding


@dataclass(frozen=True)
class PatternSpec:
    pattern: re.Pattern[str]
    label: str
    weight: float = 1.0


@dataclass
class MatchResult:
    hit: bool
    score: float
    positive_hits: list[str]
    negative_hits: list[str]
    negated: bool


STATUS_ORDER = {"FAIL": 4, "WARN": 3, "INFO": 2, "PASS": 1}
RISK_ORDER = {"LOW": 1, "MEDIUM": 2, "HIGH": 3, "CRITICAL": 4}


def rx(pattern: str, label: str, weight: float = 1.0) -> PatternSpec:
    return PatternSpec(re.compile(pattern, re.IGNORECASE), label, weight)


FEATURES: dict[str, dict[str, list[PatternSpec]]] = {
    "wifi": {
        "pos": [rx(r"\bwifi\b", "wifi", 2.0), rx(r"\bwi[ -]?fi\b", "wi-fi", 2.0), rx(r"\bwlan\b", "wlan", 1.5), rx(r"\b802\.11[a-z0-9.-]*\b", "802.11", 2.0)],
        "neg": [rx(r"\bno wifi\b", "no wifi", 3.0), rx(r"\bwithout wifi\b", "without wifi", 3.0)],
    },
    "bluetooth": {
        "pos": [rx(r"\bbluetooth\b", "bluetooth", 2.0), rx(r"\bble\b", "ble", 2.0), rx(r"\bbt ?[45](\.\d+)?\b", "bt version", 1.5)],
        "neg": [rx(r"\bno bluetooth\b", "no bluetooth", 3.0)],
    },
    "mesh_radio": {
        "pos": [rx(r"\bzigbee\b", "zigbee", 2.0), rx(r"\bthread\b", "thread", 2.0), rx(r"\bmatter\b", "matter", 2.0), rx(r"\bz-wave\b", "z-wave", 2.0)],
        "neg": [],
    },
    "cellular": {
        "pos": [rx(r"\blte\b", "lte", 2.0), rx(r"\b4g\b", "4g", 2.0), rx(r"\b5g\b", "5g", 2.0), rx(r"\bnb-?iot\b", "nb-iot", 2.0), rx(r"\bcat-?m\b", "cat-m", 2.0), rx(r"\bcellular\b", "cellular", 1.5), rx(r"\bgsm\b", "gsm", 1.5)],
        "neg": [],
    },
    "nfc": {"pos": [rx(r"\bnfc\b", "nfc", 2.0), rx(r"\bnear field\b", "near field", 1.5), rx(r"\brfid\b", "rfid", 1.2)], "neg": []},
    "cloud": {
        "pos": [rx(r"\bcloud\b", "cloud", 1.6), rx(r"\baws\b", "aws", 2.0), rx(r"\bazure\b", "azure", 2.0), rx(r"\bgoogle cloud\b", "google cloud", 2.0), rx(r"\bbackend\b", "backend", 1.4), rx(r"\bremote server\b", "remote server", 1.6), rx(r"\bapi\b", "api", 1.0), rx(r"\bsaas\b", "saas", 1.6), rx(r"\bhosted\b", "hosted", 1.0)],
        "neg": [rx(r"\bno cloud\b", "no cloud", 3.0), rx(r"\boffline only\b", "offline only", 3.0), rx(r"\bfully offline\b", "fully offline", 3.0)],
    },
    "internet": {
        "pos": [rx(r"\binternet\b", "internet", 1.8), rx(r"\bonline\b", "online", 1.4), rx(r"\bconnected\b", "connected", 1.0), rx(r"\biot\b", "iot", 1.6), rx(r"\bremote access\b", "remote access", 1.8)],
        "neg": [rx(r"\bno internet\b", "no internet", 3.0), rx(r"\bstandalone\b", "standalone", 2.0), rx(r"\bair-?gapped\b", "air-gapped", 3.0)],
    },
    "local_only": {
        "pos": [rx(r"\blocal only\b", "local only", 2.5), rx(r"\boffline\b", "offline", 2.0), rx(r"\bstandalone\b", "standalone", 1.8), rx(r"\bon-device only\b", "on-device only", 2.2), rx(r"\bno remote\b", "no remote", 2.2)],
        "neg": [],
    },
    "app": {
        "pos": [rx(r"\bmobile app\b", "mobile app", 2.0), rx(r"\bcompanion app\b", "companion app", 2.0), rx(r"\bandroid app\b", "android app", 1.8), rx(r"\bios app\b", "ios app", 1.8), rx(r"\bweb app\b", "web app", 1.8), rx(r"\bdashboard\b", "dashboard", 1.0)],
        "neg": [rx(r"\bno app\b", "no app", 2.5)],
    },
    "software": {
        "pos": [rx(r"\bsoftware\b", "software", 1.4), rx(r"\bfirmware\b", "firmware", 1.8), rx(r"\bembedded\b", "embedded", 1.2), rx(r"\bmicrocontroller\b", "microcontroller", 1.4), rx(r"\bprocessor\b", "processor", 1.0), rx(r"\brtos\b", "rtos", 1.5), rx(r"\blinux\b", "linux", 1.5)],
        "neg": [rx(r"\bno software\b", "no software", 3.0), rx(r"\bpurely mechanical\b", "purely mechanical", 3.0)],
    },
    "ota": {
        "pos": [rx(r"\bota\b", "ota", 2.0), rx(r"\bover-the-air\b", "over-the-air", 2.0), rx(r"\bfirmware update\b", "firmware update", 1.8), rx(r"\bsoftware update\b", "software update", 1.6), rx(r"\bremote update\b", "remote update", 1.8), rx(r"\bfota\b", "fota", 2.0)],
        "neg": [rx(r"\bno update\b", "no update", 1.5)],
    },
    "signed_updates": {"pos": [rx(r"\bsigned firmware\b", "signed firmware", 2.0), rx(r"\bcode signing\b", "code signing", 2.0), rx(r"\bsecure boot\b", "secure boot", 1.6), rx(r"\bsignature verification\b", "signature verification", 1.8)], "neg": []},
    "rollback": {"pos": [rx(r"\brollback\b", "rollback", 1.5), rx(r"\bdowngrade protection\b", "downgrade protection", 2.0), rx(r"\banti-rollback\b", "anti-rollback", 2.0)], "neg": []},
    "auth": {
        "pos": [rx(r"\blogin\b", "login", 1.5), rx(r"\bpassword\b", "password", 1.5), rx(r"\bauthentication\b", "authentication", 1.6), rx(r"\buser account\b", "user account", 1.6), rx(r"\bcredentials\b", "credentials", 1.4), rx(r"\bpin\b", "pin", 1.0), rx(r"\bpairing\b", "pairing", 1.0), rx(r"\boauth\b", "oauth", 2.0)],
        "neg": [rx(r"\bno login\b", "no login", 2.8), rx(r"\bno authentication\b", "no authentication", 2.8)],
    },
    "default_password": {"pos": [rx(r"\bdefault password\b", "default password", 3.0), rx(r"\bdefault credentials\b", "default credentials", 3.0), rx(r"\badmin/admin\b", "admin/admin", 3.0), rx(r"\bsame password\b", "same password", 2.5)], "neg": []},
    "unique_credentials": {"pos": [rx(r"\bunique password\b", "unique password", 2.5), rx(r"\bper-device\b", "per-device", 2.0), rx(r"\bdevice-specific\b", "device-specific", 2.0), rx(r"\bunique credentials\b", "unique credentials", 2.5)], "neg": []},
    "mfa": {"pos": [rx(r"\bmfa\b", "mfa", 2.2), rx(r"\b2fa\b", "2fa", 2.2), rx(r"\btwo-factor\b", "two-factor", 2.2), rx(r"\bmulti-factor\b", "multi-factor", 2.2)], "neg": []},
    "brute_force": {"pos": [rx(r"\brate limit\b", "rate limit", 1.8), rx(r"\bbrute force\b", "brute force", 1.8), rx(r"\blockout\b", "lockout", 1.5)], "neg": []},
    "personal_data": {
        "pos": [rx(r"\bpersonal data\b", "personal data", 2.2), rx(r"\buser data\b", "user data", 1.6), rx(r"\bemail\b", "email", 1.4), rx(r"\bname\b", "name", 0.8), rx(r"\baddress\b", "address", 1.0), rx(r"\baccount\b", "account", 1.0), rx(r"\bprofile\b", "profile", 1.0)],
        "neg": [rx(r"\bno personal data\b", "no personal data", 3.0), rx(r"\bno user data\b", "no user data", 3.0)],
    },
    "health_data": {"pos": [rx(r"\bhealth\b", "health", 1.8), rx(r"\bheart rate\b", "heart rate", 2.2), rx(r"\bspo2\b", "spo2", 2.2), rx(r"\becg\b", "ecg", 2.2), rx(r"\bsleep data\b", "sleep data", 2.0), rx(r"\bbody temperature\b", "body temperature", 2.0)], "neg": []},
    "location_data": {"pos": [rx(r"\blocation\b", "location", 1.8), rx(r"\bgps\b", "gps", 2.2), rx(r"\bgeolocation\b", "geolocation", 2.2), rx(r"\btracking\b", "tracking", 1.4), rx(r"\blatitude\b", "latitude", 1.8), rx(r"\blongitude\b", "longitude", 1.8)], "neg": []},
    "biometric_data": {"pos": [rx(r"\bbiometric\b", "biometric", 2.2), rx(r"\bfingerprint\b", "fingerprint", 2.2), rx(r"\bface id\b", "face id", 2.0), rx(r"\bvoice recognition\b", "voice recognition", 2.0), rx(r"\biris\b", "iris", 2.0)], "neg": []},
    "telemetry": {"pos": [rx(r"\btelemetry\b", "telemetry", 1.8), rx(r"\banalytics\b", "analytics", 1.5), rx(r"\busage data\b", "usage data", 1.5), rx(r"\blogs?\b", "logs", 0.8), rx(r"\bevent history\b", "event history", 1.2)], "neg": []},
    "retention": {"pos": [rx(r"\bstore[s]? data\b", "stores data", 1.5), rx(r"\bdata retention\b", "data retention", 2.0), rx(r"\bhistory\b", "history", 1.0), rx(r"\barchive\b", "archive", 1.0), rx(r"\brecords?\b", "records", 0.8)], "neg": []},
    "sharing": {"pos": [rx(r"\bthird party\b", "third party", 1.8), rx(r"\bshare data\b", "share data", 2.0), rx(r"\badvertising\b", "advertising", 1.5), rx(r"\bdata broker\b", "data broker", 2.2), rx(r"\banalytics provider\b", "analytics provider", 1.8)], "neg": []},
    "encryption": {"pos": [rx(r"\bencrypt\w*\b", "encrypt", 1.8), rx(r"\baes\b", "aes", 1.5), rx(r"\bend-to-end\b", "end-to-end", 2.0), rx(r"\bat rest\b", "at rest", 1.0), rx(r"\bin transit\b", "in transit", 1.0)], "neg": []},
    "tls": {"pos": [rx(r"\btls\b", "tls", 2.0), rx(r"\bhttps\b", "https", 2.0), rx(r"\bssl\b", "ssl", 1.0)], "neg": []},
    "anonymisation": {"pos": [rx(r"\banonymi\w*\b", "anonymised", 1.8), rx(r"\bpseudonym\w*\b", "pseudonymised", 1.8), rx(r"\baggregated\b", "aggregated", 1.2), rx(r"\bde-identified\b", "de-identified", 1.8)], "neg": []},
    "cross_border": {"pos": [rx(r"\bus server\b", "us server", 2.2), rx(r"\bnon-eu\b", "non-eu", 1.8), rx(r"\boutside eu\b", "outside eu", 1.8), rx(r"\btransfer to\b", "transfer to", 1.0)], "neg": []},
    "ai": {
        "pos": [rx(r"\bartificial intelligence\b", "artificial intelligence", 2.5), rx(r"\bmachine learning\b", "machine learning", 2.5), rx(r"\bdeep learning\b", "deep learning", 2.5), rx(r"\bllm\b", "llm", 2.2), rx(r"\bcomputer vision\b", "computer vision", 2.2), rx(r"\brecommendation engine\b", "recommendation engine", 2.0), rx(r"\bpredictive\b", "predictive", 1.5), rx(r"\binference\b", "inference", 1.5), rx(r"\bai-powered\b", "ai-powered", 2.2)],
        "neg": [rx(r"\bno ai\b", "no ai", 3.0), rx(r"\bno ml\b", "no ml", 3.0), rx(r"\bno ai features\b", "no ai features", 3.0)],
    },
    "camera": {"pos": [rx(r"\bcamera\b", "camera", 2.0), rx(r"\bvideo stream\b", "video stream", 2.0), rx(r"\bcctv\b", "cctv", 2.0), rx(r"\bsurveillance\b", "surveillance", 2.0), rx(r"\bimage capture\b", "image capture", 1.8)], "neg": []},
    "face_recognition": {"pos": [rx(r"\bface recognition\b", "face recognition", 3.0), rx(r"\bfacial recognition\b", "facial recognition", 3.0), rx(r"\bface detection\b", "face detection", 2.0)], "neg": []},
    "voice_ai": {"pos": [rx(r"\bvoice assistant\b", "voice assistant", 2.4), rx(r"\bwake word\b", "wake word", 2.2), rx(r"\bspeech recognition\b", "speech recognition", 2.2), rx(r"\bvoice command\b", "voice command", 1.8), rx(r"\balexa\b", "alexa", 1.8), rx(r"\bgoogle assistant\b", "google assistant", 1.8)], "neg": []},
    "emotion_ai": {"pos": [rx(r"\bemotion recognition\b", "emotion recognition", 3.0), rx(r"\bemotion detection\b", "emotion detection", 3.0), rx(r"\bmood detection\b", "mood detection", 2.6)], "neg": []},
    "automated_decision": {"pos": [rx(r"\bautomated decision\b", "automated decision", 2.6), rx(r"\bautonomous decision\b", "autonomous decision", 2.6), rx(r"\bscoring\b", "scoring", 1.5), rx(r"\branking users\b", "ranking users", 2.6)], "neg": []},
    "prohibited_ai": {"pos": [rx(r"\bsocial scoring\b", "social scoring", 4.0), rx(r"\breal-time biometric surveillance\b", "real-time biometric surveillance", 4.0), rx(r"\bsubliminal manipulation\b", "subliminal manipulation", 4.0), rx(r"\bexploit vulnerability ai\b", "exploit vulnerability ai", 4.0)], "neg": []},
    "mains": {"pos": [rx(r"\bmains\b", "mains", 2.0), rx(r"\b230v\b", "230v", 2.0), rx(r"\b220v\b", "220v", 2.0), rx(r"\b110v\b", "110v", 2.0), rx(r"\b120v\b", "120v", 2.0), rx(r"\bac power\b", "ac power", 2.0), rx(r"\bwall plug\b", "wall plug", 1.6), rx(r"\bhardwired\b", "hardwired", 1.8)], "neg": []},
    "battery": {"pos": [rx(r"\bbattery\b", "battery", 1.4), rx(r"\brechargeable\b", "rechargeable", 1.4), rx(r"\bli-?ion\b", "li-ion", 2.0), rx(r"\blithium ion\b", "lithium ion", 2.0), rx(r"\baa batter(y|ies)\b", "aa battery", 1.8), rx(r"\bcoin cell\b", "coin cell", 1.8)], "neg": []},
    "usb_power": {"pos": [rx(r"\busb[- ]?c power\b", "usb-c power", 2.0), rx(r"\busb powered\b", "usb powered", 2.0), rx(r"\b5v usb\b", "5v usb", 2.0)], "neg": []},
    "poe": {"pos": [rx(r"\bpoe\b", "poe", 2.0), rx(r"\bpower over ethernet\b", "power over ethernet", 2.0)], "neg": []},
    "high_voltage": {"pos": [rx(r"\bhigh voltage\b", "high voltage", 2.2), rx(r"\b400v\b", "400v", 2.0), rx(r"\binverter\b", "inverter", 1.5), rx(r"\bmotor drive\b", "motor drive", 1.5)], "neg": []},
    "consumer": {"pos": [rx(r"\bconsumer\b", "consumer", 2.0), rx(r"\bhousehold\b", "household", 1.8), rx(r"\bhome use\b", "home use", 1.8), rx(r"\bresidential\b", "residential", 1.8), rx(r"\bretail\b", "retail", 1.2)], "neg": []},
    "industrial": {"pos": [rx(r"\bindustrial\b", "industrial", 2.2), rx(r"\bb2b\b", "b2b", 1.5), rx(r"\bfactory\b", "factory", 2.0), rx(r"\bwarehouse\b", "warehouse", 1.8), rx(r"\bscada\b", "scada", 2.4), rx(r"\bplc\b", "plc", 2.4)], "neg": []},
    "medical": {"pos": [rx(r"\bmedical\b", "medical", 2.4), rx(r"\bpatient\b", "patient", 2.0), rx(r"\bclinical\b", "clinical", 2.0), rx(r"\bdiagnostic\b", "diagnostic", 2.2), rx(r"\bhospital\b", "hospital", 2.0)], "neg": []},
    "child": {"pos": [rx(r"\bchild\b", "child", 2.0), rx(r"\bchildren\b", "children", 2.0), rx(r"\bkids\b", "kids", 2.0), rx(r"\btoy\b", "toy", 1.8), rx(r"\bminors\b", "minors", 2.2)], "neg": []},
    "safety_function": {"pos": [rx(r"\bsafety function\b", "safety function", 2.4), rx(r"\bemergency\b", "emergency", 1.6), rx(r"\balarm\b", "alarm", 1.4), rx(r"\bfire\b", "fire", 1.4), rx(r"\bsmoke\b", "smoke", 1.6), rx(r"\bco detector\b", "co detector", 2.0), rx(r"\bfail safe\b", "fail safe", 2.0)], "neg": []},
    "vuln_disclosure": {"pos": [rx(r"\bvulnerability disclosure\b", "vulnerability disclosure", 2.5), rx(r"\bbug bounty\b", "bug bounty", 2.0), rx(r"\bresponsible disclosure\b", "responsible disclosure", 2.5), rx(r"\bcvd policy\b", "cvd policy", 2.5), rx(r"\bsecurity advisory\b", "security advisory", 1.8)], "neg": []},
    "sbom": {"pos": [rx(r"\bsbom\b", "sbom", 2.5), rx(r"\bsoftware bill of materials\b", "software bill of materials", 2.5), rx(r"\bcyclonedx\b", "cyclonedx", 2.0), rx(r"\bspdx\b", "spdx", 2.0)], "neg": []},
    "pentest": {"pos": [rx(r"\bpenetration test\b", "penetration test", 2.2), rx(r"\bpentest\b", "pentest", 2.2), rx(r"\bsecurity audit\b", "security audit", 1.8), rx(r"\bred team\b", "red team", 1.8)], "neg": []},
    "network_seg": {"pos": [rx(r"\bnetwork segmentation\b", "network segmentation", 2.0), rx(r"\bvlan\b", "vlan", 1.5), rx(r"\bdmz\b", "dmz", 1.5), rx(r"\bfirewall\b", "firewall", 1.5), rx(r"\bisolated network\b", "isolated network", 2.0)], "neg": []},
    "repairability": {"pos": [rx(r"\brepair\w*\b", "repair", 1.6), rx(r"\breplaceable\b", "replaceable", 1.6), rx(r"\bspare part\b", "spare part", 1.6), rx(r"\bright to repair\b", "right to repair", 2.0), rx(r"\buser replaceable\b", "user replaceable", 1.8)], "neg": []},
    "recycled": {"pos": [rx(r"\brecycled\b", "recycled", 1.4), rx(r"\brecycling\b", "recycling", 1.4), rx(r"\bcircular\b", "circular", 1.4), rx(r"\bend of life\b", "end of life", 1.4)], "neg": []},
    "energy_label": {"pos": [rx(r"\benergy label\b", "energy label", 2.0), rx(r"\benergy class\b", "energy class", 2.0), rx(r"\benergy rating\b", "energy rating", 2.0), rx(r"\ba\+\+\+\b", "a+++", 1.4), rx(r"\berp\b", "erp", 1.2)], "neg": []},
}


def normalize_text(description: str, category: str = "") -> str:
    text = f"{category} {description}".strip().lower()
    text = text.replace("wi-fi", "wifi")
    text = text.replace("bluetooth low energy", "ble")
    text = text.replace("over-the-air", "ota")
    text = re.sub(r"[^a-z0-9.+#\-/\s]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def match_feature(text: str, feature_name: str) -> MatchResult:
    cfg = FEATURES[feature_name]
    pos_hits: list[str] = []
    neg_hits: list[str] = []
    score = 0.0

    for spec in cfg.get("pos", []):
        if spec.pattern.search(text):
            pos_hits.append(spec.label)
            score += spec.weight

    for spec in cfg.get("neg", []):
        if spec.pattern.search(text):
            neg_hits.append(spec.label)
            score -= spec.weight

    negated = len(neg_hits) > 0
    hit = score > 0.6 and len(pos_hits) > 0
    if negated and score <= 0.6:
        hit = False
        score = max(score, 0.0)

    return MatchResult(hit=hit, score=round(max(score, 0.0), 2), positive_hits=pos_hits, negative_hits=neg_hits, negated=negated)


def _set_feature(facts: FactModel, field_name: str, match: MatchResult) -> None:
    setattr(facts, field_name, match.hit)
    facts.evidence[field_name] = FeatureEvidence(
        score=match.score,
        positive_hits=match.positive_hits,
        negative_hits=match.negative_hits,
        hit=match.hit,
        negated=match.negated,
    )


def extract_facts(description: str, category: str = "") -> FactModel:
    text = normalize_text(description, category)
    facts = FactModel(raw_text=description, normalized_text=text)

    for feature_name, target in [
        ("cloud", "cloud"), ("internet", "internet"), ("local_only", "local_only"), ("app", "app"),
        ("software", "software"), ("ota", "ota"), ("signed_updates", "signed_updates"), ("rollback", "rollback_protection"),
        ("auth", "auth"), ("default_password", "default_password"), ("unique_credentials", "unique_credentials"), ("mfa", "mfa"),
        ("brute_force", "brute_force_protection"), ("personal_data", "personal_data"), ("health_data", "health_data"),
        ("location_data", "location_data"), ("biometric_data", "biometric_data"), ("telemetry", "telemetry"),
        ("retention", "data_retention"), ("sharing", "data_sharing"), ("encryption", "encryption"), ("tls", "tls"),
        ("anonymisation", "anonymisation"), ("cross_border", "cross_border_transfer"), ("ai", "ai"),
        ("camera", "camera"), ("face_recognition", "face_recognition"), ("voice_ai", "voice_ai"),
        ("emotion_ai", "emotion_ai"), ("automated_decision", "automated_decision"), ("prohibited_ai", "prohibited_ai_signal"),
        ("mains", "mains_power"), ("battery", "battery_power"), ("usb_power", "usb_power"), ("poe", "poe_power"),
        ("high_voltage", "high_voltage"), ("consumer", "consumer"), ("industrial", "industrial"), ("medical", "medical_context"),
        ("child", "child_context"), ("safety_function", "safety_function"), ("vuln_disclosure", "vuln_disclosure"),
        ("sbom", "sbom"), ("pentest", "pentest"), ("network_seg", "network_segmentation"), ("repairability", "repairability"),
        ("recycled", "recycled"), ("energy_label", "energy_label"),
    ]:
        _set_feature(facts, target, match_feature(text, feature_name))

    radio_map = {"wifi": "wifi", "bluetooth": "bluetooth", "mesh_radio": "mesh", "cellular": "cellular", "nfc": "nfc"}
    for feature_name, radio_name in radio_map.items():
        match = match_feature(text, feature_name)
        if match.hit:
            facts.radios.append(radio_name)
        facts.evidence[feature_name] = FeatureEvidence(
            score=match.score,
            positive_hits=match.positive_hits,
            negative_hits=match.negative_hits,
            hit=match.hit,
            negated=match.negated,
        )

    facts.radios = sorted(set(facts.radios))
    facts.has_radio = bool(facts.radios)
    facts.firmware = facts.software or facts.ota or bool(re.search(r"\bfirmware\b", text))

    if facts.cloud:
        facts.internet = True
    if facts.local_only and not facts.cloud:
        facts.internet = False if not facts.app else facts.internet
    if facts.health_data:
        facts.personal_data = True
        if "health" not in facts.sensitive_data:
            facts.sensitive_data.append("health")
    if facts.location_data:
        facts.personal_data = True
        if "location" not in facts.sensitive_data:
            facts.sensitive_data.append("location")
    if facts.biometric_data:
        facts.personal_data = True
        if "biometric" not in facts.sensitive_data:
            facts.sensitive_data.append("biometric")
    if facts.face_recognition:
        facts.ai = True if facts.ai is not False else facts.ai
        facts.camera = True
    if facts.voice_ai:
        facts.ai = True if facts.ai is not False else facts.ai
    if facts.app or facts.cloud or facts.internet or facts.ota:
        facts.software = True
    if facts.battery_power and facts.mains_power:
        facts.contradictions.append("Description suggests both battery-powered and mains-powered operation. Confirm primary power architecture.")
    if facts.local_only and facts.cloud:
        facts.contradictions.append("Description mentions both local/offline operation and cloud/backend connectivity.")
    if facts.personal_data is False and (facts.health_data or facts.location_data or facts.biometric_data):
        facts.contradictions.append("Description says no personal data, but also mentions data types that are typically personal data.")
    if facts.auth is False and (facts.mfa or facts.unique_credentials or facts.default_password):
        facts.contradictions.append("Description says no login/authentication, but also contains authentication-related signals.")
    if facts.ai is False and (facts.face_recognition or facts.voice_ai or facts.emotion_ai or facts.automated_decision):
        facts.contradictions.append("Description says no AI, but also mentions AI-like functionality.")
    if facts.high_voltage:
        facts.mains_power = True

    return facts


def infer_directives(facts: FactModel, requested: Iterable[str] | None = None) -> list[str]:
    directives = set(requested or [])

    if facts.has_radio:
        directives.add("RED")
    if facts.software or facts.internet or facts.app or facts.ota or facts.cloud or facts.has_radio:
        directives.add("CRA")
    if facts.personal_data or facts.sensitive_data or facts.telemetry or facts.data_sharing:
        directives.add("GDPR")
    if facts.ai or facts.face_recognition or facts.voice_ai or facts.emotion_ai or facts.automated_decision:
        directives.add("AI_Act")
    if facts.mains_power or facts.high_voltage:
        directives.add("LVD")
    if facts.software or facts.mains_power or facts.battery_power or facts.has_radio or facts.usb_power or facts.poe_power:
        directives.add("EMC")
    if facts.repairability or facts.recycled or facts.energy_label:
        directives.add("ESPR")

    ordered = [d for d in ["RED", "CRA", "GDPR", "AI_Act", "LVD", "EMC", "ESPR"] if d in directives]
    facts.inferred_directives = ordered
    return ordered


def add_finding(findings: list[Finding], directive: str, article: str, status: str, finding: str, action: str | None = None) -> None:
    findings.append(Finding(directive=directive, article=article, status=status, finding=finding, action=action))


# Directive analyzers

def analyze_red(facts: FactModel, depth: str) -> list[Finding]:
    findings: list[Finding] = []
    if not facts.has_radio:
        add_finding(findings, "RED", "Art.2(1) / Art.3(3)(d-f) — Applicability", "INFO", "No radio interface was inferred. RED cybersecurity delegated requirements normally apply only to radio equipment.", "Confirm whether the product intentionally emits or receives radio waves.")
        return findings

    radio_list = ", ".join(facts.radios)
    add_finding(findings, "RED", "Art.3(3)(d-f) — Scope trigger", "WARN" if facts.internet or facts.app else "INFO", f"Radio interface detected ({radio_list}). RED cybersecurity scope is likely triggered.", "Map applicable RED essential requirements and identify harmonised standard strategy, especially EN 18031 series where relevant.")

    if facts.default_password:
        add_finding(findings, "RED", "Art.3(3)(d) — Network protection", "FAIL", "Default or common credentials were inferred. That is a strong non-conformity risk for RED cybersecurity compliance.", "Remove default credentials and use unique per-device onboarding or forced credential setup.")
    elif facts.unique_credentials:
        add_finding(findings, "RED", "Art.3(3)(d) — Network protection", "PASS", "Unique credentials or per-device credentialing was inferred.")
    else:
        add_finding(findings, "RED", "Art.3(3)(d) — Network protection", "WARN", "Authentication posture is unclear from the description.", "Clarify user authentication, pairing, credential uniqueness, and brute-force protections.")

    if facts.ota and not facts.signed_updates:
        add_finding(findings, "RED", "Art.3(3)(d) — Secure updates", "FAIL", "OTA or remote updates were inferred, but no signed update or secure boot controls were detected.", "Implement signed firmware, integrity verification, and rollback protection.")
    elif facts.ota and facts.signed_updates:
        add_finding(findings, "RED", "Art.3(3)(d) — Secure updates", "PASS", "OTA capability with signed-update signals was inferred.")

    if facts.personal_data:
        if facts.encryption or facts.tls:
            add_finding(findings, "RED", "Art.3(3)(e) — Personal data protection", "PASS", "Personal data processing was inferred together with transport/storage security signals.")
        else:
            add_finding(findings, "RED", "Art.3(3)(e) — Personal data protection", "WARN", "Personal data processing was inferred, but encryption or secure transport was not clearly stated.", "Clarify encryption in transit and at rest, plus access control and minimisation measures.")

    if facts.child_context or facts.location_data or facts.telemetry:
        add_finding(findings, "RED", "Art.3(3)(f) — Fraud / abuse exposure", "WARN", "Usage context suggests fraud, misuse, or abuse considerations may be relevant.", "Assess misuse scenarios such as spoofing, fraudulent enrolment, false alerts, or abuse against children/consumers.")

    if depth == "deep":
        add_finding(findings, "RED", "Conformity route", "INFO", "Prepare RED technical documentation, risk assessment, cybersecurity rationale, and standards mapping. For gaps against harmonised standards, a notified body route may need consideration.")
    return findings


def analyze_cra(facts: FactModel, depth: str) -> list[Finding]:
    findings: list[Finding] = []
    if not (facts.software or facts.internet or facts.app or facts.cloud or facts.ota or facts.has_radio):
        add_finding(findings, "CRA", "Art.2 / product with digital elements — Applicability", "INFO", "No strong software or digital-element signal was inferred. CRA may be out of scope if the product is purely mechanical.", "Confirm whether firmware, software, or update capability exists.")
        return findings

    is_critical = bool(facts.safety_function and facts.industrial)
    is_important_ii = bool(facts.medical_context or (facts.safety_function and facts.internet))
    is_important_i = bool(facts.has_radio or facts.auth or facts.ota or facts.cloud)

    if is_critical:
        add_finding(findings, "CRA", "Annex III / classification", "FAIL", "Product signals suggest a critical or very high assurance context.", "Validate CRA classification and third-party conformity assessment need before market access.")
    elif is_important_ii:
        add_finding(findings, "CRA", "Annex II / classification", "FAIL", "Product signals suggest Important Class II characteristics.", "Document classification rationale and plan conformity assessment route early.")
    elif is_important_i:
        add_finding(findings, "CRA", "Annex II / classification", "WARN", "Product signals suggest Important Class I characteristics.", "Confirm final classification and whether harmonised standards can fully support self-assessment.")
    else:
        add_finding(findings, "CRA", "Default classification", "INFO", "Product appears closer to default CRA classification based on current signals.")

    if facts.default_password:
        add_finding(findings, "CRA", "Annex I §1 — No known exploitable vulnerabilities", "FAIL", "Default credentials were inferred, which is a major CRA non-conformity risk.", "Remove default credentials and use unique onboarding or mandatory first-use credential setup.")
    if facts.ota and not facts.signed_updates:
        add_finding(findings, "CRA", "Annex I §2(4) — Secure updates", "FAIL", "Update capability was inferred without clear signed-update controls.", "Implement signed updates, integrity checks, rollback protection, and version control.")
    elif facts.ota and facts.signed_updates:
        add_finding(findings, "CRA", "Annex I §2(4) — Secure updates", "PASS", "Update capability with secure-signing signals was inferred.")
    if not facts.vuln_disclosure:
        add_finding(findings, "CRA", "Art.14 — Vulnerability handling/reporting", "WARN", "No coordinated vulnerability disclosure signal was found.", "Set up a public security contact and vulnerability handling process.")
    if not facts.sbom:
        add_finding(findings, "CRA", "Annex I §2 — Component inventory / SBOM", "WARN", "No SBOM or component inventory signal was found.", "Generate and maintain an SBOM for software and third-party components.")
    if facts.unique_credentials and not facts.default_password:
        add_finding(findings, "CRA", "Annex I §1 / secure by default", "PASS", "Unique credentials were inferred, supporting secure-by-default posture.")
    elif facts.auth is False:
        add_finding(findings, "CRA", "Annex I §1 / secure by default", "INFO", "No user authentication was inferred. That can be acceptable only if the attack surface is otherwise tightly constrained.", "Confirm local-only architecture, hardening, and absence of privileged remote interfaces.")

    if depth in {"standard", "deep"}:
        add_finding(findings, "CRA", "Art.13 — Security support period", "WARN", "No explicit security support/update period was inferred.", "Define and publish a minimum vulnerability handling and security update support window.")
    if depth == "deep":
        add_finding(findings, "CRA", "Annex VII / technical documentation", "INFO", "Prepare architecture, risk assessment, update strategy, SBOM, test evidence, and conformity documentation in one coherent technical file.")
    return findings



def analyze_gdpr(facts: FactModel, depth: str) -> list[Finding]:
    findings: list[Finding] = []
    if not (facts.personal_data or facts.sensitive_data or facts.telemetry or facts.data_sharing):
        add_finding(findings, "GDPR", "Art.4 — Personal data trigger", "INFO", "No clear personal-data processing signal was inferred.", "Confirm that no identifiers, accounts, telemetry linked to users, or special category data are processed.")
        return findings

    if facts.sensitive_data:
        add_finding(findings, "GDPR", "Art.9 — Special category / sensitive data", "FAIL", f"Sensitive data signals were inferred: {', '.join(facts.sensitive_data)}.", "Identify lawful basis, explicit condition where needed, minimisation, retention, transparency, and DPIA need.")
    else:
        add_finding(findings, "GDPR", "Art.5 — Data minimisation and purpose limitation", "WARN", "Personal data processing is likely, but legal basis and minimisation controls are not clear.", "Define purpose, lawful basis, retention, and access controls in product documentation.")

    if facts.encryption or facts.tls:
        add_finding(findings, "GDPR", "Art.32 — Security of processing", "PASS", "Encryption or secure transport signals were inferred.")
    else:
        add_finding(findings, "GDPR", "Art.32 — Security of processing", "WARN", "No clear encryption or secure-transport signal was found.", "Clarify TLS/HTTPS, storage encryption, key management, and access control.")

    if facts.data_retention:
        add_finding(findings, "GDPR", "Art.5(1)(e) — Storage limitation", "WARN", "Data storage/history/retention was inferred, but retention boundaries are unclear.", "Define retention periods, deletion logic, and user-facing data lifecycle statements.")
    if facts.data_sharing:
        add_finding(findings, "GDPR", "Art.28 / Art.13-14 — Third-party data sharing", "WARN", "Third-party sharing or analytics-provider use was inferred.", "Map processors/controllers, contracts, notices, and transfer mechanisms.")
    if facts.cross_border_transfer:
        add_finding(findings, "GDPR", "Chapter V — International transfers", "WARN", "Possible non-EU or cross-border transfer signal detected.", "Validate transfer mechanism, hosting location, and supplementary measures where applicable.")
    if depth == "deep":
        add_finding(findings, "GDPR", "Accountability package", "INFO", "Prepare RoPA entry, privacy notice mapping, processor list, retention schedule, and DPIA screen where risk is elevated.")
    return findings



def analyze_ai_act(facts: FactModel, depth: str) -> list[Finding]:
    findings: list[Finding] = []
    if not (facts.ai or facts.face_recognition or facts.voice_ai or facts.emotion_ai or facts.automated_decision):
        add_finding(findings, "AI_Act", "Art.3 — AI system definition", "INFO", "No strong AI-system signal was inferred.")
        return findings

    if facts.prohibited_ai_signal:
        add_finding(findings, "AI_Act", "Art.5 — Prohibited AI practices", "FAIL", "Signals potentially associated with prohibited AI practices were detected.", "Immediate legal review required. These use cases may be unavailable for EU placement.")
        return findings

    high_risk = bool(facts.face_recognition or facts.emotion_ai or facts.automated_decision or (facts.child_context and facts.ai))
    if high_risk:
        add_finding(findings, "AI_Act", "High-risk classification screen", "FAIL", "The described AI functionality may fall into a high-risk or highly sensitive area.", "Run a formal AI Act classification assessment before productisation.")
    else:
        add_finding(findings, "AI_Act", "Limited-risk / transparency screen", "WARN", "AI functionality was inferred, but the final risk tier is unclear.", "Confirm intended purpose, outputs, human oversight, and transparency obligations.")

    if facts.face_recognition or facts.voice_ai or facts.camera:
        add_finding(findings, "AI_Act", "Transparency / biometric-adjacent controls", "WARN", "Biometric or perception-related AI signals were found.", "Confirm whether biometric identification, categorisation, or recognition functions exist and whether they are on-device or cloud-based.")
    if depth == "deep":
        add_finding(findings, "AI_Act", "Governance package", "INFO", "Prepare AI use-case description, data governance notes, performance metrics, human oversight concept, and post-market monitoring rationale.")
    return findings



def analyze_lvd(facts: FactModel, depth: str) -> list[Finding]:
    findings: list[Finding] = []
    if not (facts.mains_power or facts.high_voltage):
        add_finding(findings, "LVD", "Applicability screen", "INFO", "No mains or high-voltage signal was inferred. LVD may be out of scope depending on final rated voltage.")
        return findings

    add_finding(findings, "LVD", "Applicability screen", "WARN", "Mains-powered or higher-voltage architecture was inferred.", "Confirm rated voltage range and applicable safety standard family.")
    if facts.safety_function:
        add_finding(findings, "LVD", "Safety-related functionality", "WARN", "Safety-related functionality was inferred.", "Ensure foreseeable misuse, fault conditions, and safety integrity are fully addressed in design validation.")
    if facts.battery_power:
        add_finding(findings, "LVD", "Power architecture clarity", "INFO", "Both battery and mains signals are present; verify final safety architecture and charging path.")
    return findings



def analyze_emc(facts: FactModel, depth: str) -> list[Finding]:
    findings: list[Finding] = []
    add_finding(findings, "EMC", "Applicability screen", "INFO" if not (facts.software or facts.has_radio or facts.mains_power or facts.battery_power or facts.usb_power or facts.poe_power) else "WARN", "Electronic/electrical architecture appears likely, so EMC should normally be screened.", "Confirm final power and electronics architecture and map the EMC test plan accordingly.")
    if facts.has_radio:
        add_finding(findings, "EMC", "Radio/electronics interaction", "WARN", "Radio functionality was inferred, so EMC and radio coexistence planning should be aligned.")
    return findings



def analyze_espr(facts: FactModel, depth: str) -> list[Finding]:
    findings: list[Finding] = []
    if not (facts.repairability or facts.recycled or facts.energy_label):
        add_finding(findings, "ESPR", "Sustainability screen", "INFO", "No strong sustainability or ecodesign-specific signal was inferred from the short description.")
        return findings

    add_finding(findings, "ESPR", "Sustainability screen", "WARN", "Repairability, recyclability, or energy-labelling signals were inferred.", "Confirm whether product-specific ESPR/ecodesign delegated requirements apply for the category.")
    return findings


ANALYZERS = {
    "RED": analyze_red,
    "CRA": analyze_cra,
    "GDPR": analyze_gdpr,
    "AI_Act": analyze_ai_act,
    "LVD": analyze_lvd,
    "EMC": analyze_emc,
    "ESPR": analyze_espr,
}


def summarize_product(facts: FactModel) -> str:
    parts: list[str] = []
    if facts.has_radio:
        parts.append(f"radio-enabled ({', '.join(facts.radios)})")
    if facts.local_only:
        parts.append("local/offline use signalled")
    elif facts.cloud or facts.internet:
        parts.append("network/cloud-connected")
    if facts.ota:
        parts.append("software-update capability inferred")
    if facts.personal_data:
        parts.append("personal-data processing likely")
    if facts.sensitive_data:
        parts.append(f"sensitive data likely ({', '.join(facts.sensitive_data)})")
    if facts.ai:
        parts.append("AI/ML functionality likely")
    if facts.mains_power:
        parts.append("mains-powered")
    elif facts.battery_power:
        parts.append("battery-powered")
    if facts.consumer:
        parts.append("consumer/household context")
    if facts.industrial:
        parts.append("industrial context")
    if facts.medical_context:
        parts.append("medical or patient context")
    if not parts:
        parts.append("limited signals extracted from sparse description")
    return "; ".join(parts)



def derive_overall_risk(findings: list[Finding], facts: FactModel) -> str:
    fail_count = sum(1 for f in findings if f.status == "FAIL")
    warn_count = sum(1 for f in findings if f.status == "WARN")
    if fail_count >= 3 or facts.prohibited_ai_signal:
        return "CRITICAL"
    if fail_count >= 1 or len(facts.sensitive_data) >= 1 or len(facts.contradictions) >= 2:
        return "HIGH"
    if warn_count >= 3 or len(facts.contradictions) == 1:
        return "MEDIUM"
    return "LOW"



def build_summary(findings: list[Finding], facts: FactModel, directives: list[str]) -> str:
    fail_count = sum(1 for f in findings if f.status == "FAIL")
    warn_count = sum(1 for f in findings if f.status == "WARN")
    contradiction_text = ""
    if facts.contradictions:
        contradiction_text = f" Conflicting description signals detected: {len(facts.contradictions)}."
    return f"{len(directives)} directive(s) screened. {fail_count} FAIL, {warn_count} WARN finding(s). Product profile: {summarize_product(facts)}.{contradiction_text}"



def dedupe_findings(findings: list[Finding]) -> list[Finding]:
    seen: set[tuple[str, str, str, str]] = set()
    out: list[Finding] = []
    for f in findings:
        key = (f.directive, f.article, f.status, f.finding)
        if key not in seen:
            out.append(f)
            seen.add(key)
    return out



def analyze(description: str, category: str, directives: list[str], depth: str) -> AnalysisResult:
    facts = extract_facts(description=description, category=category)
    final_directives = infer_directives(facts, requested=directives)

    findings: list[Finding] = []

    for contradiction in facts.contradictions:
        add_finding(findings, "CRA", "Inference quality / contradiction check", "WARN", contradiction, "Clarify the product description to improve triage quality and legal confidence.")

    for directive in final_directives:
        analyzer = ANALYZERS.get(directive)
        if analyzer:
            findings.extend(analyzer(facts, depth))

    findings = dedupe_findings(findings)
    findings.sort(key=lambda f: (final_directives.index(f.directive) if f.directive in final_directives else 999, -STATUS_ORDER[f.status], f.article))

    result = AnalysisResult(
        product_summary=summarize_product(facts),
        overall_risk=derive_overall_risk(findings, facts),
        findings=findings,
        summary=build_summary(findings, facts, final_directives),
    )
    return result
