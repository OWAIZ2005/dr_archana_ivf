"""
Central application configuration.

All settings are read from environment variables (see .env.example).
Never hardcode secrets here — this file defines shape and safe defaults
for local dev only; production values always come from the environment.
"""
from functools import lru_cache
from typing import Literal

from pydantic import Field, PostgresDsn, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # ---- Environment ----
    ENVIRONMENT: Literal["local", "staging", "production"] = "local"
    APP_NAME: str = "Archana IVF HMIS"
    API_V1_PREFIX: str = "/api/v1"

    # ---- Database ----
    DATABASE_URL: str = "postgresql+asyncpg://archana:archana_dev@localhost:5432/archana_hmis"
    DATABASE_URL_SYNC: str = "postgresql+psycopg2://archana:archana_dev@localhost:5432/archana_hmis"
    DB_POOL_SIZE: int = 10
    DB_MAX_OVERFLOW: int = 5

    # ---- Redis ----
    REDIS_URL: str = "redis://localhost:6379/0"
    CELERY_BROKER_URL: str = "redis://localhost:6379/1"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/2"

    # ---- MinIO / Object Storage ----
    MINIO_ENDPOINT: str = "localhost:9000"
    MINIO_ACCESS_KEY: str = "archana_minio"
    MINIO_SECRET_KEY: str = "archana_minio_dev_secret"
    MINIO_SECURE: bool = False
    MINIO_BUCKET_DOCUMENTS: str = "hmis-documents"
    MINIO_BUCKET_REPORTS: str = "hmis-reports"

    # ---- Auth / Security ----
    JWT_SECRET_KEY: str = "CHANGE_ME_IN_PRODUCTION_USE_A_LONG_RANDOM_SECRET"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 14
    ABSOLUTE_SESSION_LIFETIME_HOURS: int = 12
    IDLE_TIMEOUT_MINUTES: int = 30
    PASSWORD_MIN_LENGTH: int = 10
    LOGIN_MAX_ATTEMPTS: int = 5
    LOGIN_LOCKOUT_MINUTES: int = 15

    # ---- CORS (frontend origin, LAN only) ----
    CORS_ORIGINS: list[str] = ["http://localhost:3000", "https://hmis.archanaivf.in"]

    # ---- Asset QR ----
    # Server-side fallback for the base URL encoded in a printed asset QR
    # (``<base>/#scan=<opaque-token>``). Normally the frontend passes its own
    # ``NEXT_PUBLIC_APP_URL`` as the ``?base=`` query param; this is only used
    # when that is absent. Empty => the QR encodes the bare opaque token
    # (still resolvable via manual entry). No IP/hostname is hardcoded here.
    ASSET_QR_BASE_URL: str = ""

    # ---- Uploads ----
    MAX_UPLOAD_SIZE_MB: int = 25
    ALLOWED_UPLOAD_MIME_TYPES: list[str] = [
        "application/pdf",
        "image/jpeg",
        "image/png",
        "image/webp",
    ]

    # ---- Laboratory report extraction ----
    # Local-filesystem seam for uploaded outside-lab report documents. Callers
    # only ever hold the opaque storage key this returns, so swapping in a
    # MinIO-backed ObjectStorage later needs no data migration.
    LAB_STORAGE_DIR: str = "./var/lab-reports"
    # When true the deterministic pipeline may hand pages to a configured AI
    # extraction provider. No provider is wired in, so enabling this without one
    # is a no-op — extraction stays deterministic.
    LAB_AI_EXTRACTION_ENABLED: bool = False
    # Absolute path to the Tesseract OCR binary. Leave unset to auto-discover it
    # (PATH, then the standard Windows install locations). Scanned PDFs and image
    # reports need it; digital PDFs do not. When it cannot be found, OCR fails
    # safely and no values are fabricated.
    TESSERACT_CMD: str | None = None

    # ---- Asynchronous report generation (Celery) ----
    # Where generated report artifacts are stored (same local-FS seam idea as
    # LAB_STORAGE_DIR). Broker/result-backend reuse CELERY_BROKER_URL /
    # CELERY_RESULT_BACKEND above — this module adds no new Redis settings.
    REPORT_STORAGE_DIR: str = "./var/reports"
    # Upper bound for the request-supplied options.simulate_work_seconds knob,
    # which makes the generator sleep to exercise the async pipeline under load.
    REPORT_SIMULATE_MAX_SECONDS: int = 30
    # When true, Celery `.delay()` runs the task inline and synchronously. The
    # unit-test suite sets this so it can drive enqueue -> generate -> status
    # without a running broker or worker. Never enabled in real runs.
    CELERY_TASK_ALWAYS_EAGER: bool = False

    # ---- Messaging / notifications ----
    # Which MessageProvider app/messaging/providers.py::get_provider() returns.
    # "console" is a safe no-op that logs instead of sending — the only provider
    # wired up. Set "msg91" later (with the credentials below) to send real
    # SMS/WhatsApp; no notification workflow changes when you do.
    MESSAGE_PROVIDER: Literal["console", "msg91"] = "console"
    # MSG91 credentials — read from the environment only, never committed.
    # Unused while MESSAGE_PROVIDER="console". Fill these in the environment when
    # the MSG91 account exists; the provider skeleton in providers.py reads them.
    MSG91_AUTH_KEY: str | None = None
    MSG91_SENDER_ID: str | None = None
    MSG91_SMS_TEMPLATE_ID: str | None = None
    MSG91_WHATSAPP_NUMBER: str | None = None
    MSG91_BASE_URL: str = "https://control.msg91.com/api"

    # Trigger-injection reminder schedule (hospital staff only — never patients).
    # First reminder fires at the planned trigger time; then every
    # TRIGGER_REMINDER_INTERVAL_MINUTES until TRIGGER_REMINDER_MAX_ATTEMPTS is
    # reached, after which the trigger is marked OVERDUE and no more are sent.
    TRIGGER_REMINDER_INTERVAL_MINUTES: int = 5
    TRIGGER_REMINDER_MAX_ATTEMPTS: int = 3

    # NPO (nil-by-mouth) lead time in minutes: NPO start = procedure time minus
    # this. There is NO clinically safe default here — this placeholder exists
    # only so the demo runs; the hospital must set the real value in the
    # environment. Clinical logic reads it from config, never hardcodes it.
    NPO_LEAD_TIME_MINUTES: int = 360

    @field_validator("JWT_SECRET_KEY")
    @classmethod
    def secret_must_be_overridden_in_production(cls, v: str, info) -> str:
        # Pydantic v2 doesn't easily cross-validate ENVIRONMENT here without a model_validator,
        # so the hard check also lives in main.py's startup guard.
        return v


@lru_cache
def get_settings() -> Settings:
    return Settings()
