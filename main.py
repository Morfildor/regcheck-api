from __future__ import annotations

import logging
import os
import secrets
from contextlib import asynccontextmanager
from time import perf_counter
from typing import Annotated, Any

from fastapi import Depends, FastAPI, Header, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from env_config import init_env

init_env()

from knowledge_base import (
    KnowledgeBaseError,
    KnowledgeBaseWarmupResult,
    load_genres,
    load_legislations,
    load_meta,
    load_products,
    load_standards,
    load_traits,
    reset_cache,
    warmup_knowledge_base,
)
from models import AnalysisResult, ErrorInfo, ErrorResponse, ProductInput
from rules import ENGINE_VERSION, analyze
from runtime_state import APP_VERSION, AppRuntimeState, KnowledgeBaseWarmupSnapshot

ADMIN_RELOAD_TOKEN_ENV = "REGCHECK_ADMIN_RELOAD_TOKEN"
EXPOSE_HEALTH_DETAILS = os.getenv("REGCHECK_EXPOSE_HEALTH_DETAILS", "false").strip().lower() in {"1", "true", "yes", "on"}

logger = logging.getLogger(__name__)

DEFAULT_ALLOWED_ORIGINS = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "https://rulegrid.net",
    "https://www.rulegrid.net",
]
DEFAULT_ALLOWED_ORIGIN_REGEX = r"https://regcheck-frontend(?:-[a-z0-9-]+)?\.vercel\.app"


def _csv_env_list(name: str) -> list[str]:
    return [item.strip() for item in os.getenv(name, "").split(",") if item.strip()]


def _combine_origin_regex(parts: list[str]) -> str | None:
    cleaned = [part.strip() for part in parts if part and part.strip()]
    if not cleaned:
        return None
    if len(cleaned) == 1:
        return cleaned[0]
    return "|".join(f"(?:{part})" for part in cleaned)


def _cors_configuration() -> tuple[list[str], str | None]:
    allow_origins = sorted(set(DEFAULT_ALLOWED_ORIGINS + _csv_env_list("CORS_ALLOWED_ORIGINS")))
    allow_origin_regex = _combine_origin_regex(
        [DEFAULT_ALLOWED_ORIGIN_REGEX, os.getenv("CORS_ALLOWED_ORIGIN_REGEX", "").strip()]
    )
    return allow_origins, allow_origin_regex


def _build_warmup_snapshot(result: KnowledgeBaseWarmupResult) -> KnowledgeBaseWarmupSnapshot:
    return KnowledgeBaseWarmupSnapshot(
        counts=dict(result.counts),
        meta=dict(result.meta),
        duration_ms=result.duration_ms,
    )


def get_runtime_state(target_app: FastAPI | None = None) -> AppRuntimeState:
    app_ref = target_app or app
    runtime_state = getattr(app_ref.state, "runtime_state", None)
    if not isinstance(runtime_state, AppRuntimeState):
        runtime_state = AppRuntimeState()
        app_ref.state.runtime_state = runtime_state
    return runtime_state


def _readiness_payload(runtime_state: AppRuntimeState) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "ok": runtime_state.is_ready,
        "version": APP_VERSION,
        "engine_version": ENGINE_VERSION,
        "catalog_version": runtime_state.catalog_version,
        "knowledge_base_loaded": runtime_state.knowledge_base_loaded,
        "startup_state": runtime_state.startup_state,
    }
    if EXPOSE_HEALTH_DETAILS:
        payload.update(
            {
                "warmup_duration_ms": runtime_state.warmup_duration_ms,
                "ready_timestamp": runtime_state.ready_timestamp,
            }
        )
    return payload


def _update_runtime_state_after_warmup(target_app: FastAPI, result: KnowledgeBaseWarmupResult, *, reloaded: bool = False) -> None:
    runtime_state = get_runtime_state(target_app)
    runtime_state.mark_ready(_build_warmup_snapshot(result), reloaded=reloaded)


def _update_runtime_state_after_failure(target_app: FastAPI, error: str, *, state: str = "failed", reloaded: bool = False) -> None:
    runtime_state = get_runtime_state(target_app)
    runtime_state.mark_failed(error, state=state, reloaded=reloaded)


