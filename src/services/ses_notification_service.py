from uuid import UUID
from datetime import datetime
from src.models.models import utc_now, EmailEvent, CampaignRecipient, Campaign
from sqlalchemy import func, select
from sqlalchemy.orm import selectinload
from src.configs.config import (
    EMAIL_EVENT_BOUNCE,
    EMAIL_EVENT_COMPLAINT,
    RECIPIENT_FAILED_PERMANENT,
    RECIPIENT_SUPPRESSED,
    SUPPRESSION_REASON_COMPLAINT,
    SUPPRESSION_REASON_HARD_BOUNCE,
    SUPPRESSION_SOURCE_SES,
)
from src.services.campaigns_service import _refresh_campaign_delivery_summary
from src.services.suppression_service import suppress_email_sync_service


import json


def _load_campaign_with_recipients(db, campaign_id):
    if not campaign_id:
        return None
    
    return db.scalar(
        select(Campaign)
        .options(selectinload(Campaign.recipients))
        .where(Campaign.id == campaign_id)
    )

def _update_campaign_event_counts(db, campaign: Campaign):
    campaign.bounce_count = db.scalar(
        select(func.count())
        .select_from(EmailEvent)
        .where(
            EmailEvent.campaign_id == campaign.id,
            EmailEvent.event_type == EMAIL_EVENT_BOUNCE
        )
    ) or 0

    campaign.complaint_count = db.scalar(
        select(func.count())
        .select_from(EmailEvent)
        .where(
            EmailEvent.campaign_id == campaign.id,
            EmailEvent.event_type == EMAIL_EVENT_COMPLAINT
        )
    ) or 0

    

def process_complaint_event(db, ses_payload: dict, sns_message_id: str):
    common_fields = _get_common_event_fields(ses_payload, sns_message_id)
    parsed_recipients = parse_complaint_notification(ses_payload)

    created = 0
    duplicates = 0
    suppressed = 0

    for parsed in parsed_recipients:
        event = _store_email_event(
            db,
            {
                **common_fields,
                **parsed,
                "event_type": EMAIL_EVENT_COMPLAINT,
            },
        )

        if event is None:
            duplicates += 1
            continue

        created += 1

        
        _upsert_suppressed_recipient(
            db,
            parsed["email"],
            SUPPRESSION_REASON_COMPLAINT,
            common_fields.get("user_id"),
        )
        _update_recipient_for_complaint(
            db,
            common_fields.get("recipient_id"),
            parsed.get("complaint_feedback_type"),
        )
        suppressed += 1
    
    campaign = _load_campaign_with_recipients(db, common_fields.get("campaign_id"))
    if campaign:
        _update_campaign_event_counts(db, campaign)
        _refresh_campaign_delivery_summary(campaign, utc_now())

    db.commit()

    return {
        "status": "processed",
        "event_type": EMAIL_EVENT_COMPLAINT,
        "created": created,
        "duplicates": duplicates,
        "suppressed": suppressed,
    }

def process_bounce_event(db, ses_payload: dict, sns_message_id: str):
    common_fields = _get_common_event_fields(ses_payload, sns_message_id)
    parsed_recipients = parse_bounce_notification(ses_payload)

    created = 0
    duplicates = 0
    suppressed = 0

    for parsed in parsed_recipients:
        event = _store_email_event(
            db,
            {
                **common_fields,
                **parsed,
                "event_type": EMAIL_EVENT_BOUNCE,
            },
        )

        if event is None:
            duplicates += 1
            continue

        created += 1

        if parsed.get("bounce_type") == "Permanent":
            _upsert_suppressed_recipient(
                db,
                parsed["email"],
                SUPPRESSION_REASON_HARD_BOUNCE,
                common_fields.get("user_id"),
            )
            _update_recipient_for_bounce(
                db,
                common_fields.get("recipient_id"),
                parsed.get("bounce_type"),
                parsed.get("bounce_subtype"),
            )
            suppressed += 1
    
    campaign = _load_campaign_with_recipients(db, common_fields.get("campaign_id"))
    if campaign:
        _update_campaign_event_counts(db, campaign)
        _refresh_campaign_delivery_summary(campaign, utc_now())

    db.commit()

    return {
        "status": "processed",
        "event_type": EMAIL_EVENT_BOUNCE,
        "created": created,
        "duplicates": duplicates,
        "suppressed": suppressed,
    }
    

def _update_recipient_for_complaint(db, recipient_id, feedback_type: str | None):
    if not recipient_id:
        return None
    
    recipient = db.get(CampaignRecipient, recipient_id)

    if not recipient:
        return None
    
    recipient.status = RECIPIENT_SUPPRESSED
    recipient.sent_at = None
    recipient.error_message = f"SES complaint: {feedback_type or 'unknown'}"
    recipient.sending_started_at = None
    recipient.attempt_id = None

    return recipient

