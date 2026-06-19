from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.configs.config import (
    FINAL_RECIPIENT_STATUSES,
    RECIPIENT_CANCELLED,
    RECIPIENT_FAILED_PERMANENT,
    RECIPIENT_FAILED_TRANSIENT,
    RECIPIENT_QUEUED,
    RECIPIENT_SENDING,
    RECIPIENT_SENT,
    RECIPIENT_SUPPRESSED,
    RETRYABLE_OR_ACTIVE_RECIPIENT_STATUSES,
)
from src.models.models import Campaign, CampaignRecipient, Contact, utc_now


def _normalize_html_body(html_body: str | None) -> str | None:
    if html_body is None:
        return None

    stripped_html_body = html_body.strip()
    return stripped_html_body or None


def _normalize_optional_text(value: str | None) -> str | None:
    if value is None:
        return None

    stripped_value = value.strip()
    return stripped_value or None


def _normalize_content_type(content_type: str | None) -> str:
    return content_type or "plain"


def _normalize_send_rate(send_rate_per_second: float | None) -> float | None:
    if send_rate_per_second is None:
        return None
    return float(send_rate_per_second)


def _normalize_campaign_tags(tags: list[str] | str | None) -> list[str]:
    if tags is None:
        return []

    if isinstance(tags, str):
        raw_tags = tags.split(",")
    else:
        raw_tags = tags

    normalized_tags = []
    seen_tags = set()
    for tag in raw_tags:
        normalized_tag = str(tag).strip()
        if not normalized_tag:
            continue

        lookup_key = normalized_tag.lower()
        if lookup_key in seen_tags:
            continue

        seen_tags.add(lookup_key)
        normalized_tags.append(normalized_tag)

    return normalized_tags


def _normalize_recipient_inputs(recipients: list | None):
    normalized_recipients = []
    seen_emails = set()

    for recipient in recipients or []:
        if isinstance(recipient, str):
            email = recipient.strip()
            variables = {}
        else:
            email = (recipient.get("email") or "").strip()
            variables = recipient.get("variables") or {}

        if not email:
            continue

        normalized_email = email.lower()
        if normalized_email in seen_emails:
            continue

        seen_emails.add(normalized_email)
        normalized_recipients.append({
            "email": email,
            "variables": variables,
        })

    return normalized_recipients


async def _get_contacts_by_email(db: AsyncSession, user_id: str, emails: list[str]):
    normalized_emails = [email.strip().lower() for email in emails if email and email.strip()]
    if not normalized_emails:
        return {}

    result = await db.scalars(
        select(Contact).where(
            Contact.user_id == user_id,
            func.lower(Contact.email).in_(normalized_emails),
        )
    )

    return {contact.email.strip().lower(): contact for contact in result.all()}


async def _build_campaign_recipients(db: AsyncSession, user_id: str, recipients: list):
    normalized_recipients = _normalize_recipient_inputs(recipients)
    emails = [recipient["email"] for recipient in normalized_recipients]
    contacts_by_email = await _get_contacts_by_email(db, user_id, emails)
    campaign_recipients = []

    for recipient in normalized_recipients:
        email = recipient["email"]
        normalized_email = email.strip().lower()
        contact = contacts_by_email.get(normalized_email)
        campaign_recipients.append(
            CampaignRecipient(
                email=email,
                contact_id=contact.id if contact else None,
                status=RECIPIENT_QUEUED,
                variables=recipient["variables"] or None,
            )
        )

    return campaign_recipients


async def _replace_campaign_recipients(
    db: AsyncSession,
    campaign: Campaign,
    user_id: str,
    recipients: list,
):
    campaign.recipients = []
    await db.flush()
    campaign.recipients = await _build_campaign_recipients(db, user_id, recipients)


def _format_datetime(value: datetime | None) -> str | None:
    return value.isoformat() if value else None


def serialize_campaign(campaign: Campaign):
    return {
        "id": str(campaign.id),
        "user_id": campaign.user_id,
        "task_id": campaign.task_id or None,
        "subject": campaign.subject,
        "body": campaign.body,
        "from_email": campaign.from_email,
        "from_name": campaign.from_name,
        "reply_to_email": campaign.reply_to_email,
        "html_body": campaign.html_body,
        "content_type": campaign.content_type or "plain",
        "queued_recipients": campaign.queued_recipients,
        "recipients": [recipient.email for recipient in campaign.recipients],
        "status": campaign.status,
        "created_at": _format_datetime(campaign.created_at),
        "batch_size": campaign.batch_size,
        "per_batch_delay": campaign.per_batch_delay,
        "send_rate_per_second": campaign.send_rate_per_second,
        "track_opens": campaign.track_opens if campaign.track_opens is not None else True,
        "track_clicks": campaign.track_clicks if campaign.track_clicks is not None else True,
        "category": campaign.category,
        "tags": campaign.tags or [],
        "sent_count": campaign.sent_count,
        "opened_count": campaign.opened_count,
        "clicked_count": campaign.clicked_count,
        "updated_at": _format_datetime(campaign.updated_at),
        "sent_at": _format_datetime(campaign.sent_at),
        "scheduled_at": _format_datetime(campaign.scheduled_at),
    }


