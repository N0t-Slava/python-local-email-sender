import csv
import io

from src.services.contacts_service import is_valid_email


def _decode_csv_content(content: bytes) -> str:
    try:
        return content.decode("utf-8")
    except UnicodeDecodeError:
        return content.decode("latin-1")


def parse_campaign_recipients_csv(
    content: bytes,
    allow_empty: bool = False,
    reject_invalid: bool = True,
):
    text = _decode_csv_content(content)
    reader = csv.DictReader(io.StringIO(text))
    recipients = []
    invalid_recipients = []
    duplicate_count = 0
    seen_emails = set()
    columns = [column for column in (reader.fieldnames or []) if column]

    if "email" not in columns:
        if allow_empty:
            return {
                "recipients": [],
                "invalid_emails": [],
                "duplicate_count": 0,
                "columns": columns,
            }
        raise ValueError("CSV must include an email column")

    for row in reader:
        raw_email = (row.get("email") or "").strip()
        if not raw_email:
            continue

        if not is_valid_email(raw_email):
            invalid_recipients.append(raw_email)
            continue

        normalized_email = raw_email.lower()
        if normalized_email in seen_emails:
            duplicate_count += 1
            continue

        seen_emails.add(normalized_email)
        variables = {
            key: value.strip()
            for key, value in row.items()
            if key and key != "email" and value and value.strip()
        }
        recipients.append({
            "email": raw_email,
            "variables": variables,
        })

    if not recipients and not allow_empty:
        raise ValueError("Campaign must include at least one valid recipient email")

    if invalid_recipients and reject_invalid:
        raise ValueError(f"Invalid recipient emails: {', '.join(invalid_recipients)}")

    return {
        "recipients": recipients,
        "invalid_emails": invalid_recipients,
        "duplicate_count": duplicate_count,
        "columns": columns,
    }
