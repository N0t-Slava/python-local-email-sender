from src.services.email_service import send_email
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter()

class EmailRequest(BaseModel):
    email: str
    subject: str
    body: str = ""
    from_email: str
    html_body: str | None = None
    content_type: str = "plain"

@router.post("/send_email")
def send_email_endpoint(email_request: EmailRequest):
    try:
        send_email(
            email_request.email,
            email_request.subject,
            email_request.body,
            email_request.from_email,
            html_body=email_request.html_body,
            content_type=email_request.content_type,
        )
        return {"message": "Email sent successfully"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
