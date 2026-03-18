from models import Finding

# ── Helpers ────────────────────────────────────────────────────────────────

def detect(text: str, keywords: list) -> bool:
    t = text.lower()
    return any(k in t for k in keywords)

def score(text: str, keywords: list) -> int:
    """Count how many keywords match — used to gauge confidence."""
    t = text.lower()
    return sum(1 for k in keywords if k in t)

# ── Main analysis engine ───────────────────────────────────────────────────

def analyze(description: str, category: str, directives: list, depth: str) -> dict:
    findings = []
    t = description.lower()

    # ── Feature detection ─────────────────────────────────────────────────
    # Radio / connectivity
    has_wifi         = detect(t, ["wifi", "wi-fi", "wlan", "802.11", "2.4ghz", "5ghz", "6ghz"])
    has_bt           = detect(t, ["bluetooth", " bt ", "ble", "bt5", "bt4"])
    has_zigbee       = detect(t, ["zigbee", "ieee 802.15", "z-wave", "thread", "matter"])
    has_lora         = detect(t, ["lora", "lorawan", "868mhz", "915mhz", "lpwan"])
    has_nfc          = detect(t, ["nfc", "near field"])
    has_cellular     = detect(t, ["lte", "4g", "5g", "nb-iot", "cat-m", "cellular", "gsm", "3gpp"])
    has_radio        = has_wifi or has_bt or has_zigbee or has_lora or has_nfc or has_cellular or detect(t, ["radio", "wireless", "rf module", "rf transmit"])

    # Connectivity / services
    has_cloud        = detect(t, ["cloud", "server", "remote server", "aws", "azure", "google cloud", "backend", "hosted", "saas", "api endpoint"])
    has_app          = detect(t, ["mobile app", "smartphone app", "android app", "ios app", "web app", "web interface", "dashboard", "companion app"])
    has_internet     = has_cloud or has_app or detect(t, ["internet", "online", "connected", "iot"])
    has_local_only   = detect(t, ["local only", "no cloud", "offline", "no internet", "standalone", "no remote"])

    # Updates & software
    has_ota          = detect(t, ["ota", "over-the-air", "firmware update", "software update", "remote update", "automatic update", "fota"])
    has_signed_fw    = detect(t, ["signed firmware", "firmware signature", "secure boot", "code signing", "cryptographic signature"])
    has_rollback     = detect(t, ["rollback", "roll back", "downgrade protection", "anti-rollback"])

    # Authentication & access control
    has_auth         = detect(t, ["login", "password", "authentication", "user account", "credentials", "passphrase", "pin code", "mfa", "2fa", "oauth", "pairing"])
    has_default_pw   = detect(t, ["default password", "default credentials", "admin/admin", "admin password", "factory default password", "same password"])
    has_unique_pw    = detect(t, ["unique password", "per-device", "device-specific", "unique credentials", "unique per device"])
    has_mfa          = detect(t, ["mfa", "2fa", "two-factor", "multi-factor", "totp"])
    has_lockout      = detect(t, ["lockout", "rate limit", "brute force", "account lock"])

    # Data & privacy
    has_personal     = detect(t, ["personal data", "user data", "usage data", "usage pattern", "user profile", "account data", "email", "name", "address"])
    has_health       = detect(t, ["health", "heart rate", "blood", "spo2", "sleep data", "medical", "ecg", "stress level", "body temperature"])
    has_location     = detect(t, ["location", "gps", "geolocation", "tracking", "latitude", "longitude", "position"])
    has_biometric    = detect(t, ["biometric", "fingerprint", "face id", "facial recognition", "iris scan", "voice recognition", "retina"])
    has_sensitive    = has_health or has_location or has_biometric
    has_behavioral   = detect(t, ["behavior", "behavioural", "usage pattern", "activity", "consumption data", "habits"])
    has_energy_data  = detect(t, ["energy data", "consumption", "power usage", "electricity usage", "smart meter"])
    has_encrypt      = detect(t, ["encrypt", "tls", "https", "ssl", "aes", "e2e", "end-to-end", "at rest", "in transit"])
    has_tls          = detect(t, ["tls", "https", "ssl", "tls 1.2", "tls 1.3"])
    has_retention    = detect(t, ["store data", "stores data", "data retention", "log", "history", "archive", "record"])
    has_data_sharing = detect(t, ["share data", "third party", "analytics provider", "advertising", "monetis", "sell data", "data broker"])
    has_cross_border = detect(t, ["us server", "us cloud", "aws", "azure", "google cloud", "non-eu", "outside eu", "us-based server", "transfer to"])
    has_anon         = detect(t, ["anonymi", "pseudonym", "aggregated", "de-identified"])

    # AI / ML
    has_ai           = detect(t, ["artificial intelligence", " ai ", "machine learning", " ml ", "neural network", "deep learning", "inference", "model", "llm", "computer vision", "nlp", "recommendation engine", "predictive"])
    has_camera       = detect(t, ["camera", "video stream", "image capture", "snapshot", "cctv", "surveillance"])
    has_face_recog   = detect(t, ["face recognition", "facial recognition", "face detection", "face id"])
    has_voice_ai     = detect(t, ["voice assistant", "wake word", "always listening", "speech recognition", "voice command", "alexa", "google assistant"])
    has_emotion      = detect(t, ["emotion recognition", "emotion detection", "sentiment", "mood detection"])
    has_decision     = detect(t, ["automated decision", "autonomous decision", "scoring", "ranking users", "user scoring"])
    has_child_ai     = detect(t, ["educational ai", "children's ai", "ai for kids", "adaptive learning"])
    is_high_risk_ai  = has_face_recog or has_emotion or has_decision or has_child_ai or detect(t, ["critical infrastructure ai", "biometric ai", "law enforcement ai", "credit scoring ai", "recruitment ai"])
    has_prohibited_ai = detect(t, ["social scoring", "real-time biometric surveillance", "subliminal manipulation", "exploit vulnerability ai"])

    # Power / hardware
    has_mains        = detect(t, ["mains", "230v", "110v", "120v", "ac power", "power supply", "wall plug", "hardwired", "mains-powered", "grid"])
    has_battery      = detect(t, ["battery", "rechargeable", "li-ion", "lithium ion", "lipo", "li-po", "alkaline battery", "aa battery", "coin cell"])
    has_usb_power    = detect(t, ["usb power", "usb-c power", "usb powered", "5v usb"])
    has_poe          = detect(t, ["poe", "power over ethernet"])
    has_high_voltage = detect(t, ["high voltage", "400v", "hv", "motor drive", "inverter"])

    # Product type signals
    is_consumer      = detect(t, ["consumer", "residential", "household", "home use", "personal use", "retail", "end user"])
    is_industrial    = detect(t, ["industrial", "b2b", "factory", "warehouse", "professional use", "scada", "plc"])
    is_medical       = detect(t, ["medical", "patient", "clinical", "diagnostic", "therapeutic", "hospital", "wellness device"])
    has_child        = detect(t, ["child", "children", "kids", "toy", "school", "minors", "parental control", "age verification"])
    has_safety_func  = detect(t, ["safety function", "emergency", "alarm", "fire", "co detector", "smoke", "critical safety", "fail safe"])

    # Security posture signals
    has_vuln_prog    = detect(t, ["vulnerability disclosure", "bug bounty", "responsible disclosure", "cvd policy", "security patch", "cve", "security advisory"])
    has_sbom         = detect(t, ["sbom", "software bill of materials", "component inventory", "open source inventory"])
    has_pentest      = detect(t, ["penetration test", "pentest", "security audit", "security assessment", "red team"])
    has_iso27001     = detect(t, ["iso 27001", "iso27001", "isms", "information security management"])
    has_network_seg  = detect(t, ["network segmentation", "vlan", "dmz", "firewall", "isolated network"])

    # Environmental / sustainability
    has_repairability = detect(t, ["repair", "replaceable", "spare part", "ifixit", "right to repair", "user replaceable"])
    has_recycled     = detect(t, ["recycled", "recycling", "circular", "eol", "end of life", "take back"])
    has_energy_label = detect(t, ["energy label", "energy class", "energy rating", "a+++", "erp"])

    # ── RED Art.3(3)(d-f) ─────────────────────────────────────────────────
    if "RED" in directives:
        if not has_radio:
            findings.append(Finding(
                directive="RED", article="Art.3(3)(d-f) — Applicability",
                status="INFO",
                finding="No radio interface detected in the description. Delegated Regulation (EU) 2022/30 applying Art.3(3)(d)(e)(f) applies exclusively to radio equipment as defined in Art.2(1) of RED. Without a radio interface, these cybersecurity articles do not apply.",
                action="Confirm whether product intentionally emits or receives radio waves. If it does not, consider whether CRA applies instead."
            ))
        else:
            # Identify which radio technologies are present
            radio_types = []
            if has_wifi:    radio_types.append("WiFi")
            if has_bt:      radio_types.append("Bluetooth")
            if has_zigbee:  radio_types.append("Zigbee/Thread/Matter")
            if has_lora:    radio_types.append("LoRa/LPWAN")
            if has_nfc:     radio_types.append("NFC")
            if has_cellular: radio_types.append("Cellular (LTE/5G)")
            radio_str = ", ".join(radio_types) if radio_types else "radio"

            # Art.3(3)(d) — Network protection
            if has_default_pw:
                findings.append(Finding(
                    directive="RED", article="Art.3(3)(d) — Network protection [ETSI EN 303 645 cl.5.1 / EN 18031-1]",
                    status="FAIL",
                    finding=f"Default credentials detected on a {radio_str} device. This is a direct non-conformity under Art.3(3)(d) and Del. Reg. (EU) 2022/30. Universal default passwords are explicitly prohibited — they allow trivial mass compromise of the network.",
                    action="Replace all default credentials with unique, per-device credentials generated at manufacture. No shared or universal passwords permitted. Implement at factory level before market placement."
                ))
            elif has_internet and not has_local_only:
                findings.append(Finding(
                    directive="RED", article="Art.3(3)(d) — Network protection [ETSI EN 303 645 cl.5.3 / EN 18031-1]",
                    status="WARN",
                    finding=f"This {radio_str} product connects to external services. Art.3(3)(d) requires it does not harm the network, disrupt network services, or misuse network resources. Network-level attack surface must be assessed and minimised.",
                    action="Document all network interfaces, ports, and protocols used. Disable unused services. Apply principle of least privilege to network access. Reference ETSI EN 303 645 clause 5.3."
                ))
            else:
                findings.append(Finding(
                    directive="RED", article="Art.3(3)(d) — Network protection [EN 18031-1]",
                    status="PASS",
                    finding=f"No cloud or internet connectivity detected for this {radio_str} device. Network harm risk appears low for local-only operation.",
                    action=None
                ))

            # Art.3(3)(e) — User protection
            if has_sensitive:
                sensitive_types = []
                if has_health:    sensitive_types.append("health data")
                if has_location:  sensitive_types.append("location data")
                if has_biometric: sensitive_types.append("biometric data")
                findings.append(Finding(
                    directive="RED", article="Art.3(3)(e) — User protection [ETSI EN 303 645 cl.5.8 / EN 18031-3]",
                    status="FAIL",
                    finding=f"Sensitive personal data ({', '.join(sensitive_types)}) processed on a radio device. Art.3(3)(e) requires robust safeguards protecting users against harm from unauthorised access to or misuse of personal data. Sensitive categories demand strongest protections.",
                    action="Implement encryption at rest (AES-256 minimum) and in transit (TLS 1.3). Apply strict data minimisation. Conduct DPIA. Reference ETSI EN 303 645 clause 5.8 and EN 18031-3."
                ))
            elif has_personal or has_energy_data:
                findings.append(Finding(
                    directive="RED", article="Art.3(3)(e) — User protection [ETSI EN 303 645 cl.5.8 / EN 18031-3]",
                    status="WARN",
                    finding="Personal or usage data is processed by this radio device. Art.3(3)(e) requires measures protecting the privacy and personal data of users and third parties.",
                    action="Implement access controls and encryption for all personal data. Apply data minimisation at device level. Cross-reference GDPR obligations. See EN 18031-3."
                ))
            else:
                findings.append(Finding(
                    directive="RED", article="Art.3(3)(e) — User protection [EN 18031-3]",
                    status="PASS",
                    finding="No personal data processing detected on this radio device. Art.3(3)(e) obligations appear minimal.",
                    action=None
                ))

            # Art.3(3)(f) — Fraud protection
            if has_default_pw and not has_unique_pw:
                findings.append(Finding(
                    directive="RED", article="Art.3(3)(f) — Fraud protection [ETSI EN 303 645 cl.5.1]",
                    status="FAIL",
                    finding="Default credentials make fraudulent access trivial. Art.3(3)(f) prohibits design choices that facilitate fraudulent use of the device or associated services.",
                    action="Unique per-device credentials mandatory. Implement during manufacturing. See ETSI EN 303 645 clause 5.1 — this is the most-cited non-conformity in market surveillance."
                ))
            elif has_auth:
                auth_notes = []
                if has_mfa:     auth_notes.append("MFA present — positive")
                if has_lockout: auth_notes.append("brute-force protection present — positive")
                if not has_mfa:     auth_notes.append("no MFA detected")
                if not has_lockout: auth_notes.append("no brute-force lockout mentioned")
                findings.append(Finding(
                    directive="RED", article="Art.3(3)(f) — Fraud protection [ETSI EN 303 645 cl.5.1 / cl.5.4]",
                    status="PASS" if (has_mfa and has_lockout) else "WARN",
                    finding=f"Authentication mechanism detected. Fraud protection assessment: {'; '.join(auth_notes)}.",
                    action=None if (has_mfa and has_lockout) else "Add MFA for high-value operations. Implement account lockout after failed attempts. Document auth scheme in technical file."
                ))
            else:
                findings.append(Finding(
                    directive="RED", article="Art.3(3)(f) — Fraud protection [ETSI EN 303 645 cl.5.1]",
                    status="INFO",
                    finding="No authentication mechanism mentioned. If this device has any remote access, pairing, or account linkage, Art.3(3)(f) applies.",
                    action="Confirm whether pairing, remote access, or user accounts exist. If yes, document authentication approach in technical file."
                ))

            # OTA update security
            if has_ota:
                ota_status = "PASS" if has_signed_fw else "WARN"
                findings.append(Finding(
                    directive="RED", article="Art.3(3)(d-f) — OTA security [ETSI EN 303 645 cl.5.5]",
                    status=ota_status,
                    finding="OTA firmware updates detected. " + (
                        "Signed firmware mentioned — positive. Ensure update integrity and authenticity are verified before installation." if has_signed_fw
                        else "No cryptographic signature verification mentioned for OTA updates. Unsigned OTA is a critical attack vector — arbitrary firmware installation by an attacker."
                    ),
                    action=None if has_signed_fw else "Implement cryptographic signature verification (RSA-2048 or ECDSA-P256 minimum) for all firmware packages. Verify signature before installation, reject unsigned updates. Consider rollback protection."
                ))

            # Supply chain / third party
            if detect(t, ["third party", "third-party", "sdk", "open source component", "supplier module", "vendor module"]):
                findings.append(Finding(
                    directive="RED", article="Art.3(3)(d-f) — Supply chain [ETSI EN 303 645 cl.5.6]",
                    status="WARN",
                    finding="Third-party components or SDKs detected. Vulnerabilities in supplier components are the manufacturer's regulatory responsibility — the CE mark certifies the whole product, not just your code.",
                    action="Maintain SBOM for all software components. Monitor CVEs for all third-party libraries. Assess supplier security posture. Reference ETSI EN 303 645 clause 5.6."
                ))

            # Delegated Regulation timeline note
            if depth != "quick":
                findings.append(Finding(
                    directive="RED", article="Del. Reg. (EU) 2022/30 — Compliance status [OJEU 2022]",
                    status="INFO",
                    finding="Delegated Regulation (EU) 2022/30 making Art.3(3)(d)(e)(f) mandatory is in force. Harmonised standards EN 18031-1/-2/-3 are available but not yet listed in the OJEU — ETSI EN 303 645 and ETSI EN 305 645 currently serve as best-practice references.",
                    action="Monitor OJEU for EN 18031 series listing. Consider early adoption of EN 18031 to future-proof technical file. Ensure DoC explicitly references Del. Reg. (EU) 2022/30."
                ))

            if depth == "deep":
                findings.append(Finding(
                    directive="RED", article="Technical File — Cybersecurity [RED Annex V / Del. Reg. Art.4]",
                    status="INFO",
                    finding="RED cybersecurity technical file must include: (1) threat and risk analysis, (2) security architecture description, (3) SBOM, (4) vulnerability disclosure policy, (5) test reports against ETSI EN 303 645 or EN 18031 series, (6) Declaration of Conformity explicitly referencing Del. Reg. (EU) 2022/30.",
                    action="Prepare dedicated cybersecurity section in technical file. Retain for 10 years post market placement. DoC must list Del. Reg. (EU) 2022/30 as legal basis."
                ))

    # ── CRA — Cyber Resilience Act ────────────────────────────────────────
    if "CRA" in directives:
        has_digital_elements = has_radio or has_internet or has_app or has_ota or detect(t, ["software", "firmware", "digital", "processor", "microcontroller", "embedded"])

        if not has_digital_elements:
            findings.append(Finding(
                directive="CRA", article="Art.2 — Scope [Regulation (EU) 2024/2847]",
                status="INFO",
                finding="No digital elements detected. CRA applies to products with digital elements — hardware with software components, network connectivity, or data processing capability.",
                action="Confirm whether product contains any software, firmware, or connectivity. Pure mechanical products without software are out of scope."
            ))
        else:
            # Classification
            is_important_class1 = has_radio or has_auth or has_ota or detect(t, ["vpn", "password manager", "firewall", "ids", "ips"])
            is_important_class2 = has_safety_func or is_medical or detect(t, ["industrial control", "scada", "plc", "operating system", "hypervisor", "microprocessor security"])
            is_critical         = detect(t, ["critical infrastructure", "power grid", "water treatment", "transport system", "health infrastructure"])

            if is_critical:
                classification = "CRITICAL"
                class_color = "FAIL"
                class_note = "Critical product — Annex III. Mandatory EU type-examination by Notified Body."
            elif is_important_class2:
                classification = "Important Class II"
                class_color = "FAIL"
                class_note = "Important Class II — Annex II. Third-party conformity assessment or EU type-examination required."
            elif is_important_class1:
                classification = "Important Class I"
                class_color = "WARN"
                class_note = "Important Class I — Annex II. Self-declaration allowed only if harmonised standards applied in full; otherwise third-party assessment."
            else:
                classification = "Default"
                class_color = "INFO"
                class_note = "Default category. Self-declaration of conformity permitted."

            findings.append(Finding(
                directive="CRA", article=f"Art.7 — Classification: {classification} [CRA Annex I/II/III]",
                status=class_color,
                finding=f"Product classified as: {classification}. {class_note}",
                action="Document classification rationale in technical file. If Important Class I/II, engage Notified Body or apply harmonised standards in full."
            ))

            # Essential cybersecurity requirements
            if has_default_pw:
                findings.append(Finding(
                    directive="CRA", article="Annex I §1 — No known exploitable vulnerabilities [ETSI EN 303 645 cl.5.1]",
                    status="FAIL",
                    finding="Default credentials constitute a known exploitable vulnerability under CRA Annex I. Products must be placed on market with no known exploitable vulnerabilities.",
                    action="Eliminate default credentials. Implement unique per-device passwords at manufacture. This is a blocking non-conformity under CRA."
                ))

            if not has_vuln_prog:
                findings.append(Finding(
                    directive="CRA", article="Art.14 — Vulnerability reporting [ENISA / Art.14(1)]",
                    status="FAIL",
                    finding="No vulnerability disclosure programme detected. CRA Art.14 requires manufacturers to report actively exploited vulnerabilities to ENISA within 24 hours of becoming aware, and notify affected users.",
                    action="Establish Coordinated Vulnerability Disclosure (CVD) policy. Set up dedicated security contact (e.g. security@yourdomain.com). Register with ENISA notification portal. Publish CVD policy publicly."
                ))

            if not has_sbom:
                findings.append(Finding(
                    directive="CRA", article="Annex I §2(1) — Software Bill of Materials [SPDX / CycloneDX]",
                    status="WARN",
                    finding="No SBOM mentioned. CRA Annex I requires manufacturers to identify and document all software components including open-source and third-party to enable vulnerability tracking throughout the product lifecycle.",
                    action="Generate machine-readable SBOM in SPDX or CycloneDX format. Include all software components with version numbers. Update on every firmware release. Include in technical documentation."
                ))

            if has_ota and not has_signed_fw:
                findings.append(Finding(
                    directive="CRA", article="Annex I §2(4) — Secure updates [IEC 62443-4-2]",
                    status="FAIL",
                    finding="OTA updates present but no secure update mechanism mentioned. CRA Annex I requires updates to be distributed securely, integrity-verified, and deployed without adding vulnerabilities.",
                    action="Implement cryptographically signed firmware updates. Verify signature before installation. Prevent downgrade to vulnerable versions. Apply rollback protection."
                ))

            if depth != "quick":
                update_years = "5 years minimum (or product's expected lifetime if longer)"
                findings.append(Finding(
                    directive="CRA", article="Art.13(8) — Security update period [CRA Art.13]",
                    status="WARN",
                    finding=f"CRA requires manufacturers to provide security updates for {update_years}. No software support commitment detected in the description.",
                    action="Define and publicly commit to a minimum security update support period. Document in product information sheet and on product webpage. Update period starts from date of market placement."
                ))

                findings.append(Finding(
                    directive="CRA", article="Annex I §1(2) — Secure by default [ETSI EN 303 645 cl.5.2]",
                    status="PASS" if (has_unique_pw and not has_default_pw) else "WARN",
                    finding="CRA requires products to be shipped in a secure-by-default configuration — minimal attack surface, unnecessary features disabled, least-privilege principle applied." if not (has_unique_pw and not has_default_pw) else "Unique credentials detected — secure-by-default posture partially confirmed.",
                    action=None if (has_unique_pw and not has_default_pw) else "Audit default configuration. Disable all unused interfaces, ports, and services. Ensure product operates securely out of the box without requiring user configuration."
                ))

            if depth == "deep":
                findings.append(Finding(
                    directive="CRA", article="Technical Documentation — Annex VII [CRA Art.31]",
                    status="INFO",
                    finding="CRA Annex VII technical documentation must include: (1) product description and intended use, (2) design and development documentation including architecture diagrams, (3) risk assessment (CRA Annex I compliance), (4) SBOM, (5) conformity assessment procedure applied, (6) EU Declaration of Conformity.",
                    action="Prepare CRA technical file. Significant overlap with RED technical file — consolidate into unified document where possible. Retain for 10 years."
                ))

    # ── EU AI Act ─────────────────────────────────────────────────────────
    if "AI_Act" in directives:
        if not has_ai:
            findings.append(Finding(
                directive="AI Act", article="Art.3(1) — AI system definition [Regulation 2024/1689]",
                status="INFO",
                finding="No AI system detected. EU AI Act applies only to AI systems as defined in Art.3(1): machine-based systems that infer outputs such as predictions, content, recommendations, or decisions from inputs.",
                action="Confirm no ML inference, recommendation engine, or automated decision-making runs on-device or in associated cloud services."
            ))
        else:
            # Prohibited practices
            if has_prohibited_ai:
                findings.append(Finding(
                    directive="AI Act", article="Art.5 — PROHIBITED practice [AI Act Art.5]",
                    status="FAIL",
                    finding="The AI functionality described may constitute a prohibited practice under Art.5: real-time biometric surveillance in public spaces, social scoring systems, or subliminal manipulation. These are unconditionally banned in the EU — no conformity assessment can authorise them.",
                    action="IMMEDIATE LEGAL REVIEW REQUIRED. Prohibited AI systems cannot be placed on EU market under any circumstances. Redesign or eliminate the prohibited functionality before any market placement."
                ))

            # Risk classification
            elif is_high_risk_ai:
                risk_reasons = []
                if has_face_recog:  risk_reasons.append("facial recognition (Annex III §1)")
                if has_emotion:     risk_reasons.append("emotion recognition (Annex III §1)")
                if has_decision:    risk_reasons.append("automated individual decision-making")
                if has_child_ai:    risk_reasons.append("AI in education/children context (Annex III §3)")
                findings.append(Finding(
                    directive="AI Act", article=f"Art.6 — HIGH-RISK classification [Annex III: {', '.join(risk_reasons)}]",
                    status="FAIL",
                    finding=f"AI system classified as HIGH-RISK under Annex III based on: {', '.join(risk_reasons)}. Mandatory conformity assessment required before market placement. Cannot self-declare — Notified Body involvement required.",
                    action="Conduct mandatory conformity assessment (Art.43). Register in EU AI public database (Art.71) before placing on market. Appoint EU Authorised Representative if manufacturer is outside EU. Implement all Chapter III obligations."
                ))
            else:
                ai_type = []
                if has_voice_ai: ai_type.append("voice/conversational AI")
                if has_camera:   ai_type.append("computer vision")
                if has_ai:       ai_type.append("ML inference")
                findings.append(Finding(
                    directive="AI Act", article="Art.6 — Risk classification [AI Act Annex I/III]",
                    status="WARN",
                    finding=f"AI functionality detected ({', '.join(ai_type) if ai_type else 'general ML'}). Appears to be Limited or Minimal Risk based on description, but classification must be formally documented and justified.",
                    action="Document classification decision with legal rationale. If Limited Risk (chatbot, emotion recognition), transparency obligations under Art.50 apply. If Minimal Risk, no mandatory obligations but voluntary codes of conduct recommended."
                ))

            # Transparency (Art.50)
            if has_voice_ai or detect(t, ["chatbot", "conversational", "virtual assistant"]):
                findings.append(Finding(
                    directive="AI Act", article="Art.50 — Transparency obligations [AI Act Art.50]",
                    status="WARN",
                    finding="Voice assistant or conversational AI detected. Art.50 requires users to be clearly informed they are interacting with an AI system, unless this is obvious from context.",
                    action="Add unambiguous AI disclosure at start of interaction. Cannot be buried in T&Cs. Must be in clear, plain language in all relevant EU languages."
                ))

            if depth != "quick":
                findings.append(Finding(
                    directive="AI Act", article="Art.9 — Risk management system [ISO/IEC 42001 / ISO/IEC 23894]",
                    status="WARN",
                    finding="All AI systems must have an established, implemented, documented, and maintained risk management system (Art.9). This is a continuous obligation throughout the lifecycle, not a one-time assessment.",
                    action="Implement risk management system aligned with ISO/IEC 42001 or NIST AI RMF. Document risk identification, evaluation, and mitigation measures. Establish post-market monitoring."
                ))

                findings.append(Finding(
                    directive="AI Act", article="Art.10 — Training data governance [ISO/IEC 25059]",
                    status="INFO",
                    finding="Training, validation and test datasets must meet quality criteria for high-risk AI: relevance, representativeness, freedom from errors, completeness. Data governance and lineage must be documented.",
                    action="Document data sources, collection methodology, preprocessing steps, and bias assessment. Retain dataset documentation. Address known biases explicitly."
                ))

            if depth == "deep":
                findings.append(Finding(
                    directive="AI Act", article="Technical Documentation — Annex IV [AI Act Art.11]",
                    status="INFO",
                    finding="AI technical documentation (Annex IV) must include: (1) general description and intended purpose, (2) system architecture and design choices, (3) training data description, (4) validation and testing methodology, (5) performance metrics including accuracy, robustness, cybersecurity, (6) risk management records, (7) post-market monitoring plan, (8) instructions for use.",
                    action="Prepare full Annex IV technical documentation. If product also falls under RED, LVD or MDR, integrate into unified technical file to minimise duplication."
                ))

    # ── GDPR ──────────────────────────────────────────────────────────────
    if "GDPR" in directives:
        if not has_personal and not has_cloud and not has_health and not has_location:
            findings.append(Finding(
                directive="GDPR", article="Art.4(1) — Personal data scope [Regulation 2016/679]",
                status="PASS",
                finding="No personal data processing, cloud connectivity, or sensitive data detected. GDPR obligations appear minimal for this product as described.",
                action=None
            ))
        else:
            # Lawful basis
            findings.append(Finding(
                directive="GDPR", article="Art.6 — Lawful basis [EDPB Guidelines 2/2019]",
                status="WARN",
                finding="Personal data processing detected. Every processing activity requires a documented lawful basis under Art.6. For consumer IoT, the most common bases are consent (Art.6(1)(a)) or contract performance (Art.6(1)(b)). Legitimate interest (Art.6(1)(f)) is harder to justify for sensitive data.",
                action="Identify and document lawful basis for each processing activity. Granular consent required for non-essential processing. Include in Records of Processing Activities (RoPA)."
            ))

            # Privacy by design
            findings.append(Finding(
                directive="GDPR", article="Art.25 — Privacy by design & default [ISO/IEC 27701]",
                status="PASS" if has_tls else "WARN",
                finding="Privacy by design (Art.25) requires data protection to be integrated into product architecture from design stage — not added as an afterthought." + (" TLS encryption detected — positive signal." if has_tls else " No encryption mentioned — significant gap."),
                action=None if has_tls else "Implement TLS 1.2+ minimum (TLS 1.3 recommended) for all data in transit. Encrypt personal data at rest using AES-256. Apply data minimisation at device firmware level."
            ))

            # DPIA trigger assessment
            dpia_triggers = []
            if has_sensitive:    dpia_triggers.append("special category data (Art.35(3)(b))")
            if has_behavioral:   dpia_triggers.append("systematic behavioural monitoring (Art.35(3)(c))")
            if has_location:     dpia_triggers.append("location tracking")
            if has_child:        dpia_triggers.append("data concerning children")
            if is_medical:       dpia_triggers.append("health/medical context")
            if has_face_recog:   dpia_triggers.append("biometric processing (Art.35(3)(b))")

            if dpia_triggers:
                findings.append(Finding(
                    directive="GDPR", article=f"Art.35 — DPIA mandatory [ISO/IEC 29134 / EDPB Guidelines]",
                    status="FAIL",
                    finding=f"Data Protection Impact Assessment (DPIA) is MANDATORY due to: {', '.join(dpia_triggers)}. Processing cannot begin until DPIA is completed and, if high residual risk remains, supervisory authority consulted (Art.36).",
                    action="Conduct DPIA before product launch. Follow EDPB guidelines and ISO/IEC 29134. Document risks, mitigations, and residual risk. Consult DPA if high residual risk cannot be mitigated."
                ))
            else:
                findings.append(Finding(
                    directive="GDPR", article="Art.35 — DPIA assessment [EDPB Guidelines 9/2022]",
                    status="WARN",
                    finding="DPIA may be required depending on processing volume and context. Conduct DPIA screening assessment to determine obligation.",
                    action="Complete DPIA screening checklist per EDPB Guidelines 9/2022. Document outcome regardless of whether full DPIA is required."
                ))

            # Special category data
            if has_sensitive:
                sensitive_list = []
                if has_health:    sensitive_list.append("health data (Art.9(1))")
                if has_biometric: sensitive_list.append("biometric data for identification (Art.9(1))")
                if has_location and is_medical: sensitive_list.append("location in medical context")
                findings.append(Finding(
                    directive="GDPR", article=f"Art.9 — Special category data [{', '.join(sensitive_list)}]",
                    status="FAIL",
                    finding=f"Special category data detected: {', '.join(sensitive_list)}. Art.9 imposes strict processing conditions — explicit consent or one of the Art.9(2) exceptions required. Standard consent (Art.6) is insufficient.",
                    action="Obtain explicit, granular, withdrawable consent per Art.7+9. Alternatively, identify applicable Art.9(2) exception and document it. Implement additional technical safeguards. DPIA mandatory."
                ))

            # Children
            if has_child:
                findings.append(Finding(
                    directive="GDPR", article="Art.8 — Children's consent [EDPB Guidelines 5/2022]",
                    status="FAIL",
                    finding="Product targets or is likely used by children (under 16, or lower per national law). Art.8 requires verifiable parental consent for digital service processing. Standard consent mechanisms insufficient for minors.",
                    action="Implement robust age verification mechanism. Obtain verifiable parental consent. Review national implementations (NL: 16, DE: 16, UK AADC: 13). Apply Children's Code (UK) if UK market."
                ))

            # Cross-border transfer
            if has_cross_border:
                findings.append(Finding(
                    directive="GDPR", article="Art.46 — International data transfers [EDPB Recommendations 01/2020]",
                    status="FAIL",
                    finding="Data transfer to servers outside the EU/EEA detected (e.g. US cloud provider). Transfer of personal data to third countries requires an appropriate safeguard mechanism under Chapter V.",
                    action="Implement Standard Contractual Clauses (SCCs — Commission Decision 2021/914). Conduct Transfer Impact Assessment (TIA). Consider EU-hosted data infrastructure. Inform users of transfer destination and safeguard mechanism in privacy notice."
                ))

            # Data sharing / third party
            if has_data_sharing:
                findings.append(Finding(
                    directive="GDPR", article="Art.28 — Data processor agreements [GDPR Art.28(3)]",
                    status="WARN",
                    finding="Data sharing with third parties (analytics, advertising, SDK providers) detected. Every processor receiving personal data requires a Data Processing Agreement (DPA) meeting Art.28(3) requirements.",
                    action="Identify all processors. Execute Art.28-compliant DPAs. List processors in privacy notice with processing purpose. Review sub-processor chains."
                ))

            # Retention
            if has_retention:
                findings.append(Finding(
                    directive="GDPR", article="Art.5(1)(e) — Storage limitation [EDPB Guidelines]",
                    status="WARN",
                    finding="Data storage or logging detected. Personal data must not be retained longer than necessary for the purpose for which it was collected.",
                    action="Define retention periods for each data category. Implement automated deletion. Document retention schedule in RoPA. Inform users of retention periods in privacy notice."
                ))

    # ── EMC ───────────────────────────────────────────────────────────────
    if "EMC" in directives:
        findings.append(Finding(
            directive="EMC", article="Art.6 — Essential requirements [Directive 2014/30/EU Annex I]",
            status="INFO",
            finding="EMC Directive 2014/30/EU applies. Two essential requirements: (1) equipment must not generate electromagnetic disturbance exceeding levels preventing normal use of radio, telecoms, or other equipment; (2) equipment must have adequate immunity to electromagnetic disturbance.",
            action=None
        ))

        if has_radio:
            radio_standards = []
            if has_wifi or has_bt: radio_standards.append("EN 301 489-17 (WiFi/BT)")
            if has_zigbee:         radio_standards.append("EN 301 489-3 (SRDs)")
            if has_lora:           radio_standards.append("EN 301 489-3 (SRDs <1GHz)")
            if has_cellular:       radio_standards.append("EN 301 489-52 (LTE/5G)")
            if has_nfc:            radio_standards.append("EN 301 489-3 (NFC)")

            findings.append(Finding(
                directive="EMC", article=f"ETSI EN 301 489-1 + product-specific [{', '.join(radio_standards) if radio_standards else 'EN 301 489 series'}]",
                status="WARN",
                finding=f"Radio product requires EMC testing per EN 301 489-1 (generic EMC for radio) combined with the relevant product-specific standard ({', '.join(radio_standards) if radio_standards else 'EN 301 489-x'}). Both must be tested and documented.",
                action="Commission accredited test laboratory (ILAC/MRA member). Test both emissions and immunity. Include test reports in technical file with exact standard versions used."
            ))
        else:
            emission_std = "EN 55032 Class B" if is_consumer else "EN 55032 Class A"
            findings.append(Finding(
                directive="EMC", article=f"EN 55032 (emissions) + EN 55035 (immunity) [{emission_std}]",
                status="WARN",
                finding=f"Non-radio electrical product. Apply EN 55032 ({emission_std} for {'residential' if is_consumer else 'industrial'} environment) for emissions and EN 55035 for immunity. Additional EN 61000-4-x immunity tests required.",
                action="Identify applicable class (A or B) based on intended environment. Commission accredited lab. Document standard versions applied."
            ))

        if has_mains:
            findings.append(Finding(
                directive="EMC", article="EN 55032 — Conducted emissions, mains port [CISPR 32]",
                status="WARN",
                finding="Mains-connected product must be tested for conducted emissions on the mains port (EN 55032, 150kHz–30MHz). This is separate from radiated emissions testing.",
                action="Include mains port conducted emissions in test scope. Ensure power supply design minimises conducted noise. Consider EMC filter on mains input."
            ))

        if depth == "deep":
            findings.append(Finding(
                directive="EMC", article="Technical File — EMC [Directive 2014/30/EU Art.15]",
                status="INFO",
                finding="EMC technical file must include: (1) general description of equipment, (2) design and manufacturing drawings, (3) list of harmonised standards applied (with version dates), (4) test reports from accredited laboratory, (5) EU Declaration of Conformity.",
                action="Retain technical file for 10 years. DoC must list exact standard versions. Lab must be ILAC/MRA accredited (check BELAC, DAkkS, UKAS, RvA, etc.)."
            ))

    # ── LVD ───────────────────────────────────────────────────────────────
    if "LVD" in directives:
        if not has_mains and not has_battery and not has_usb_power and not has_poe:
            findings.append(Finding(
                directive="LVD", article="Art.3 — Scope [Directive 2014/35/EU]",
                status="INFO",
                finding="No electrical power supply detected. LVD applies to electrical equipment designed for use with a voltage rating of 50–1000V AC or 75–1500V DC. Confirm power supply voltage range.",
                action="Confirm supply voltage. If battery-only below 75V DC, LVD likely does not apply. If mains-powered, LVD is mandatory."
            ))
        else:
            if has_mains:
                lvd_std = "EN 60335-1 + EN 60335-2-x" if is_consumer else "EN 62368-1"
                findings.append(Finding(
                    directive="LVD", article=f"Annex I — Safety objectives, mains [{lvd_std}]",
                    status="WARN",
                    finding=f"Mains-connected product. LVD essential safety requirements apply: protection against electric shock (basic insulation, double insulation, protective earth), fire hazard, mechanical hazard, and radiation. Apply {lvd_std}.",
                    action=f"Apply {lvd_std}. Conduct insulation coordination analysis (EN 60664-1). Perform dielectric strength test. Ensure correct fusing. Include in technical file."
                ))

                if has_high_voltage:
                    findings.append(Finding(
                        directive="LVD", article="Annex I — High voltage safety [EN 60664-1]",
                        status="WARN",
                        finding="High voltage or motor drive detected. Additional safety measures required: creepage and clearance distances, reinforced insulation, protective guarding.",
                        action="Apply EN 60664-1 for insulation coordination. Calculate minimum creepage and clearance for working voltage and pollution degree. Document in technical file."
                    ))

            if has_battery:
                battery_std = "IEC 62133-2" if detect(t, ["li-ion", "lipo", "lithium"]) else "IEC 60086 series"
                findings.append(Finding(
                    directive="LVD", article=f"Annex I — Battery safety [{battery_std} / EN 62368-1 §5.4]",
                    status="WARN",
                    finding=f"Rechargeable battery detected. Li-ion/LiPo cells carry thermal runaway risk if overcharged, over-discharged, or short-circuited. Battery management system (BMS) design is safety-critical.",
                    action=f"Apply {battery_std}. Document cell specifications (manufacturer, model, capacity, max charge/discharge current). Design and test BMS: overcharge protection, over-discharge protection, short-circuit protection, thermal monitoring. Include in technical file."
                ))

            if has_usb_power:
                findings.append(Finding(
                    directive="LVD", article="USB Power Delivery safety [EN 62368-1 / IEC 63002]",
                    status="INFO",
                    finding="USB-powered product. If powered from external USB adapter, the adapter is a separate product under LVD. Product itself (≤5V DC) is likely outside LVD scope but must be compatible with safe USB power sources.",
                    action="Confirm power source. If product includes USB charger/adapter, that adapter requires LVD compliance separately. Document power supply requirements in user manual."
                ))

            if depth == "deep":
                findings.append(Finding(
                    directive="LVD", article="Technical File — Safety [Directive 2014/35/EU Art.15]",
                    status="INFO",
                    finding="LVD technical file must include: (1) general description, (2) conceptual design, circuit diagrams, component descriptions, (3) risk assessment, (4) list of harmonised standards applied, (5) copies of test reports, (6) copy of EU Declaration of Conformity.",
                    action="All safety testing must be performed by accredited laboratory. DoC must reference specific harmonised standards with version dates. Retain for 10 years."
                ))

    # ── ESPR ──────────────────────────────────────────────────────────────
    if "ESPR" in directives:
        findings.append(Finding(
            directive="ESPR", article="Regulation (EU) 2024/1781 — Scope & timeline",
            status="INFO",
            finding="ESPR replaces the Ecodesign Directive (2009/125/EC) with broader scope covering sustainability, repairability, recyclability, and software longevity. Product-specific Delegated Acts are being developed per the ESPR Working Plan 2022–2024. General framework applies from July 2024.",
            action="Monitor EU ESPR working plan for your product category. Begin sustainability data collection now. Identify likely Delegated Act timeline for your category."
        ))

        # Software support
        if has_ota:
            findings.append(Finding(
                directive="ESPR", article="Software longevity — OTA capability [IEC 63074]",
                status="PASS",
                finding="OTA update capability confirmed — strong compliance signal for ESPR software supportability requirements. Ensures security and functionality updates can be delivered throughout product lifetime.",
                action="Define and publicly commit to minimum software support period (years from market placement). Publish support end date. Document update policy in product information sheet."
            ))
        else:
            findings.append(Finding(
                directive="ESPR", article="Software longevity — OTA capability [IEC 63074]",
                status="WARN",
                finding="No OTA update capability detected. ESPR Delegated Acts are expected to require minimum software update availability matching the product's expected use lifetime. Products unable to receive security updates will face market barriers.",
                action="Evaluate feasibility of adding OTA update capability. If OTA not feasible, document rationale and define alternative security maintenance strategy."
            ))

        # Repairability
        if has_repairability:
            findings.append(Finding(
                directive="ESPR", article="Repairability — Spare parts & manuals [EN 45554]",
                status="PASS",
                finding="Repairability features mentioned — positive signal for ESPR compliance. Spare parts availability and repair documentation are key ESPR requirements.",
                action="Formalise repairability index per EN 45554. Commit to minimum spare parts availability period (typically 7–10 years post last sale). Publish repair manual."
            ))
        else:
            findings.append(Finding(
                directive="ESPR", article="Repairability — Spare parts & manuals [EN 45554]",
                status="WARN",
                finding="No repairability features mentioned. ESPR Delegated Acts will likely mandate minimum spare parts availability and repair documentation for most product categories.",
                action="Identify critical spare parts for your product. Plan minimum availability commitment. Prepare repair and disassembly documentation. Calculate repairability index per EN 45554."
            ))

        if depth != "quick":
            findings.append(Finding(
                directive="ESPR", article="Digital Product Passport (DPP) [ESPR Art.9 / CIRPASS]",
                status="INFO",
                finding="ESPR introduces Digital Product Passports (DPP) accessible via QR code or RFID, containing sustainability and circularity data. DPP requirements are being phased in from 2026 per product category.",
                action="Monitor DPP Delegated Act for your product category. Begin building product data infrastructure: materials declaration, component list, recyclability scores, repair scores, carbon footprint. Align with CIRPASS data model."
            ))

            if has_energy_data or detect(t, ["energy consumption", "standby", "watts", "power consumption"]):
                findings.append(Finding(
                    directive="ESPR", article="Energy performance [ErP Regulation / Energy Labelling Reg. 2017/1369]",
                    status="WARN",
                    finding="Energy consumption data detected. ESPR and linked Energy Labelling Regulation may require energy efficiency class labelling and minimum performance standards.",
                    action="Measure standby, networked standby, and operational power consumption. Check if Energy Label applies to your product category. Apply Ecodesign Regulation requirements if product category covered."
                ))

        if depth == "deep":
            findings.append(Finding(
                directive="ESPR", article="Product Information Requirements [ESPR Art.7]",
                status="INFO",
                finding="ESPR Art.7 requires specific product information to be available: durability, reparability, presence of hazardous substances, recycled content, spare parts and repair manual availability, and software update availability.",
                action="Prepare product information sheet meeting Art.7 requirements. Include in packaging and product webpage. Ensure information is accessible digitally (QR code or URL). Translate into all relevant EU languages."
            ))

    # ── Overall risk calculation ───────────────────────────────────────────
    fail_count = sum(1 for f in findings if f.status == "FAIL")
    warn_count = sum(1 for f in findings if f.status == "WARN")
    pass_count = sum(1 for f in findings if f.status == "PASS")

    if fail_count >= 3:
        risk = "CRITICAL"
    elif fail_count >= 1:
        risk = "HIGH"
    elif warn_count >= 4:
        risk = "MEDIUM"
    elif warn_count >= 1:
        risk = "MEDIUM"
    else:
        risk = "LOW"

    if fail_count > 0:
        summary_text = f"{fail_count} blocking non-conformity(ies) and {warn_count} warning(s) identified across {len(directives)} directive(s). Product cannot be CE-marked or placed on EU market in current state. Address all FAIL items before conformity assessment."
    elif warn_count > 0:
        summary_text = f"No blocking non-conformities found. {warn_count} warning(s) require attention before CE marking. Address all WARN items and verify with accredited testing."
    else:
        summary_text = f"Product appears broadly compliant across {len(directives)} directive(s) based on the description provided. Verify compliance with accredited laboratory testing before CE marking. Keep technical file updated."

    return {
        "product_summary": description[:90] + "..." if len(description) > 90 else description,
        "overall_risk": risk,
        "findings": [f.dict() for f in findings],
        "summary": summary_text
    }