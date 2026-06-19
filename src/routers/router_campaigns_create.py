import json
from datetime import UTC, datetime
from uuid import uuid4
from fastapi import UploadFile, File, Form, APIRouter, Depends, HTTPException, Response
from sqlalchemy.ext.asyncio import AsyncSession
from src.services.local_user_service import get_local_user
from src.database.sqlalchemy import get_db
from src.configs.config import BULK_CAMPAIGN_THRESHOLD, CAMPAIGN_DEFAULT_QUEUE, SES_PREFLIGHT_ENABLED
from src.schemas.Campaign import CampaignResponse
from src.services.contacts_service import is_valid_email
from src.integrations.ses_service import (
    validate_ses_preflight,
)
from src.services.domains_service import DomainError, check_domain_for_sending_service
from src.services.campaigns_service import (
    add_campaign_service,
    cancel_campaign_service,
    claim_campaign_for_sending_service,
    delete_campaign_service,
    delete_current_draft_service,
    get_current_draft_service,
    get_campaign_service,
    list_campaigns_service,
    pause_campaign_service,
    resume_campaign_service,
    save_campaign_from_draft_service,
    save_current_draft_service,
    schedule_campaign_service,
    serialize_campaign,
)
from src.tasks import enqueue_campaign_worker_pool, send_campaign, start_scheduled_campaign
from src.services.email_content_service import validate_email_content
from src.services.email_service import send_email
from src.services.campaign_recipients_csv_service import parse_campaign_recipients_csv

router = APIRouter()


@router.get("/campaigns", response_model=list[CampaignResponse])
async def list_campaigns(db: AsyncSession = Depends(get_db)):
    current_user = get_local_user()
    return await list_campaigns_service(db, current_user["id"])


def parse_recipients(
        content: bytes, 
        allow_empty: bool = False, 
        reject_invalid: bool = True,
        ):
    try:
        return parse_campaign_recipients_csv(
            content,
            allow_empty=allow_empty,
            reject_invalid=reject_invalid,
        )["recipients"]
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


