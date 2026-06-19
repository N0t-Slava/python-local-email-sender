import uuid
from datetime import UTC, datetime

from sqlalchemy import Column, DateTime, Float, ForeignKey, Index, Integer, JSON, String, Table, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.database.sqlalchemy import SQLBase


def utc_now():
    return datetime.now(UTC).replace(tzinfo=None)


# Таблица связей (Many-to-Many)
contact_tags = Table(
    "contact_tags",
    SQLBase.metadata,
    Column("contact_id", ForeignKey("contacts.id", ondelete="CASCADE"), primary_key=True),
    Column("tag_id", ForeignKey("tags.id", ondelete="CASCADE"), primary_key=True),
)


class Contact(SQLBase):
    __tablename__ = "contacts"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[str] = mapped_column(String, index=True)
    email: Mapped[str] = mapped_column(String, index=True)
    name: Mapped[str] = mapped_column(String, default="")
    status: Mapped[str] = mapped_column(String, default="subscribed")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, onupdate=utc_now)

    tags: Mapped[list["Tag"]] = relationship(secondary=contact_tags, back_populates="contacts")

    __table_args__ = (UniqueConstraint("user_id", "email", name="_user_email_uc"),)


class Campaign(SQLBase):
    __tablename__ = "campaigns"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[str] = mapped_column(String, index=True)
    task_id: Mapped[str | None] = mapped_column(String, nullable=True)
    subject: Mapped[str] = mapped_column(String)
    body: Mapped[str] = mapped_column(Text)
    from_email: Mapped[str] = mapped_column(String)
    from_name: Mapped[str | None] = mapped_column(String, nullable=True)
    reply_to_email: Mapped[str | None] = mapped_column(String, nullable=True)
    html_body: Mapped[str | None] = mapped_column(Text, nullable=True)
    content_type: Mapped[str] = mapped_column(String, default="plain")
    status: Mapped[str] = mapped_column(String, default="Draft")
    queued_recipients: Mapped[int] = mapped_column(Integer, default=0)
    sent_count: Mapped[int] = mapped_column(Integer, default=0)
    opened_count: Mapped[int] = mapped_column(Integer, default=0)
    clicked_count: Mapped[int] = mapped_column(Integer, default=0)
    bounce_count: Mapped[int] = mapped_column(Integer, default=0)
    complaint_count: Mapped[int] = mapped_column(Integer, default=0)
    batch_size: Mapped[int | None] = mapped_column(Integer, nullable=True)
    per_batch_delay: Mapped[float | None] = mapped_column(Float, nullable=True)
    send_rate_per_second: Mapped[float | None] = mapped_column(Float, nullable=True)
    track_opens: Mapped[bool] = mapped_column(default=True)
    track_clicks: Mapped[bool] = mapped_column(default=True)
    category: Mapped[str | None] = mapped_column(String, nullable=True)
    tags: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, onupdate=utc_now)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    scheduled_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    recipients: Mapped[list["CampaignRecipient"]] = relationship(
        back_populates="campaign",
        cascade="all, delete-orphan",
        order_by="CampaignRecipient.created_at",
    )


class CampaignRecipient(SQLBase):
    __tablename__ = "campaign_recipients"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    campaign_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("campaigns.id", ondelete="CASCADE"), index=True)
    contact_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("contacts.id", ondelete="SET NULL"), nullable=True)
    email: Mapped[str] = mapped_column(String)
    __table_args__ = (
        UniqueConstraint("campaign_id", "email", name="_campaign_email_uc"),
        Index(
            "ix_campaign_recipients_claim",
            "campaign_id",
            "status",
            "attempt_count",
            "created_at",
        ),
    )
    batch_id: Mapped[str | None] = mapped_column(String, nullable=True)
    attempt_id: Mapped[str | None] = mapped_column(String, nullable=True)
    sending_started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    status: Mapped[str] = mapped_column(String, default="queued")
    sent_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    error_message: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    campaign: Mapped[Campaign] = relationship(back_populates="recipients")
    contact: Mapped[Contact | None] = relationship()
    attempt_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    variables: Mapped[dict | None] = mapped_column(JSON, nullable=True)