@asynccontextmanager
async def lifespan(target_app: FastAPI):
    runtime_state = get_runtime_state(target_app)
    runtime_state.mark_warming("warming_up")
    try:
        result = warmup_knowledge_base()
        _update_runtime_state_after_warmup(target_app, result)
        logger.info(
            "startup_warmup_success startup_state=%s knowledge_base_loaded=%s duration_ms=%s catalog_version=%s",
            runtime_state.startup_state,
            runtime_state.knowledge_base_loaded,
            runtime_state.warmup_duration_ms,
            runtime_state.catalog_version or "",
        )
    except KnowledgeBaseError as exc:
        _update_runtime_state_after_failure(target_app, str(exc), state="failed")
        logger.exception("startup_warmup_failed startup_state=%s", runtime_state.startup_state)
    yield


app = FastAPI(title="RegCheck API", version=APP_VERSION, lifespan=lifespan)
app.state.runtime_state = AppRuntimeState()

allow_origins, allow_origin_regex = _cors_configuration()

app.add_middleware(
    CORSMiddleware,
    allow_origins=allow_origins,
    allow_origin_regex=allow_origin_regex,
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Admin-Token", "X-Request-Id"],
)


def _standard_directives(row: dict[str, Any]) -> list[str]:
    directives = row.get("directives")
    if isinstance(directives, list):
        values = [item for item in directives if isinstance(item, str) and item]
        if values:
            return values

    legislation_key = row.get("legislation_key")
    if isinstance(legislation_key, str) and legislation_key:
        return [legislation_key]

    return ["OTHER"]


def _http_error(status_code: int, code: str, message: str) -> HTTPException:
    return HTTPException(status_code=status_code, detail={"code": code, "message": message})


def _normalize_error_detail(detail: Any, *, default_code: str) -> tuple[str, str]:
    if isinstance(detail, dict):
        code = str(detail.get("code") or default_code)
        message = str(detail.get("message") or detail.get("detail") or "Request failed")
        return code, message
    if isinstance(detail, str):
        return default_code, detail
    return default_code, "Request failed"


def _validation_error_message(exc: RequestValidationError) -> str:
    details: list[str] = []
    for error in exc.errors():
        location = ".".join(str(part) for part in error.get("loc", []) if part != "body")
        message = str(error.get("msg") or "Invalid value")
        details.append(f"{location}: {message}" if location else message)
    if not details:
        return "Request validation failed"
    return "Request validation failed: " + "; ".join(details)


def _request_id(request: Request | None) -> str | None:
    if request is None:
        return None
    request_id = request.headers.get("x-request-id")
    return request_id.strip() if request_id else None


def _analyzer_ready_or_raise() -> AppRuntimeState:
    runtime_state = get_runtime_state()
    if not runtime_state.is_ready:
        message = runtime_state.warmup_error or "Knowledge base is not ready."
        raise _http_error(status.HTTP_503_SERVICE_UNAVAILABLE, "knowledge_base_not_ready", message)
    return runtime_state


def _require_admin_reload_token(
    x_admin_token: Annotated[str | None, Header(alias="X-Admin-Token")] = None,
) -> None:
    expected_token = os.getenv(ADMIN_RELOAD_TOKEN_ENV, "").strip()
    if not expected_token:
        raise _http_error(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "admin_reload_disabled",
            f"Admin reload is disabled. Set {ADMIN_RELOAD_TOKEN_ENV} to enable it.",
        )
    if not x_admin_token or not secrets.compare_digest(x_admin_token, expected_token):
        raise _http_error(status.HTTP_403_FORBIDDEN, "forbidden", "Forbidden")


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    code, message = _normalize_error_detail(exc.detail, default_code="http_error")
    payload = ErrorResponse(error=ErrorInfo(code=code, message=message, request_id=_request_id(request)))
    return JSONResponse(status_code=exc.status_code, content=payload.model_dump())


