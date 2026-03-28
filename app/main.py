from __future__ import annotations

import logging
import secrets
from contextlib import asynccontextmanager
from time import perf_counter
from typing import Annotated, Any

from fastapi import Depends, FastAPI, Header, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.core.logging import clear_request_id, configure_logging, set_request_id
from app.core.runtime_state import APP_VERSION, AppRuntimeState, KnowledgeBaseWarmupSnapshot
from app.core.settings import get_settings, load_settings
from app.domain.models import (
    AnalysisResult,
    ErrorInfo,
    ErrorResponse,
    HealthResponse,
    MetadataOptionsResponse,
    MetadataStandardsResponse,
    ProductInput,
    ReloadResponse,
    RootResponse,
)
from app.services.knowledge_base import (
    KnowledgeBaseError,
    KnowledgeBaseWarmupResult,
    load_metadata_payload,
    warmup_knowledge_base,
)
from app.services.rules import AnalysisTrace, ENGINE_VERSION, analyze

configure_logging()
logger = logging.getLogger(__name__)


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


def _compat_main_attr(name: str) -> Any | None:
    try:
        import main as compat_main
    except ImportError:
        return None
    return getattr(compat_main, name, None)


def _warmup_knowledge_base() -> KnowledgeBaseWarmupResult:
    compat_warmup = _compat_main_attr("warmup_knowledge_base")
    if callable(compat_warmup):
        return compat_warmup(refresh_paths=True)
    return warmup_knowledge_base(refresh_paths=True)


def _analyze_product(*, description: str, category: str, directives: list[str] | None, depth: str, trace: AnalysisTrace) -> AnalysisResult:
    compat_analyze = _compat_main_attr("analyze")
    analyzer = compat_analyze if callable(compat_analyze) else analyze
    return analyzer(
        description=description,
        category=category,
        directives=directives,
        depth=depth,
        trace=trace,
    )


def _readiness_payload(runtime_state: AppRuntimeState) -> dict[str, Any]:
    settings = get_settings()
    snapshot = runtime_state.snapshot()
    payload: dict[str, Any] = {
        "ok": snapshot.is_ready,
        "version": APP_VERSION,
        "engine_version": ENGINE_VERSION,
        "catalog_version": snapshot.catalog_version,
        "knowledge_base_loaded": snapshot.knowledge_base_loaded,
        "startup_state": snapshot.startup_state,
    }
    if settings.expose_health_details:
        payload.update(
            {
                "warmup_duration_ms": snapshot.warmup_duration_ms,
                "ready_timestamp": snapshot.ready_timestamp,
                "last_reload_error": snapshot.last_reload_error,
            }
        )
    return payload


def _update_runtime_state_after_warmup(
    target_app: FastAPI,
    result: KnowledgeBaseWarmupResult,
    *,
    reloaded: bool = False,
) -> None:
    get_runtime_state(target_app).mark_ready(_build_warmup_snapshot(result), reloaded=reloaded)


def _update_runtime_state_after_failure(
    target_app: FastAPI,
    error: str,
    *,
    state: str = "failed",
    reloaded: bool = False,
) -> None:
    runtime_state = get_runtime_state(target_app)
    if reloaded and runtime_state.catalog_version:
        runtime_state.mark_reload_failed(error)
        return
    runtime_state.mark_failed(error, state=state, reloaded=reloaded)


@asynccontextmanager
async def lifespan(target_app: FastAPI):
    runtime_state = get_runtime_state(target_app)
    runtime_state.mark_warming("warming_up")
    try:
        result = _warmup_knowledge_base()
        _update_runtime_state_after_warmup(target_app, result)
        snapshot = runtime_state.snapshot()
        logger.info(
            "startup_warmup_success startup_state=%s knowledge_base_loaded=%s duration_ms=%s catalog_version=%s",
            snapshot.startup_state,
            snapshot.knowledge_base_loaded,
            snapshot.warmup_duration_ms,
            snapshot.catalog_version or "",
        )
    except KnowledgeBaseError as exc:
        _update_runtime_state_after_failure(target_app, str(exc), state="failed")
        logger.exception("startup_warmup_failed startup_state=%s", runtime_state.snapshot().startup_state)
    yield


app = FastAPI(title="RegCheck API", version=APP_VERSION, lifespan=lifespan)
app.state.runtime_state = AppRuntimeState()

settings = get_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors.allow_origins,
    allow_origin_regex=settings.cors.allow_origin_regex,
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Admin-Token", "X-Request-Id"],
)


@app.middleware("http")
async def request_context_middleware(request: Request, call_next):
    request_id = request.headers.get("x-request-id")
    normalized_request_id = request_id.strip() if request_id and request_id.strip() else secrets.token_hex(8)
    request.state.request_id = normalized_request_id
    set_request_id(normalized_request_id)
    try:
        response = await call_next(request)
    finally:
        clear_request_id()
    response.headers["X-Request-Id"] = normalized_request_id
    return response


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
    request_id = getattr(request.state, "request_id", None)
    if isinstance(request_id, str) and request_id:
        return request_id
    header_value = request.headers.get("x-request-id")
    return header_value.strip() if header_value else None


