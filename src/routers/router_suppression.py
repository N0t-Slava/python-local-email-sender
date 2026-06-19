from src.services.local_user_service import get_local_user
from src.database.sqlalchemy import get_db
from sqlalchemy.ext.asyncio import AsyncSession
from src.configs.config import SUPPRESSION_REASON_MANUAL, SUPPRESSION_SOURCE_ADMIN
from src.services.contacts_service import is_valid_email
from src.services.suppression_service import (
    get_suppression_status_service,
    list_suppression_entries_service,
    suppress_email_service,
    sync_ses_suppression_list_service,
    unsuppress_email_service,
)

from fastapi import APIRouter, Depends, Form, HTTPException

router = APIRouter()

@router.post("/suppression/sync-ses")
async def sync_suppression_list(db: AsyncSession = Depends(get_db)):
    return await sync_ses_suppression_list_service(db)
    
@router.get("/suppression")
async def get_suppression_list(
    status: str | None = None,
    reason: str | None = None,
    source: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    current_user = get_local_user()
    return await list_suppression_entries_service(
        db,
        user_id=current_user["id"],
        status=status,
        reason=reason,
        source=source,
    )

@router.post("/suppression/manual")
async def add_manual_suppression(
    email: str = Form(...),
    note: str | None = Form(None),
    db: AsyncSession = Depends(get_db),
):
    current_user = get_local_user()
    if not is_valid_email(email):
        raise HTTPException(status_code=400, detail="Invalid email")

    return await suppress_email_service(
        db,
        email=email,
        reason=SUPPRESSION_REASON_MANUAL,
        source=SUPPRESSION_SOURCE_ADMIN,
        user_id=current_user["id"],
        note=note,
        created_by_user_id=current_user["id"],
    )

@router.post("/suppression/{email}/deactivate")
async def deactivate_suppression(
    email: str,
    db: AsyncSession = Depends(get_db),
):
    current_user = get_local_user()
    if not is_valid_email(email):
        raise HTTPException(status_code=400, detail="Invalid email")

    entry = await unsuppress_email_service(db, email, user_id=current_user["id"])
    if not entry:
        raise HTTPException(status_code=404, detail="Suppression entry not found")

    return entry

@router.get("/suppression/status")
async def check_suppression_status(db: AsyncSession = Depends(get_db)):
    return await get_suppression_status_service(db)