class Tag(SQLBase):
    __tablename__ = "tags"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[str] = mapped_column()
    name: Mapped[str] = mapped_column()
    
    contacts: Mapped[list["Contact"]] = relationship(secondary=contact_tags, back_populates="tags")
    
    __table_args__ = (UniqueConstraint('owner_id', 'name', name='_owner_tag_uc'),)


class SuppressionListEntry(SQLBase):
    __tablename__ = "suppression_list"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[str | None] = mapped_column(String, index=True, nullable=True)
    email: Mapped[str] = mapped_column(String, index=True)
    reason: Mapped[str | None] = mapped_column(String, nullable=True)
    source: Mapped[str] = mapped_column(String, index=True)
    status: Mapped[str] = mapped_column(String, index=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by_user_id: Mapped[str | None] = mapped_column(String, nullable=True)
    first_seen_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, onupdate=utc_now)

    __table_args__ = (UniqueConstraint("user_id", "email", name="_suppression_list_user_email_uc"),)

class SuppressionSyncRun(SQLBase):
    __tablename__ = "suppression_sync_runs"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    source: Mapped[str] = mapped_column(String, index=True)
    status: Mapped[str] = mapped_column(String, index=True)
    started_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    synced: Mapped[int] = mapped_column(Integer, default=0)
    created_count: Mapped[int] = mapped_column(Integer, default=0)
    updated_count: Mapped[int] = mapped_column(Integer, default=0)
    skipped_count: Mapped[int] = mapped_column(Integer, default=0)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

class EmailEvent(SQLBase):
    __tablename__ = "email_events"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    event_type: Mapped[str] = mapped_column(String, index=True)
    email: Mapped[str] = mapped_column(String, index=True)
    user_id: Mapped[str | None] = mapped_column(String, index=True, nullable=True)
    campaign_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("campaigns.id", ondelete="CASCADE"), index=True, nullable=True)
    recipient_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("campaign_recipients.id", ondelete="SET NULL"), index=True, nullable=True)
    attempt_id: Mapped[str | None] = mapped_column(String, nullable=True)
    ses_message_id: Mapped[str | None] = mapped_column(String, index=True, nullable=True)
    sns_message_id: Mapped[str | None] = mapped_column(String, index=True, nullable=True)
    bounce_type: Mapped[str | None] = mapped_column(String, nullable=True)
    bounce_subtype: Mapped[str | None] = mapped_column(String, nullable=True)
    complaint_feedback_type: Mapped[str | None] = mapped_column(String, nullable=True)
    diagnostic_code: Mapped[str | None] = mapped_column(Text, nullable=True)
    raw_payload: Mapped[str | None] = mapped_column(Text, nullable=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)

    __table_args__ = (
        UniqueConstraint("sns_message_id", "event_type", "email", name="_sns_event_email_uc"),
    )

class EmailTemplate(SQLBase):
    __tablename__ = "email_templates"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[str] = mapped_column(String, index=True)
    name: Mapped[str] = mapped_column(String)
    subject: Mapped[str] = mapped_column(String)
    body: Mapped[str] = mapped_column(Text, default="")
    html_body: Mapped[str | None] = mapped_column(Text, nullable=True)
    content_type: Mapped[str] = mapped_column(String, default="plain")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, onupdate=utc_now)

    __table_args__ = (UniqueConstraint("user_id", "name", name="_user_template_name_uc"),)

class SendingDomain(SQLBase):
    __tablename__ = "sending_domains"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[str] = mapped_column(String, index=True)
    domain: Mapped[str] = mapped_column(String)
    mail_from_domain: Mapped[str] = mapped_column(String)
    verification_status: Mapped[str] = mapped_column(String, default="unknown")
    dkim_status: Mapped[str] = mapped_column(String, default="unknown")
    spf_status: Mapped[str] = mapped_column(String, default="unknown")
    dmarc_status: Mapped[str] = mapped_column(String, default="unknown")
    mail_from_status: Mapped[str] = mapped_column(String, default="unknown")
    last_checked_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, onupdate=utc_now)

    __table_args__ = (
        UniqueConstraint("user_id", "domain", name="_user_domain_uc"),
    )