@app.exception_handler(RequestValidationError)
async def request_validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    payload = ErrorResponse(
        error=ErrorInfo(
            code="request_validation_failed",
            message=_validation_error_message(exc),
            request_id=_request_id(request),
        )
    )
    return JSONResponse(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, content=payload.model_dump())


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("unhandled_request_failure request_id=%s path=%s", _request_id(request), request.url.path)
    payload = ErrorResponse(
        error=ErrorInfo(code="internal_error", message="Internal server error", request_id=_request_id(request))
    )
    return JSONResponse(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, content=payload.model_dump())


@app.get("/")
def root() -> dict[str, str]:
    return {"status": "RegCheck API is running", "version": APP_VERSION, "engine_version": ENGINE_VERSION}


@app.get("/health/live")
def health_live() -> dict[str, Any]:
    return {"ok": True, "version": APP_VERSION}


@app.get("/health/ready")
def health_ready() -> JSONResponse:
    runtime_state = get_runtime_state()
    payload = _readiness_payload(runtime_state)
    status_code = status.HTTP_200_OK if runtime_state.is_ready else status.HTTP_503_SERVICE_UNAVAILABLE
    return JSONResponse(status_code=status_code, content=payload)


@app.get("/health")
def health() -> JSONResponse:
    return health_ready()


@app.get("/metadata/options")
def metadata_options() -> dict[str, Any]:
    _analyzer_ready_or_raise()

    traits = load_traits()
    genres = load_genres()
    products = load_products()
    legislations = load_legislations()

    return {
        "traits": [{"id": row["id"], "label": row["label"], "description": row["description"]} for row in traits],
        "genres": [
            {
                "id": row["id"],
                "label": row["label"],
                "keywords": row.get("keywords", []),
                "traits": row.get("traits", []),
                "default_traits": row.get("default_traits", []),
                "functional_classes": row.get("functional_classes", []),
                "likely_standards": row.get("likely_standards", []),
            }
            for row in genres
        ],
        "products": [
            {
                "id": row["id"],
                "label": row["label"],
                "product_family": row.get("product_family"),
                "product_subfamily": row.get("product_subfamily"),
                "genres": row.get("genres", []),
                "aliases": row.get("aliases", []),
                "family_keywords": row.get("family_keywords", []),
                "genre_keywords": row.get("genre_keywords", []),
                "required_clues": row.get("required_clues", []),
                "preferred_clues": row.get("preferred_clues", []),
                "exclude_clues": row.get("exclude_clues", []),
                "confusable_with": row.get("confusable_with", []),
                "functional_classes": row.get("functional_classes", []),
                "genre_functional_classes": row.get("genre_functional_classes", []),
                "family_traits": row.get("family_traits", []),
                "genre_traits": row.get("genre_traits", []),
                "genre_default_traits": row.get("genre_default_traits", []),
                "subtype_traits": row.get("subtype_traits", []),
                "core_traits": row.get("core_traits", []),
                "default_traits": row.get("default_traits", []),
                "implied_traits": row.get("implied_traits", []),
                "likely_standards": row.get("likely_standards", []),
                "genre_likely_standards": row.get("genre_likely_standards", []),
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
                "bucket": row.get("bucket", "non_ce"),
            }
            for row in legislations
        ],
        "knowledge_base_meta": load_meta(),
    }


@app.get("/metadata/standards")
def metadata_standards() -> dict[str, Any]:
    _analyzer_ready_or_raise()

    return {
        "knowledge_base_meta": load_meta(),
        "standards": [
            {
                "directive": _standard_directives(row)[0],
                "directives": _standard_directives(row),
                "code": row["code"],
                "title": row["title"],
                "category": row["category"],
                "legislation_key": row.get("legislation_key"),
                "item_type": row.get("item_type", "standard"),
                "standard_family": row.get("standard_family"),
                "harmonization_status": row.get("harmonization_status", "unknown"),
                "is_harmonized": row.get("is_harmonized"),
                "harmonized_under": row.get("harmonized_under"),
                "harmonized_reference": row.get("harmonized_reference"),
                "version": row.get("version"),
                "dated_version": row.get("dated_version"),
                "supersedes": row.get("supersedes"),
                "test_focus": row.get("test_focus", []),
                "evidence_hint": row.get("evidence_hint", []),
                "keywords": row.get("keywords", []),
                "selection_group": row.get("selection_group"),
                "selection_priority": row.get("selection_priority", 0),
                "required_fact_basis": row.get("required_fact_basis", "inferred"),
                "applies_if_products": row.get("applies_if_products", []),
                "applies_if_genres": row.get("applies_if_genres", []),
                "applies_if_all": row.get("applies_if_all", []),
                "applies_if_any": row.get("applies_if_any", []),
                "exclude_if_genres": row.get("exclude_if_genres", []),
            }
            for row in load_standards()
        ],
    }