def _analyzer_ready_or_raise() -> AppRuntimeState:
    runtime_state = get_runtime_state()
    snapshot = runtime_state.snapshot()
    if not snapshot.is_ready:
        message = snapshot.warmup_error or "Knowledge base is not ready."
        raise _http_error(status.HTTP_503_SERVICE_UNAVAILABLE, "knowledge_base_not_ready", message)
    return runtime_state


def _require_admin_reload_token(
    x_admin_token: Annotated[str | None, Header(alias="X-Admin-Token")] = None,
) -> None:
    settings = load_settings()
    expected_token = settings.admin_reload_token
    if not expected_token:
        raise _http_error(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "admin_reload_disabled",
            f"Admin reload is disabled. Set {settings.admin_reload_token_env} to enable it.",
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


@app.get("/", response_model=RootResponse)
def root() -> RootResponse:
    return RootResponse(status="RegCheck API is running", version=APP_VERSION, engine_version=ENGINE_VERSION)


@app.get("/health/live", response_model=HealthResponse)
def health_live() -> HealthResponse:
    return HealthResponse(ok=True, version=APP_VERSION)


@app.get("/health/ready", response_model=HealthResponse)
def health_ready() -> JSONResponse:
    runtime_state = get_runtime_state()
    payload = _readiness_payload(runtime_state)
    status_code = status.HTTP_200_OK if runtime_state.snapshot().is_ready else status.HTTP_503_SERVICE_UNAVAILABLE
    return JSONResponse(status_code=status_code, content=HealthResponse.model_validate(payload).model_dump())


@app.get("/health", response_model=HealthResponse)
def health() -> JSONResponse:
    return health_ready()


@app.get("/metadata/options", response_model=MetadataOptionsResponse)
def metadata_options() -> dict[str, Any]:
    _analyzer_ready_or_raise()
    return MetadataOptionsResponse.model_validate(load_metadata_payload("options")).model_dump()


@app.get("/metadata/standards", response_model=MetadataStandardsResponse)
def metadata_standards() -> dict[str, Any]:
    _analyzer_ready_or_raise()
    return MetadataStandardsResponse.model_validate(load_metadata_payload("standards")).model_dump()


@app.post("/admin/reload", response_model=ReloadResponse)
def admin_reload(_: None = Depends(_require_admin_reload_token)) -> dict[str, Any]:
    runtime_state = get_runtime_state()
    with runtime_state.reload_guard():
        runtime_state.mark_warming("reloading", preserve_snapshot=True)
        try:
            result = _warmup_knowledge_base()
            _update_runtime_state_after_warmup(app, result, reloaded=True)
            snapshot = runtime_state.snapshot()
            logger.info(
                "reload_success startup_state=%s duration_ms=%s catalog_version=%s",
                snapshot.startup_state,
                snapshot.warmup_duration_ms,
                snapshot.catalog_version or "",
            )
            return ReloadResponse(
                ok=True,
                version=APP_VERSION,
                engine_version=ENGINE_VERSION,
                catalog_version=snapshot.catalog_version,
                knowledge_base_loaded=snapshot.knowledge_base_loaded,
                startup_state=snapshot.startup_state,
                knowledge_base=snapshot.warmup_counts,
            ).model_dump()
        except KnowledgeBaseError as exc:
            _update_runtime_state_after_failure(app, str(exc), state="failed", reloaded=True)
            logger.exception("reload_failed startup_state=%s", runtime_state.snapshot().startup_state)
            raise _http_error(status.HTTP_503_SERVICE_UNAVAILABLE, "knowledge_base_reload_failed", str(exc)) from exc


def run_analysis(product: ProductInput, request: Request | None = None) -> AnalysisResult:
    _analyzer_ready_or_raise()
    request_id = _request_id(request)
    started = perf_counter()
    trace = AnalysisTrace(request_id=request_id)
    try:
        logger.info(
            "analysis_start request_id=%s chars=%s category=%s directives=%s depth=%s",
            request_id or "",
            len(product.description or ""),
            product.category or "",
            ",".join(product.directives or []),
            product.depth,
        )
        result = _analyze_product(
            description=product.description,
            category=product.category,
            directives=product.directives,
            depth=product.depth,
            trace=trace,
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
        "analysis_end request_id=%s latency_ms=%s classification_ms=%s legislation_routing_ms=%s standards_selection_ms=%s response_assembly_ms=%s depth=%s product_type=%s ambiguity=%s degraded_mode=%s",
        request_id or "",
        latency_ms,
        trace.stage_timings_ms.get("classification", 0),
        trace.stage_timings_ms.get("legislation_routing", 0),
        trace.stage_timings_ms.get("standards_selection", 0),
        trace.stage_timings_ms.get("response_assembly", 0),
        product.depth,
        result.product_type or "",
        result.classification_is_ambiguous,
        result.degraded_mode,
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
