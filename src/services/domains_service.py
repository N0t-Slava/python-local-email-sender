from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.configs.config import AWS_REGION
from src.integrations.ses_service import (
    get_ses_dkim_setup_records,
    get_ses_domain_status,
    is_from_email_verified,
)
from src.services.dns_validation_service import combine_mail_from_status, get_domain_dns_status
from src.models.models import SendingDomain, utc_now


class DomainError(ValueError):
    pass


REQUIRED_SENDING_STATUSES = {
    "verification_status": "SES verification",
    "dkim_status": "DKIM",
    "spf_status": "SPF",
    "dmarc_status": "DMARC",
    "mail_from_status": "MAIL FROM",
}


def normalize_domain(value: str | None):
    normalized = (value or "").strip().lower()
    if normalized.startswith("https://"):
        normalized = normalized.removeprefix("https://")
    elif normalized.startswith("http://"):
        normalized = normalized.removeprefix("http://")

    normalized = normalized.split("/", 1)[0].strip().strip(".")

    if not normalized:
        raise DomainError("Domain is required")
    if "@" in normalized or "/" in normalized or " " in normalized:
        raise DomainError("Invalid domain")
    if "." not in normalized:
        raise DomainError("Domain must include a public suffix")

    return normalized


def normalize_mail_from_domain(value: str | None, domain: str):
    normalized = normalize_domain(value)
    if normalized == domain:
        raise DomainError("MAIL FROM domain must be a subdomain")
    if not normalized.endswith(f".{domain}"):
        raise DomainError("MAIL FROM domain must belong to the sending domain")

    return normalized


def _format_datetime(value):
    return value.isoformat() if value else None


def _parse_domain_id(domain_id: str):
    try:
        return UUID(domain_id)
    except ValueError:
        return None


def _normalize_email(value: str | None):
    return (value or "").strip().lower()


def _domain_from_email(value: str | None):
    email = _normalize_email(value)
    if not email or email.count("@") != 1:
        raise DomainError("Invalid from email")

    local_part, domain = email.rsplit("@", 1)
    if not local_part or not domain:
        raise DomainError("Invalid from email")

    return normalize_domain(domain)


def serialize_domain(domain: SendingDomain):
    return {
        "id": str(domain.id),
        "user_id": domain.user_id,
        "domain": domain.domain,
        "mail_from_domain": domain.mail_from_domain,
        "verification_status": domain.verification_status,
        "dkim_status": domain.dkim_status,
        "spf_status": domain.spf_status,
        "dmarc_status": domain.dmarc_status,
        "mail_from_status": domain.mail_from_status,
        "last_checked_at": _format_datetime(domain.last_checked_at),
        "created_at": _format_datetime(domain.created_at),
        "updated_at": _format_datetime(domain.updated_at),
    }


async def create_domain_service(
    db: AsyncSession,
    user_id: str,
    domain: str,
    mail_from_domain: str,
):
    normalized_domain = normalize_domain(domain)
    normalized_mail_from_domain = normalize_mail_from_domain(
        mail_from_domain,
        normalized_domain,
    )

    existing_domain = await db.scalar(
        select(SendingDomain).where(
            SendingDomain.user_id == user_id,
            SendingDomain.domain == normalized_domain,
        )
    )
    if existing_domain:
        return None

    sending_domain = SendingDomain(
        user_id=user_id,
        domain=normalized_domain,
        mail_from_domain=normalized_mail_from_domain,
    )
    db.add(sending_domain)
    await db.commit()
    await db.refresh(sending_domain)

    return serialize_domain(sending_domain)


async def list_domains_service(db: AsyncSession, user_id: str):
    domains = await db.scalars(
        select(SendingDomain)
        .where(SendingDomain.user_id == user_id)
        .order_by(SendingDomain.created_at.desc())
    )

    return [serialize_domain(domain) for domain in domains.all()]


async def get_domain_service(db: AsyncSession, user_id: str, domain_id: str):
    parsed_domain_id = _parse_domain_id(domain_id)
    if not parsed_domain_id:
        return None

    domain = await db.scalar(
        select(SendingDomain).where(
            SendingDomain.id == parsed_domain_id,
            SendingDomain.user_id == user_id,
        )
    )

    return serialize_domain(domain) if domain else None


