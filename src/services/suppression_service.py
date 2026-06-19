import hashlib
import hmac
from base64 import urlsafe_b64decode, urlsafe_b64encode
from urllib.parse import urlencode

from sqlalchemy import desc, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.configs.config import (
    PUBLIC_API_BASE_URL,
    SUPPRESSION_REASON_COMPLAINT,
    SUPPRESSION_REASON_HARD_BOUNCE,
    SUPPRESSION_REASON_UNSUBSCRIBE,
    SUPPRESSION_SOURCE_LOCAL,
    SUPPRESSION_SOURCE_SES,
    SUPPRESSION_STATUS_ACTIVE,
    SUPPRESSION_STATUS_INACTIVE,
    SUPPRESSION_SYNC_STATUS_FAILED,
    SUPPRESSION_SYNC_STATUS_SUCCESS,
    UNSUBSCRIBE_SECRET,
)
from src.integrations.ses_service import list_ses_suppressed_destinations
from src.models.models import Contact, SuppressionListEntry, SuppressionSyncRun, utc_now


def _normalize_suppressed_email(email: str | None):
    return (email or "").strip().lower()


def _urlsafe_b64encode(value: str):
    return urlsafe_b64encode(value.encode("utf-8")).decode("ascii").rstrip("=")


def _urlsafe_b64decode(value: str):
    padding = "=" * (-len(value) % 4)
    return urlsafe_b64decode(f"{value}{padding}".encode("ascii")).decode("utf-8")


