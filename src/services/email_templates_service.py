from datetime import datetime
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.models import EmailTemplate, utc_now
from src.services.email_content_service import validate_email_content


def _format_datetime(value: datetime | None) -> str | None:
    return value.isoformat() if value else None


def _parse_template_id(template_id: str):
    try:
        return UUID(template_id)
    except ValueError:
        return None


def _normalize_optional_text(value: str | None) -> str | None:
    if value is None:
        return None

    stripped = value.strip()
    return stripped or None


def _require_text(value: str | None, field_name: str) -> str:
    normalized = _normalize_optional_text(value)
    if not normalized:
        raise ValueError(f"{field_name} is required")
    return normalized


def serialize_email_template(template: EmailTemplate):
    return {
        "id": str(template.id),
        "user_id": template.user_id,
        "name": template.name,
        "subject": template.subject,
        "body": template.body,
        "html_body": template.html_body,
        "content_type": template.content_type or "plain",
        "created_at": _format_datetime(template.created_at),
        "updated_at": _format_datetime(template.updated_at),
    }


async def create_email_template_service(
    db: AsyncSession,
    user_id: str,
    name: str,
    subject: str,
    body: str = "",
    html_body: str | None = None,
    content_type: str = "plain",
):
    name = _require_text(name, "Template name")
    subject = _require_text(subject, "Subject")

    content_type = validate_email_content(
        body=body,
        html_body=html_body,
        content_type=content_type,
    )

    template = EmailTemplate(
        user_id=user_id,
        name=name,
        subject=subject,
        body=body or "",
        html_body=_normalize_optional_text(html_body),
        content_type=content_type,
    )

    db.add(template)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise ValueError("Template name already exists")

    await db.refresh(template)
    return serialize_email_template(template)


async def list_email_templates_service(db: AsyncSession, user_id: str):
    result = await db.scalars(
        select(EmailTemplate)
        .where(EmailTemplate.user_id == user_id)
        .order_by(EmailTemplate.updated_at.desc())
    )
    return [serialize_email_template(template) for template in result.all()]


async def get_email_template_service(db: AsyncSession, user_id: str, template_id: str):
    parsed_template_id = _parse_template_id(template_id)
    if not parsed_template_id:
        return None

    template = await db.scalar(
        select(EmailTemplate).where(
            EmailTemplate.id == parsed_template_id,
            EmailTemplate.user_id == user_id,
        )
    )
    return serialize_email_template(template) if template else None


async def update_email_template_service(
    db: AsyncSession,
    user_id: str,
    template_id: str,
    **updates,
):
    parsed_template_id = _parse_template_id(template_id)
    if not parsed_template_id:
        return None

    template = await db.scalar(
        select(EmailTemplate).where(
            EmailTemplate.id == parsed_template_id,
            EmailTemplate.user_id == user_id,
        )
    )
    if not template:
        return None

    next_name = _require_text(updates.get("name", template.name), "Template name")
    next_subject = _require_text(updates.get("subject", template.subject), "Subject")
    next_body = updates.get("body", template.body)
    next_html_body = updates.get("html_body", template.html_body)
    next_content_type = updates.get("content_type", template.content_type)

    next_content_type = validate_email_content(
        body=next_body,
        html_body=next_html_body,
        content_type=next_content_type,
    )

    template.name = next_name
    template.subject = next_subject
    template.body = next_body or ""
    template.html_body = _normalize_optional_text(next_html_body)
    template.content_type = next_content_type
    template.updated_at = utc_now()

    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise ValueError("Template name already exists")

    await db.refresh(template)
    return serialize_email_template(template)


async def delete_email_template_service(db: AsyncSession, user_id: str, template_id: str) -> bool:
    parsed_template_id = _parse_template_id(template_id)
    if not parsed_template_id:
        return False

    result = await db.execute(
        delete(EmailTemplate).where(
            EmailTemplate.id == parsed_template_id,
            EmailTemplate.user_id == user_id,
        )
    )
    await db.commit()
    return bool(result.rowcount)
