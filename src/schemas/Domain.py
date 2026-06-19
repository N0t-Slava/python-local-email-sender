from pydantic import BaseModel, Field


class Domain(BaseModel):
    domain: str


class DomainCreate(Domain):
    mail_from_domain: str


class DomainResponse(Domain):
    id: str
    user_id: str
    mail_from_domain: str
    verification_status: str
    dkim_status: str
    spf_status: str
    dmarc_status: str
    mail_from_status: str
    last_checked_at: str
    created_at: str
    updated_at: str


class DomainSendingCheckRequest(BaseModel):
    from_email: str


class DomainSendingCheckResponse(BaseModel):
    can_send: bool
    from_email: str
    domain: str
    sending_domain: DomainResponse | None = None
    blockers: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class DomainDnsRecord(BaseModel):
    type: str
    host: str
    value: str
    purpose: str


class DomainSetupRecordsResponse(BaseModel):
    domain_id: str
    domain: str
    mail_from_domain: str
    records: list[DomainDnsRecord] = Field(default_factory=list)