def _parse_campaign_id(campaign_id: str):
    try:
        return UUID(campaign_id)
    except ValueError:
        return None


def _select_recipient_for_result(recipients: list[CampaignRecipient]):
    return next(
        (recipient for recipient in recipients if recipient.status in RETRYABLE_OR_ACTIVE_RECIPIENT_STATUSES),
        None,
    )


def _apply_recipient_results(campaign: Campaign, results: list[dict], now: datetime):
    recipients_by_email = {}
    for recipient in campaign.recipients:
        recipients_by_email.setdefault(recipient.email, []).append(recipient)

    for result in results:
        email = result.get("email")
        recipient = _select_recipient_for_result(recipients_by_email.get(email) or [])
        if recipient is None:
            continue

        if result.get("status") == "sent":
            recipient.status = RECIPIENT_SENT
            recipient.sent_at = now
            recipient.error_message = None
        else:
            recipient.status = result.get("status") or RECIPIENT_FAILED_TRANSIENT
            recipient.sent_at = None
            recipient.error_message = result.get("error") or result.get("error_message") or "Failed to send"

async def claim_campaign_for_sending_service(
    db: AsyncSession,
    user_id: str,
    campaign_id: str,
    task_id: str,
):
    parsed_campaign_id = _parse_campaign_id(campaign_id)
    if not parsed_campaign_id:
        return None

    result = await db.execute(
        update(Campaign)
        .where(
            Campaign.id == parsed_campaign_id,
            Campaign.user_id == user_id,
            Campaign.status.in_({"Draft", "Ready"}),
        )
        .values(
            status="Sending",
            task_id=task_id,
            sent_at=None,
            sent_count=0,
        )
    )

    if result.rowcount != 1:
        await db.rollback()
        return None

    await db.commit()
    campaign = await get_campaign_service(db, user_id, campaign_id)
    return serialize_campaign(campaign) if campaign else None


async def mark_campaign_sending_service(
    db: AsyncSession,
    user_id: str,
    campaign_id: str,
    task_id: str,
):
    if hasattr(db, "execute"):
        return await claim_campaign_for_sending_service(db, user_id, campaign_id, task_id)

    campaign = await get_campaign_service(db, user_id, campaign_id)
    if not campaign or campaign.status not in {"Draft", "Ready"}:
        return None

    campaign.status = "Sending"
    campaign.task_id = task_id
    campaign.sent_at = None
    campaign.sent_count = 0
    await db.commit()
    return serialize_campaign(campaign)


async def schedule_campaign_service(
    db: AsyncSession,
    user_id: str,
    campaign_id: str,
    task_id: str,
    scheduled_at: datetime,
):
    parsed_campaign_id = _parse_campaign_id(campaign_id)
    if not parsed_campaign_id:
        return None

    result = await db.execute(
        update(Campaign)
        .where(
            Campaign.id == parsed_campaign_id,
            Campaign.user_id == user_id,
            Campaign.status.in_({"Draft", "Ready", "Scheduled"}),
        )
        .values(
            status="Scheduled",
            task_id=task_id,
            scheduled_at=scheduled_at,
            sent_at=None,
            sent_count=0,
        )
    )

    if result.rowcount != 1:
        await db.rollback()
        return None

    await db.commit()
    campaign = await get_campaign_service(db, user_id, campaign_id)
    return serialize_campaign(campaign) if campaign else None


async def get_current_draft_service(db: AsyncSession, user_id: str):
    campaign = await db.scalar(
        select(Campaign)
        .options(selectinload(Campaign.recipients))
        .where(Campaign.user_id == user_id, Campaign.status == "Draft")
        .order_by(Campaign.updated_at.desc())
    )
    return serialize_campaign(campaign) if campaign else None


