import os
from dotenv import load_dotenv

load_dotenv()


def _sync_database_url(database_url: str) -> str:
    if database_url.startswith("postgresql+asyncpg://"):
        return database_url.replace("postgresql+asyncpg://", "postgresql+psycopg2://", 1)
    if database_url.startswith("postgres://"):
        return database_url.replace("postgres://", "postgresql+psycopg2://", 1)
    if database_url.startswith("postgresql://"):
        return database_url.replace("postgresql://", "postgresql+psycopg2://", 1)
    return database_url


def _validated_database_url(database_url: str, name: str) -> str:
    if "://USER:PASSWORD@" in database_url:
        raise RuntimeError(
            f"{name} still contains placeholder credentials. "
            "Set real database username and password in the environment."
        )
    return database_url


def _required_secret(name: str, fallback_name: str | None = None) -> str:
    value = os.getenv(name)
    if value:
        return value

    if fallback_name:
        fallback_value = os.getenv(fallback_name)
        if fallback_value:
            return fallback_value

    if APP_ENV in {"production", "prod"}:
        fallback_message = f" or {fallback_name}" if fallback_name else ""
        raise RuntimeError(f"{name}{fallback_message} is required in production")

    return "change-me-local-dev-only"


def _env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default

    return value.strip().lower() in {"1", "true", "yes", "on"}


APP_ENV = os.getenv("APP_ENV", "development").strip().lower()
LOCAL_USER_ID = os.getenv("LOCAL_USER_ID", "local-test-user")
LOCAL_USER_EMAIL = os.getenv("LOCAL_USER_EMAIL", "local-test@example.com")
LOCAL_USER_NAME = os.getenv("LOCAL_USER_NAME", "Local Test")
LOCAL_USER_UNSUBSCRIBE_PUBLIC_KEY = os.getenv(
    "LOCAL_USER_UNSUBSCRIBE_PUBLIC_KEY",
    "local-test-unsubscribe-key",
)
AWS_REGION = os.getenv("AWS_REGION", "eu-central-1")
SECRETS_BACKEND = os.getenv("SECRETS_BACKEND", "env").strip().lower()
SES_PREFLIGHT_ENABLED = _env_bool(
    "SES_PREFLIGHT_ENABLED",
    APP_ENV in {"production", "prod"} and SECRETS_BACKEND == "aws",
)
SMTP_SECRET_ID = os.getenv("SMTP_SECRET_ID")
SMTP_SECRET_CACHE_SECONDS = int(os.getenv("SMTP_SECRET_CACHE_SECONDS", 300))
PUBLIC_API_BASE_URL = os.getenv("PUBLIC_API_BASE_URL", "http://localhost:8000").rstrip("/")
UNSUBSCRIBE_SECRET = _required_secret("UNSUBSCRIBE_SECRET", "JWT_SECRET")
TRACKING_SECRET = _required_secret("TRACKING_SECRET", "UNSUBSCRIBE_SECRET")

RABBITMQ_URL = os.getenv("RABBITMQ_URL", "amqp://guest:guest@localhost:5672//")

CELERY_BACKEND = os.getenv("CELERY_BACKEND", "redis://127.0.0.1:6379/0")
REDIS_URL = os.getenv("REDIS_URL", CELERY_BACKEND)

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+asyncpg://postgres:postgres@localhost:5432/email_service",
)
DATABASE_URL = _validated_database_url(DATABASE_URL, "DATABASE_URL")
SYNC_DATABASE_URL = os.getenv("SYNC_DATABASE_URL") or _sync_database_url(DATABASE_URL)
SYNC_DATABASE_URL = _validated_database_url(SYNC_DATABASE_URL, "SYNC_DATABASE_URL")

