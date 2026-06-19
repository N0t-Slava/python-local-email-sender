from src.services.email_content_service import build_email_message, validate_email_content
from src.services.smtp_connection_service import open_smtp_connection

def send_email(
    to: str,
    subject: str,
    body: str,
    from_email: str,
    attachments: list = None,
    timeout: int = 30,
    html_body: str | None = None,
    content_type: str = "plain",
    from_name: str | None = None,
    reply_to_email: str | None = None,
):
    """
    attachments: list of dicts {'filename': str, 'content': bytes, 'mime_type': 'image/png'}
    """
    content_type = validate_email_content(
        body=body,
        html_body=html_body,
        content_type=content_type,
    )

    msg = build_email_message(
        to=to,
        subject=subject,
        body=body,
        from_email=from_email,
        from_name=from_name,
        reply_to_email=reply_to_email,
        html_body=html_body,
        content_type=content_type,
    )

    if attachments:
        for a in attachments:
            filename = a["filename"]
            content = a["content"]
            mime_type = a.get("mime_type", "application/octet-stream")
            maintype, subtype = mime_type.split("/", 1)
            msg.add_attachment(content, maintype=maintype, subtype=subtype, filename=filename)

    with open_smtp_connection(timeout=timeout)[0] as smtp:
        smtp.send_message(msg)
