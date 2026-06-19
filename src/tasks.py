import time
import base64
import smtplib
from datetime import timedelta
from uuid import UUID, uuid4
from celery import Celery
from celery.utils.log import get_task_logger
from redis import Redis, RedisError
from sqlalchemy import func, or_, select, update
from sqlalchemy.orm import selectinload

from src.integrations.ses_service import get_quota_per_email_delay
from src.configs.config import (
    CAMPAIGN_ACTIVE_WORKER_TTL_SECONDS,
    BULK_CAMPAIGN_THRESHOLD,
    CAMPAIGN_DEFAULT_QUEUE,
    CAMPAIGN_MAX_ACTIVE_WORKERS,
    CAMPAIGN_WORKER_BATCH_SIZE,
    CAMPAIGN_WORKER_MAX_BATCHES,
    CELERY_BACKEND,
    DEFAULT_BATCH_SIZE,
    DEFAULT_PER_BATCH_DELAY,
    RABBITMQ_URL,
    RECIPIENT_FAILED_PERMANENT,
    RECIPIENT_FAILED_TRANSIENT,
    RECIPIENT_CANCELLED,
    RECIPIENT_SUPPRESSED,
    RECIPIENT_QUEUED,
    RECIPIENT_SENDING,
    RECIPIENT_SENT,
    SENDING_TIMEOUT_SECONDS,
    MAX_RECIPIENT_SEND_ATTEMPTS,
    REDIS_URL,
    SEND_RATE_LIMIT_PER_SECOND,
    SEND_RATE_LIMIT_REDIS_TTL_SECONDS,
    SES_PREFLIGHT_ENABLED,
    SES_CONFIGURATION_SET,
)
from src.database.sqlalchemy import sync_session_factory
from src.models.models import Campaign, CampaignRecipient, utc_now
from src.services.campaigns_service import _refresh_campaign_delivery_summary
from src.services.email_content_service import build_email_message, validate_rendered_email_content
from src.services.email_template_service import render_email_template
from src.services.tracking_service import instrument_email_tracking
from src.services.suppression_service import (
    get_active_suppression_map,
    sync_ses_suppression_list_sync_service,
)
from src.services.ses_notification_service import process_ses_notification
from src.services.smtp_connection_service import open_smtp_connection


logger = get_task_logger(__name__)
_sync_redis_client = None
_per_email_delay_cache = {
    "expires_at": 0,
    "value": None,
}

celery_app = Celery('tasks', broker=RABBITMQ_URL, backend=CELERY_BACKEND)
try:
    celery_app.config_from_object('src.configs.celeryconfig')
except Exception:
    pass


def _get_sync_redis():
    global _sync_redis_client
    if _sync_redis_client is None:
        _sync_redis_client = Redis.from_url(REDIS_URL, decode_responses=True)
    return _sync_redis_client


def _safe_rate_limit_key_part(value: str | None):
    return (value or "unknown").strip().lower().replace(" ", "_")


def _configured_per_email_delay(send_rate_per_second: float | None = None):
    if send_rate_per_second and send_rate_per_second > 0:
        return 1 / send_rate_per_second
    if SEND_RATE_LIMIT_PER_SECOND and SEND_RATE_LIMIT_PER_SECOND > 0:
        return 1 / SEND_RATE_LIMIT_PER_SECOND
    if not SES_PREFLIGHT_ENABLED:
        return None

    now = time.time()
    if _per_email_delay_cache["expires_at"] > now:
        return _per_email_delay_cache["value"]

    value = get_quota_per_email_delay()
    _per_email_delay_cache["value"] = value
    _per_email_delay_cache["expires_at"] = now + 60
    return value


def _wait_for_send_rate_limit(user_id: str, from_email: str, send_rate_per_second: float | None = None):
    per_email_delay = _configured_per_email_delay(send_rate_per_second)
    if not per_email_delay or per_email_delay <= 0:
        return

    key = (
        "send-rate:"
        f"user:{_safe_rate_limit_key_part(user_id)}:"
        f"from:{_safe_rate_limit_key_part(from_email)}"
    )
    now_ms = int(time.time() * 1000)
    interval_ms = max(1, int(per_email_delay * 1000))
    ttl_ms = max(SEND_RATE_LIMIT_REDIS_TTL_SECONDS * 1000, interval_ms * 2)

    script = """
    local key = KEYS[1]
    local now_ms = tonumber(ARGV[1])
    local interval_ms = tonumber(ARGV[2])
    local ttl_ms = tonumber(ARGV[3])
    local last_ms = tonumber(redis.call('GET', key) or '0')
    local next_ms = math.max(now_ms, last_ms) + interval_ms
    redis.call('SET', key, next_ms, 'PX', ttl_ms)
    return next_ms - now_ms
    """

    try:
        wait_ms = int(_get_sync_redis().eval(script, 1, key, now_ms, interval_ms, ttl_ms))
    except RedisError:
        logger.exception("Redis send rate limiter unavailable; falling back to local delay")
        time.sleep(per_email_delay)
        return

    if wait_ms > 0:
        time.sleep(wait_ms / 1000)