@app.post("/admin/reload")
def admin_reload(_: None = Depends(_require_admin_reload_token)) -> dict[str, Any]:
    runtime_state = get_runtime_state()
    runtime_state.mark_warming("reloading")
    try:
        reset_cache()
        result = warmup_knowledge_base()
        _update_runtime_state_after_warmup(app, result, reloaded=True)
        logger.info(
            "admin_reload_success startup_state=%s duration_ms=%s catalog_version=%s",
            runtime_state.startup_state,
            runtime_state.warmup_duration_ms,
            runtime_state.catalog_version or "",
        )
        return {
            "ok": True,
            "version": APP_VERSION,
            "engine_version": ENGINE_VERSION,
            "catalog_version": runtime_state.catalog_version,
            "knowledge_base_loaded": runtime_state.knowledge_base_loaded,
            "startup_state": runtime_state.startup_state,
            "knowledge_base": runtime_state.warmup_counts,
        }
    except KnowledgeBaseError as exc:
        _update_runtime_state_after_failure(app, str(exc), state="failed", reloaded=True)
        logger.exception("admin_reload_failed startup_state=%s", runtime_state.startup_state)
        raise _http_error(status.HTTP_503_SERVICE_UNAVAILABLE, "knowledge_base_reload_failed", str(exc)) from exc


def run_analysis(product: ProductInput, request: Request | None = None) -> AnalysisResult:
    _analyzer_ready_or_raise()

    request_id = _request_id(request)
    started = perf_counter()
    try:
        logger.info(
            "analysis_request request_id=%s chars=%s category=%s directives=%s depth=%s",
            request_id or "",
            len(product.description or ""),
            product.category or "",
            ",".join(product.directives or []),
            product.depth,
        )
        result = analyze(
            description=product.description,
            category=product.category,
            directives=product.directives,
            depth=product.depth,
        )
    except KnowledgeBaseError as exc:
        logger.warning("analysis_service_unavailable request_id=%s detail=%s", request_id or "", str(exc))
        raise _http_error(status.HTTP_503_SERVICE_UNAVAILABLE, "knowledge_base_unavailable", str(exc)) from exc
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("analysis_failed request_id=%s", request_id or "")
        raise _http_error(status.HTTP_500_INTERNAL_SERVER_ERROR, "analysis_failed", "Analysis failed") from exc

    latency_ms = int((perf_counter() - started) * 1000)
    logger.info(
        "analysis_completed request_id=%s latency_ms=%s depth=%s product_type=%s ambiguity=%s degraded_mode=%s",
        request_id or "",
        latency_ms,
        product.depth,
        result.product_type or "",
        result.classification_is_ambiguous,
        result.degraded_mode,
    )
    if result.product_match_confidence == "low" or result.classification_is_ambiguous:
        logger.warning(
            "analysis_low_confidence request_id=%s product_type=%s confidence=%s ambiguity=%s",
            request_id or "",
            result.product_type or "",
            result.product_match_confidence,
            result.classification_is_ambiguous,
        )
    if result.degraded_mode:
        logger.warning(
            "analysis_degraded request_id=%s product_type=%s reasons=%s",
            request_id or "",
            result.product_type or "",
            ",".join(result.degraded_reasons),
        )
    return result


@app.post("/analyze", response_model=AnalysisResult)
def analyze_route(product: ProductInput, request: Request) -> AnalysisResult:
    return run_analysis(product, request)
