from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.ext.asyncio import AsyncSession

from src.services.local_user_service import get_local_user
from src.database.sqlalchemy import get_db
from src.schemas.EmailTemplate import (
    EmailTemplateCreate,
    EmailTemplatePreviewRequest,
    EmailTemplatePreviewResponse,
    EmailTemplateResponse,
    EmailTemplateUpdate,
)
from src.services.email_content_service import validate_rendered_email_content
from src.services.email_template_service import render_email_template
from src.services.email_templates_service import (
    create_email_template_service,
    delete_email_template_service,
    get_email_template_service,
    list_email_templates_service,
    update_email_template_service,
)


router = APIRouter()


@router.get("/email-templates", response_model=list[EmailTemplateResponse])
async def list_email_templates(
    db: AsyncSession = Depends(get_db),
):
    current_user = get_local_user()
    return await list_email_templates_service(db, current_user["id"])


@router.post("/email-templates", response_model=EmailTemplateResponse)
async def create_email_template(
    template: EmailTemplateCreate,
    db: AsyncSession = Depends(get_db),
):
    current_user = get_local_user()
    try:
        return await create_email_template_service(
            db,
            user_id=current_user["id"],
            name=template.name,
            subject=template.subject,
            body=template.body,
            html_body=template.html_body,
            content_type=template.content_type,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/email-templates/preview", response_model=EmailTemplatePreviewResponse)
async def preview_email_template(
    preview: EmailTemplatePreviewRequest,
):

    context = {
        "campaign": {"id": "preview-campaign", "subject": preview.subject},
        "contact": preview.contact.model_dump(),
        "variables": preview.variables,
    }

    try:
        rendered = render_email_template(
            subject_template=preview.subject,
            body_template=preview.body,
            html_body_template=preview.html_body,
            context=context,
        )
        content_type = validate_rendered_email_content(
            subject=rendered.subject,
            body=rendered.body,
            html_body=rendered.html_body,
            content_type=preview.content_type,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    return EmailTemplatePreviewResponse(
        subject=rendered.subject,
        body=rendered.body,
        html_body=rendered.html_body,
        content_type=content_type,
    )


@router.get("/email-templates/{template_id}", response_model=EmailTemplateResponse)
async def get_email_template(
    template_id: str,
    db: AsyncSession = Depends(get_db),
):
    current_user = get_local_user()
    template = await get_email_template_service(db, current_user["id"], template_id)
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    return template


@router.put("/email-templates/{template_id}", response_model=EmailTemplateResponse)
async def update_email_template(
    template_id: str,
    template: EmailTemplateUpdate,
    db: AsyncSession = Depends(get_db),
):
    current_user = get_local_user()
    updates = template.model_dump(exclude_unset=True)

    try:
        updated_template = await update_email_template_service(
            db,
            user_id=current_user["id"],
            template_id=template_id,
            **updates,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    if not updated_template:
        raise HTTPException(status_code=404, detail="Template not found")

    return updated_template


@router.delete("/email-templates/{template_id}", status_code=204)
async def delete_email_template(
    template_id: str,
    db: AsyncSession = Depends(get_db),
):
    current_user = get_local_user()
    deleted = await delete_email_template_service(db, current_user["id"], template_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Template not found")

    return Response(status_code=204)