DEFAULT_BATCH_SIZE = int(os.getenv("DEFAULT_BATCH_SIZE", 200))
DEFAULT_PER_BATCH_DELAY = float(os.getenv("DEFAULT_PER_BATCH_DELAY", 0.2))
CAMPAIGN_WORKER_BATCH_SIZE = int(os.getenv("CAMPAIGN_WORKER_BATCH_SIZE", DEFAULT_BATCH_SIZE))
CAMPAIGN_WORKER_MAX_BATCHES = int(os.getenv("CAMPAIGN_WORKER_MAX_BATCHES", 15))
CAMPAIGN_MAX_ACTIVE_WORKERS = int(os.getenv("CAMPAIGN_MAX_ACTIVE_WORKERS", 4))
BULK_CAMPAIGN_THRESHOLD = int(os.getenv("BULK_CAMPAIGN_THRESHOLD", 10000))
SEND_RATE_LIMIT_PER_SECOND = float(os.getenv("SEND_RATE_LIMIT_PER_SECOND", 0))
SEND_RATE_LIMIT_REDIS_TTL_SECONDS = int(os.getenv("SEND_RATE_LIMIT_REDIS_TTL_SECONDS", 3600))
CAMPAIGN_ACTIVE_WORKER_TTL_SECONDS = int(os.getenv("CAMPAIGN_ACTIVE_WORKER_TTL_SECONDS", 3600))
CAMPAIGN_DEFAULT_QUEUE = os.getenv("CAMPAIGN_DEFAULT_QUEUE", "campaigns_default")
CAMPAIGN_HIGH_QUEUE = os.getenv("CAMPAIGN_HIGH_QUEUE", "campaigns_high")
CAMPAIGN_LOW_QUEUE = os.getenv("CAMPAIGN_LOW_QUEUE", "campaigns_low")
WEBHOOKS_QUEUE = os.getenv("WEBHOOKS_QUEUE", "webhooks")
MAINTENANCE_QUEUE = os.getenv("MAINTENANCE_QUEUE", "maintenance")
MONGO_URL = os.getenv("MONGO_URL", "mongodb://localhost:27017/python_email_sender")

MAX_RECIPIENT_SEND_ATTEMPTS = 3

SENDING_TIMEOUT_SECONDS = int(os.getenv("SENDING_TIMEOUT_SECONDS", 900))
SENDING_RECOVERY_INTERVAL_SECONDS = int(os.getenv("SENDING_RECOVERY_INTERVAL_SECONDS", 300))
SUPPRESSION_SYNC_INTERVAL_SECONDS = int(os.getenv("SUPPRESSION_SYNC_INTERVAL_SECONDS", 21600))

SES_CONFIGURATION_SET=os.getenv("SES_CONFIGURATION_SET")
SNS_SES_TOPIC_ARN = os.getenv("SNS_SES_TOPIC_ARN")

EMAIL_EVENT_COMPLAINT = "complaint"
EMAIL_EVENT_BOUNCE = "bounce"
EMAIL_EVENT_OPEN = "open"
EMAIL_EVENT_CLICK = "click"
SUPPRESSION_SYNC_STATUS_SUCCESS = "success"
SUPPRESSION_SYNC_STATUS_FAILED = "failed"
SUPPRESSION_STATUS_INACTIVE = "inactive"
SUPPRESSION_SOURCE_SES = "ses"
SUPPRESSION_REASON_MANUAL = "manual"
SUPPRESSION_REASON_UNSUBSCRIBE = "unsubscribe"
SUPPRESSION_REASON_HARD_BOUNCE = "hard_bounce"
SUPPRESSION_REASON_COMPLAINT = "complaint"
SUPPRESSION_SOURCE_LOCAL = "local"
SUPPRESSION_SOURCE_ADMIN = "admin"
SUPPRESSION_STATUS_ACTIVE = "active"

RECIPIENT_QUEUED = "queued"
RECIPIENT_SENT = "sent"
RECIPIENT_FAILED_PERMANENT = "failed_permanent"
RECIPIENT_FAILED_TRANSIENT = "failed_transient"
RECIPIENT_SENDING = "sending"
RECIPIENT_SUPPRESSED = "suppressed"
RECIPIENT_CANCELLED = "cancelled"

FINAL_RECIPIENT_STATUSES = {
    RECIPIENT_CANCELLED,
    RECIPIENT_FAILED_PERMANENT,
    RECIPIENT_SUPPRESSED,
    RECIPIENT_SENT,
}
RETRYABLE_OR_ACTIVE_RECIPIENT_STATUSES = {
    RECIPIENT_SENDING,
    RECIPIENT_QUEUED,
    RECIPIENT_FAILED_TRANSIENT,
}
