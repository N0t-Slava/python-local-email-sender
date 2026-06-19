from email.message import EmailMessage
from email.utils import formataddr
from html.parser import HTMLParser

from src.services.suppression_service import build_unsubscribe_url

VALID_CONTENT_TYPES = {"plain", "html", "multipart"}

class HTMLToPlainTextParser(HTMLParser):
    BLOCK_TAGS = {
        "address",
        "article",
        "aside",
        "blockquote",
        "div",
        "footer",
        "h1",
        "h2",
        "h3",
        "h4",
        "h5",
        "h6",
        "header",
        "li",
        "main",
        "nav",
        "ol",
        "p",
        "section",
        "table",
        "tr",
        "ul",
    }

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []

    def handle_starttag(self, tag: str, attrs):
        if tag == "br":
            self.parts.append("\n")

    def handle_endtag(self, tag: str):
        if tag in self.BLOCK_TAGS:
            self.parts.append("\n")

    def handle_data(self, data: str):
        if data:
            self.parts.append(data)

    def get_text(self) -> str:
        raw_text = "".join(self.parts)
        lines = [" ".join(line.split()) for line in raw_text.splitlines()]
        lines = [line for line in lines if line]
        return "\n".join(lines)


class EmailContentValidationError(ValueError):
    pass


def validate_rendered_email_content(
    subject: str | None,
    body: str | None,
    html_body: str | None,
    content_type: str | None,
) -> str:
    if not normalize_optional_text(subject):
        raise EmailContentValidationError("Rendered subject is required")

    return validate_email_content(
        body=body,
        html_body=html_body,
        content_type=content_type,
        require_complete=True,
    )


def normalize_content_type(content_type: str | None) -> str:
    normalized = (content_type or "plain").strip().lower()

    if normalized not in VALID_CONTENT_TYPES:
        raise EmailContentValidationError(
            "content_type must be one of: plain, html, multipart"
        )

    return normalized


def normalize_optional_text(value: str | None) -> str | None:
    if value is None:
        return None

    stripped = value.strip()
    return stripped or None


def validate_email_content(
    body: str | None,
    html_body: str | None,
    content_type: str | None,
    require_complete: bool = True,
) -> str:
    normalized_content_type = normalize_content_type(content_type)

    plain_body = normalize_optional_text(body)
    normalized_html_body = normalize_optional_text(html_body)

    if not require_complete:
        return normalized_content_type

    if normalized_content_type == "plain" and not plain_body:
        raise EmailContentValidationError("Plain text body is required")

    if normalized_content_type == "html" and not normalized_html_body:
        raise EmailContentValidationError("HTML body is required")

    if normalized_content_type == "multipart" and (
        not plain_body or not normalized_html_body
    ):
        raise EmailContentValidationError(
            "Multipart emails require both plain text body and HTML body"
        )

    return normalized_content_type


def validate_email_message_input(
    to: str | None,
    subject: str | None,
    from_email: str | None,
    body: str | None,
    html_body: str | None,
    content_type: str | None,
    require_complete: bool = True,
) -> str:
    if not normalize_optional_text(to):
        raise EmailContentValidationError("Recipient email is required")

    if not normalize_optional_text(subject):
        raise EmailContentValidationError("Subject is required")

    if not normalize_optional_text(from_email):
        raise EmailContentValidationError("From email is required")

    return validate_email_content(
        body=body,
        html_body=html_body,
        content_type=content_type,
        require_complete=require_complete,
    )


def html_to_plain_text(html_body: str | None) -> str:
    parser = HTMLToPlainTextParser()
    parser.feed(html_body or "")
    parser.close()
    return parser.get_text()


def append_unsubscribe_link(body: str | None, to: str, user_id: str | None):
    if not user_id:
        return body or ""

    unsubscribe_url = build_unsubscribe_url(to, user_id)
    body = body or ""
    return f"{body}\n\nUnsubscribe: {unsubscribe_url}"


def append_unsubscribe_link_html(html_body: str | None, to: str, user_id: str | None):
    if not user_id:
        return html_body or ""

    unsubscribe_url = build_unsubscribe_url(to, user_id)
    html_body = html_body or ""
    return f'{html_body}<p><a href="{unsubscribe_url}">Unsubscribe</a></p>'


def build_email_content_parts(
    body: str | None,
    html_body: str | None,
    content_type: str | None,
    to: str,
    user_id: str | None = None,
):
    normalized_content_type = normalize_content_type(content_type)

    if normalized_content_type == "html":
        plain = html_to_plain_text(html_body)
        return {
            "plain": append_unsubscribe_link(plain, to, user_id),
            "html": append_unsubscribe_link_html(html_body, to, user_id),
        }

    if normalized_content_type == "multipart":
        return {
            "plain": append_unsubscribe_link(body, to, user_id),
            "html": append_unsubscribe_link_html(html_body, to, user_id),
        }

    return {
        "plain": append_unsubscribe_link(body, to, user_id),
        "html": None,
    }


def build_email_message(
    to: str,
    subject: str,
    body: str | None,
    from_email: str,
    from_name: str | None = None,
    reply_to_email: str | None = None,
    html_body: str | None = None,
    content_type: str | None = "plain",
    user_id: str | None = None,
):
    msg = EmailMessage()
    msg["From"] = formataddr((from_name.strip(), from_email)) if from_name and from_name.strip() else from_email
    msg["To"] = to
    msg["Subject"] = subject
    if reply_to_email and reply_to_email.strip():
        msg["Reply-To"] = reply_to_email.strip()

    content_type = validate_email_message_input(
        to=to,
        subject=subject,
        from_email=from_email,
        body=body,
        html_body=html_body,
        content_type=content_type,
    )

    content_parts = build_email_content_parts(
        body=body,
        html_body=html_body,
        content_type=content_type,
        to=to,
        user_id=user_id,
    )

    msg.set_content(content_parts["plain"])

    if content_parts["html"]:
        msg.add_alternative(content_parts["html"], subtype="html")

    return msg
