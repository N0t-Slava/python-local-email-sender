from fastapi import APIRouter, Depends, Form, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from src.services.local_user_service import get_local_user
from src.database.sqlalchemy import get_db
from src.services.contacts_service import is_valid_email
from src.services.suppression_service import (
    get_user_id_from_unsubscribe_public_key,
    resubscribe_email_service,
    unsubscribe_email_service,
    verify_unsubscribe_token,
)

router = APIRouter()

async def _unsubscribe_with_token(public_key: str, email: str, token: str | None, db: AsyncSession):
    if not is_valid_email(email):
        raise HTTPException(status_code=400, detail="Invalid email")

    user_id = get_user_id_from_unsubscribe_public_key(public_key)
    if not user_id or not verify_unsubscribe_token(public_key, email, token):
        raise HTTPException(status_code=403, detail="Invalid unsubscribe token")

    entry = await unsubscribe_email_service(db, email, user_id=user_id)
    if not entry:
        raise HTTPException(status_code=400, detail="Invalid email")

    return {
        "status": "unsubscribed",
        "suppression": entry,
    }


@router.get("/unsubscribe")
async def unsubscribe_from_link(
    public_key: str,
    email: str,
    token: str,
    db: AsyncSession = Depends(get_db),
):
    return await _unsubscribe_with_token(public_key, email, token, db)


@router.post("/unsubscribe")
async def unsubscribe(
    public_key: str = Form(...),
    email: str = Form(...),
    token: str = Form(...),
    db: AsyncSession = Depends(get_db),
):
    return await _unsubscribe_with_token(public_key, email, token, db)


@router.post("/unsubscribe/{email}/resubscribe")
async def resubscribe(
    email: str,
    db: AsyncSession = Depends(get_db),
):
    current_user = get_local_user()
    if not is_valid_email(email):
        raise HTTPException(status_code=400, detail="Invalid email")

    entry = await resubscribe_email_service(db, email, user_id=current_user["id"])
    if not entry:
        raise HTTPException(status_code=404, detail="Unsubscribe entry not found")

    return {
        "status": "resubscribed",
        "suppression": entry,
    }