async def save_current_draft_service(
    db: AsyncSession,
    user_id: str,
    subject: str,
    body: str,
    from_email: str,
    from_name: str | None = None,
    reply_to_email: str | None = None,
    html_body: str | None = None,
    content_type: str | None = "plain",
    recipients: list[str] = None,
    batch_size: int = None,
    per_batch_delay: float = None,
    send_rate_per_second: float = None,
    track_opens: bool = True,
    track_clicks: bool = True,
    category: str | None = None,
    tags: list[str] | str | None = None,
):
    existing_draft = await db.scalar(
        select(Campaign)
        .options(selectinload(Campaign.recipients))
        .where(Campaign.user_id == user_id, Campaign.status == "Draft")
        .order_by(Campaign.updated_at.desc())
    )

    normalized_recipients = _normalize_recipient_inputs(recipients)

    if existing_draft:
        existing_draft.subject = subject
        existing_draft.body = body
        existing_draft.from_email = from_email
        existing_draft.from_name = _normalize_optional_text(from_name)
        existing_draft.reply_to_email = _normalize_optional_text(reply_to_email)
        existing_draft.html_body = _normalize_html_body(html_body)
        existing_draft.content_type = _normalize_content_type(content_type)
        existing_draft.batch_size = batch_size
        existing_draft.per_batch_delay = per_batch_delay
        existing_draft.send_rate_per_second = _normalize_send_rate(send_rate_per_second)
        existing_draft.track_opens = track_opens
        existing_draft.track_clicks = track_clicks
        existing_draft.category = _normalize_optional_text(category)
        existing_draft.tags = _normalize_campaign_tags(tags)
        existing_draft.queued_recipients = len(normalized_recipients)
        await _replace_campaign_recipients(db, existing_draft, user_id, normalized_recipients)
        existing_draft.task_id = None
        existing_draft.sent_at = None
        existing_draft.scheduled_at = None
    else:
        existing_draft = Campaign(
            id=uuid4(),
            user_id=user_id,
            task_id=None,
            subject=subject,
            body=body,
            from_email=from_email,
            from_name=_normalize_optional_text(from_name),
            reply_to_email=_normalize_optional_text(reply_to_email),
            html_body=_normalize_html_body(html_body),
            content_type=_normalize_content_type(content_type),
            queued_recipients=len(normalized_recipients),
            status="Draft",
            batch_size=batch_size,
            per_batch_delay=per_batch_delay,
            send_rate_per_second=_normalize_send_rate(send_rate_per_second),
            track_opens=track_opens,
            track_clicks=track_clicks,
            category=_normalize_optional_text(category),
            tags=_normalize_campaign_tags(tags),
            sent_at=None,
            scheduled_at=None,
        )
        existing_draft.recipients = await _build_campaign_recipients(db, user_id, normalized_recipients)
        db.add(existing_draft)

    await db.commit()
    await db.refresh(existing_draft)
    draft = await get_campaign_service(db, user_id, str(existing_draft.id))
    return serialize_campaign(draft) if draft else None


async def delete_current_draft_service(db: AsyncSession, user_id: str) -> bool:
    result = await db.execute(
        delete(Campaign).where(Campaign.user_id == user_id, Campaign.status == "Draft")
    )
    await db.commit()
    return bool(result.rowcount)


async def delete_campaign_service(db: AsyncSession, user_id: str, campaign_id: str):
    parsed_campaign_id = _parse_campaign_id(campaign_id)
    if not parsed_campaign_id:
        return "not_found"

    campaign = await db.scalar(
        select(Campaign).where(
            Campaign.id == parsed_campaign_id,
            Campaign.user_id == user_id,
        )
    )
    if not campaign:
        return "not_found"

    if campaign.status in {"Sending", "Partially Sent"}:
        return "active"

    await db.delete(campaign)
    await db.commit()
    return "deleted"


async def pause_campaign_service(db: AsyncSession, user_id: str, campaign_id: str):
    parsed_campaign_id = _parse_campaign_id(campaign_id)
    if not parsed_campaign_id:
        return None

    result = await db.execute(
        update(Campaign)
        .where(
            Campaign.id == parsed_campaign_id,
            Campaign.user_id == user_id,
            Campaign.status == "Sending",
        )
        .values(status="Paused")
    )
    if result.rowcount != 1:
        await db.rollback()
        return None

    await db.commit()
    campaign = await get_campaign_service(db, user_id, campaign_id)
    return serialize_campaign(campaign) if campaign else None


async def resume_campaign_service(db: AsyncSession, user_id: str, campaign_id: str, task_id: str):
    parsed_campaign_id = _parse_campaign_id(campaign_id)
    if not parsed_campaign_id:
        return None

    result = await db.execute(
        update(Campaign)
        .where(
            Campaign.id == parsed_campaign_id,
            Campaign.user_id == user_id,
            Campaign.status == "Paused",
        )
        .values(status="Sending", task_id=task_id)
    )
    if result.rowcount != 1:
        await db.rollback()
        return None

    await db.commit()
    campaign = await get_campaign_service(db, user_id, campaign_id)
    return serialize_campaign(campaign) if campaign else None


