from __future__ import annotations

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from knowledge_base import KnowledgeBaseError, warmup_knowledge_base
from models import AnalysisResult, ProductInput
from rules import analyze

APP_VERSION = "2.2.0"

app = FastAPI(title="RegCheck API", version=APP_VERSION)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "https://rulegrid.net",
        "https://www.rulegrid.net",
        "https://regcheck-frontend-kutrb6fg3-morfildors-projects.vercel.app",
    ],
    allow_methods=["*"],
    allow_headers=["*"],
)

_kb_status: dict = {"ok": False, "error": None, "counts": {}}


@app.on_event("startup")
def startup_event() -> None:
    global _kb_status
    try:
        counts = warmup_knowledge_base()
        _kb_status = {"ok": True, "error": None, "counts": counts}
    except KnowledgeBaseError as exc:
        _kb_status = {"ok": False, "error": str(exc), "counts": {}}


@app.get("/")
def root():
    return {"status": "RegCheck API is running", "version": APP_VERSION}


@app.get("/health")
def health():
    return {
        "ok": _kb_status["ok"],
        "version": APP_VERSION,
        "knowledge_base": _kb_status["counts"],
        "error": _kb_status["error"],
    }


@app.post("/analyze", response_model=AnalysisResult)
def run_analysis(product: ProductInput):
    if not _kb_status["ok"]:
        raise HTTPException(status_code=503, detail=f"Knowledge base failed to load: {_kb_status['error']}")
    try:
        return analyze(
            description=product.description,
            category=product.category,
            directives=product.directives,
            depth=product.depth,
        )
    except KnowledgeBaseError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Analysis failed: {exc}") from exc
