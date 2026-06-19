import boto3
from src.configs.config import AWS_REGION
from botocore.exceptions import ClientError


def get_ses_client():
    return boto3.client("sesv2", region_name=AWS_REGION)

def get_ses_account():
    client = get_ses_client()
    return client.get_account()

def is_ses_sending_enabled():
    account = get_ses_account()
    return account.get("SendingEnabled") is True


def _domain_from_email(email: str | None):
    normalized_email = (email or "").strip().lower()
    if "@" not in normalized_email:
        return None

    local_part, domain = normalized_email.rsplit("@", 1)
    if not local_part or not domain:
        return None

    return domain


def is_from_email_verified(from_email: str):
    identity = get_ses_identity(from_email)
    return bool(identity and identity.get("VerifiedForSendingStatus"))


def is_sender_verified(from_email: str):
    if is_from_email_verified(from_email):
        return True

    domain = _domain_from_email(from_email)
    if not domain:
        return False

    identity = get_ses_domain_identity(domain)
    return bool(identity and identity.get("VerifiedForSendingStatus"))


def get_ses_identity(from_email: str):
    client = get_ses_client()
    try:
        response = client.get_email_identity(
            EmailIdentity=from_email
        )
        return response
    except ClientError as e:
        if e.response['Error']['Code'] == 'NotFoundException':
            return None
        raise


def get_ses_domain_identity(domain: str):
    return get_ses_identity(domain)


def _map_ses_identity_status(identity: dict | None):
    if not identity:
        return "missing"

    return "valid" if identity.get("VerifiedForSendingStatus") is True else "pending"


def _map_ses_dkim_status(identity: dict | None):
    if not identity:
        return "missing"

    dkim_attributes = identity.get("DkimAttributes") or {}
    status = (dkim_attributes.get("Status") or "").lower()

    if status == "success":
        return "valid"
    if status in {"pending", "not_started"}:
        return "pending"
    if status in {"failed", "temporary_failure"}:
        return "failed"

    return "unknown"


def _map_ses_mail_from_status(identity: dict | None, mail_from_domain: str | None = None):
    if not identity:
        return "missing"

    mail_from_attributes = identity.get("MailFromAttributes") or {}
    configured_mail_from_domain = mail_from_attributes.get("MailFromDomain")
    status = (mail_from_attributes.get("MailFromDomainStatus") or "").lower()

    if not configured_mail_from_domain:
        return "missing"
    if mail_from_domain and configured_mail_from_domain.lower() != mail_from_domain.lower():
        return "invalid"
    if status == "success":
        return "valid"
    if status in {"pending", "temporary_failure"}:
        return "pending"
    if status == "failed":
        return "failed"

    return "unknown"


def get_ses_domain_status(domain: str, mail_from_domain: str | None = None):
    identity = get_ses_domain_identity(domain)
    return {
        "verification_status": _map_ses_identity_status(identity),
        "dkim_status": _map_ses_dkim_status(identity),
        "mail_from_status": _map_ses_mail_from_status(identity, mail_from_domain),
    }


def get_ses_dkim_setup_records(domain: str):
    identity = get_ses_domain_identity(domain)
    dkim_attributes = (identity or {}).get("DkimAttributes") or {}
    tokens = dkim_attributes.get("Tokens") or []

    return [
        {
            "type": "CNAME",
            "host": f"{token}._domainkey",
            "value": f"{token}.dkim.amazonses.com",
            "purpose": "dkim",
        }
        for token in tokens
    ]

def list_ses_suppressed_destinations():
    client = get_ses_client()
    suppressed = []
    next_token = None

    while True:
        params = {}
        if next_token:
            params["NextToken"] = next_token

        response = client.list_suppressed_destinations(**params)
        for item in response.get("SuppressedDestinationSummaries", []):
            suppressed.append({
                "email": item.get("EmailAddress"),
                "reason": item.get("Reason"),
                "last_update_time": item.get("LastUpdateTime"),
            })

        next_token = response.get("NextToken")
        if not next_token:
            break

    return suppressed

def get_quota():
    account = get_ses_account()
    quota = account.get("SendQuota") or {}
    max_24h_send = quota.get("Max24HourSend")
    sent_last_24h = quota.get("SentLast24Hours")
    remaining_24h = max_24h_send

    if max_24h_send is not None and sent_last_24h is not None:
        remaining_24h = max(0, max_24h_send - sent_last_24h)

    return {
        "max_24h_send": max_24h_send,
        "sent_last_24h": sent_last_24h,
        "remaining_24h": remaining_24h,
        "max_send_rate": quota.get("MaxSendRate"),
    }


def get_quota_max_send_rate():
    return get_quota().get("max_send_rate")


def get_quota_per_email_delay():
    max_send_rate = get_quota_max_send_rate()
    if not max_send_rate or max_send_rate <= 0:
        return None

    return 1 / (max_send_rate * 0.8)


def validate_ses_preflight(from_email: str = None, recipient_emails: list = None):
    account = get_ses_account()
    sending = account.get("SendingEnabled") is True
    quota = get_quota()
    remaining_24h = quota.get("remaining_24h")
    recipient_count = len(recipient_emails or [])

    sender_verified = is_sender_verified(from_email)

    if not sender_verified or not sending:
        return False

    if remaining_24h is not None and recipient_count > remaining_24h:
        return False

    return True

def build_ses_alerts(status):
    alerts = []
    quota = status.get("quota") or {}
    max_24h_send = quota.get("max_24h_send")
    remaining_24h = quota.get("remaining_24h")
    max_send_rate = quota.get("max_send_rate")

    if not status.get("sending_enabled"):
        alerts.append({
            "level": "error",
            "code": "ses_sending_disabled",
            "message": "SES sending is disabled",
        })

    if not status.get("sender_verified"):
        alerts.append({
            "level": "error",
            "code": "ses_sender_not_verified",
            "message": "Sender email or domain is not verified in SES",
        })

    if status.get("mode") == "sandbox":
        alerts.append({
            "level": "warning",
            "code": "ses_sandbox_mode",
            "message": "SES account is in sandbox mode",
        })

    if remaining_24h == 0:
        alerts.append({
            "level": "error",
            "code": "ses_daily_quota_exhausted",
            "message": "SES daily quota exhausted"
        })
    elif max_24h_send and remaining_24h is not None:
        near_email_send_limit = remaining_24h / max_24h_send <= 0.1
        if near_email_send_limit:
            alerts.append({
                "level": "warning",
                "code": "ses_daily_quota_low",
                "message": "SES daily quota is almost exhausted",
            })

    if max_send_rate is not None and max_send_rate <= 1:
        alerts.append({
            "level": "warning",
            "code": "ses_send_rate_low",
            "message": "SES send rate is very low",
        })

    return alerts

def get_ses_dashboard_status_from_email(from_email: str):
    client = get_ses_client()
    account = get_ses_account()
    identity = get_ses_identity(from_email)

    quota = get_quota()

    production_access_enabled = account.get("ProductionAccessEnabled") is True
    mode = "production" if production_access_enabled else "sandbox"

    status = {
        "region": client.meta.region_name,
        "sending_enabled": account.get("SendingEnabled") is True,
        "production_access_enabled": production_access_enabled,
        "mode": mode,
        "from_email": from_email,
        "from_email_verified": bool(identity and identity.get("VerifiedForSendingStatus")),
        "sender_verified": is_sender_verified(from_email),
        "quota": quota,
    }
    status["alerts"] = build_ses_alerts(status)
    return status
