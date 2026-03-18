from pydantic import BaseModel


class ProductInput(BaseModel):
    description: str
    category: str = ""
    directives: list[str] = []
    depth: str = "standard"


class Finding(BaseModel):
    directive: str
    article: str
    status: str        # PASS, WARN, FAIL, INFO
    finding: str
    action: str | None = None


class AnalysisResult(BaseModel):
    product_summary: str
    overall_risk: str  # LOW, MEDIUM, HIGH, CRITICAL
    findings: list[Finding]
    summary: str