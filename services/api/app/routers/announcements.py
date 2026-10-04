from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import SystemAnnouncement

router = APIRouter(prefix="/api/v1/announcements", tags=["announcements"])


@router.get("")
def list_public_announcements(
    limit: int = Query(default=3, ge=1, le=20),
    notice_type: str = Query(default="NORMAL", max_length=32),
    db: Session = Depends(get_db),
):
    rows = list(
        db.scalars(
            select(SystemAnnouncement)
            .where(
                SystemAnnouncement.status == "PUBLISHED",
                SystemAnnouncement.notice_type == notice_type.upper(),
            )
            .order_by(
                SystemAnnouncement.published_at.desc().nullslast(),
                SystemAnnouncement.created_at.desc(),
            )
            .limit(limit)
        )
    )
    return [
        {
            "id": str(item.id),
            "title": item.title,
            "content": item.content,
            "audience": item.audience,
            "noticeType": item.notice_type,
            "publishedAt": item.published_at,
        }
        for item in rows
    ]
