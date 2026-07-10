"""SOKOL API — Reports, bookmarks, and laudo generation."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import text

from .db import get_session_factory

router = APIRouter(prefix="/reports", tags=["reports"])


# ── Models ─────────────────────────────────────────────────────────────────
class BookmarkCreate(BaseModel):
    case_id: str
    event_id: Optional[str] = None
    message_id: Optional[str] = None
    chunk_id: Optional[str] = None
    label: str
    note: Optional[str] = None
    color: str = "blue"


class Bookmark(BaseModel):
    id: str
    case_id: str
    event_id: Optional[str]
    message_id: Optional[str]
    chunk_id: Optional[str]
    label: str
    note: Optional[str]
    color: str
    created_by: str
    created_at: datetime


class ReportRequest(BaseModel):
    case_id: str
    title: str
    bookmarks_only: bool = False
    include_audit_log: bool = True


class Report(BaseModel):
    id: str
    case_id: str
    title: str
    content: dict
    generated_by: str
    generated_at: datetime
    sha256: str


# ── Endpoints ──────────────────────────────────────────────────────────────
@router.post("/bookmarks", response_model=Bookmark)
def create_bookmark(body: BookmarkCreate, user_id: str = "system"):
    """Create a bookmark on an event/message/chunk."""
    factory = get_session_factory()
    with factory() as db:
        # Verify case exists
        case = db.execute(
            text("SELECT id FROM cases WHERE id = :id"), {"id": body.case_id}
        ).fetchone()
        if not case:
            raise HTTPException(status_code=404, detail="Case not found")

        bookmark_id = db.execute(text("SELECT gen_random_uuid()")).fetchone()[0]

        db.execute(
            text("""
                INSERT INTO bookmarks (id, case_id, event_id, message_id, chunk_id, label, note, color, created_by)
                VALUES (:id, :case_id, :event_id, :message_id, :chunk_id, :label, :note, :color, :created_by)
            """),
            {
                "id": bookmark_id,
                "case_id": body.case_id,
                "event_id": body.event_id,
                "message_id": body.message_id,
                "chunk_id": body.chunk_id,
                "label": body.label,
                "note": body.note,
                "color": body.color,
                "created_by": user_id,
            },
        )
        db.commit()

        row = db.execute(
            text("SELECT * FROM bookmarks WHERE id = :id"), {"id": bookmark_id}
        ).fetchone()
        return Bookmark(**{k: row[k] for k in Bookmark.model_fields.keys()})


@router.get("/bookmarks/{case_id}", response_model=list[Bookmark])
def list_bookmarks(case_id: str):
    """List all bookmarks for a case."""
    factory = get_session_factory()
    with factory() as db:
        rows = db.execute(
            text(
                "SELECT * FROM bookmarks WHERE case_id = :case_id ORDER BY created_at DESC"
            ),
            {"case_id": case_id},
        ).fetchall()
        return [
            Bookmark(**{k: r[k] for k in Bookmark.model_fields.keys()}) for r in rows
        ]


@router.delete("/bookmarks/{bookmark_id}")
def delete_bookmark(bookmark_id: str):
    """Delete a bookmark."""
    factory = get_session_factory()
    with factory() as db:
        result = db.execute(
            text("DELETE FROM bookmarks WHERE id = :id"), {"id": bookmark_id}
        )
        if result.rowcount == 0:
            raise HTTPException(status_code=404, detail="Bookmark not found")
        db.commit()
    return {"status": "deleted"}


@router.post("/generate", response_model=Report)
def generate_report(body: ReportRequest, user_id: str = "system"):
    """Generate a forensic report (laudo) from case data."""
    factory = get_session_factory()
    with factory() as db:
        # Get case
        case = db.execute(
            text("SELECT * FROM cases WHERE id = :id"), {"id": body.case_id}
        ).fetchone()
        if not case:
            raise HTTPException(status_code=404, detail="Case not found")

        # Get bookmarks if bookmarks_only
        bookmarks = []
        if body.bookmarks_only:
            rows = db.execute(
                text(
                    "SELECT * FROM bookmarks WHERE case_id = :case_id ORDER BY created_at"
                ),
                {"case_id": body.case_id},
            ).fetchall()
            bookmarks = [dict(r) for r in rows]

        # Get events
        events = db.execute(
            text("SELECT * FROM events WHERE case_id = :case_id ORDER BY ts"),
            {"case_id": body.case_id},
        ).fetchall()

        # Get messages
        messages = db.execute(
            text("SELECT * FROM messages WHERE case_id = :case_id ORDER BY ts"),
            {"case_id": body.case_id},
        ).fetchall()

        # Get audit log
        audit_log = []
        if body.include_audit_log:
            rows = db.execute(
                text(
                    "SELECT * FROM audit_log WHERE case_id = :case_id ORDER BY created_at"
                ),
                {"case_id": body.case_id},
            ).fetchall()
            audit_log = [dict(r) for r in rows]

        content = {
            "case": dict(case),
            "events": [dict(e) for e in events],
            "messages": [dict(m) for m in messages],
            "bookmarks": bookmarks,
            "audit_log": audit_log,
            "summary": {
                "total_events": len(events),
                "total_messages": len(messages),
                "total_bookmarks": len(bookmarks),
            },
        }

        # Generate report
        import hashlib

        report_json = json.dumps(content, default=str, sort_keys=True)
        sha256 = hashlib.sha256(report_json.encode()).hexdigest()

        report_id = db.execute(text("SELECT gen_random_uuid()")).fetchone()[0]

        db.execute(
            text("""
                INSERT INTO reports (id, case_id, title, content, generated_by, sha256)
                VALUES (:id, :case_id, :title, :content, :generated_by, :sha256)
            """),
            {
                "id": report_id,
                "case_id": body.case_id,
                "title": body.title,
                "content": json.dumps(content),
                "generated_by": user_id,
                "sha256": sha256,
            },
        )
        db.commit()

        return Report(
            id=str(report_id),
            case_id=body.case_id,
            title=body.title,
            content=content,
            generated_by=user_id,
            generated_at=datetime.now(timezone.utc),
            sha256=sha256,
        )


@router.get("/{case_id}", response_model=list[Report])
def list_reports(case_id: str):
    """List all reports for a case."""
    factory = get_session_factory()
    with factory() as db:
        rows = db.execute(
            text(
                "SELECT id, case_id, title, generated_by, generated_at, sha256 FROM reports WHERE case_id = :case_id ORDER BY generated_at DESC"
            ),
            {"case_id": case_id},
        ).fetchall()
        return [
            Report(
                id=str(r[0]),
                case_id=r[1],
                title=r[2],
                content={},
                generated_by=r[3],
                generated_at=r[4],
                sha256=r[5],
            )
            for r in rows
        ]


@router.get("/{case_id}/{report_id}/verify")
def verify_report(report_id: str):
    """Verify report integrity via SHA-256."""
    factory = get_session_factory()
    with factory() as db:
        row = db.execute(
            text("SELECT content, sha256 FROM reports WHERE id = :id"),
            {"id": report_id},
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Report not found")

        import hashlib

        calculated = hashlib.sha256(
            json.dumps(json.loads(row[0]), default=str, sort_keys=True).encode()
        ).hexdigest()

        return {
            "valid": calculated == row[1],
            "expected": row[1],
            "calculated": calculated,
        }
