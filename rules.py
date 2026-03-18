from models import Finding


def detect(text: str, keywords: list) -> bool:
    t = text.lower()
    return any(k in t for k in keywords)


def analyze(description: str, category: str, directives: list, depth: str) -> dict:
    findings = []
    t = description.lower()

    # ── Feature detection ──────────────────────────────────────────────────
    has_radio        = detect(t, ["wifi", "wi-fi", "bluetooth", "zigbee", "lora", "lorawan", "nfc", "z-wave", "thread", "matter", "wireless", "rf ", "radio", "868mhz", "915mhz", "2.4ghz", "5ghz"])
    has_cloud        = detect(t, ["cloud", "server", "remote", "api", "internet", "online", "saas", "backend", "hosted"])
    has_app          = detect(t, ["app", "mobile", "smartphone", "android", "ios", "web interface", "dashboard"])
    has_ota          = detect(t, ["ota", "firmware update", "over-the-air", "software update", "remote update", "automatic update"])
    has_auth         = detect(t, ["login", "password", "authentication", "user account", "credentials", "auth", "pin", "passphrase", "pairing"])
    has_default_cred = detect(t, ["default password", "default credentials", "factory password", "admin/admin", "admin password"])
    has_personal     = detect(t, ["personal data", "user data", "usage data", "energy data", "location", "profile", "behaviour", "behavioral", "biometric", "health data", "heart rate", "sleep"])
    has_sensitive    = detect(t, ["health", "medical", "heart rate", "blood", "sleep", "stress", "biometric", "location tracking", "gps"])
    has_ai           = detect(t, ["ai", "artificial intelligence", "machine learning", "ml", "neural", "deep learning", "model", "inference", "prediction", "recommendation", "computer vision", "nlp", "llm"])
    has_camera       = detect(t, ["camera", "video", "image recognition", "face recognition", "facial", "object detection"])
    has_biometric    = detect(t, ["biometric", "fingerprint", "face id", "iris", "voice recognition"])
    has_child        = detect(t, ["child", "children", "kids", "toy", "school", "education", "minors", "parental"])
    has_safety       = detect(t, ["safety", "critical", "infrastructure", "industrial control", "scada", "emergency", "alarm"])
    has_mains        = detect(t, ["mains", "230v", "110v", "ac power", "power supply", "plug", "socket", "wired power", "hardwired"])
    has_battery      = detect(t, ["battery", "rechargeable", "lithium", "li-ion", "lipo", "li-po", "cell"])
    has_encrypt      = detect(t, ["encrypt", "tls", "https", "ssl", "aes", "secure", "end-to-end", "e2e"])
    has_open_source  = detect(t, ["open source", "opensource", "github", "open firmware"])
    has_third_party  = detect(t, ["third party", "third-party", "partner", "vendor", "supplier component", "sdk"])
    has_data_sharing = detect(t, ["share data", "data sharing", "third party data", "analytics", "advertising", "monetis"])
    has_retention    = detect(t, ["data retention", "store data", "stores data", "logs", "history", "archive"])
    has_cross_border = detect(t, ["us server", "aws", "azure", "google cloud", "us-based", "outside eu", "non-eu", "transfer data"])
    has_voice        = detect(t, ["voice", "microphone", "always on", "wake word", "alexa", "google assistant", "siri"])
    has_consumer     = detect(t, ["consumer", "residential", "household", "home", "personal use", "retail"])
    has_vuln_prog    = detect(t, ["vulnerability", "bug bounty", "responsible disclosure", "cvd", "security update", "patch"])
    has_sbom         = detect(t, ["sbom", "software bill", "component list", "open source component"])

    # ── RED Art.3(3)(d-f) ─────────────────────────────────────────────────
    if "RED" in directives:
        if not has_radio:
            findings.append(Finding(
                directive="RED",
                article="Art.3(3)(d-f) — Applicability",
                status="INFO",
                finding="No radio interface detected. RED Art.3(3)(d-f) and Delegated Regulation (EU) 2022/30 apply only to radio equipment as defined in Art.2(1). Verify product scope.",
                action="Confirm whether the product intentionally emits or receives radio waves. If no radio, RED cybersecurity articles do not apply — consider CRA instead."
            ))
        else:
            # Art.3(3)(d) — Network protection
            status_d = "FAIL" if has_default_cred else ("WARN" if (has_cloud or has_app) else "PASS")
            finding_d = (
                "Default credentials detected — direct non-conformity with Art.3(3)(d). Network harm through credential abuse is a known attack vector."
                if has_default_cred else
                "Product connects to network via cloud/app. Must demonstrate it does not harm the network or cause service degradation."
                if (has_cloud or has_app) else
                "No cloud or app connectivity detected. Network harm risk appears low."
            )
            action_d = (
                "Replace default credentials with unique per-device credentials before market placement. See ETSI EN 303 645 clause 5.1."
                if has_default_cred else
                "Document network behaviour. Apply ETSI EN 303 645 cl.5.3. Reference EN 18031-1 once published in OJEU."
                if (has_cloud or has_app) else None
            )
            findings.append(Finding(directive="RED", article="Art.3(3)(d) — Network protection", status=status_d, finding=finding_d, action=action_d))

            # Art.3(3)(e) — User protection
            status_e = "FAIL" if has_sensitive else ("WARN" if has_personal else "PASS")
            finding_e = (
                "Sensitive personal data (health, biometric, location) detected. Heightened protection obligations under Art.3(3)(e). Risk of harm to users is significant."
                if has_sensitive else
                "Personal/usage data processed. Art.3(3)(e) requires safeguards protecting user privacy and personal data from unauthorised access."
                if has_personal else
                "No personal data processing detected. Art.3(3)(e) obligations appear minimal."
            )
            action_e = (
                "Apply strict access controls, encryption at rest and in transit. Conduct DPIA. Reference EN 18031-3 and ETSI EN 303 645 cl.5.8."
                if has_sensitive else
                "Implement data minimisation and access controls. Cross-reference GDPR. Apply EN 18031-3."
                if has_personal else None
            )
            findings.append(Finding(directive="RED", article="Art.3(3)(e) — User protection", status=status_e, finding=finding_e, action=action_e))

            # Art.3(3)(f) — Fraud protection
            status_f = "FAIL" if has_default_cred else ("WARN" if has_auth else "INFO")
            finding_f = (
                "Default credentials present — direct FAIL under Art.3(3)(f). Fraudulent access via known default passwords is a primary attack vector."
                if has_default_cred else
                "Authentication mechanism present. Must prevent fraudulent use of the device or associated services."
                if has_auth else
                "No authentication or pairing mechanism mentioned. If product has any access control, Art.3(3)(f) applies."
            )
            action_f = (
                "Implement unique per-device credentials at manufacture. No universal default passwords permitted. See EN 303 645 cl.5.1."
                if has_default_cred else
                "Enforce strong authentication. Implement account lockout, rate limiting. Document in technical file."
                if has_auth else
                "Clarify whether pairing, login, or remote access exists. Document authentication approach."
            )
            findings.append(Finding(directive="RED", article="Art.3(3)(f) — Fraud protection", status=status_f, finding=finding_f, action=action_f))

            # OTA security
            if has_ota:
                findings.append(Finding(
                    directive="RED",
                    article="Art.3(3)(d-f) — OTA update security",
                    status="WARN",
                    finding="OTA firmware updates detected. Update mechanism must be secured — unsigned or unauthenticated updates are a critical vulnerability.",
                    action="Implement cryptographic signature verification for all firmware updates. Ensure rollback protection. Reference EN 303 645 cl.5.5."
                ))

            # Third party components
            if has_third_party:
                findings.append(Finding(
                    directive="RED",
                    article="Art.3(3)(d-f) — Supply chain security",
                    status="WARN",
                    finding="Third-party components or SDKs detected. Vulnerabilities in supplier components are your regulatory responsibility as manufacturer.",
                    action="Maintain software bill of materials (SBOM). Assess third-party component security. Monitor CVEs for all components."
                ))

            if depth != "quick":
                findings.append(Finding(
                    directive="RED",
                    article="Delegated Reg. (EU) 2022/30 — Timeline",
                    status="INFO",
                    finding="Delegated Regulation (EU) 2022/30 applying Art.3(3)(d-f) entered into force. Compliance is mandatory for new products placed on EU market.",
                    action="Verify your product's market placement date and confirm compliance deadline applicability. Check OJEU for EN 18031 harmonised standard publication."
                ))

            if depth == "deep":
                findings.append(Finding(
                    directive="RED",
                    article="Technical File — Cybersecurity section",
                    status="INFO",
                    finding="Technical file must include: threat model, security architecture, SBOM, vulnerability disclosure policy, test reports (EN 303 645 / EN 18031 series), and Declaration of Conformity referencing delegated regulation.",
                    action="Build cybersecurity section of technical file. Ensure DoC references Delegated Regulation (EU) 2022/30."
                ))

    # ── CRA — Cyber Resilience Act ────────────────────────────────────────
    if "CRA" in directives:
        if not has_radio and not has_cloud and not has_app:
            findings.append(Finding(
                directive="CRA",
                article="Art.2 — Scope",
                status="INFO",
                finding="No digital connectivity detected. CRA applies to products with digital elements — hardware and software with network connectivity or data processing capability.",
                action="Confirm whether product has any digital interface, connectivity, or software component."
            ))
        else:
            is_important = has_safety or has_cloud or has_auth
            findings.append(Finding(
                directive="CRA",
                article="Art.7 — Product classification",
                status="WARN" if is_important else "INFO",
                finding="Product likely falls under CRA scope as a 'product with digital elements'. Connected products with authentication or safety functions may be classified as Important Class I or II, requiring stricter conformity assessment." if is_important else "Product falls under CRA general scope. Default conformity assessment via self-declaration applies unless reclassified.",
                action="Determine classification: Default / Important Class I / Important Class II. Class I and II require third-party assessment or EU type-examination."
            ))

            findings.append(Finding(
                directive="CRA",
                article="Art.13 — Manufacturer obligations",
                status="WARN",
                finding="CRA requires: no known exploitable vulnerabilities at shipment, secure by default configuration, vulnerability handling process, security updates for minimum 5 years (or expected product lifetime).",
                action="Establish vulnerability disclosure and handling process. Commit to minimum 5-year security update support. Document in product information."
            ))

            if not has_vuln_prog:
                findings.append(Finding(
                    directive="CRA",
                    article="Art.14 — Vulnerability reporting",
                    status="FAIL",
                    finding="No vulnerability disclosure programme detected. CRA mandates manufacturers report actively exploited vulnerabilities to ENISA within 24 hours of discovery.",
                    action="Establish coordinated vulnerability disclosure (CVD) policy. Set up reporting channel. Register with ENISA notification process."
                ))

            if not has_sbom:
                findings.append(Finding(
                    directive="CRA",
                    article="Annex I — SBOM requirement",
                    status="WARN",
                    finding="No software bill of materials (SBOM) mentioned. CRA Annex I requires manufacturers to identify and document software components including third-party and open-source.",
                    action="Generate and maintain SBOM in machine-readable format (e.g. SPDX or CycloneDX). Include in technical documentation."
                ))

            if depth == "deep":
                findings.append(Finding(
                    directive="CRA",
                    article="Technical Documentation — Annex VII",
                    status="INFO",
                    finding="CRA technical documentation must include: product description, design and development documentation, risk assessment, SBOM, conformity assessment procedures, and EU Declaration of Conformity.",
                    action="Prepare CRA technical file in parallel with RED technical file. Significant overlap exists — consolidate where possible."
                ))

    # ── EU AI Act ─────────────────────────────────────────────────────────
    if "AI_Act" in directives:
        if not has_ai:
            findings.append(Finding(
                directive="AI Act",
                article="Art.6 — Scope",
                status="INFO",
                finding="No AI functionality detected. EU AI Act (Regulation 2024/1689) does not apply to products without an AI system as defined in Art.3(1).",
                action="Confirm no ML inference, recommendation engine, or automated decision-making runs on-device or in associated cloud service."
            ))
        else:
            # Risk classification
            is_unacceptable = detect(t, ["social scoring", "real-time biometric", "subliminal", "exploit vulnerability"])
            is_high_risk = has_camera or has_biometric or has_child or has_safety or detect(t, ["credit scoring", "employment", "insurance", "critical infrastructure", "law enforcement", "migration"])
            is_limited_risk = has_voice or detect(t, ["chatbot", "deepfake", "emotion recognition"])

            if is_unacceptable:
                findings.append(Finding(
                    directive="AI Act",
                    article="Art.5 — Prohibited practices",
                    status="FAIL",
                    finding="AI system may involve a prohibited practice under Art.5 — real-time biometric surveillance, social scoring, or subliminal manipulation. These are banned in the EU.",
                    action="Legal review required immediately. Prohibited AI systems cannot be placed on EU market under any circumstance."
                ))
            elif is_high_risk:
                findings.append(Finding(
                    directive="AI Act",
                    article="Art.6 — High-risk classification",
                    status="FAIL",
                    finding="Product contains a HIGH-RISK AI system (Annex III). Mandatory conformity assessment, registration in EU AI database, and Notified Body involvement required before market placement.",
                    action="Conduct conformity assessment per Art.43. Register in EU AI public database. Appoint EU representative if needed."
                ))
            else:
                findings.append(Finding(
                    directive="AI Act",
                    article="Art.6 — Risk classification",
                    status="WARN",
                    finding="AI functionality detected. System appears to be Limited or Minimal Risk based on description. Classification must be formally documented.",
                    action="Document classification decision with rationale. If Limited Risk (e.g. chatbot, emotion recognition), transparency obligations under Art.50 apply."
                ))

            if is_limited_risk:
                findings.append(Finding(
                    directive="AI Act",
                    article="Art.50 — Transparency obligations",
                    status="WARN",
                    finding="Voice, chatbot, or emotion recognition detected. Users must be informed they are interacting with an AI system.",
                    action="Add clear AI disclosure in product UI and documentation. Cannot be buried in terms and conditions."
                ))

            if depth != "quick":
                findings.append(Finding(
                    directive="AI Act",
                    article="Art.9 — Risk management system",
                    status="WARN",
                    finding="A risk management system must be established, implemented, documented, and maintained throughout the AI system lifecycle — not just at launch.",
                    action="Implement ongoing risk management system. Include residual risk assessment and post-market monitoring plan in technical documentation."
                ))

                findings.append(Finding(
                    directive="AI Act",
                    article="Art.10 — Training data governance",
                    status="INFO",
                    finding="For high-risk AI: training, validation, and test datasets must meet quality criteria. Data governance and lineage must be documented.",
                    action="Document data sources, preprocessing steps, and bias assessment. Retain records of dataset versions used."
                ))

            if depth == "deep":
                findings.append(Finding(
                    directive="AI Act",
                    article="Art.11 — Technical documentation",
                    status="INFO",
                    finding="AI technical documentation (Annex IV) must cover: system description, architecture, training data, performance metrics, risk management records, post-market monitoring plan, and instructions for use.",
                    action="Prepare AI technical documentation package. If product also falls under RED or LVD, integrate into unified technical file."
                ))

    # ── GDPR ──────────────────────────────────────────────────────────────
    if "GDPR" in directives:
        if not has_personal and not has_cloud:
            findings.append(Finding(
                directive="GDPR",
                article="Art.4 — Scope",
                status="PASS",
                finding="No personal data processing or cloud connectivity detected. GDPR obligations appear minimal for this product.",
                action=None
            ))
        else:
            findings.append(Finding(
                directive="GDPR",
                article="Art.5 — Data principles",
                status="WARN",
                finding="Personal data processing detected. Core GDPR principles apply: lawfulness, purpose limitation, data minimisation, accuracy, storage limitation, integrity, and accountability.",
                action="Conduct Data Protection Impact Assessment (DPIA) per Art.35. Document lawful basis for each processing activity."
            ))

            findings.append(Finding(
                directive="GDPR",
                article="Art.25 — Privacy by design",
                status="PASS" if has_encrypt else "FAIL",
                finding="Encryption in place — positive indicator for privacy by design." if has_encrypt else "No encryption mentioned. Art.25 and Art.32 require appropriate technical measures including encryption of personal data.",
                action=None if has_encrypt else "Implement TLS 1.2+ for data in transit. Encrypt personal data at rest using AES-256 or equivalent. Document in security architecture."
            ))

            if has_retention:
                findings.append(Finding(
                    directive="GDPR",
                    article="Art.5(1)(e) — Storage limitation",
                    status="WARN",
                    finding="Data storage or logging detected. Personal data must not be retained longer than necessary for its purpose.",
                    action="Define and document data retention periods for each data category. Implement automatic deletion. Inform users in privacy notice."
                ))

            if has_data_sharing:
                findings.append(Finding(
                    directive="GDPR",
                    article="Art.28 — Data processors",
                    status="WARN",
                    finding="Data sharing with third parties or analytics providers detected. Data Processing Agreements (DPAs) required with all processors.",
                    action="Identify all data processors. Execute DPAs per Art.28. List processors in privacy notice."
                ))

            if has_cross_border:
                findings.append(Finding(
                    directive="GDPR",
                    article="Art.46 — International transfers",
                    status="FAIL",
                    finding="Data transfer to non-EU servers (e.g. US cloud providers) detected. Transfer outside EEA requires appropriate safeguard mechanism.",
                    action="Implement Standard Contractual Clauses (SCCs) or verify adequacy decision. Document transfer impact assessment (TIA). Inform users of transfer destination."
                ))

            if has_child:
                findings.append(Finding(
                    directive="GDPR",
                    article="Art.8 — Children's data",
                    status="FAIL",
                    finding="Product targets or is likely used by children. Special rules apply — parental consent required for users under 16 (or lower age per member state law).",
                    action="Implement age verification. Obtain verifiable parental consent mechanism. Review against national implementations (e.g. UK AADC, DE GDPR implementation)."
                ))

            if has_sensitive:
                findings.append(Finding(
                    directive="GDPR",
                    article="Art.9 — Special category data",
                    status="FAIL",
                    finding="Health, biometric, or sensitive personal data detected. Art.9 imposes strict processing conditions — explicit consent or specific legal basis required.",
                    action="Identify lawful basis under Art.9(2). Explicit consent must be granular and withdrawable. Conduct DPIA mandatory under Art.35(3)(b)."
                ))

    # ── EMC ───────────────────────────────────────────────────────────────
    if "EMC" in directives:
        findings.append(Finding(
            directive="EMC",
            article="Art.6 — Essential requirements",
            status="INFO",
            finding="EMC Directive 2014/30/EU applies. Product must not generate electromagnetic disturbance exceeding limits, and must have adequate immunity to disturbance.",
            action=None
        ))
        if has_radio:
            findings.append(Finding(
                directive="EMC",
                article="ETSI EN 301 489 series",
                status="WARN",
                finding="Radio equipment requires EMC testing per EN 301 489-1 (generic) combined with the relevant product-specific part (e.g. EN 301 489-17 for 2.4GHz WLAN/BT, EN 301 489-3 for SRDs).",
                action="Identify correct EN 301 489-x part for your radio technology. Commission accredited test lab. Include test reports in technical file."
            ))
        else:
            findings.append(Finding(
                directive="EMC",
                article="IEC/EN 61000 series",
                status="WARN",
                finding="Non-radio electrical product: apply relevant EN 61000 series for conducted and radiated emissions (EN 55032) and immunity (EN 55035 or EN 61000-4-x series).",
                action="Identify applicable standards for product class. Commission EMC testing at accredited lab."
            ))
        if has_mains:
            findings.append(Finding(
                directive="EMC",
                article="Conducted emissions — mains port",
                status="WARN",
                finding="Mains-connected product: conducted emissions on the mains port must be tested per EN 55032 class B (residential) or class A (industrial).",
                action="Confirm intended environment (residential vs industrial). Test mains port emissions accordingly."
            ))

    # ── LVD ───────────────────────────────────────────────────────────────
    if "LVD" in directives:
        if not has_mains and not has_battery:
            findings.append(Finding(
                directive="LVD",
                article="Art.3 — Scope",
                status="INFO",
                finding="No mains or battery power supply detected. LVD applies to equipment operating between 50–1000V AC or 75–1500V DC. Scope unclear from description.",
                action="Confirm operating voltage. If battery-only below 75V DC, LVD may not apply."
            ))
        else:
            if has_mains:
                findings.append(Finding(
                    directive="LVD",
                    article="Annex I — Safety objectives (mains)",
                    status="WARN",
                    finding="Mains-connected product. LVD essential safety requirements apply: protection against electric shock, energy hazards, fire, mechanical hazards, and radiation.",
                    action="Apply EN 60335 series (household appliances) or EN 62368-1 (AV/IT). Perform insulation coordination analysis. Include in technical file."
                ))
            if has_battery:
                findings.append(Finding(
                    directive="LVD",
                    article="Annex I — Battery safety",
                    status="WARN",
                    finding="Rechargeable battery detected. Li-ion and LiPo cells carry thermal runaway risk. Battery protection circuitry and cell quality are critical safety elements.",
                    action="Apply IEC 62133-2 for Li-ion portable batteries. Document cell specifications, BMS design, and overcharge/short-circuit protection in technical file."
                ))
            if depth == "deep":
                findings.append(Finding(
                    directive="LVD",
                    article="Technical File — Safety",
                    status="INFO",
                    finding="LVD technical file must include: electrical schematic, risk assessment, list of standards applied, test reports, and Declaration of Conformity.",
                    action="Ensure test reports are from accredited lab (ILAC/MRA member). DoC must reference specific harmonised standards applied."
                ))

    # ── ESPR ──────────────────────────────────────────────────────────────
    if "ESPR" in directives:
        findings.append(Finding(
            directive="ESPR",
            article="Regulation 2024/1781 — Scope",
            status="INFO",
            finding="ESPR replaces the Ecodesign Directive. Product-specific delegated regulations are being developed per the working plan. General obligations apply from 2025 onwards.",
            action="Monitor EU ESPR working plan for your product category. Begin preparing sustainability data infrastructure early."
        ))
        if has_ota:
            findings.append(Finding(
                directive="ESPR",
                article="Software supportability",
                status="PASS",
                finding="OTA update capability detected — strong positive indicator for ESPR software longevity requirements. Ensures product can receive security and functionality updates.",
                action="Define and publicly commit to minimum software support period. Document update policy in product information sheet."
            ))
        else:
            findings.append(Finding(
                directive="ESPR",
                article="Software supportability",
                status="WARN",
                finding="No OTA update capability detected. ESPR is expected to require software update availability for the product's reasonable expected lifetime.",
                action="Evaluate feasibility of adding OTA update capability. Document software support strategy."
            ))

        if depth != "quick":
            findings.append(Finding(
                directive="ESPR",
                article="Repairability and spare parts",
                status="INFO",
                finding="ESPR delegated acts will likely require minimum availability of spare parts, repair manuals, and disassembly instructions for consumer products.",
                action="Begin documenting repairability index. Identify critical spare parts. Plan spare parts availability commitment."
            ))

        if depth == "deep":
            findings.append(Finding(
                directive="ESPR",
                article="Digital Product Passport (DPP)",
                status="INFO",
                finding="ESPR introduces Digital Product Passports (DPP) phased in from 2026. DPPs must contain product sustainability data accessible via QR code or RFID.",
                action="Monitor DPP delegated act for your category. Begin building product data infrastructure (materials, components, repairability, recyclability scores)."
            ))

    # ── Overall risk ──────────────────────────────────────────────────────
    fail_count = sum(1 for f in findings if f.status == "FAIL")
    warn_count = sum(1 for f in findings if f.status == "WARN")

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

    summary = (
        f"{fail_count} critical gap(s) and {warn_count} warning(s) identified across "
        f"{len(directives)} directive(s). "
        + (
            "Immediate regulatory action required before market placement."
            if fail_count > 0 else
            "No blocking issues found — address warnings before CE marking."
            if warn_count > 0 else
            "Product appears broadly compliant based on description. Verify with accredited testing."
        )
    )

    return {
        "product_summary": description[:80] + "..." if len(description) > 80 else description,
        "overall_risk": risk,
        "findings": [f.dict() for f in findings],
        "summary": summary
    }