def _campaign_active_workers_key(campaign_id: str):
    return f"campaign:{campaign_id}:active-workers"


def _acquire_campaign_worker_slot(campaign_id: str) -> bool:
    key = _campaign_active_workers_key(campaign_id)
    try:
        redis_client = _get_sync_redis()
        active_workers = redis_client.incr(key)
        redis_client.expire(key, CAMPAIGN_ACTIVE_WORKER_TTL_SECONDS)
        if active_workers > CAMPAIGN_MAX_ACTIVE_WORKERS:
            remaining = redis_client.decr(key)
            if remaining <= 0:
                redis_client.delete(key)
            return False
        return True
    except RedisError:
        logger.exception("Redis worker accounting unavailable; allowing campaign worker to continue")
        return True


def _release_campaign_worker_slot(campaign_id: str):
    key = _campaign_active_workers_key(campaign_id)
    try:
        remaining = _get_sync_redis().decr(key)
        if remaining <= 0:
            _get_sync_redis().delete(key)
    except RedisError:
        logger.exception("Redis worker accounting release failed")

def _format_ses_message_tags(tags: dict[str, str]):
    return ", ".join(f"{key}={value}" for key, value in tags.items() if value)


def _build_template_context(campaign: Campaign, recipient: CampaignRecipient):
    contact = recipient.contact

    return {
        "campaign": {
            "id": str(campaign.id),
            "subject": campaign.subject,
        },
        "contact": {
            "id": str(contact.id) if contact else None,
            "email": recipient.email,
            "name": contact.name if contact else "",
        },
        "variables": recipient.variables or {},
    }


def _send_single(
    smtp: smtplib.SMTP,
    to: str,
    subject: str,
    body: str,
    from_email: str,
    from_name: str | None = None,
    reply_to_email: str | None = None,
    html_body: str | None = None,
    content_type: str = "plain",
    attachments=None,
    ses_tags: dict[str, str] = None,
    user_id: str = None,
):
    msg = build_email_message(
        to=to,
        subject=subject,
        body=body,
        from_email=from_email,
        from_name=from_name,
        reply_to_email=reply_to_email,
        html_body=html_body,
        content_type=content_type,
        user_id=user_id,
    )

    if SES_CONFIGURATION_SET:
        msg["X-SES-CONFIGURATION-SET"] = SES_CONFIGURATION_SET

    if ses_tags:
        msg["X-SES-MESSAGE-TAGS"] = _format_ses_message_tags(ses_tags)
    
    if attachments:
        for a in attachments:
            maintype, subtype = a['mime_type'].split('/', 1)
            msg.add_attachment(a['content'], maintype=maintype, subtype=subtype, filename=a['filename'])
    smtp.send_message(msg)


def _decode_attachments(attachments_b64=None):
    if not attachments_b64:
        return None

    attachments = []
    for attachment in attachments_b64:
        content = base64.b64decode(attachment['content_b64'])
        attachments.append({
            'filename': attachment['filename'],
            'content': content,
            'mime_type': attachment.get('mime_type', 'application/octet-stream')
        })
    return attachments


def _load_campaign_for_sending(db, campaign_id: str, user_id: str):
    return db.scalar(
        select(Campaign)
        .options(selectinload(Campaign.recipients).selectinload(CampaignRecipient.contact))
        .where(Campaign.id == campaign_id, Campaign.user_id == user_id) 
    )


def _parse_uuid(value: str | UUID | None):
    if isinstance(value, UUID):
        return value
    try:
        return UUID(str(value))
    except (TypeError, ValueError):
        return None


def _stale_sending_cutoff():
    return utc_now() - timedelta(seconds=SENDING_TIMEOUT_SECONDS)


def _stale_sending_filter(cutoff):
    return (
        CampaignRecipient.status == RECIPIENT_SENDING,
        or_(
            CampaignRecipient.sending_started_at.is_(None),
            CampaignRecipient.sending_started_at < cutoff,
        ),
    )