def _user_unsubscribe_secret(user_id: str):
    return hmac.new(
        UNSUBSCRIBE_SECRET.encode("utf-8"),
        f"unsubscribe-secret:{user_id}".encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def generate_unsubscribe_public_key(user_id: str):
    encoded_user_id = _urlsafe_b64encode(user_id)
    signature = hmac.new(
        UNSUBSCRIBE_SECRET.encode("utf-8"),
        f"unsubscribe-public:{user_id}".encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()[:24]
    return f"upk_{encoded_user_id}.{signature}"


def get_user_id_from_unsubscribe_public_key(public_key: str | None):
    if not public_key or not public_key.startswith("upk_") or "." not in public_key:
        return None

    encoded_user_id, signature = public_key[4:].split(".", 1)
    try:
        user_id = _urlsafe_b64decode(encoded_user_id)
    except Exception:
        return None

    expected_public_key = generate_unsubscribe_public_key(user_id)
    if not hmac.compare_digest(expected_public_key, public_key):
        return None

    return user_id


def generate_unsubscribe_token(email: str, user_id: str):
    normalized_email = _normalize_suppressed_email(email)
    return hmac.new(
        _user_unsubscribe_secret(user_id).encode("utf-8"),
        normalized_email.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def verify_unsubscribe_token(public_key: str, email: str, token: str | None):
    if not token:
        return False

    user_id = get_user_id_from_unsubscribe_public_key(public_key)
    if not user_id:
        return False

    expected_token = generate_unsubscribe_token(email, user_id)
    return hmac.compare_digest(expected_token, token)


def build_unsubscribe_url(email: str, user_id: str):
    normalized_email = _normalize_suppressed_email(email)
    public_key = generate_unsubscribe_public_key(user_id)
    query = urlencode({
        "public_key": public_key,
        "email": normalized_email,
        "token": generate_unsubscribe_token(normalized_email, user_id),
    })
    return f"{PUBLIC_API_BASE_URL}/unsubscribe?{query}"


def _map_ses_suppression_reason(reason: str | None):
    if (reason or "").upper() == "COMPLAINT":
        return SUPPRESSION_REASON_COMPLAINT

    return SUPPRESSION_REASON_HARD_BOUNCE


def _serialize_sync_run(run: SuppressionSyncRun | None):
    if not run:
        return None

    return {
        "id": str(run.id),
        "source": run.source,
        "status": run.status,
        "started_at": run.started_at,
        "finished_at": run.finished_at,
        "synced": run.synced,
        "created": run.created_count,
        "updated": run.updated_count,
        "skipped": run.skipped_count,
        "error_message": run.error_message,
    }


def _serialize_suppression_entry(entry: SuppressionListEntry | None):
    if not entry:
        return None

    return {
        "id": str(entry.id),
        "user_id": entry.user_id,
        "email": entry.email,
        "reason": entry.reason,
        "source": entry.source,
        "status": entry.status,
        "note": entry.note,
        "created_by_user_id": entry.created_by_user_id,
        "first_seen_at": entry.first_seen_at,
        "last_seen_at": entry.last_seen_at,
        "created_at": entry.created_at,
        "updated_at": entry.updated_at,
    }


async def suppress_email_service(
    db: AsyncSession,
    email: str,
    reason: str,
    source: str,
    user_id: str | None = None,
    note: str | None = None,
    created_by_user_id: str | None = None,
):
    normalized_email = _normalize_suppressed_email(email)
    if not normalized_email:
        return None

    now = utc_now()
    entry = await db.scalar(
        select(SuppressionListEntry).where(
            SuppressionListEntry.user_id == user_id,
            SuppressionListEntry.email == normalized_email,
        )
    )

    if entry:
        entry.reason = reason
        entry.source = source
        entry.status = SUPPRESSION_STATUS_ACTIVE
        entry.last_seen_at = now
        if note is not None:
            entry.note = note
        if created_by_user_id is not None:
            entry.created_by_user_id = created_by_user_id
    else:
        entry = SuppressionListEntry(
            user_id=user_id,
            email=normalized_email,
            reason=reason,
            source=source,
            status=SUPPRESSION_STATUS_ACTIVE,
            note=note,
            created_by_user_id=created_by_user_id,
            first_seen_at=now,
            last_seen_at=now,
        )
        db.add(entry)

    await db.commit()
    await db.refresh(entry)
    return _serialize_suppression_entry(entry)


def suppress_email_sync_service(
    db,
    email: str,
    reason: str,
    source: str,
    user_id: str | None = None,
    note: str | None = None,
    created_by_user_id: str | None = None,
    commit: bool = True,
):
    normalized_email = _normalize_suppressed_email(email)
    if not normalized_email:
        return None

    now = utc_now()
    entry = db.scalar(
        select(SuppressionListEntry).where(
            SuppressionListEntry.user_id == user_id,
            SuppressionListEntry.email == normalized_email,
        )
    )

    if entry:
        entry.reason = reason
        entry.source = source
        entry.status = SUPPRESSION_STATUS_ACTIVE
        entry.last_seen_at = now
        if note is not None:
            entry.note = note
        if created_by_user_id is not None:
            entry.created_by_user_id = created_by_user_id
    else:
        entry = SuppressionListEntry(
            user_id=user_id,
            email=normalized_email,
            reason=reason,
            source=source,
            status=SUPPRESSION_STATUS_ACTIVE,
            note=note,
            created_by_user_id=created_by_user_id,
            first_seen_at=now,
            last_seen_at=now,
        )
        db.add(entry)

    if commit:
        db.commit()
        db.refresh(entry)

    return entry


async def unsuppress_email_service(db: AsyncSession, email: str, user_id: str | None = None):
    normalized_email = _normalize_suppressed_email(email)
    if not normalized_email:
        return None

    entry = await db.scalar(
        select(SuppressionListEntry).where(
            SuppressionListEntry.user_id == user_id,
            SuppressionListEntry.email == normalized_email,
        )
    )
    if not entry:
        return None

    entry.status = SUPPRESSION_STATUS_INACTIVE
    entry.last_seen_at = utc_now()

    await db.commit()
    await db.refresh(entry)
    return _serialize_suppression_entry(entry)


async def unsubscribe_email_service(db: AsyncSession, email: str, user_id: str):
    normalized_email = _normalize_suppressed_email(email)
    if not normalized_email:
        return None

    now = utc_now()
    entry = await db.scalar(
        select(SuppressionListEntry).where(
            SuppressionListEntry.user_id == user_id,
            SuppressionListEntry.email == normalized_email,
        )
    )

    if entry:
        entry.reason = SUPPRESSION_REASON_UNSUBSCRIBE
        entry.source = SUPPRESSION_SOURCE_LOCAL
        entry.status = SUPPRESSION_STATUS_ACTIVE
        entry.last_seen_at = now
    else:
        entry = SuppressionListEntry(
            user_id=user_id,
            email=normalized_email,
            reason=SUPPRESSION_REASON_UNSUBSCRIBE,
            source=SUPPRESSION_SOURCE_LOCAL,
            status=SUPPRESSION_STATUS_ACTIVE,
            first_seen_at=now,
            last_seen_at=now,
        )
        db.add(entry)

    await db.execute(
        update(Contact)
        .where(Contact.user_id == user_id, Contact.email == normalized_email)
        .values(status="unsubscribed", updated_at=now)
    )

    await db.commit()
    await db.refresh(entry)
    return _serialize_suppression_entry(entry)


async def resubscribe_email_service(db: AsyncSession, email: str, user_id: str):
    normalized_email = _normalize_suppressed_email(email)
    if not normalized_email:
        return None

    now = utc_now()
    entry = await db.scalar(
        select(SuppressionListEntry).where(
            SuppressionListEntry.user_id == user_id,
            SuppressionListEntry.email == normalized_email,
            SuppressionListEntry.reason == SUPPRESSION_REASON_UNSUBSCRIBE,
        )
    )
    if not entry:
        return None

    entry.status = SUPPRESSION_STATUS_INACTIVE
    entry.last_seen_at = now

    await db.execute(
        update(Contact)
        .where(Contact.user_id == user_id, Contact.email == normalized_email)
        .values(status="subscribed", updated_at=now)
    )

    await db.commit()
    await db.refresh(entry)
    return _serialize_suppression_entry(entry)


async def list_suppression_entries_service(
    db: AsyncSession,
    user_id: str | None = None,
    status: str | None = None,
    reason: str | None = None,
    source: str | None = None,
):
    query = select(SuppressionListEntry)

    if user_id is not None:
        query = query.where(SuppressionListEntry.user_id == user_id)
    if status:
        query = query.where(SuppressionListEntry.status == status)
    if reason:
        query = query.where(SuppressionListEntry.reason == reason)
    if source:
        query = query.where(SuppressionListEntry.source == source)

    result = await db.scalars(query.order_by(desc(SuppressionListEntry.updated_at)))
    return [_serialize_suppression_entry(entry) for entry in result.all()]


async def sync_ses_suppression_list_service(db: AsyncSession):
    run = SuppressionSyncRun(
        source=SUPPRESSION_SOURCE_SES,
        status=SUPPRESSION_SYNC_STATUS_FAILED,
        started_at=utc_now(),
    )
    db.add(run)
    await db.flush()

    try:
        items = list_ses_suppressed_destinations()
        now = utc_now()
        created = 0
        updated = 0
        skipped = 0

        for item in items:
            email = _normalize_suppressed_email(item.get("email"))
            if not email:
                skipped += 1
                continue
            reason = _map_ses_suppression_reason(item.get("reason"))
        
            existing = await db.scalar(
                select(SuppressionListEntry).where(
                    SuppressionListEntry.user_id.is_(None),
                    SuppressionListEntry.email == email,
                )
                )
            
            if existing:
                existing.reason = reason
                existing.source = SUPPRESSION_SOURCE_SES
                existing.status = SUPPRESSION_STATUS_ACTIVE
                existing.last_seen_at = item.get("last_update_time") or now
                updated += 1
            else:
                db.add(
                    SuppressionListEntry(
                        email=email,
                        reason=reason,
                        source=SUPPRESSION_SOURCE_SES,
                        status=SUPPRESSION_STATUS_ACTIVE,
                        first_seen_at=item.get("last_update_time") or now,
                        last_seen_at=item.get("last_update_time") or now,
                    )
                )
                created += 1
        
        run.status = SUPPRESSION_SYNC_STATUS_SUCCESS
        run.finished_at = utc_now()
        run.synced = created + updated
        run.created_count = created
        run.updated_count = updated
        run.skipped_count = skipped

        await db.commit()
        return _serialize_sync_run(run)
    
    except Exception as exc:
        run.status = SUPPRESSION_SYNC_STATUS_FAILED
        run.finished_at = utc_now()
        run.error_message = str(exc)

        await db.commit()
        raise


def sync_ses_suppression_list_sync_service(db):
    run = SuppressionSyncRun(
        source=SUPPRESSION_SOURCE_SES,
        status=SUPPRESSION_SYNC_STATUS_FAILED,
        started_at=utc_now(),
    )
    db.add(run)
    db.flush()

    try:
        items = list_ses_suppressed_destinations()
        now = utc_now()
        created = 0
        updated = 0
        skipped = 0

        for item in items:
            email = _normalize_suppressed_email(item.get("email"))
            if not email:
                skipped += 1
                continue
            reason = _map_ses_suppression_reason(item.get("reason"))

            existing = db.scalar(
                select(SuppressionListEntry).where(
                    SuppressionListEntry.user_id.is_(None),
                    SuppressionListEntry.email == email,
                )
            )

            if existing:
                existing.reason = reason
                existing.source = SUPPRESSION_SOURCE_SES
                existing.status = SUPPRESSION_STATUS_ACTIVE
                existing.last_seen_at = item.get("last_update_time") or now
                updated += 1
            else:
                db.add(
                    SuppressionListEntry(
                        email=email,
                        reason=reason,
                        source=SUPPRESSION_SOURCE_SES,
                        status=SUPPRESSION_STATUS_ACTIVE,
                        first_seen_at=item.get("last_update_time") or now,
                        last_seen_at=item.get("last_update_time") or now,
                    )
                )
                created += 1

        run.status = SUPPRESSION_SYNC_STATUS_SUCCESS
        run.finished_at = utc_now()
        run.synced = created + updated
        run.created_count = created
        run.updated_count = updated
        run.skipped_count = skipped

        db.commit()
        return _serialize_sync_run(run)

    except Exception as exc:
        run.status = SUPPRESSION_SYNC_STATUS_FAILED
        run.finished_at = utc_now()
        run.error_message = str(exc)

        db.commit()
        raise


async def get_suppression_status_service(db: AsyncSession):
    active_count = await db.scalar(
        select(func.count()).select_from(SuppressionListEntry).where(
            SuppressionListEntry.status == SUPPRESSION_STATUS_ACTIVE,
        )
    )

    latest_run = await db.scalar(
        select(SuppressionSyncRun)
        .order_by(desc(SuppressionSyncRun.started_at))
        .limit(1)
    )

    return {
        "active_count": active_count or 0,
        "last_sync": _serialize_sync_run(latest_run),
    }


def get_active_suppressed_emails(db, emails: list[str], user_id: str | None = None):
    normalized_emails = {
        _normalize_suppressed_email(email)
        for email in emails
        if _normalize_suppressed_email(email)
    }

    if not normalized_emails:
        return set()

    rows = db.execute(
        select(SuppressionListEntry.email).where(
            SuppressionListEntry.status == SUPPRESSION_STATUS_ACTIVE,
            SuppressionListEntry.email.in_(normalized_emails),
            or_(
                SuppressionListEntry.user_id == user_id,
                SuppressionListEntry.user_id.is_(None),
            ),
        )
    )

    return {email for email, in rows}


def get_active_suppression_map(db, emails: list[str], user_id: str | None = None):
    normalized_emails = {
        _normalize_suppressed_email(email)
        for email in emails
        if _normalize_suppressed_email(email)
    }

    if not normalized_emails:
        return {}

    rows = db.execute(
        select(
            SuppressionListEntry.email,
            SuppressionListEntry.reason,
            SuppressionListEntry.source,
        ).where(
            SuppressionListEntry.status == SUPPRESSION_STATUS_ACTIVE,
            SuppressionListEntry.email.in_(normalized_emails),
            or_(
                SuppressionListEntry.user_id == user_id,
                SuppressionListEntry.user_id.is_(None),
            ),
        )
    )

    return {
        email: {
            "reason": reason,
            "source": source,
        }
        for email, reason, source in rows
    }
