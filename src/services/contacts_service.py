from datetime import datetime
import re
from uuid import UUID, uuid4

from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.models import Contact


EMAIL_PATTERN = re.compile(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", re.IGNORECASE)


def _normalize_email(email: str) -> str:
    return email.strip().lower()


def _format_datetime(value: datetime | None) -> str | None:
    return value.isoformat() if value else None


def _serialize_contact(contact: Contact):
    return {
        "id": str(contact.id),
        "email": contact.email,
        "name": contact.name or "",
        "status": contact.status,
        "created_at": _format_datetime(contact.created_at),
        "updated_at": _format_datetime(contact.updated_at),
    }


def extract_emails_from_text(text: str) -> list[str]:
    emails = []
    seen = set()

    for match in EMAIL_PATTERN.findall(text):
        email = _normalize_email(match)
        if email not in seen:
            seen.add(email)
            emails.append(email)

    return emails


def is_valid_email(email: str) -> bool:
    return bool(EMAIL_PATTERN.fullmatch(email.strip()))


async def add_contact_service(db: AsyncSession, user_id: str, email: str, name: str = None):
    email = _normalize_email(email)
    existing = await db.scalar(
        select(Contact).where(Contact.user_id == user_id, Contact.email == email)
    )
    if existing:
        return None

    contact = Contact(
        id=uuid4(),
        user_id=user_id,
        email=email,
        name=name or "",
        status="subscribed",
    )
    db.add(contact)

    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        return None

    await db.refresh(contact)
    return _serialize_contact(contact)


async def list_contacts_service(db: AsyncSession, user_id: str):
    result = await db.scalars(
        select(Contact)
        .where(Contact.user_id == user_id)
        .order_by(Contact.created_at.desc())
    )
    return [_serialize_contact(contact) for contact in result.all()]


async def delete_contact_service(db: AsyncSession, user_id: str, contact_id: str):
    try:
        parsed_contact_id = UUID(contact_id)
    except ValueError:
        return None

    contact = await db.scalar(
        select(Contact).where(Contact.user_id == user_id, Contact.id == parsed_contact_id)
    )
    if not contact:
        return None

    serialized = _serialize_contact(contact)
    await db.execute(delete(Contact).where(Contact.user_id == user_id, Contact.id == parsed_contact_id))
    await db.commit()

    return serialized


async def import_contacts_service(db: AsyncSession, user_id: str, emails: list[str]):
    added_contacts = []
    duplicate_count = 0

    for email in emails:
        if not is_valid_email(email):
            duplicate_count += 1
            continue

        contact = await add_contact_service(db, user_id=user_id, email=email)
        if contact:
            added_contacts.append(contact)
        else:
            duplicate_count += 1

    return {
        "contacts": added_contacts,
        "created_count": len(added_contacts),
        "duplicate_count": duplicate_count,
        "total_found": len(emails),
    }