def _mark_stale_sending_as_transient(db, *where_clauses) -> int:
    result = db.execute(
        update(CampaignRecipient)
        .where(*where_clauses)
        .values(
            status=RECIPIENT_FAILED_TRANSIENT,
            sent_at=None,
            sending_started_at=None,
            error_message="Sending attempt timed out",
            attempt_id=None,
        )
    )
    db.commit()
    return result.rowcount or 0


def _load_campaign_by_id(db, campaign_id):
    return db.scalar(
        select(Campaign)
        .options(selectinload(Campaign.recipients))
        .where(Campaign.id == campaign_id)
    )


def _reset_stale_sending_recipients(db, campaign: Campaign) -> int:
    cutoff = _stale_sending_cutoff()
    return _mark_stale_sending_as_transient(
        db,
        CampaignRecipient.campaign_id == campaign.id,
        *_stale_sending_filter(cutoff),
    )


@celery_app.task(name="src.tasks.recover_stale_sending_recipients")
def recover_stale_sending_recipients():
    cutoff = _stale_sending_cutoff()

    with sync_session_factory() as db:
        affected_campaign_ids = [
            row[0]
            for row in db.execute(
                select(CampaignRecipient.campaign_id)
                .where(*_stale_sending_filter(cutoff))
                .distinct()
            )
        ]

        recovered = _mark_stale_sending_as_transient(db, *_stale_sending_filter(cutoff))

        now = utc_now()
        for campaign_id in affected_campaign_ids:
            campaign = _load_campaign_by_id(db, campaign_id)
            if campaign:
                _refresh_campaign_delivery_summary(campaign, now)

        db.commit()

    return {
        "recovered_recipients": recovered,
        "affected_campaigns": len(affected_campaign_ids),
    }


@celery_app.task(name="src.tasks.sync_ses_suppression_list")
def sync_ses_suppression_list():
    with sync_session_factory() as db:
        return sync_ses_suppression_list_sync_service(db)


@celery_app.task(name="src.tasks.process_ses_notification")
def process_ses_notification_task(ses_payload: dict, sns_message_id: str):
    with sync_session_factory() as db:
        return process_ses_notification(db, ses_payload, sns_message_id)


def _claim_recipient(db, recipient: CampaignRecipient, current_attempt_id: str, current_batch_id: str) -> bool:
    now = utc_now()

    result = db.execute(
        update(CampaignRecipient)
        .where(
            CampaignRecipient.id == recipient.id,
            CampaignRecipient.status.in_({RECIPIENT_QUEUED, RECIPIENT_FAILED_TRANSIENT}),
            CampaignRecipient.attempt_count < MAX_RECIPIENT_SEND_ATTEMPTS
        )
        .values(
            status=RECIPIENT_SENDING,
            error_message=None,
            sending_started_at=now,
            attempt_id=current_attempt_id,
            batch_id=current_batch_id,
            attempt_count=CampaignRecipient.attempt_count + 1,
        )
    )
    db.commit()

    if result.rowcount != 1:
        return False

    recipient.attempt_count = (recipient.attempt_count or 0) + 1
    recipient.status = RECIPIENT_SENDING
    recipient.error_message = None
    recipient.sending_started_at = now
    recipient.attempt_id = current_attempt_id
    recipient.batch_id = current_batch_id
    return True


def _claim_recipient_batch(
    db,
    campaign_id: str,
    batch_size: int,
    current_batch_id: str,
) -> list[CampaignRecipient]:
    parsed_campaign_id = _parse_uuid(campaign_id)
    if not parsed_campaign_id:
        return []

    now = utc_now()
    recipients = db.scalars(
        select(CampaignRecipient)
        .options(selectinload(CampaignRecipient.contact))
        .where(
            CampaignRecipient.campaign_id == parsed_campaign_id,
            CampaignRecipient.status.in_({RECIPIENT_QUEUED, RECIPIENT_FAILED_TRANSIENT}),
            CampaignRecipient.attempt_count < MAX_RECIPIENT_SEND_ATTEMPTS,
        )
        .order_by(CampaignRecipient.created_at, CampaignRecipient.id)
        .limit(batch_size)
        .with_for_update(skip_locked=True)
    ).all()

    for recipient in recipients:
        recipient.status = RECIPIENT_SENDING
        recipient.error_message = None
        recipient.sending_started_at = now
        recipient.attempt_id = str(uuid4())
        recipient.batch_id = current_batch_id
        recipient.attempt_count = (recipient.attempt_count or 0) + 1

    db.commit()
    return recipients


