from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.ext.asyncio import AsyncSession

from src.services.local_user_service import get_local_user
from src.configs.config import SES_PREFLIGHT_ENABLED
from src.database.sqlalchemy import get_db
from src.schemas.Domain import (
    DomainCreate,
    DomainResponse,
    DomainSendingCheckRequest,
    DomainSendingCheckResponse,
    DomainSetupRecordsResponse,
)
from src.services.domains_service import (
    DomainError,
    check_domain_for_sending_service,
    create_domain_service,
    delete_domain_service,
    get_domain_service,
    get_domain_setup_records_service,
    list_domains_service,
    refresh_domain_service,
)

router = APIRouter()


def _local_sending_check(from_email: str):
    normalized_email = from_email.strip().lower()
    if "@" not in normalized_email:
        raise DomainError("Invalid from email")

    local_part, domain = normalized_email.rsplit("@", 1)
    if not local_part or not domain:
        raise DomainError("Invalid from email")

    return {
        "can_send": True,
        "from_email": normalized_email,
        "domain": domain,
        "sending_domain": None,
        "blockers": [],
        "warnings": ["SES preflight is disabled for local SMTP sending"],
    }


@router.post("/domains", response_model=DomainResponse)
async def add_domain(
    domain: DomainCreate,
    db: AsyncSession = Depends(get_db),
):
    current_user = get_local_user()
    try:
        created_domain = await create_domain_service(
            db,
            user_id=current_user["id"],
            domain=domain.domain,
            mail_from_domain=domain.mail_from_domain,
        )
    except DomainError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    if not created_domain:
        raise HTTPException(status_code=409, detail="Domain already exists")

    return created_domain


@router.post("/domains/check-sending", response_model=DomainSendingCheckResponse)
async def check_domain_for_sending(
    payload: DomainSendingCheckRequest,
    db: AsyncSession = Depends(get_db),
):
    current_user = get_local_user()
    if not SES_PREFLIGHT_ENABLED:
        try:
            return _local_sending_check(payload.from_email)
        except DomainError as exc:
            raise HTTPException(status_code=400, detail=str(exc))

    try:
        return await check_domain_for_sending_service(
            db,
            user_id=current_user["id"],
            from_email=payload.from_email,
        )
    except DomainError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.get("/domains", response_model=list[DomainResponse])
async def list_domains(
    db: AsyncSession = Depends(get_db),
):
    current_user = get_local_user()
    return await list_domains_service(db, current_user["id"])


@router.get("/domains/{domain_id}", response_model=DomainResponse)
async def get_domain(
    domain_id: str,
    db: AsyncSession = Depends(get_db),
):
    current_user = get_local_user()
    domain = await get_domain_service(db, current_user["id"], domain_id)
    if not domain:
        raise HTTPException(status_code=404, detail="Domain not found")

    return domain


@router.delete("/domains/{domain_id}", status_code=204)
async def delete_domain(
    domain_id: str,
    db: AsyncSession = Depends(get_db),
):
    current_user = get_local_user()
    deleted = await delete_domain_service(db, current_user["id"], domain_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Domain not found")

    return Response(status_code=204)


@router.get("/domains/{domain_id}/setup-records", response_model=DomainSetupRecordsResponse)
async def get_domain_setup_records(
    domain_id: str,
    db: AsyncSession = Depends(get_db),
):
    current_user = get_local_user()
    setup_records = await get_domain_setup_records_service(db, current_user["id"], domain_id)
    if not setup_records:
        raise HTTPException(status_code=404, detail="Domain not found")

    return setup_records


@router.post("/domains/{domain_id}/refresh", response_model=DomainResponse)
async def refresh_domain(
    domain_id: str,
    db: AsyncSession = Depends(get_db),
):
    current_user = get_local_user()
    domain = await refresh_domain_service(db, current_user["id"], domain_id)
    if not domain:
        raise HTTPException(status_code=404, detail="Domain not found")

    return domain
