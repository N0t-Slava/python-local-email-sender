from typing import Optional

from pydantic import BaseModel, Field


class EmailTemplateCreate(BaseModel):
    name: str
    subject: str
    body: str = ""
    html_body: Optional[str] = None
    content_type: str = "plain"


class EmailTemplateUpdate(BaseModel):
    name: Optional[str] = None
    subject: Optional[str] = None
    body: Optional[str] = None
    html_body: Optional[str] = None
    content_type: Optional[str] = None


class EmailTemplateResponse(BaseModel):
    id: str
    user_id: str
    name: str
    subject: str
    body: str
    html_body: Optional[str] = None
    content_type: str
    created_at: str
    updated_at: Optional[str] = None


class EmailTemplatePreviewContact(BaseModel):
    id: Optional[str] = None
    email: str = "recipient@example.com"
    name: str = "Recipient"


class EmailTemplatePreviewRequest(BaseModel):
    subject: str
    body: str = ""
    html_body: Optional[str] = None
    content_type: str = "plain"
    contact: EmailTemplatePreviewContact = Field(default_factory=EmailTemplatePreviewContact)
    variables: dict[str, object] = Field(default_factory=dict)


class EmailTemplatePreviewResponse(BaseModel):
    subject: str
    body: str
    html_body: Optional[str] = None
    content_type: str