def _mark_exhausted_transient_recipients_failed(db, campaign_id: str) -> int:
    parsed_campaign_id = _parse_uuid(campaign_id)
    if not parsed_campaign_id:
        return 0

    result = db.execute(
        update(CampaignRecipient)
        .where(
            CampaignRecipient.campaign_id == parsed_campaign_id,
            CampaignRecipient.status == RECIPIENT_FAILED_TRANSIENT,
            CampaignRecipient.attempt_count >= MAX_RECIPIENT_SEND_ATTEMPTS,
        )
        .values(
            status=RECIPIENT_FAILED_PERMANENT,
            sent_at=None,
            sending_started_at=None,
            attempt_id=None,
            error_message="Max attempts exhausted",
        )
    )
    db.commit()
    return result.rowcount or 0


def _refresh_campaign_delivery_summary_from_db(db, campaign_id: str):
    parsed_campaign_id = _parse_uuid(campaign_id)
    if not parsed_campaign_id:
        return None

    status_counts = dict(
        db.execute(
            select(CampaignRecipient.status, func.count(CampaignRecipient.id))
            .where(CampaignRecipient.campaign_id == parsed_campaign_id)
            .group_by(CampaignRecipient.status)
        ).all()
    )
    total = sum(status_counts.values())
    sent_count = status_counts.get(RECIPIENT_SENT, 0)
    active_count = sum(
        status_counts.get(status, 0)
        for status in {RECIPIENT_QUEUED, RECIPIENT_SENDING, RECIPIENT_FAILED_TRANSIENT}
    )
    now = utc_now()

    campaign = db.get(Campaign, parsed_campaign_id)
    if not campaign:
        return None

    campaign.sent_count = sent_count
    campaign.queued_recipients = total
    campaign.opened_count = campaign.opened_count or 0
    campaign.clicked_count = campaign.clicked_count or 0

    if campaign.status in {"Paused", "Cancelled"}:
        db.commit()
        return campaign

    if total == 0:
        campaign.status = "Failed"
    elif active_count:
        campaign.status = "Sending"
    elif sent_count == total:
        campaign.status = "Sent"
        campaign.sent_at = campaign.sent_at or now
    elif sent_count == 0:
        campaign.status = "Failed"
    else:
        campaign.status = "Partially Sent"
        campaign.sent_at = campaign.sent_at or now

    db.commit()
    return campaign


def _record_recipient_results_bulk(db, campaign_id: str, results: list[dict]) -> int:
    parsed_campaign_id = _parse_uuid(campaign_id)
    if not parsed_campaign_id:
        return 0

    now = utc_now()
    recorded = 0

    for result in results:
        status = result["status"]
        values = {
            "status": status,
            "sent_at": now if status == RECIPIENT_SENT else None,
            "error_message": None if status == RECIPIENT_SENT else (result.get("error") or "Failed to send"),
            "sending_started_at": None,
            "attempt_id": None,
        }
        update_result = db.execute(
            update(CampaignRecipient)
            .where(
                CampaignRecipient.id == result["recipient_id"],
                CampaignRecipient.campaign_id == parsed_campaign_id,
                CampaignRecipient.attempt_id == result["attempt_id"],
                CampaignRecipient.status == RECIPIENT_SENDING,
            )
            .values(**values)
        )
        recorded += update_result.rowcount or 0

    db.commit()
    _refresh_campaign_delivery_summary_from_db(db, campaign_id)
    return recorded


def _has_claimable_recipients(db, campaign_id: str) -> bool:
    parsed_campaign_id = _parse_uuid(campaign_id)
    if not parsed_campaign_id:
        return False

    return bool(
        db.scalar(
            select(CampaignRecipient.id)
            .where(
                CampaignRecipient.campaign_id == parsed_campaign_id,
                CampaignRecipient.status.in_({RECIPIENT_QUEUED, RECIPIENT_FAILED_TRANSIENT}),
                CampaignRecipient.attempt_count < MAX_RECIPIENT_SEND_ATTEMPTS,
            )
            .limit(1)
        )
    )


def _campaign_stop_status(db, campaign: Campaign):
    db.refresh(campaign)
    if campaign.status in {"Paused", "Cancelled"}:
        return campaign.status
    return None


