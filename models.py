from __future__ import annotations

from typing import Literal
from pydantic import BaseModel, Field

Status = Literal["PASS", "WARN", "FAIL", "INFO"]
RiskLevel = Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"]


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


class StandardItem(BaseModel):
    code: str
    title: str
    directive: str
    category: str
    confidence: Literal["low", "medium", "high"] = "medium"
    reason: str | None = None
    notes: str | None = None


class AnalysisResult(BaseModel):
    product_summary: str
    overall_risk: RiskLevel
    summary: str

    product_type: str | None = None
    functional_classes: list[str] = Field(default_factory=list)

    explicit_traits: list[str] = Field(default_factory=list)
    inferred_traits: list[str] = Field(default_factory=list)
    all_traits: list[str] = Field(default_factory=list)

    directives: list[str] = Field(default_factory=list)
    standards: list[StandardItem] = Field(default_factory=list)
    missing_information: list[str] = Field(default_factory=list)
    contradictions: list[str] = Field(default_factory=list)

    findings: list[Finding] = Field(default_factory=list)