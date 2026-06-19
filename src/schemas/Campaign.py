from typing import Optional

from pydantic import BaseModel, Field


class CampaignResponse(BaseModel):
    id: str
    user_id: str
    task_id: Optional[str] = None
    subject: str
    body: str
    from_email: str
    from_name: Optional[str] = None
    reply_to_email: Optional[str] = None
    html_body: Optional[str] = None
    content_type: str = "plain"
    queued_recipients: int
    status: str
    created_at: str
    recipients: list[str] = Field(default_factory=list)
    batch_size: Optional[int] = None
    per_batch_delay: Optional[float] = None
    send_rate_per_second: Optional[float] = None
    track_opens: bool = True
    track_clicks: bool = True
    category: Optional[str] = None
    tags: list[str] = Field(default_factory=list)
    sent_count: int = 0
    opened_count: int = 0
    clicked_count: int = 0
    updated_at: Optional[str] = None
    sent_at: Optional[str] = None
    scheduled_at: Optional[str] = None
