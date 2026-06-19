from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from src.services.local_user_service import get_local_user
from src.database.sqlalchemy import get_db
from src.schemas.Contact import ContactCreate, ContactImportResponse, ContactResponse
from src.services.contacts_service import (
    add_contact_service,
    delete_contact_service,
    extract_emails_from_text,
    import_contacts_service,
    is_valid_email,
    list_contacts_service,
)

router = APIRouter()


async def get_current_user_id() -> str:
    result = get_local_user()
    return result["id"]


@router.get("/contacts", response_model=list[ContactResponse])
async def list_contacts(
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    return await list_contacts_service(db, user_id)


@router.delete("/contacts/{contact_id}", response_model=ContactResponse)
async def delete_contact(
    contact_id: str,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    contact = await delete_contact_service(db, user_id, contact_id)

    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found")

    return contact


@router.post("/contact/add", response_model=ContactResponse)
@router.post("/contacts/add", response_model=ContactResponse)
async def add_contact(
    data: ContactCreate,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    if not is_valid_email(data.email):
        raise HTTPException(status_code=400, detail="Invalid email address")
    contact = await add_contact_service(db, user_id=user_id, email=data.email, name=data.name)
 
    if not contact:
        raise HTTPException(status_code=400, detail="Contact already exists")

    return contact


@router.post("/contacts/import", response_model=ContactImportResponse)
async def import_contacts(
    file: UploadFile = File(...),
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    filename = (file.filename or "").lower()
    if not filename.endswith((".csv", ".txt")):
        raise HTTPException(status_code=400, detail="Upload a CSV or TXT file")

    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Uploaded file is empty")

    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = content.decode("latin-1")

    emails = extract_emails_from_text(text)
    if not emails:
        raise HTTPException(status_code=400, detail="No email addresses found")

    return await import_contacts_service(db, user_id, emails)