def enqueue_campaign_worker_pool(campaign_id: str, user_id: str, worker_count: int | None = None):
    tasks = []
    for _ in range(worker_count or CAMPAIGN_MAX_ACTIVE_WORKERS):
        task = send_campaign_worker.apply_async(
            kwargs={
                "campaign_id": campaign_id,
                "user_id": user_id,
            },
            queue=CAMPAIGN_DEFAULT_QUEUE,
            priority=5,
        )
        tasks.append(task.id)
    return tasks


@celery_app.task(bind=True, max_retries=3, default_retry_delay=30, name="src.tasks.start_scheduled_campaign")
def start_scheduled_campaign(self, campaign_id: str, user_id: str):
    parsed_campaign_id = _parse_uuid(campaign_id)
    if not parsed_campaign_id:
        return {"status": "invalid_campaign_id", "campaign_id": campaign_id}

    with sync_session_factory() as db:
        campaign = db.scalar(
            select(Campaign)
            .where(Campaign.id == parsed_campaign_id, Campaign.user_id == user_id)
        )
        if not campaign:
            return {"status": "not_found", "campaign_id": campaign_id, "user_id": user_id}

        if campaign.status != "Scheduled":
            return {
                "status": "ignored",
                "reason": "campaign_not_scheduled",
                "campaign_status": campaign.status,
                "campaign_id": campaign_id,
            }

        now = utc_now()
        if campaign.scheduled_at and campaign.scheduled_at > now:
            countdown = max(1, min(int((campaign.scheduled_at - now).total_seconds()), 300))
            raise self.retry(countdown=countdown)

        campaign.status = "Sending"
        campaign.sent_at = None
        campaign.sent_count = 0
        campaign.scheduled_at = None
        db.commit()

        recipient_count = db.scalar(
            select(func.count(CampaignRecipient.id))
            .where(CampaignRecipient.campaign_id == campaign.id)
        ) or 0

        if recipient_count >= BULK_CAMPAIGN_THRESHOLD:
            worker_task_ids = enqueue_campaign_worker_pool(str(campaign.id), str(campaign.user_id))
            return {
                "status": "bulk_started",
                "campaign_id": campaign_id,
                "worker_task_ids": worker_task_ids,
            }

        task = send_campaign.apply_async(
            kwargs={
                "campaign_id": str(campaign.id),
                "user_id": str(campaign.user_id),
            },
            queue=CAMPAIGN_DEFAULT_QUEUE,
            priority=5,
        )
        return {
            "status": "standard_started",
            "campaign_id": campaign_id,
            "task_id": task.id,
        }


def _mark_campaign_recipients_failed_permanent(db, campaign: Campaign, error: str = None):
    now = utc_now()

    result = db.execute(
        update(CampaignRecipient)
        .where(
            CampaignRecipient.campaign_id == campaign.id,
            CampaignRecipient.status.in_({
                RECIPIENT_QUEUED,
                RECIPIENT_SENDING,
                RECIPIENT_FAILED_TRANSIENT,
            }),
        )
        .values(
            status=RECIPIENT_FAILED_PERMANENT,
            sent_at=None,
            error_message=error,
            sending_started_at=None,
            attempt_id=None,
        )
    )
    _refresh_campaign_delivery_summary(campaign, now)
    db.commit()

    return result.rowcount or 0

@celery_app.task(
    bind=True,
    name="src.tasks.record_recipient_result_task",
    max_retries=10,
    default_retry_delay=5,
)
def record_recipient_result_task(
    self,
    campaign_id: str,
    recipient_id: str,
    attempt_id: str,
    status: str,
    error: str = None,
):
    try:
        with sync_session_factory() as db:
            campaign = _load_campaign_by_id(db, campaign_id)
            if not campaign:
                return {"status": "campaign_not_found"}
            
            recipient = db.get(CampaignRecipient, recipient_id)
            if not recipient:
                return {"status": "recipient_not_found"}
            
            recorded = _record_recipient_result(
                db,
                campaign,
                recipient,
                attempt_id,
                status,
                error,
            )

            return {
                "status": "recorded" if recorded else "ignored",
                "campaign_id": campaign_id,
                "recipient_id": recipient_id,
            }
    except Exception as exc:
        raise self.retry(exc=exc)


