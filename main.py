from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from models import ProductInput
from rules import analyze

app = FastAPI(title="RegCheck API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
    "http://localhost:3000",
    "https://regcheck1.netlify.app"
],
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def root():
    return {"status": "RegCheck API is running"}

@app.post("/analyze")
def run_analysis(product: ProductInput):
    result = analyze(
        description=product.description,
        category=product.category,
        directives=product.directives,
        depth=product.depth
    )
    return result