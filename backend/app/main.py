"""
FastAPI application factory. Registers every module's router under
/api/v1, wires request-ID correlation, structured logging, CORS
(hospital LAN origins only), and a single consistent error-response
shape for every DomainError subclass raised anywhere in the app.
"""
import time
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.core.config import get_settings
from app.core.exceptions import DomainError
from app.core.logging import configure_logging, new_request_id, request_id_ctx

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging(settings.ENVIRONMENT)

    if settings.ENVIRONMENT == "production" and "CHANGE_ME" in settings.JWT_SECRET_KEY:
        raise RuntimeError(
            "JWT_SECRET_KEY is still the development placeholder — refusing to start in production. "
            "Set a long, random secret via the environment before deploying."
        )

    from app.integrations.storage import ensure_buckets_exist
    try:
        ensure_buckets_exist()
    except Exception as e:  # pragma: no cover - MinIO may not be reachable in unit tests
        import logging
        logging.getLogger(__name__).warning("Could not verify MinIO buckets on startup: %s", e)

    yield


app = FastAPI(
    title=settings.APP_NAME,
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/api/docs" if settings.ENVIRONMENT != "production" else None,
    redoc_url=None,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "PUT", "DELETE"],
    allow_headers=["Authorization", "Content-Type", "Idempotency-Key"],
)


@app.middleware("http")
async def request_id_and_timing_middleware(request: Request, call_next):
    req_id = request.headers.get("X-Request-ID") or new_request_id()
    token = request_id_ctx.set(req_id)
    start = time.monotonic()
    try:
        response = await call_next(request)
    finally:
        request_id_ctx.reset(token)
    response.headers["X-Request-ID"] = req_id
    response.headers["X-Response-Time-Ms"] = str(round((time.monotonic() - start) * 1000, 1))
    return response


@app.middleware("http")
async def security_headers_middleware(request: Request, call_next):
    """Per docs/security/network.md — applied here so it's enforced even
    before Nginx's own header configuration is finalized in Phase 8."""
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "same-origin"
    if settings.ENVIRONMENT == "production":
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return response


@app.exception_handler(DomainError)
async def domain_error_handler(request: Request, exc: DomainError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error_code": exc.error_code,
            "message": exc.message,
            "request_id": request_id_ctx.get(),
        },
    )


@app.get("/api/v1/health")
async def health() -> dict:
    return {"status": "ok", "environment": settings.ENVIRONMENT}


# ---------------------------------------------------------------------------
# Router registration — one line per module, matching the directory
# structure in ARCHITECTURE.md §2.2.
# ---------------------------------------------------------------------------
from app.accounting.router import router as accounting_router
from app.administration.router import router as administration_router
from app.appointments.router import router as appointments_router
from app.appointments.reminders import router as reminders_router
from app.appointments.communications import router as communications_router
from app.assets.router import router as assets_router
from app.audit.router import router as audit_router
from app.auth.router import router as auth_router
from app.billing.router import router as billing_router
from app.clinical.router import router as clinical_router
from app.clinical_documents.router import router as clinical_documents_router
from app.cryostorage.router import router as cryostorage_router
from app.donor.router import router as donor_router
from app.embryology.router import router as embryology_router
from app.hr.router import router as hr_router
from app.inventory.router import router as inventory_router
from app.ivf.router import router as ivf_router
from app.laboratory.router import router as laboratory_router
from app.maintenance.router import router as maintenance_router
from app.messaging.router import router as messaging_router
from app.notifications.router import router as notifications_router
from app.nursing.router import router as nursing_router
from app.ot.router import router as ot_router
from app.patients.documents import router as patient_documents_router
from app.patients.router import router as patients_router
from app.pharmacy.router import router as pharmacy_router
from app.pharmacy.templates import router as pharmacy_templates_router
from app.pharmacy.purchase_returns import router as pharmacy_purchase_returns_router
from app.pharmacy.purchase_orders import router as pharmacy_purchase_orders_router
from app.pharmacy.settings import router as pharmacy_settings_router
from app.pharmacy.reports import router as pharmacy_reports_router
from app.prescription.router import router as prescription_router
from app.printing.router import router as printing_router
from app.purchasing.router import router as purchasing_router
from app.quality.router import router as quality_router
from app.reports.router import router as reports_router
from app.roles.router import router as roles_router
from app.users.router import router as users_router

for router in (
    auth_router, users_router, roles_router,
    patients_router, patient_documents_router, appointments_router, reminders_router, communications_router,
    clinical_router, ivf_router, laboratory_router, embryology_router, cryostorage_router, ot_router,
    pharmacy_router, pharmacy_templates_router, pharmacy_purchase_returns_router,
    pharmacy_purchase_orders_router, pharmacy_settings_router, pharmacy_reports_router,
    inventory_router, purchasing_router, billing_router, accounting_router,
    assets_router, maintenance_router, quality_router, hr_router,
    notifications_router, printing_router, reports_router, administration_router, audit_router,
    donor_router, prescription_router, clinical_documents_router, messaging_router,
    nursing_router,
):
    app.include_router(router, prefix=settings.API_V1_PREFIX)