def _record_recipient_result(db, campaign: Campaign, recipient: CampaignRecipient, current_attempt_id: str, status: str, error: str = None):
    
    now = utc_now()
    values = {
        "status": status,
        "sent_at": now if status == RECIPIENT_SENT else None,
        "error_message": None if status == RECIPIENT_SENT else (error or "Failed to send"),
    }

    result = db.execute(
        update(CampaignRecipient)
        .where(
            CampaignRecipient.attempt_id == current_attempt_id,
            CampaignRecipient.id == recipient.id,
            CampaignRecipient.status == RECIPIENT_SENDING,
        )
        .values(**values, sending_started_at=None, attempt_id=None,)
    )
    db.commit()

    if result.rowcount != 1:
        return False

    recipient.status = values["status"]
    recipient.sent_at = values["sent_at"]
    recipient.error_message = values["error_message"]
    recipient.sending_started_at = None
    recipient.attempt_id = None
    _refresh_campaign_delivery_summary(campaign, now)
    db.commit()
    return True

# change to outbox or create table of attempts
def _enqueue_recipient_result_recording(
    db,
    campaign: Campaign,
    recipient: CampaignRecipient,
    current_attempt_id: str,
    status: str,
    error: str = None,
):
    try:
        record_recipient_result_task.apply_async(
            kwargs={
                "campaign_id": str(campaign.id),
                "recipient_id": str(recipient.id),
                "attempt_id": current_attempt_id,
                "status": status,
                "error": error,
            },
            queue=CAMPAIGN_DEFAULT_QUEUE,
            priority=5,
        )
        return True
    except Exception:
        logger.exception(
            "Failed to enqueue result recording for recipient %s; using direct DB fallback",
            recipient.email,
        )
        return _record_recipient_result(
            db,
            campaign,
            recipient,
            current_attempt_id,
            status,
            error,
        )


def email_exception_classifier(exc: Exception) -> str:
    if isinstance(exc, smtplib.SMTPResponseException):
        if 400 <= exc.smtp_code < 500:
            return RECIPIENT_FAILED_TRANSIENT, exc.smtp_code
        elif 500 <= exc.smtp_code < 599:
            return RECIPIENT_FAILED_PERMANENT, exc.smtp_code
    return RECIPIENT_FAILED_TRANSIENT, None


def campaign_exception_classifier(exc: Exception) -> str:
    if isinstance(exc, smtplib.SMTPAuthenticationError):
        return "permanent_config"
    elif isinstance(exc, smtplib.SMTPConnectError):
        return "transient_config"
    elif isinstance(exc, smtplib.SMTPServerDisconnected):
        return "transient_config"
    elif isinstance(exc, TimeoutError):
        return "transient_config"
    elif isinstance(exc, OSError):
        return "transient_config"
    else:
        return "transient_config"


def _send_claimed_recipient_batch(
    db,
    smtp: smtplib.SMTP,
    campaign: Campaign,
    recipients: list[CampaignRecipient],
    attachments=None,
) -> tuple[int, int]:
    suppression_map = get_active_suppression_map(
        db,
        [recipient.email for recipient in recipients],
        user_id=str(campaign.user_id),
    )
    results = []
    sent = 0

    for recipient in recipients:
        current_attempt_id = recipient.attempt_id
        suppression = suppression_map.get(recipient.email.strip().lower())
        if suppression:
            reason = suppression.get("reason") or "unknown"
            source = suppression.get("source") or "unknown"
            results.append({
                "recipient_id": recipient.id,
                "attempt_id": current_attempt_id,
                "status": RECIPIENT_SUPPRESSED,
                "error": f"Suppressed: {reason} ({source})",
            })
            continue

        if recipient.attempt_count >= MAX_RECIPIENT_SEND_ATTEMPTS:
            logger.warning(
                "Sending final attempt %s/%s for recipient %s in campaign %s",
                recipient.attempt_count,
                MAX_RECIPIENT_SEND_ATTEMPTS,
                recipient.email,
                campaign.id,
            )

        try:
            rendered = render_email_template(
                campaign.subject,
                campaign.body,
                campaign.html_body,
                _build_template_context(campaign, recipient),
            )
            validate_rendered_email_content(
                subject=rendered.subject,
                body=rendered.body,
                html_body=rendered.html_body,
                content_type=campaign.content_type,
            )
            tracked_html_body = instrument_email_tracking(
                rendered.html_body,
                campaign_id=str(campaign.id),
                recipient_id=str(recipient.id),
                user_id=str(campaign.user_id),
                email=recipient.email,
                attempt_id=current_attempt_id,
                track_opens=bool(campaign.track_opens),
                track_clicks=bool(campaign.track_clicks),
            )
            _wait_for_send_rate_limit(
                str(campaign.user_id),
                campaign.from_email,
                campaign.send_rate_per_second,
            )
            _send_single(
                smtp,
                recipient.email,
                rendered.subject,
                rendered.body,
                campaign.from_email,
                from_name=campaign.from_name,
                reply_to_email=campaign.reply_to_email,
                html_body=tracked_html_body,
                content_type=campaign.content_type,
                attachments=attachments,
                ses_tags={
                    "campaign_id": str(campaign.id),
                    "recipient_id": str(recipient.id),
                    "attempt_id": current_attempt_id,
                    "user_id": str(campaign.user_id),
                },
                user_id=str(campaign.user_id),
            )
        except Exception as e:
            logger.exception("Failed to send to %s: %s", recipient.email, e)
            mistake, code = email_exception_classifier(e)
            final_mistake = mistake
            error = str(e)

            if mistake == RECIPIENT_FAILED_TRANSIENT and recipient.attempt_count >= MAX_RECIPIENT_SEND_ATTEMPTS:
                final_mistake = RECIPIENT_FAILED_PERMANENT
                if code:
                    error = f"SMTP {code}. Max attempts exhausted: {str(e)}"
                else:
                    error = f"Max attempts exhausted: {str(e)}"

            results.append({
                "recipient_id": recipient.id,
                "attempt_id": current_attempt_id,
                "status": final_mistake,
                "error": error,
            })
        else:
            results.append({
                "recipient_id": recipient.id,
                "attempt_id": current_attempt_id,
                "status": RECIPIENT_SENT,
                "error": None,
            })
            sent += 1

    recorded = _record_recipient_results_bulk(db, str(campaign.id), results)
    return sent, recorded


