import hashlib
import hmac
import json
from uuid import UUID
from base64 import urlsafe_b64decode, urlsafe_b64encode
from html.parser import HTMLParser
from html import escape
from urllib.parse import urlparse

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.configs.config import (
    EMAIL_EVENT_CLICK,
    EMAIL_EVENT_OPEN,
    PUBLIC_API_BASE_URL,
    TRACKING_SECRET,
)
from src.models.models import Campaign, EmailEvent, utc_now


class TrackingTokenError(ValueError):
    pass

def _normalize_event_type(event_type: str) -> str:
    if event_type == "open":
        return EMAIL_EVENT_OPEN

    if event_type == "click":
        return EMAIL_EVENT_CLICK

    raise TrackingTokenError("Invalid tracking event")

def build_tracking_metadata(
    user_agent: str | None = None,
    ip_address: str | None = None,
    target_url: str | None = None,
) -> dict:
    metadata = {}

    if user_agent:
        metadata["user_agent"] = user_agent

    if ip_address:
        metadata["ip_address"] = ip_address

    if target_url:
        metadata["target_url"] = target_url

    return metadata

def _parse_uuid(value: str | None):
    if not value:
        return None

    try:
        return UUID(str(value))
    except (TypeError, ValueError):
        return None

def _urlsafe_b64encode(value: str) -> str:
    return urlsafe_b64encode(value.encode("utf-8")).decode("ascii").rstrip("=")


def _urlsafe_b64decode(value: str) -> str:
    padding = "=" * (-len(value) % 4)
    return urlsafe_b64decode(f"{value}{padding}".encode("ascii")).decode("utf-8")


def _sign_payload(encoded_payload: str) -> str:
    return hmac.new(
        TRACKING_SECRET.encode("utf-8"),
        encoded_payload.encode("ascii"),
        hashlib.sha256,
    ).hexdigest()


def generate_tracking_token(payload: dict) -> str:
    encoded_payload = _urlsafe_b64encode(
        json.dumps(payload, separators=(",", ":"), sort_keys=True)
    )
    signature = _sign_payload(encoded_payload)
    return f"{encoded_payload}.{signature}"


def verify_tracking_token(token: str) -> dict:
    if not token or "." not in token:
        raise TrackingTokenError("Invalid tracking token")

    encoded_payload, signature = token.split(".", 1)
    expected_signature = _sign_payload(encoded_payload)

    if not hmac.compare_digest(expected_signature, signature):
        raise TrackingTokenError("Invalid tracking token")

    try:
        decoded_payload = _urlsafe_b64decode(encoded_payload)
        payload = json.loads(decoded_payload)
    except Exception as exc:
        raise TrackingTokenError("Invalid tracking token") from exc

    if not isinstance(payload, dict):
        raise TrackingTokenError("Invalid tracking token")

    return payload

def build_open_tracking_url(
    campaign_id: str,
    recipient_id: str,
    user_id: str,
    email: str,
    attempt_id: str | None = None,
) -> str:
    token = generate_tracking_token({
        "event": "open",
        "campaign_id": campaign_id,
        "recipient_id": recipient_id,
        "user_id": user_id,
        "email": email,
        "attempt_id": attempt_id,
    })
    return f"{PUBLIC_API_BASE_URL}/track/open/{token}.gif"

def build_click_tracking_url(
    campaign_id: str,
    recipient_id: str,
    user_id: str,
    email: str,
    target_url: str,
    attempt_id: str | None = None,
) -> str:
    token = generate_tracking_token({
        "event": "click",
        "campaign_id": campaign_id,
        "recipient_id": recipient_id,
        "user_id": user_id,
        "email": email,
        "attempt_id": attempt_id,
        "target_url": target_url,
    })
    return f"{PUBLIC_API_BASE_URL}/track/click/{token}"

def _is_trackable_url(url: str | None) -> bool:
    if not url:
        return False

    parsed_url = urlparse(url)
    if parsed_url.scheme not in {"http", "https"}:
        return False

    path = parsed_url.path.lower()
    if path.startswith("/track/") or path.startswith("/unsubscribe"):
        return False

    return True
    
class ClickTrackingHTMLParser(HTMLParser):
    def __init__(
        self,
        campaign_id: str,
        recipient_id: str,
        user_id: str,
        email: str,
        attempt_id: str | None = None,
    ):
        super().__init__(convert_charrefs=False)
        self.campaign_id = campaign_id
        self.recipient_id = recipient_id
        self.user_id = user_id
        self.email = email
        self.attempt_id = attempt_id
        self.parts: list[str] = []

    def handle_starttag(self, tag: str, attrs):
        self.parts.append(self._format_start_tag(tag, attrs, closed=False))

    def handle_startendtag(self, tag: str, attrs):
        self.parts.append(self._format_start_tag(tag, attrs, closed=True))

    def handle_endtag(self, tag: str):
        self.parts.append(f"</{tag}>")

    def handle_data(self, data: str):
        self.parts.append(data)

    def handle_entityref(self, name: str):
        self.parts.append(f"&{name};")

    def handle_charref(self, name: str):
        self.parts.append(f"&#{name};")

    def handle_comment(self, data: str):
        self.parts.append(f"<!--{data}-->")

    def _format_start_tag(self, tag: str, attrs, closed: bool) -> str:
        formatted_attrs = []

        for name, value in attrs:
            attr_value = value

            if tag.lower() == "a" and name.lower() == "href" and _is_trackable_url(value):
                attr_value = build_click_tracking_url(
                    campaign_id=self.campaign_id,
                    recipient_id=self.recipient_id,
                    user_id=self.user_id,
                    email=self.email,
                    target_url=value,
                    attempt_id=self.attempt_id,
                )

            if attr_value is None:
                formatted_attrs.append(name)
            else:
                formatted_attrs.append(f'{name}="{escape(attr_value, quote=True)}"')

        attrs_text = f" {' '.join(formatted_attrs)}" if formatted_attrs else ""
        closing = " /" if closed else ""
        return f"<{tag}{attrs_text}{closing}>"

    def get_html(self) -> str:
        return "".join(self.parts)
    
