import dns.exception
import dns.resolver

from src.configs.config import AWS_REGION


DNS_TIMEOUT_SECONDS = 3
AMAZON_SES_SPF_INCLUDE = "include:amazonses.com"


def _resolver():
    resolver = dns.resolver.Resolver()
    resolver.timeout = DNS_TIMEOUT_SECONDS
    resolver.lifetime = DNS_TIMEOUT_SECONDS
    return resolver


def _status(status: str, details: str | None = None):
    return {
        "status": status,
        "details": details,
    }


def get_txt_records(name: str):
    try:
        answers = _resolver().resolve(name, "TXT")
    except dns.resolver.NXDOMAIN:
        return []
    except dns.resolver.NoAnswer:
        return []
    except dns.exception.DNSException:
        raise

    records = []
    for answer in answers:
        records.append("".join(part.decode("utf-8") for part in answer.strings))

    return records


def get_mx_records(name: str):
    try:
        answers = _resolver().resolve(name, "MX")
    except dns.resolver.NXDOMAIN:
        return []
    except dns.resolver.NoAnswer:
        return []
    except dns.exception.DNSException:
        raise

    records = []
    for answer in answers:
        records.append({
            "preference": int(answer.preference),
            "exchange": str(answer.exchange).rstrip(".").lower(),
        })

    return records


def _find_spf_records(name: str):
    return [
        record.strip()
        for record in get_txt_records(name)
        if record.strip().lower().startswith("v=spf1")
    ]


def validate_spf(domain: str):
    try:
        spf_records = _find_spf_records(domain)
    except dns.exception.DNSException as exc:
        return _status("unknown", str(exc))

    if not spf_records:
        return _status("missing", "SPF TXT record is missing")
    if len(spf_records) > 1:
        return _status("invalid", "Multiple SPF records found")

    spf_record = spf_records[0].lower()
    if AMAZON_SES_SPF_INCLUDE not in spf_record:
        return _status("invalid", "SPF record does not include amazonses.com")

    return _status("valid")


def validate_dmarc(domain: str):
    dmarc_name = f"_dmarc.{domain}"
    try:
        dmarc_records = [
            record.strip()
            for record in get_txt_records(dmarc_name)
            if record.strip().lower().startswith("v=dmarc1")
        ]
    except dns.exception.DNSException as exc:
        return _status("unknown", str(exc))

    if not dmarc_records:
        return _status("missing", "DMARC TXT record is missing")
    if len(dmarc_records) > 1:
        return _status("invalid", "Multiple DMARC records found")

    dmarc_record = dmarc_records[0].lower()
    if "p=" not in dmarc_record:
        return _status("invalid", "DMARC policy is missing")

    return _status("valid")


def _expected_ses_feedback_host():
    return f"feedback-smtp.{AWS_REGION}.amazonses.com"


def validate_mail_from_dns(mail_from_domain: str):
    expected_mx_host = _expected_ses_feedback_host()

    try:
        mx_records = get_mx_records(mail_from_domain)
        spf_status = validate_spf(mail_from_domain)
    except dns.exception.DNSException as exc:
        return _status("unknown", str(exc))

    matching_mx = any(
        record["preference"] == 10 and record["exchange"] == expected_mx_host
        for record in mx_records
    )
    if not matching_mx:
        return _status("missing", "MAIL FROM MX record is missing")

    if spf_status["status"] != "valid":
        return _status(spf_status["status"], spf_status.get("details"))

    return _status("valid")


def combine_mail_from_status(ses_status: str, dns_status: str):
    if ses_status == "invalid" or dns_status == "invalid":
        return "invalid"
    if ses_status == "failed" or dns_status == "failed":
        return "failed"
    if ses_status == "missing" or dns_status == "missing":
        return "missing"
    if ses_status == "pending" or dns_status == "pending":
        return "pending"
    if ses_status == "unknown" or dns_status == "unknown":
        return "unknown"
    if ses_status == "valid" and dns_status == "valid":
        return "valid"

    return "unknown"


def get_domain_dns_status(domain: str, mail_from_domain: str):
    spf_status = validate_spf(domain)
    dmarc_status = validate_dmarc(domain)
    mail_from_status = validate_mail_from_dns(mail_from_domain)

    return {
        "spf_status": spf_status["status"],
        "dmarc_status": dmarc_status["status"],
        "mail_from_dns_status": mail_from_status["status"],
    }
