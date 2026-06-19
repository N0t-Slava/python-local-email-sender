from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.configs.config import EMAIL_EVENT_BOUNCE, EMAIL_EVENT_COMPLAINT
from src.models.models import Campaign, EmailEvent


BOUNCE_WARNING_RATE = 0.02
BOUNCE_CRITICAL_RATE = 0.05
COMPLAINT_WARNING_RATE = 0.001
COMPLAINT_CRITICAL_RATE = 0.003


def _format_datetime(value):
    return value.isoformat() if value else None


def _rate(part: int, total: int):
    if total <= 0:
        return 0.0

    return part / total


def _worst_status(*statuses: str):
    if "critical" in statuses:
        return "critical"
    if "warning" in statuses:
        return "warning"
    return "good"


def _rate_status(rate: float, warning_threshold: float, critical_threshold: float):
    if rate >= critical_threshold:
        return "critical"
    if rate >= warning_threshold:
        return "warning"
    return "good"


def _build_alerts(bounce_rate: float, complaint_rate: float):
    alerts = []

    if bounce_rate >= BOUNCE_CRITICAL_RATE:
        alerts.append({
            "level": "critical",
            "code": "bounce_rate_critical",
            "message": "Bounce rate is critically high",
        })
    elif bounce_rate >= BOUNCE_WARNING_RATE:
        alerts.append({
            "level": "warning",
            "code": "bounce_rate_warning",
            "message": "Bounce rate is elevated",
        })

    if complaint_rate >= COMPLAINT_CRITICAL_RATE:
        alerts.append({
            "level": "critical",
            "code": "complaint_rate_critical",
            "message": "Complaint rate is critically high",
        })
    elif complaint_rate >= COMPLAINT_WARNING_RATE:
        alerts.append({
            "level": "warning",
            "code": "complaint_rate_warning",
            "message": "Complaint rate is elevated",
        })

    return alerts


async def get_deliverability_summary_service(db: AsyncSession, user_id: str):
    row = (
        await db.execute(
            select(
                func.coalesce(func.sum(Campaign.sent_count), 0),
                func.coalesce(func.sum(Campaign.bounce_count), 0),
                func.coalesce(func.sum(Campaign.complaint_count), 0),
                func.count(Campaign.id),
            ).where(Campaign.user_id == user_id)
        )
    ).one()

    sent_count = int(row[0] or 0)
    bounce_count = int(row[1] or 0)
    complaint_count = int(row[2] or 0)
    campaign_count = int(row[3] or 0)
    bounce_rate = _rate(bounce_count, sent_count)
    complaint_rate = _rate(complaint_count, sent_count)
    bounce_status = _rate_status(bounce_rate, BOUNCE_WARNING_RATE, BOUNCE_CRITICAL_RATE)
    complaint_status = _rate_status(
        complaint_rate,
        COMPLAINT_WARNING_RATE,
        COMPLAINT_CRITICAL_RATE,
    )
    reputation_status = _worst_status(bounce_status, complaint_status)

    return {
        "campaign_count": campaign_count,
        "sent_count": sent_count,
        "bounce_count": bounce_count,
        "complaint_count": complaint_count,
        "bounce_rate": bounce_rate,
        "complaint_rate": complaint_rate,
        "bounce_status": bounce_status,
        "complaint_status": complaint_status,
        "reputation_status": reputation_status,
        "thresholds": {
            "bounce_warning_rate": BOUNCE_WARNING_RATE,
            "bounce_critical_rate": BOUNCE_CRITICAL_RATE,
            "complaint_warning_rate": COMPLAINT_WARNING_RATE,
            "complaint_critical_rate": COMPLAINT_CRITICAL_RATE,
        },
        "alerts": _build_alerts(bounce_rate, complaint_rate),
    }


async def list_deliverability_events_service(
    db: AsyncSession,
    user_id: str,
    limit: int = 25,
):
    normalized_limit = max(1, min(limit, 100))
    events = await db.scalars(
        select(EmailEvent)
        .where(
            EmailEvent.user_id == user_id,
            EmailEvent.event_type.in_({EMAIL_EVENT_BOUNCE, EMAIL_EVENT_COMPLAINT}),
        )
        .order_by(EmailEvent.occurred_at.desc(), EmailEvent.created_at.desc())
        .limit(normalized_limit)
    )

    return [
        {
            "id": str(event.id),
            "event_type": event.event_type,
            "email": event.email,
            "campaign_id": str(event.campaign_id) if event.campaign_id else None,
            "recipient_id": str(event.recipient_id) if event.recipient_id else None,
            "attempt_id": event.attempt_id,
            "ses_message_id": event.ses_message_id,
            "sns_message_id": event.sns_message_id,
            "bounce_type": event.bounce_type,
            "bounce_subtype": event.bounce_subtype,
            "complaint_feedback_type": event.complaint_feedback_type,
            "diagnostic_code": event.diagnostic_code,
            "occurred_at": _format_datetime(event.occurred_at),
            "created_at": _format_datetime(event.created_at),
        }
        for event in events.all()
    ]