def rewrite_click_tracking_links(
    html_body: str | None,
    campaign_id: str,
    recipient_id: str,
    user_id: str,
    email: str,
    attempt_id: str | None = None,
) -> str | None:
    if not html_body:
        return html_body

    parser = ClickTrackingHTMLParser(
        campaign_id=campaign_id,
        recipient_id=recipient_id,
        user_id=user_id,
        email=email,
        attempt_id=attempt_id,
    )
    parser.feed(html_body)
    parser.close()
    return parser.get_html()

def append_open_tracking_pixel(
    html_body: str | None,
    campaign_id: str,
    recipient_id: str,
    user_id: str,
    email: str,
    attempt_id: str | None = None,
) -> str | None:
    if not html_body:
        return html_body

    open_tracking_url = build_open_tracking_url(
        campaign_id=campaign_id,
        recipient_id=recipient_id,
        user_id=user_id,
        email=email,
        attempt_id=attempt_id,
    )
    pixel = (
        f'<img src="{escape(open_tracking_url, quote=True)}" '
        'width="1" height="1" border="0" alt="" '
        'style="display:block;width:1px;height:1px;max-width:1px;'
        'max-height:1px;overflow:hidden;border:0;outline:none;'
        'text-decoration:none;margin:0;padding:0;line-height:0;font-size:0;" />'
    )

    body_close_index = html_body.lower().rfind("</body>")
    if body_close_index == -1:
        return f"{html_body}{pixel}"

    return f"{html_body[:body_close_index]}{pixel}{html_body[body_close_index:]}"

def instrument_email_tracking(
    html_body: str | None,
    campaign_id: str,
    recipient_id: str,
    user_id: str,
    email: str,
    attempt_id: str | None = None,
    track_opens: bool = True,
    track_clicks: bool = True,
) -> str | None:
    tracked_html = html_body

    if track_clicks:
        tracked_html = rewrite_click_tracking_links(
            tracked_html,
            campaign_id=campaign_id,
            recipient_id=recipient_id,
            user_id=user_id,
            email=email,
            attempt_id=attempt_id,
        )

    if track_opens:
        tracked_html = append_open_tracking_pixel(
            tracked_html,
            campaign_id=campaign_id,
            recipient_id=recipient_id,
            user_id=user_id,
            email=email,
            attempt_id=attempt_id,
        )

    return tracked_html

async def refresh_campaign_tracking_counts(db: AsyncSession, campaign_id):
    parsed_campaign_id = _parse_uuid(campaign_id)
    if not parsed_campaign_id:
        return None

    campaign = await db.get(Campaign, parsed_campaign_id)
    if not campaign:
        return None

    opened_count = await db.scalar(
        select(func.count(func.distinct(EmailEvent.recipient_id))).where(
            EmailEvent.campaign_id == campaign.id,
            EmailEvent.event_type == EMAIL_EVENT_OPEN,
        )
    )

    clicked_count = await db.scalar(
        select(func.count(func.distinct(EmailEvent.recipient_id))).where(
            EmailEvent.campaign_id == campaign.id,
            EmailEvent.event_type == EMAIL_EVENT_CLICK,
        )
    )

    campaign.opened_count = int(opened_count or 0)
    campaign.clicked_count = int(clicked_count or 0)
    return campaign

async def record_tracking_event(
    db: AsyncSession,
    payload: dict,
    metadata: dict | None = None,
) -> EmailEvent:
    event_type = _normalize_event_type(payload.get("event"))
    campaign_id = _parse_uuid(payload.get("campaign_id"))
    recipient_id = _parse_uuid(payload.get("recipient_id"))

    if not campaign_id or not recipient_id:
        raise TrackingTokenError("Invalid tracking token")

    raw_payload = {
        "tracking": payload,
        "metadata": metadata or {},
    }

    event = EmailEvent(
        event_type=event_type,
        email=payload.get("email") or "",
        user_id=payload.get("user_id"),
        campaign_id=campaign_id,
        recipient_id=recipient_id,
        attempt_id=payload.get("attempt_id"),
        raw_payload=json.dumps(raw_payload, default=str),
        occurred_at=utc_now(),
    )
    db.add(event)

    await db.flush()
    await refresh_campaign_tracking_counts(db, campaign_id)

    await db.commit()
    return event