def validate_campaign_content(
    body: str | None,
    html_body: str | None,
    content_type: str | None,
    require_complete: bool = True,
):
    try:
        return validate_email_content(
            body=body,
            html_body=html_body,
            content_type=content_type,
            require_complete=require_complete,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


def normalize_optional_form_text(value: str | None):
    if value is None:
        return None

    stripped_value = value.strip()
    return stripped_value or None


def validate_reply_to_email(reply_to_email: str | None):
    normalized_reply_to = normalize_optional_form_text(reply_to_email)
    if normalized_reply_to and not is_valid_email(normalized_reply_to):
        raise HTTPException(status_code=400, detail="Invalid reply-to email")
    return normalized_reply_to


def validate_send_rate(send_rate_per_second: str | float | None):
    normalized_send_rate = normalize_optional_form_text(str(send_rate_per_second)) if send_rate_per_second is not None else None
    if normalized_send_rate is None:
        return None

    try:
        parsed_send_rate = float(normalized_send_rate)
    except ValueError:
        raise HTTPException(status_code=400, detail="Send rate must be a number")

    if parsed_send_rate <= 0:
        raise HTTPException(status_code=400, detail="Send rate must be greater than 0")

    return parsed_send_rate


async def validate_sender_for_delivery(
    db: AsyncSession,
    user_id: str,
    from_email: str,
    recipients: list[str],
):
    if not SES_PREFLIGHT_ENABLED:
        return

    if not validate_ses_preflight(from_email, recipients):
        raise HTTPException(
            status_code=503,
            detail="SES preflight failed: sending disabled, sender not verified, or quota exceeded",
        )

    try:
        deliverability_check = await check_domain_for_sending_service(
            db,
            user_id=user_id,
            from_email=from_email,
        )
    except DomainError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    if not deliverability_check["can_send"]:
        raise HTTPException(
            status_code=400,
            detail={
                "message": "Sending domain is not ready",
                "from_email": deliverability_check["from_email"],
                "domain": deliverability_check["domain"],
                "blockers": deliverability_check["blockers"],
                "warnings": deliverability_check["warnings"],
            },
        )


def parse_campaign_tags(value: str | None):
    normalized_value = normalize_optional_form_text(value)
    if not normalized_value:
        return []

    if normalized_value.startswith("["):
        try:
            parsed_tags = json.loads(normalized_value)
        except json.JSONDecodeError:
            raise HTTPException(status_code=400, detail="Campaign tags must be comma-separated text or a JSON array")

        if not isinstance(parsed_tags, list):
            raise HTTPException(status_code=400, detail="Campaign tags must be a JSON array")

        return parsed_tags

    return [tag.strip() for tag in normalized_value.split(",") if tag.strip()]


def parse_scheduled_at(value: str | None):
    normalized_value = normalize_optional_form_text(value)
    if not normalized_value:
        raise HTTPException(status_code=400, detail="Scheduled time is required")

    try:
        parsed_value = datetime.fromisoformat(normalized_value.replace("Z", "+00:00"))
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid scheduled time")

    if parsed_value.tzinfo:
        parsed_value = parsed_value.astimezone(UTC).replace(tzinfo=None)

    if parsed_value <= datetime.now(UTC).replace(tzinfo=None):
        raise HTTPException(status_code=400, detail="Scheduled time must be in the future")

    return parsed_value


@router.post("/campaigns/create")
async def campaigns_create(
    subject: str = Form(...),
    body: str = Form(""),
    csv_file: UploadFile = File(...),
    from_email: str = Form(...),
    from_name: str = Form(None),
    reply_to_email: str = Form(None),
    batch_size: int = Form(None),
    html_body: str = Form(None),
    content_type: str = Form("plain"),
    per_batch_delay: float = Form(None),
    send_rate_per_second: str = Form(None),
    track_opens: bool = Form(True),
    track_clicks: bool = Form(True),
    category: str = Form(None),
    tags: str = Form(None),
    db: AsyncSession = Depends(get_db),
):
    current_user = get_local_user()

    content = await csv_file.read()
    recipients = parse_recipients(content)

    if not is_valid_email(from_email):
        raise HTTPException(status_code=400, detail="Invalid from email")

    from_name = normalize_optional_form_text(from_name)
    reply_to_email = validate_reply_to_email(reply_to_email)
    send_rate_per_second = validate_send_rate(send_rate_per_second)
    category = normalize_optional_form_text(category)
    tags = parse_campaign_tags(tags)
    content_type = validate_campaign_content(body, html_body, content_type)

    campaign = await add_campaign_service(
        db,
        user_id=current_user["id"],
        task_id=None,
        subject=subject,
        body=body,
        from_email=from_email,
        from_name=from_name,
        reply_to_email=reply_to_email,
        queued_recipients=len(recipients),
        html_body=html_body,
        content_type=content_type,
        recipients=recipients,
        status="Ready",
        batch_size=batch_size,
        per_batch_delay=per_batch_delay,
        send_rate_per_second=send_rate_per_second,
        track_opens=track_opens,
        track_clicks=track_clicks,
        category=category,
        tags=tags,
    )


    return {"queued_recipients": len(recipients), "campaign": campaign}


@router.post("/campaigns/test-send")
async def test_send_campaign_email(
    to_email: str = Form(...),
    subject: str = Form(...),
    body: str = Form(""),
    from_email: str = Form(...),
    from_name: str = Form(None),
    reply_to_email: str = Form(None),
    html_body: str = Form(None),
    content_type: str = Form("plain"),
    db: AsyncSession = Depends(get_db),
):
    current_user = get_local_user()
    normalized_to_email = to_email.strip()
    normalized_from_email = from_email.strip()
    from_name = normalize_optional_form_text(from_name)
    reply_to_email = validate_reply_to_email(reply_to_email)

    if not is_valid_email(normalized_to_email):
        raise HTTPException(status_code=400, detail="Invalid test recipient email")

    if not is_valid_email(normalized_from_email):
        raise HTTPException(status_code=400, detail="Invalid from email")

    content_type = validate_campaign_content(body, html_body, content_type)

    await validate_sender_for_delivery(db, current_user["id"], normalized_from_email, [normalized_to_email])

    try:
        send_email(
            to=normalized_to_email,
            subject=subject,
            body=body,
            from_email=normalized_from_email,
            html_body=html_body,
            content_type=content_type,
            from_name=from_name,
            reply_to_email=reply_to_email,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

    return {"status": "sent", "to_email": normalized_to_email}


@router.get("/campaigns/draft/current", response_model=CampaignResponse | None)
async def get_current_draft(
    db: AsyncSession = Depends(get_db),
):
    current_user = get_local_user()
    return await get_current_draft_service(db, current_user["id"])


@router.post("/campaigns/draft", response_model=CampaignResponse)
async def save_campaign_draft(
    subject: str = Form(""),
    body: str = Form(""),
    csv_file: UploadFile | None = File(None),
    from_email: str = Form(""),
    from_name: str = Form(None),
    reply_to_email: str = Form(None),
    html_body: str = Form(None),
    content_type: str = Form("plain"),
    batch_size: int = Form(None),
    per_batch_delay: float = Form(None),
    send_rate_per_second: str = Form(None),
    track_opens: bool = Form(True),
    track_clicks: bool = Form(True),
    category: str = Form(None),
    tags: str = Form(None),
    db: AsyncSession = Depends(get_db),
):
    current_user = get_local_user()
    content_type = validate_campaign_content(body, html_body, content_type, require_complete=False)
    from_name = normalize_optional_form_text(from_name)
    reply_to_email = validate_reply_to_email(reply_to_email)
    send_rate_per_second = validate_send_rate(send_rate_per_second)
    category = normalize_optional_form_text(category)
    tags = parse_campaign_tags(tags)
    recipients = []
    if csv_file:
        recipients = parse_recipients(
            await csv_file.read(),
            allow_empty=True,
            reject_invalid=False,
        )

    return await save_current_draft_service(
        db,
        user_id=current_user["id"],
        subject=subject,
        body=body,
        from_email=from_email,
        from_name=from_name,
        reply_to_email=reply_to_email,
        html_body=html_body,
        content_type=content_type,
        recipients=recipients,
        batch_size=batch_size,
        per_batch_delay=per_batch_delay,
        send_rate_per_second=send_rate_per_second,
        track_opens=track_opens,
        track_clicks=track_clicks,
        category=category,
        tags=tags,
    )


@router.put("/campaigns/draft/current", response_model=CampaignResponse)
async def update_current_draft(
    subject: str = Form(""),
    body: str = Form(""),
    csv_file: UploadFile | None = File(None),
    from_email: str = Form(""),
    from_name: str = Form(None),
    reply_to_email: str = Form(None),
    html_body: str = Form(None),
    content_type: str = Form("plain"),
    batch_size: int = Form(None),
    per_batch_delay: float = Form(None),
    send_rate_per_second: str = Form(None),
    track_opens: bool = Form(True),
    track_clicks: bool = Form(True),
    category: str = Form(None),
    tags: str = Form(None),
    db: AsyncSession = Depends(get_db),
):
    current_user = get_local_user()
    content_type = validate_campaign_content(body, html_body, content_type, require_complete=False)
    from_name = normalize_optional_form_text(from_name)
    reply_to_email = validate_reply_to_email(reply_to_email)
    send_rate_per_second = validate_send_rate(send_rate_per_second)
    category = normalize_optional_form_text(category)
    tags = parse_campaign_tags(tags)
    recipients = []
    if csv_file:
        recipients = parse_recipients(
            await csv_file.read(),
            allow_empty=True,
            reject_invalid=False,
        )

    return await save_current_draft_service(
        db,
        user_id=current_user["id"],
        subject=subject,
        body=body,
        from_email=from_email,
        from_name=from_name,
        reply_to_email=reply_to_email,
        html_body=html_body,
        content_type=content_type,
        recipients=recipients,
        batch_size=batch_size,
        per_batch_delay=per_batch_delay,
        send_rate_per_second=send_rate_per_second,
        track_opens=track_opens,
        track_clicks=track_clicks,
        category=category,
        tags=tags,
    )


@router.delete("/campaigns/draft/current", status_code=204)
async def delete_current_draft(
    db: AsyncSession = Depends(get_db),
):
    current_user = get_local_user()
    await delete_current_draft_service(db, current_user["id"])
    return Response(status_code=204)


@router.delete("/campaigns/{campaign_id}", status_code=204)
async def delete_campaign_route(
    campaign_id: str,
    db: AsyncSession = Depends(get_db),
):
    current_user = get_local_user()
    result = await delete_campaign_service(db, current_user["id"], campaign_id)

    if result == "not_found":
        raise HTTPException(status_code=404, detail="Campaign not found")

    if result == "active":
        raise HTTPException(status_code=400, detail="Active campaigns cannot be deleted")

    return Response(status_code=204)


@router.post("/campaigns/draft/save")
async def save_campaign_from_draft(
    db: AsyncSession = Depends(get_db),
):
    current_user = get_local_user()
    draft = await get_current_draft_service(db, current_user["id"])
    if not draft:
        raise HTTPException(status_code=404, detail="Draft not found")

    validate_campaign_content(
        draft.get("body"),
        draft.get("html_body"),
        draft.get("content_type"),
    )

    campaign = await save_campaign_from_draft_service(db, current_user["id"])
    if not campaign:
        raise HTTPException(status_code=404, detail="Draft not found")

    return {"queued_recipients": campaign["queued_recipients"], "campaign": campaign}


async def _send_campaign(
    db: AsyncSession,
    user_id: str,
    campaign_id: str,
    campaign: dict,
):
    task_id = str(uuid4())
    recipients = campaign.get("recipients", [])
    if not recipients:
        raise HTTPException(status_code=400, detail="Campaign has no recipients")

    if campaign["status"] not in {"Draft", "Ready"}:
        raise HTTPException(status_code=400, detail="Only draft or ready campaigns can be sent")

    await validate_sender_for_delivery(db, user_id, campaign["from_email"], recipients)

    claimed_campaign = await claim_campaign_for_sending_service(
        db,
        user_id,
        campaign_id,
        task_id,
    )

    if not claimed_campaign:
        raise HTTPException(status_code=409, detail="Campaign already started")

    if len(recipients) >= BULK_CAMPAIGN_THRESHOLD:
        worker_task_ids = enqueue_campaign_worker_pool(campaign["id"], user_id)
        return {
            "task_id": task_id,
            "worker_task_ids": worker_task_ids,
            "queued_recipients": len(recipients),
            "campaign": claimed_campaign,
        }

    task = send_campaign.apply_async(
        kwargs={
            "campaign_id": campaign["id"],
            "user_id": user_id,
        },
        task_id=task_id,
        queue=CAMPAIGN_DEFAULT_QUEUE,
        priority=5,
    )

    return {"task_id": task.id, "queued_recipients": len(recipients), "campaign": claimed_campaign}


@router.post("/campaigns/{campaign_id}/schedule")
async def schedule_campaign_route(
    campaign_id: str,
    scheduled_at: str = Form(...),
    db: AsyncSession = Depends(get_db),
):
    current_user = get_local_user()
    campaign_model = await get_campaign_service(db, current_user["id"], campaign_id)

    if not campaign_model:
        raise HTTPException(status_code=404, detail="Campaign not found")

    campaign = serialize_campaign(campaign_model)
    recipients = campaign.get("recipients", [])
    if not recipients:
        raise HTTPException(status_code=400, detail="Campaign has no recipients")

    if campaign["status"] not in {"Draft", "Ready", "Scheduled"}:
        raise HTTPException(status_code=400, detail="Only draft, ready, or scheduled campaigns can be scheduled")

    validate_campaign_content(
        campaign.get("body"),
        campaign.get("html_body"),
        campaign.get("content_type"),
    )

    await validate_sender_for_delivery(db, current_user["id"], campaign["from_email"], recipients)

    parsed_scheduled_at = parse_scheduled_at(scheduled_at)
    task_id = str(uuid4())
    scheduled_campaign = await schedule_campaign_service(
        db,
        current_user["id"],
        campaign_id,
        task_id,
        parsed_scheduled_at,
    )

    if not scheduled_campaign:
        raise HTTPException(status_code=409, detail="Campaign could not be scheduled")

    task = start_scheduled_campaign.apply_async(
        kwargs={
            "campaign_id": campaign_id,
            "user_id": current_user["id"],
        },
        task_id=task_id,
        eta=parsed_scheduled_at,
        queue=CAMPAIGN_DEFAULT_QUEUE,
        priority=5,
    )

    return {"task_id": task.id, "scheduled_at": scheduled_campaign["scheduled_at"], "campaign": scheduled_campaign}


@router.post("/campaigns/{campaign_id}/send")
async def send_campaign_route(
    campaign_id: str,
    db: AsyncSession = Depends(get_db),
):
    current_user = get_local_user()
    campaign_model = await get_campaign_service(db, current_user["id"], campaign_id)

    if not campaign_model:
        raise HTTPException(status_code=404, detail="Campaign not found")


    campaign = serialize_campaign(campaign_model)
    return await _send_campaign(
        db,
        current_user["id"],
        campaign_id,
        campaign,
    )


@router.post("/campaigns/{campaign_id}/pause")
async def pause_campaign_route(
    campaign_id: str,
    db: AsyncSession = Depends(get_db),
):
    current_user = get_local_user()
    campaign = await pause_campaign_service(db, current_user["id"], campaign_id)
    if not campaign:
        raise HTTPException(status_code=400, detail="Only sending campaigns can be paused")

    return {"campaign": campaign}


@router.post("/campaigns/{campaign_id}/resume")
async def resume_campaign_route(
    campaign_id: str,
    db: AsyncSession = Depends(get_db),
):
    current_user = get_local_user()
    task_id = str(uuid4())
    campaign = await resume_campaign_service(db, current_user["id"], campaign_id, task_id)
    if not campaign:
        raise HTTPException(status_code=400, detail="Only paused campaigns can be resumed")

    recipients = campaign.get("recipients", [])
    if len(recipients) >= BULK_CAMPAIGN_THRESHOLD:
        worker_task_ids = enqueue_campaign_worker_pool(campaign["id"], current_user["id"])
        return {"task_id": task_id, "worker_task_ids": worker_task_ids, "campaign": campaign}

    task = send_campaign.apply_async(
        kwargs={
            "campaign_id": campaign["id"],
            "user_id": current_user["id"],
        },
        task_id=task_id,
        queue=CAMPAIGN_DEFAULT_QUEUE,
        priority=5,
    )
    return {"task_id": task.id, "campaign": campaign}


@router.post("/campaigns/{campaign_id}/cancel")
async def cancel_campaign_route(
    campaign_id: str,
    db: AsyncSession = Depends(get_db),
):
    current_user = get_local_user()
    campaign = await cancel_campaign_service(db, current_user["id"], campaign_id)
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")

    return {"campaign": campaign}