@celery_app.task(bind=True, max_retries=5, default_retry_delay=10, name="src.tasks.send_campaign_worker")
def send_campaign_worker(self, attachments_b64=None, campaign_id: str = None, user_id: str = None):
    attachments = _decode_attachments(attachments_b64)
    smtp = None
    campaign = None
    db = None
    total_claimed = 0
    total_sent = 0
    total_recorded = 0
    worker_slot_acquired = False
    should_enqueue_replacement = False
    replacement_campaign_id = None
    replacement_user_id = None

    try:
        if not campaign_id or not user_id:
            raise ValueError("campaign_id and user_id are required")

        with sync_session_factory() as db:
            parsed_campaign_id = _parse_uuid(campaign_id)
            if not parsed_campaign_id:
                return {"status": "invalid_campaign_id", "sent": 0, "claimed": 0, "campaign_id": campaign_id}

            replacement_campaign_id = str(parsed_campaign_id)
            replacement_user_id = str(user_id)
            worker_slot_acquired = _acquire_campaign_worker_slot(replacement_campaign_id)
            if not worker_slot_acquired:
                return {
                    "status": "worker_slot_unavailable",
                    "sent": 0,
                    "claimed": 0,
                    "campaign_id": campaign_id,
                    "max_active_workers": CAMPAIGN_MAX_ACTIVE_WORKERS,
                }

            campaign = db.scalar(
                select(Campaign)
                .where(Campaign.id == parsed_campaign_id, Campaign.user_id == user_id)
            )
            if not campaign:
                return {"status": "not_found", "sent": 0, "claimed": 0, "campaign_id": campaign_id}

            _reset_stale_sending_recipients(db, campaign)
            _mark_exhausted_transient_recipients_failed(db, str(campaign.id))
            smtp, _smtp_credentials = open_smtp_connection(timeout=30)

            for _ in range(CAMPAIGN_WORKER_MAX_BATCHES):
                stop_status = _campaign_stop_status(db, campaign)
                if stop_status:
                    return {
                        "status": stop_status.lower(),
                        "sent": total_sent,
                        "claimed": total_claimed,
                        "recorded": total_recorded,
                        "campaign_id": campaign_id,
                        "user_id": user_id,
                    }

                current_batch_id = str(uuid4())
                recipients = _claim_recipient_batch(
                    db,
                    str(campaign.id),
                    CAMPAIGN_WORKER_BATCH_SIZE,
                    current_batch_id,
                )
                if not recipients:
                    break

                total_claimed += len(recipients)
                sent, recorded = _send_claimed_recipient_batch(
                    db,
                    smtp,
                    campaign,
                    recipients,
                    attachments=attachments,
                )
                total_sent += sent
                total_recorded += recorded

            _mark_exhausted_transient_recipients_failed(db, str(campaign.id))
            _refresh_campaign_delivery_summary_from_db(db, str(campaign.id))

            if _has_claimable_recipients(db, str(campaign.id)):
                should_enqueue_replacement = True

        return {
            "status": "ok",
            "sent": total_sent,
            "claimed": total_claimed,
            "recorded": total_recorded,
            "campaign_id": campaign_id,
            "user_id": user_id,
        }

    except Exception as exc:
        error_kind = campaign_exception_classifier(exc)

        if error_kind == "transient_config":
            logger.exception("Campaign worker failed, will retry")
            raise self.retry(exc=exc)

        if error_kind == "permanent_config":
            logger.exception("Campaign worker failed permanently, won't retry")
            failed = 0

            if campaign and db:
                failed = _mark_campaign_recipients_failed_permanent(db, campaign, str(exc))

            return {
                "status": "failed_config",
                "failed": failed,
                "campaign_id": campaign_id,
                "user_id": user_id,
                "error": str(exc),
            }
    finally:
        if smtp:
            try:
                smtp.quit()
            except Exception:
                pass
        if worker_slot_acquired and replacement_campaign_id:
            _release_campaign_worker_slot(replacement_campaign_id)
            if should_enqueue_replacement and replacement_user_id:
                enqueue_campaign_worker_pool(replacement_campaign_id, replacement_user_id, worker_count=1)

