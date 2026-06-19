from pydantic import BaseModel, EmailStr
from typing import Optional

class UserResponse(BaseModel):
    id: str
    email: EmailStr
    name: Optional[str] = None
    unsubscribe_public_key: Optional[str] = None

    class Config:
        from_attributes = True
