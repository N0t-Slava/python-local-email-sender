from fastapi import APIRouter, HTTPException, Request

from src.configs.config import WEBHOOKS_QUEUE
from src.services.sns_service import (
    confirm_sns_subscription,
    get_sns_type,
    parse_ses_message_from_sns,
    parse_sns_message,
    verify_sns_message,
)
from src.tasks import process_ses_notification_task

router = APIRouter()


@router.post("/webhooks/aws/sns/ses")
async def handle_ses_sns_webhook(request: Request):
    raw_body = await request.body()

    try:
        sns_message = parse_sns_message(raw_body)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid SNS message")

    try:
        signature_valid = verify_sns_message(sns_message)
    except Exception:
        raise HTTPException(status_code=403, detail="Invalid SNS signature")

    if not signature_valid:
        raise HTTPException(status_code=403, detail="Invalid SNS signature")

    sns_type = get_sns_type(sns_message)

    if sns_type == "SubscriptionConfirmation":
        return confirm_sns_subscription(sns_message)

    if sns_type == "Notification":
        try:
            ses_payload = parse_ses_message_from_sns(sns_message)
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid SES message")

        task = process_ses_notification_task.apply_async(
            args=[
                ses_payload,
                sns_message.get("MessageId"),
            ],
            queue=WEBHOOKS_QUEUE,
        )
        return {"status": "queued", "task_id": task.id}

    return {"status": "ignored", "sns_type": sns_type}