async def cancel_campaign_service(db: AsyncSession, user_id: str, campaign_id: str):
    parsed_campaign_id = _parse_campaign_id(campaign_id)
    if not parsed_campaign_id:
        return None

    campaign = await db.scalar(
        select(Campaign)
        .options(selectinload(Campaign.recipients))
        .where(Campaign.id == parsed_campaign_id, Campaign.user_id == user_id)
    )
    if not campaign:
        return None

    if campaign.status in {"Sent", "Failed", "Cancelled"}:
        return serialize_campaign(campaign)

    now = utc_now()
    await db.execute(
        update(CampaignRecipient)
        .where(
            CampaignRecipient.campaign_id == parsed_campaign_id,
            CampaignRecipient.status.in_({
                RECIPIENT_QUEUED,
                RECIPIENT_SENDING,
                RECIPIENT_FAILED_TRANSIENT,
            }),
        )
        .values(
            status=RECIPIENT_CANCELLED,
            sent_at=None,
            sending_started_at=None,
            attempt_id=None,
            error_message="Campaign cancelled",
        )
    )
    campaign.status = "Cancelled"
    campaign.scheduled_at = None
    campaign.sent_at = campaign.sent_at or now
    _refresh_campaign_delivery_summary(campaign, now)
    await db.commit()

    updated_campaign = await get_campaign_service(db, user_id, campaign_id)
    return serialize_campaign(updated_campaign) if updated_campaign else None


async def save_campaign_from_draft_service(db: AsyncSession, user_id: str):
    draft = await db.scalar(
        select(Campaign)
        .options(selectinload(Campaign.recipients))
        .where(Campaign.user_id == user_id, Campaign.status == "Draft")
        .order_by(Campaign.updated_at.desc())
    )
    if not draft:
        return None

    draft.status = "Ready"
    draft.task_id = None
    draft.sent_at = None
    draft.scheduled_at = None
    await db.commit()
    campaign = await get_campaign_service(db, user_id, str(draft.id))
    return serialize_campaign(campaign) if campaign else None

def _refresh_campaign_delivery_summary(campaign: Campaign, now: datetime):
    recipient_statuses = [recipient.status for recipient in campaign.recipients]
    sent_count = sum(1 for status in recipient_statuses if status == RECIPIENT_SENT)

    campaign.sent_count = sent_count
    campaign.queued_recipients = len(campaign.recipients)
    campaign.opened_count = campaign.opened_count or 0
    campaign.clicked_count = campaign.clicked_count or 0

    if campaign.status in {"Paused", "Cancelled"}:
        return

    if not recipient_statuses:
        campaign.status = "Failed"
        return

    if all(status == RECIPIENT_SENT for status in recipient_statuses):
        campaign.status = "Sent"
        campaign.sent_at = campaign.sent_at or now
    elif any(status in RETRYABLE_OR_ACTIVE_RECIPIENT_STATUSES for status in recipient_statuses):
        campaign.status = "Sending"
    elif sent_count == 0 and all(status in FINAL_RECIPIENT_STATUSES or status == "failed" for status in recipient_statuses):
        campaign.status = "Failed"
    else:
        campaign.status = "Partially Sent"
        campaign.sent_at = campaign.sent_at or now


async def add_campaign_service(
    db: AsyncSession,
    user_id: str,
    task_id: str | None,
    subject: str,
    body: str,
    from_email: str,
    queued_recipients: int,
    html_body: str | None = None,
    content_type: str | None = "plain",
    recipients: list[str] = None,
    status: str = "Sent",
    batch_size: int = None,
    per_batch_delay: float = None,
    from_name: str | None = None,
    reply_to_email: str | None = None,
    send_rate_per_second: float = None,
    track_opens: bool = True,
    track_clicks: bool = True,
    category: str | None = None,
    tags: list[str] | str | None = None,
):
    if isinstance(html_body, list) and recipients is None:
        recipients = html_body
        status = content_type or status
        html_body = None
        content_type = "plain"

    now = utc_now()
    normalized_recipients = _normalize_recipient_inputs(recipients)
    recipient_count = len(normalized_recipients)
    campaign = Campaign(
        id=uuid4(),
        user_id=user_id,
        task_id=task_id or None,
        subject=subject,
        body=body,
        from_email=from_email,
        from_name=_normalize_optional_text(from_name),
        reply_to_email=_normalize_optional_text(reply_to_email),
        html_body=_normalize_html_body(html_body),
        content_type=_normalize_content_type(content_type),
        queued_recipients=recipient_count,
        status=status,
        batch_size=batch_size,
        per_batch_delay=per_batch_delay,
        send_rate_per_second=_normalize_send_rate(send_rate_per_second),
        track_opens=track_opens,
        track_clicks=track_clicks,
        category=_normalize_optional_text(category),
        tags=_normalize_campaign_tags(tags),
        sent_at=now if status == "Sent" else None,
        scheduled_at=None,
    )
    campaign.recipients = await _build_campaign_recipients(db, user_id, normalized_recipients)

    db.add(campaign)
    await db.commit()

    saved_campaign = await get_campaign_service(db, user_id, str(campaign.id))
    return serialize_campaign(saved_campaign)


