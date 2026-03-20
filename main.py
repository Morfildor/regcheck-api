from __future__ import annotations

import os

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from knowledge_base import (
    KnowledgeBaseError,
    load_legislations,
    load_products,
    load_traits,
    warmup_knowledge_base,
)
from models import AnalysisResult, ProductInput
from rules import analyze

APP_VERSION = "3.2.1"

app = FastAPI(title="RegCheck API", version=APP_VERSION)

DEFAULT_ALLOWED_ORIGINS = [
    "http://localhost:3000",
    "https://rulegrid.net",
    "https://www.rulegrid.net",
    "https://regcheck-frontend-kutrb6fg3-morfildors-projects.vercel.app",
    "https://regcheck-frontend-git-main-morfildors-projects.vercel.app",
    "https://regcheck-frontend-gxo61fmnd-morfildors-projects.vercel.app",
]

extra_origins = [
    origin.strip()
    for origin in os.getenv("CORS_ALLOWED_ORIGINS", "").split(",")
    if origin.strip()
]

allow_origins = sorted(set(DEFAULT_ALLOWED_ORIGINS + extra_origins))

app.add_middleware(
    CORSMiddleware,
    allow_origins=allow_origins,
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
    return {
        "status": "RegCheck API is running",
        "version": APP_VERSION,
    }


@app.get("/health")
def health():
    return {
        "ok": _kb_status["ok"],
        "version": APP_VERSION,
        "knowledge_base": _kb_status["counts"],
        "error": _kb_status["error"],
        "cors_allowed_origins": allow_origins,
    }


@app.get("/metadata/options")
def metadata_options():
    if not _kb_status["ok"]:
        raise HTTPException(status_code=503, detail=f"Knowledge base failed to load: {_kb_status['error']}")

    traits = load_traits()
    products = load_products()
    legislations = load_legislations()

    return {
        "traits": [
            {"id": row["id"], "label": row["label"], "description": row["description"]}
            for row in traits
        ],
        "products": [
            {
                "id": row["id"],
                "label": row["label"],
                "aliases": row.get("aliases", []),
                "functional_classes": row.get("functional_classes", []),
                "implied_traits": row.get("implied_traits", []),
            }
            for row in products
        ],
        "legislations": [
            {
                "code": row["code"],
                "title": row["title"],
                "directive_key": row["directive_key"],
                "family": row["family"],
                "priority": row.get("priority", "conditional"),
            }
            for row in legislations
        ],
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