@celery_app.task(bind=True, max_retries=5, default_retry_delay=10)
def send_campaign(self, attachments_b64=None, campaign_id: str = None, user_id: str = None):
    """
    attachments_b64: list of {'filename','content_b64','mime_type'} where content_b64 is base64 string
    """
    attachments = _decode_attachments(attachments_b64)

    smtp = None
    campaign = None
    db = None

    try:
        if not campaign_id or not user_id:
            raise ValueError("campaign_id and user_id are required")
        
        with sync_session_factory() as db:
            campaign = _load_campaign_for_sending(db, str(campaign_id), str(user_id))
            if not campaign:
                return {"status": "not_found", "sent": 0, "total": 0, "campaign_id": campaign_id, "user_id": user_id}

            if _reset_stale_sending_recipients(db, campaign):
                campaign = _load_campaign_for_sending(db, str(campaign_id), str(user_id))

            batch_size = campaign.batch_size or DEFAULT_BATCH_SIZE
            per_batch_delay = campaign.per_batch_delay
            if per_batch_delay is None:
                per_batch_delay = DEFAULT_PER_BATCH_DELAY

            recipients_to_send = [
                recipient
                for recipient in campaign.recipients
                if recipient.status in {RECIPIENT_QUEUED, RECIPIENT_FAILED_TRANSIENT}
            ]

            total = len(recipients_to_send)
            sent = 0

            smtp, _smtp_credentials = open_smtp_connection(timeout=30)

            for i in range(0, total, batch_size):
                stop_status = _campaign_stop_status(db, campaign)
                if stop_status:
                    return {
                        "status": stop_status.lower(),
                        "sent": sent,
                        "total": total,
                        "campaign_id": campaign_id,
                        "user_id": user_id,
                    }

                batch = recipients_to_send[i:i+batch_size]
                start_batch = time.time()
                current_batch_id = str(uuid4())
                claimed_recipients = []

                for recipient in batch:
                    current_attempt_id = str(uuid4())
                    if not _claim_recipient(db, recipient, current_attempt_id, current_batch_id):
                        continue

                    claimed_recipients.append(recipient)

                if claimed_recipients:
                    batch_sent, _recorded = _send_claimed_recipient_batch(
                        db,
                        smtp,
                        campaign,
                        claimed_recipients,
                        attachments=attachments,
                    )
                    sent += batch_sent

                elapsed = time.time() - start_batch
                if per_batch_delay and per_batch_delay > elapsed:
                    time.sleep(per_batch_delay - elapsed)

        return {"status": "ok", "sent": sent, "total": total, "campaign_id": campaign_id, "user_id": user_id}
    
    except Exception as exc:
        error_kind = campaign_exception_classifier(exc)

        if error_kind == "transient_config":
            logger.exception("Campaign failed, will retry")
            raise self.retry(exc=exc)
        
        if error_kind == "permanent_config":
            logger.exception("Campaign failed permanently, won't retry")
            failed = 0

            if campaign:
                failed = _mark_campaign_recipients_failed_permanent(
                    db,
                    campaign,
                    str(exc),
                )               

            return {
                "status": "failed_config",
                "failed": failed,
                "campaign_id": campaign_id,
                "user_id": user_id,
                "error": str(exc),
            }   
        
    finally:
        if smtp:
            try:
                smtp.quit()
            except Exception:
                pass