def _update_recipient_for_bounce(db, recipient_id, bounce_type: str | None, bounce_subtype: str | None):
    if bounce_type != "Permanent" or not recipient_id:
        return None
    
    recipient = db.get(CampaignRecipient, recipient_id)
    if not recipient:
        return None
    
    recipient.status = RECIPIENT_FAILED_PERMANENT
    recipient.sent_at = None
    recipient.error_message = f"SES permanent bounce: {bounce_subtype or 'unknown'}"
    recipient.sending_started_at = None
    recipient.attempt_id = None

    return recipient

def _upsert_suppressed_recipient(db, email: str, reason: str, user_id: str | None):
    return suppress_email_sync_service(
        db,
        email=email,
        reason=reason,
        source=SUPPRESSION_SOURCE_SES,
        user_id=user_id,
        commit=False,
    )

def _get_common_event_fields(ses_payload: dict, sns_message_id: str) -> dict:
    mail = _get_mail(ses_payload)

    return {
        "user_id": _get_tag(ses_payload, "user_id"),
        "campaign_id": _parse_uuid(_get_tag(ses_payload, "campaign_id")),
        "recipient_id": _parse_uuid(_get_tag(ses_payload, "recipient_id")),
        "attempt_id": _get_tag(ses_payload, "attempt_id"),
        "ses_message_id": mail.get("messageId"),
        "sns_message_id": sns_message_id,
        "occurred_at": _parse_ses_timestamp(mail.get("timestamp")),
        "raw_payload": json.dumps(ses_payload, default=str),
    }

def _parse_ses_timestamp(value: str | None):
    if not value:
        return utc_now()

    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).replace(tzinfo=None)
    except ValueError:
        return utc_now()

def _store_email_event(db, event_data: dict):
    existing = db.scalar(
        select(EmailEvent.id).where(
            EmailEvent.sns_message_id == event_data.get("sns_message_id"),
            EmailEvent.event_type == event_data.get("event_type"),
            EmailEvent.email == event_data.get("email"),
        )
    )

    if existing:
        return None
    
    event = EmailEvent(**event_data)
    db.add(event)
    db.flush()

    return event

def _parse_uuid(value: str | None):
    if not value:
        return None
    
    try:
        return UUID(value)
    except ValueError:
        return None

def _get_event_type(ses_payload: dict) -> str | None:
    return ses_payload.get("eventType") or ses_payload.get("notificationType")

def _get_mail(ses_payload: dict) -> dict: 
    return ses_payload.get("mail") or {}

def _get_mail_tags(ses_payload: dict) -> dict:
    return _get_mail(ses_payload).get("tags") or {}

def _get_tag(ses_payload: dict, name: str) -> str | None:
    value = _get_mail_tags(ses_payload).get(name)

    if isinstance(value, list):
        return value[0] if value else None
    
    return value

def _normalize_email(email: str | None) -> str:
    return (email or "").strip().lower()

def parse_bounce_notification(ses_payload: dict) -> list[dict]:
    bounce = ses_payload.get("bounce") or {}
    bounce_type = bounce.get("bounceType")
    bounce_subtype = bounce.get("bounceSubType")
    recipients = bounce.get("bouncedRecipients") or []

    parsed = []

    for recipient in recipients:
        email = _normalize_email(recipient.get("emailAddress"))

        if not email:
            continue

        parsed.append({
            "email": email,
            "bounce_type": bounce_type,
            "bounce_subtype": bounce_subtype,
            "diagnostic_code": recipient.get("diagnosticCode") or recipient.get("status"),        
        })

    return parsed

def parse_complaint_notification(ses_payload: dict) -> list[dict]:
    complaint = ses_payload.get("complaint") or {}
    feedback_type = complaint.get("complaintFeedbackType")
    recipients = complaint.get("complainedRecipients") or []

    parsed = []

    for recipient in recipients:
        email = _normalize_email(recipient.get("emailAddress"))
        if not email:
            continue

        parsed.append({
            "email": email,
            "complaint_feedback_type": feedback_type,
        })

    return parsed

def process_ses_notification(db, ses_payload: dict, sns_message_id: str):

    event_type = _get_event_type(ses_payload)

    if event_type == "Bounce":
        return process_bounce_event(db, ses_payload, sns_message_id)

    if event_type == "Complaint":
        return process_complaint_event(db, ses_payload, sns_message_id)

    return {"status": "ignored", "event_type": event_type}
