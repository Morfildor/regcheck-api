from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from models import AnalysisResult, ProductInput
from rules import analyze

app = FastAPI(title="RegCheck API", version="2.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "https://rulegrid.net",
        "https://www.rulegrid.net",
    ],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def root():
    return {"status": "RegCheck API is running", "version": "2.1.0"}


@app.get("/health")
def health():
    return {"ok": True}


@app.post("/analyze", response_model=AnalysisResult)
def run_analysis(product: ProductInput):
    return analyze(
        description=product.description,
        category=product.category,
        directives=product.directives,
        depth=product.depth,
    )