async def delete_domain_service(db: AsyncSession, user_id: str, domain_id: str):
    parsed_domain_id = _parse_domain_id(domain_id)
    if not parsed_domain_id:
        return False

    domain = await db.scalar(
        select(SendingDomain).where(
            SendingDomain.id == parsed_domain_id,
            SendingDomain.user_id == user_id,
        )
    )
    if not domain:
        return False

    await db.delete(domain)
    await db.commit()
    return True


def _static_setup_records(domain: SendingDomain):
    mail_from_host = domain.mail_from_domain.removesuffix(f".{domain.domain}")

    return [
        {
            "type": "TXT",
            "host": "@",
            "value": "v=spf1 include:amazonses.com -all",
            "purpose": "spf",
        },
        {
            "type": "TXT",
            "host": "_dmarc",
            "value": f"v=DMARC1; p=none; rua=mailto:dmarc@{domain.domain}",
            "purpose": "dmarc",
        },
        {
            "type": "MX",
            "host": mail_from_host,
            "value": f"10 feedback-smtp.{AWS_REGION}.amazonses.com",
            "purpose": "mail_from_mx",
        },
        {
            "type": "TXT",
            "host": mail_from_host,
            "value": "v=spf1 include:amazonses.com -all",
            "purpose": "mail_from_spf",
        },
    ]


async def get_domain_setup_records_service(db: AsyncSession, user_id: str, domain_id: str):
    parsed_domain_id = _parse_domain_id(domain_id)
    if not parsed_domain_id:
        return None

    domain = await db.scalar(
        select(SendingDomain).where(
            SendingDomain.id == parsed_domain_id,
            SendingDomain.user_id == user_id,
        )
    )
    if not domain:
        return None

    try:
        dkim_records = get_ses_dkim_setup_records(domain.domain)
    except Exception:
        dkim_records = []

    records = [
        *dkim_records,
        *_static_setup_records(domain),
    ]

    return {
        "domain_id": str(domain.id),
        "domain": domain.domain,
        "mail_from_domain": domain.mail_from_domain,
        "records": records,
    }


def _build_sending_check_report(from_email: str, email_domain: str, domain: SendingDomain | None):
    blockers = []
    warnings = []
    serialized_domain = serialize_domain(domain) if domain else None

    if not domain:
        blockers.append("Sending domain is not added to this account")
    else:
        for field, label in REQUIRED_SENDING_STATUSES.items():
            status = getattr(domain, field)
            if status != "valid":
                blockers.append(f"{label} is {status}")

        if domain.last_checked_at is None:
            warnings.append("Domain status has never been refreshed")

    return {
        "can_send": not blockers,
        "from_email": _normalize_email(from_email),
        "domain": email_domain,
        "sending_domain": serialized_domain,
        "blockers": blockers,
        "warnings": warnings,
    }

def _build_verified_email_identity_report(from_email: str, email_domain: str):
    return {
        "can_send": True,
        "from_email": _normalize_email(from_email),
        "domain": email_domain,
        "sending_domain": None,
        "verification_source": "email_identity",
        "blockers": [],
        "warnings": [],
    }

async def check_domain_for_sending_service(db: AsyncSession, user_id: str, from_email: str):
    email_domain = _domain_from_email(from_email)

    if is_from_email_verified(_normalize_email(from_email)):
        return _build_verified_email_identity_report(from_email, email_domain)

    domain = await db.scalar(
        select(SendingDomain)
        .where(
            SendingDomain.user_id == user_id,
            SendingDomain.domain == email_domain,
        )
    )

    return _build_sending_check_report(from_email, email_domain, domain)

async def refresh_domain_service(db: AsyncSession, user_id: str, domain_id: str):
    parsed_domain_id = _parse_domain_id(domain_id)
    if not parsed_domain_id:
        return None

    domain = await db.scalar(
        select(SendingDomain).where(
            SendingDomain.id == parsed_domain_id,
            SendingDomain.user_id == user_id,
        )
    )
    if not domain:
        return None

    ses_status = get_ses_domain_status(domain.domain, domain.mail_from_domain)
    dns_status = get_domain_dns_status(domain.domain, domain.mail_from_domain)
    domain.verification_status = ses_status["verification_status"]
    domain.dkim_status = ses_status["dkim_status"]
    domain.spf_status = dns_status["spf_status"]
    domain.dmarc_status = dns_status["dmarc_status"]
    domain.mail_from_status = combine_mail_from_status(
        ses_status["mail_from_status"],
        dns_status["mail_from_dns_status"],
    )
    domain.last_checked_at = utc_now()
    await db.commit()
    await db.refresh(domain)

    return serialize_domain(domain)
