from __future__ import annotations

from typing import Literal
from pydantic import BaseModel, Field


Status = Literal["PASS", "WARN", "FAIL", "INFO"]
RiskLevel = Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"]
DirectiveName = Literal["RED", "CRA", "GDPR", "AI_Act", "LVD", "EMC", "ESPR"]


class ProductInput(BaseModel):
    description: str
    category: str = ""
    directives: list[str] = Field(default_factory=list)
    depth: Literal["quick", "standard", "deep"] = "standard"


class Finding(BaseModel):
    directive: str
    article: str
    status: Status
    finding: str
    action: str | None = None


class AnalysisResult(BaseModel):
    product_summary: str
    overall_risk: RiskLevel
    findings: list[Finding] = Field(default_factory=list)
    summary: str


class FeatureEvidence(BaseModel):
    score: float = 0.0
    positive_hits: list[str] = Field(default_factory=list)
    negative_hits: list[str] = Field(default_factory=list)
    hit: bool = False
    negated: bool = False


class FactModel(BaseModel):
    raw_text: str = ""
    normalized_text: str = ""

    radios: list[str] = Field(default_factory=list)
    has_radio: bool | None = None
    internet: bool | None = None
    cloud: bool | None = None
    local_only: bool | None = None
    app: bool | None = None
    software: bool | None = None
    firmware: bool | None = None
    ota: bool | None = None
    signed_updates: bool | None = None
    rollback_protection: bool | None = None

    auth: bool | None = None
    default_password: bool | None = None
    unique_credentials: bool | None = None
    mfa: bool | None = None
    brute_force_protection: bool | None = None

    personal_data: bool | None = None
    health_data: bool | None = None
    location_data: bool | None = None
    biometric_data: bool | None = None
    sensitive_data: list[str] = Field(default_factory=list)
    telemetry: bool | None = None
    data_retention: bool | None = None
    data_sharing: bool | None = None
    encryption: bool | None = None
    tls: bool | None = None
    anonymisation: bool | None = None
    cross_border_transfer: bool | None = None

    ai: bool | None = None
    camera: bool | None = None
    face_recognition: bool | None = None
    voice_ai: bool | None = None
    emotion_ai: bool | None = None
    automated_decision: bool | None = None
    prohibited_ai_signal: bool | None = None

    mains_power: bool | None = None
    battery_power: bool | None = None
    usb_power: bool | None = None
    poe_power: bool | None = None
    high_voltage: bool | None = None

    consumer: bool | None = None
    industrial: bool | None = None
    medical_context: bool | None = None
    child_context: bool | None = None
    safety_function: bool | None = None

    vuln_disclosure: bool | None = None
    sbom: bool | None = None
    pentest: bool | None = None
    network_segmentation: bool | None = None

    repairability: bool | None = None
    recycled: bool | None = None
    energy_label: bool | None = None

    inferred_directives: list[str] = Field(default_factory=list)
    contradictions: list[str] = Field(default_factory=list)
    evidence: dict[str, FeatureEvidence] = Field(default_factory=dict)
