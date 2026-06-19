from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse, Response
from sqlalchemy.ext.asyncio import AsyncSession
from urllib.parse import urlparse

from src.database.sqlalchemy import get_db
from src.services.tracking_service import (
    TrackingTokenError,
    build_tracking_metadata,
    record_tracking_event,
    verify_tracking_token,
)

router = APIRouter()

TRANSPARENT_GIF = (
    b"GIF89a"
    b"\x01\x00\x01\x00"
    b"\x80\x00\x00"
    b"\x00\x00\x00"
    b"\xff\xff\xff"
    b"\x21\xf9\x04\x01\x00\x00\x00\x00"
    b"\x2c\x00\x00\x00\x00\x01\x00\x01\x00\x00"
    b"\x02\x02\x44\x01\x00"
    b"\x3b"
)


def _no_cache_headers() -> dict[str, str]:
    return {
        "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
        "Pragma": "no-cache",
        "Expires": "0",
    }


def _is_safe_redirect_url(url: str | None) -> bool:
    if not url:
        return False

    parsed_url = urlparse(url)
    return parsed_url.scheme in {"http", "https"}


def _client_ip(request: Request) -> str | None:
    forwarded_for = request.headers.get("x-forwarded-for")
    if forwarded_for:
        return forwarded_for.split(",", 1)[0].strip()

    return request.client.host if request.client else None


async def _record_event_from_request(
    db: AsyncSession,
    payload: dict,
    request: Request,
):
    metadata = build_tracking_metadata(
        user_agent=request.headers.get("user-agent"),
        ip_address=_client_ip(request),
        target_url=payload.get("target_url"),
    )
    await record_tracking_event(db, payload, metadata)


@router.get("/track/open/{token}.gif")
async def track_open(
    token: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    try:
        payload = verify_tracking_token(token)
        if payload.get("event") != "open":
            raise TrackingTokenError("Invalid tracking token")

        await _record_event_from_request(db, payload, request)
    except TrackingTokenError:
        raise HTTPException(status_code=404, detail="Not found")
    except Exception:
        await db.rollback()

    return Response(
        content=TRANSPARENT_GIF,
        media_type="image/gif",
        headers=_no_cache_headers(),
    )


@router.get("/track/click/{token}")
async def track_click(
    token: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    try:
        payload = verify_tracking_token(token)
        if payload.get("event") != "click":
            raise TrackingTokenError("Invalid tracking token")
    except TrackingTokenError:
        raise HTTPException(status_code=404, detail="Not found")

    target_url = payload.get("target_url")
    if not _is_safe_redirect_url(target_url):
        raise HTTPException(status_code=404, detail="Not found")

    try:
        await _record_event_from_request(db, payload, request)
    except TrackingTokenError:
        raise HTTPException(status_code=404, detail="Not found")
    except Exception:
        await db.rollback()

    return RedirectResponse(
        url=target_url,
        status_code=302,
        headers=_no_cache_headers(),
    )