async def get_campaign_service(db: AsyncSession, user_id: str, campaign_id: str):
    parsed_campaign_id = _parse_campaign_id(campaign_id)
    if not parsed_campaign_id:
        return None

    return await db.scalar(
        select(Campaign)
        .options(selectinload(Campaign.recipients))
        .where(Campaign.user_id == user_id, Campaign.id == parsed_campaign_id)
    )


async def update_campaign_service(db: AsyncSession, user_id: str, campaign_id: str, **updates):
    campaign = await get_campaign_service(db, user_id, campaign_id)
    if not campaign:
        return None

    for key, value in updates.items():
        if key == "recipients":
            normalized_recipients = _normalize_recipient_inputs(value)
            await _replace_campaign_recipients(db, campaign, user_id, normalized_recipients)
            campaign.queued_recipients = len(normalized_recipients)
        elif hasattr(campaign, key):
            if key == "task_id":
                setattr(campaign, key, value or None)
            elif key in {"from_name", "reply_to_email"}:
                setattr(campaign, key, _normalize_optional_text(value))
            elif key == "send_rate_per_second":
                setattr(campaign, key, _normalize_send_rate(value))
            elif key == "category":
                setattr(campaign, key, _normalize_optional_text(value))
            elif key == "tags":
                setattr(campaign, key, _normalize_campaign_tags(value))
            else:
                setattr(campaign, key, value)

    if updates.get("status") == "Sent" and not campaign.sent_at:
        campaign.sent_at = utc_now()

    await db.commit()

    updated_campaign = await get_campaign_service(db, user_id, campaign_id)
    return serialize_campaign(updated_campaign)


def sync_record_campaign_send_results_service(
    db,
    campaign_id: str,
    results: list[dict],
    user_id: str = None,
):
    parsed_campaign_id = _parse_campaign_id(campaign_id)
    if not parsed_campaign_id:
        return None

    query = (
        select(Campaign)
        .options(selectinload(Campaign.recipients))
        .where(Campaign.id == parsed_campaign_id)
    )
    if user_id:
        query = query.where(Campaign.user_id == user_id)

    campaign = db.scalar(query)
    if not campaign:
        return None

    now = utc_now()
    _apply_recipient_results(campaign, results, now)
    _refresh_campaign_delivery_summary(campaign, now)

    db.commit()

    updated_campaign = db.scalar(
        select(Campaign)
        .options(selectinload(Campaign.recipients))
        .where(Campaign.id == parsed_campaign_id)
    )
    return serialize_campaign(updated_campaign)

async def record_campaign_send_results_service(
    db: AsyncSession,
    campaign_id: str,
    results: list[dict],
    user_id: str = None,
):
    parsed_campaign_id = _parse_campaign_id(campaign_id)
    if not parsed_campaign_id:
        return None

    query = (
        select(Campaign)
        .options(selectinload(Campaign.recipients))
        .where(Campaign.id == parsed_campaign_id)
    )
    if user_id:
        query = query.where(Campaign.user_id == user_id)

    campaign = await db.scalar(query)
    if not campaign:
        return None

    now = utc_now()
    _apply_recipient_results(campaign, results, now)
    _refresh_campaign_delivery_summary(campaign, now)

    await db.commit()

    updated_campaign = await db.scalar(
        select(Campaign)
        .options(selectinload(Campaign.recipients))
        .where(Campaign.id == parsed_campaign_id)
    )
    return serialize_campaign(updated_campaign)


async def list_campaigns_service(db: AsyncSession, user_id: str):
    result = await db.scalars(
        select(Campaign)
        .options(selectinload(Campaign.recipients))
        .where(Campaign.user_id == user_id, Campaign.status != "Draft")
        .order_by(Campaign.created_at.desc())
    )

    return [serialize_campaign(campaign) for campaign in result.all()]
