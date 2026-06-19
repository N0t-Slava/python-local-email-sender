from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from src.services.local_user_service import get_local_user
from src.database.sqlalchemy import get_db
from src.configs.config import AWS_REGION, SES_PREFLIGHT_ENABLED
from src.integrations.ses_service import get_ses_dashboard_status_from_email
from src.security.secrets import get_smtp_credentials
from src.services.deliverability_metrics_service import (
    get_deliverability_summary_service,
    list_deliverability_events_service,
)

router = APIRouter()


def _local_smtp_status(from_email: str):
    return {
        "region": AWS_REGION,
        "sending_enabled": True,
        "production_access_enabled": False,
        "mode": "local",
        "from_email": from_email,
        "from_email_verified": True,
        "sender_verified": True,
        "quota": {
            "max_24h_send": None,
            "sent_last_24h": None,
            "remaining_24h": None,
            "max_send_rate": None,
        },
        "alerts": [
            {
                "level": "info",
                "code": "local_smtp_mode",
                "message": "SES preflight is disabled; messages are sent through the configured SMTP server.",
            }
        ],
    }


@router.get("/dashboard/ses-status")
async def get_ses_status():
    from_email = get_smtp_credentials().from_email
    if not SES_PREFLIGHT_ENABLED:
        return _local_smtp_status(from_email)

    return get_ses_dashboard_status_from_email(from_email)


@router.get("/dashboard/deliverability-summary")
async def get_deliverability_summary(
    db: AsyncSession = Depends(get_db),
):
    current_user = get_local_user()
    return await get_deliverability_summary_service(db, current_user["id"])


@router.get("/dashboard/email-events")
async def list_deliverability_events(
    limit: int = Query(25, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    current_user = get_local_user()
    return await list_deliverability_events_service(db, current_user["id"], limit)
