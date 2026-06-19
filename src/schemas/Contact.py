from pydantic import BaseModel
from typing import Optional

class ContactCreate(BaseModel):
    email: str
    name: Optional[str] = None

class ContactResponse(ContactCreate):
    id: str
    status: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class ContactImportResponse(BaseModel):
    contacts: list[ContactResponse]
    created_count: int
    duplicate_count: int
    total_found: int
