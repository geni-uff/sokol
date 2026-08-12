"""SOKOL API — case comments / working notes (issue v2-08).

Internal annotations only: never consumed by reports/laudo.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import text

from .audit import append_audit
from .auth import CurrentUser, get_current_user, require_case_member
from .db import get_session_factory

router = APIRouter(prefix="/comments", tags=["comments"])

TargetKind = Literal["case", "event", "media"]
_WRITE_ROLES = ["admin", "analista"]


class CommentCreate(BaseModel):
    target_kind: TargetKind
    target_id: UUID | None = None
    body: str = Field(min_length=1)


class CommentUpdate(BaseModel):
    body: str = Field(min_length=1)


class CommentOut(BaseModel):
    id: str
    case_id: str
    author_user_id: str
    author_username: str
    target_kind: str
    target_id: str | None
    body: str
    created_at: str
    edited_at: str | None


class CommentListResponse(BaseModel):
    comments: list[CommentOut]
    viewer_role: str
    viewer_user_id: str
    can_write: bool


def _validate_target(db, case_id: UUID, target_kind: str, target_id: UUID | None) -> None:
    if target_kind == "case":
        if target_id is not None:
            raise HTTPException(
                status_code=422,
                detail="target_id must be null when target_kind is 'case'",
            )
        return

    if target_id is None:
        raise HTTPException(
            status_code=422,
            detail=f"target_id is required when target_kind is '{target_kind}'",
        )

    if target_kind == "event":
        row = db.execute(
            text("SELECT 1 FROM events WHERE id = :tid AND case_id = :cid"),
            {"tid": target_id, "cid": case_id},
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Event not found in this case")
        return

    # media: artifact with media, message with media, or media event — same case only
    row = db.execute(
        text("""
            SELECT 1 FROM artifacts
            WHERE id = :tid AND case_id = :cid AND media_hash IS NOT NULL
            UNION ALL
            SELECT 1 FROM messages
            WHERE id = :tid AND case_id = :cid AND media_hash IS NOT NULL
            UNION ALL
            SELECT 1 FROM events
            WHERE id = :tid AND case_id = :cid AND kind = 'media'
            LIMIT 1
        """),
        {"tid": target_id, "cid": case_id},
    ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Media target not found in this case")


def _row_to_out(r) -> CommentOut:
    return CommentOut(
        id=str(r[0]),
        case_id=str(r[1]),
        author_user_id=str(r[2]),
        author_username=r[3] or "?",
        target_kind=r[4],
        target_id=str(r[5]) if r[5] else None,
        body=r[6],
        created_at=str(r[7]),
        edited_at=str(r[8]) if r[8] else None,
    )


@router.post("/{case_id}", response_model=CommentOut, status_code=201)
def create_comment(
    case_id: UUID,
    body: CommentCreate,
    user: CurrentUser = Depends(get_current_user),
):
    factory = get_session_factory()
    with factory() as db:
        require_case_member(db, case_id, user.user_id, roles=_WRITE_ROLES)
        _validate_target(db, case_id, body.target_kind, body.target_id)

        cleaned = body.body.strip()
        if not cleaned:
            raise HTTPException(status_code=422, detail="body must not be blank")

        comment_id = uuid4()
        now = datetime.now(timezone.utc)
        db.execute(
            text("""
                INSERT INTO case_comments
                    (id, case_id, author_user_id, target_kind, target_id, body, created_at)
                VALUES
                    (:id, :cid, :uid, :kind, :tid, :body, :now)
            """),
            {
                "id": comment_id,
                "cid": case_id,
                "uid": user.user_id,
                "kind": body.target_kind,
                "tid": body.target_id,
                "body": cleaned,
                "now": now,
            },
        )
        append_audit(
            db,
            case_id=case_id,
            actor_user_id=user.user_id,
            action="comment.created",
            payload={
                "comment_id": str(comment_id),
                "target_kind": body.target_kind,
                "target_id": str(body.target_id) if body.target_id else None,
            },
        )
        db.commit()

        row = db.execute(
            text("""
                SELECT c.id, c.case_id, c.author_user_id, u.username,
                       c.target_kind, c.target_id, c.body, c.created_at, c.edited_at
                FROM case_comments c
                JOIN users u ON u.id = c.author_user_id
                WHERE c.id = :id
            """),
            {"id": comment_id},
        ).fetchone()

    return _row_to_out(row)


@router.get("/{case_id}", response_model=CommentListResponse)
def list_comments(
    case_id: UUID,
    target_kind: TargetKind | None = Query(None),
    target_id: UUID | None = Query(None),
    user: CurrentUser = Depends(get_current_user),
):
    factory = get_session_factory()
    with factory() as db:
        role = require_case_member(db, case_id, user.user_id)

        conditions = ["c.case_id = :cid", "c.deleted = false"]
        bind: dict = {"cid": case_id}
        if target_kind is not None:
            conditions.append("c.target_kind = :kind")
            bind["kind"] = target_kind
        if target_id is not None:
            conditions.append("c.target_id = :tid")
            bind["tid"] = target_id
        elif target_kind == "case":
            conditions.append("c.target_id IS NULL")

        rows = db.execute(
            text(f"""
                SELECT c.id, c.case_id, c.author_user_id, u.username,
                       c.target_kind, c.target_id, c.body, c.created_at, c.edited_at
                FROM case_comments c
                JOIN users u ON u.id = c.author_user_id
                WHERE {" AND ".join(conditions)}
                ORDER BY c.created_at ASC
            """),
            bind,
        ).fetchall()

    return CommentListResponse(
        comments=[_row_to_out(r) for r in rows],
        viewer_role=role,
        viewer_user_id=str(user.user_id),
        can_write=role in _WRITE_ROLES,
    )


@router.patch("/{comment_id}", response_model=CommentOut)
def update_comment(
    comment_id: UUID,
    body: CommentUpdate,
    user: CurrentUser = Depends(get_current_user),
):
    factory = get_session_factory()
    with factory() as db:
        row = db.execute(
            text("""
                SELECT case_id, author_user_id, deleted
                FROM case_comments WHERE id = :id
            """),
            {"id": comment_id},
        ).fetchone()
        if not row or row[2]:
            raise HTTPException(status_code=404, detail="Comment not found")

        case_id = row[0]
        require_case_member(db, case_id, user.user_id, roles=_WRITE_ROLES)
        if row[1] != user.user_id:
            raise HTTPException(status_code=403, detail="Only the author can edit this comment")

        cleaned = body.body.strip()
        if not cleaned:
            raise HTTPException(status_code=422, detail="body must not be blank")

        now = datetime.now(timezone.utc)
        db.execute(
            text("""
                UPDATE case_comments
                SET body = :body, edited_at = :now
                WHERE id = :id
            """),
            {"body": cleaned, "now": now, "id": comment_id},
        )
        append_audit(
            db,
            case_id=case_id,
            actor_user_id=user.user_id,
            action="comment.updated",
            payload={"comment_id": str(comment_id)},
        )
        db.commit()

        out = db.execute(
            text("""
                SELECT c.id, c.case_id, c.author_user_id, u.username,
                       c.target_kind, c.target_id, c.body, c.created_at, c.edited_at
                FROM case_comments c
                JOIN users u ON u.id = c.author_user_id
                WHERE c.id = :id
            """),
            {"id": comment_id},
        ).fetchone()

    return _row_to_out(out)


@router.delete("/{comment_id}")
def delete_comment(
    comment_id: UUID,
    user: CurrentUser = Depends(get_current_user),
) -> dict[str, str]:
    factory = get_session_factory()
    with factory() as db:
        row = db.execute(
            text("""
                SELECT case_id, author_user_id, deleted
                FROM case_comments WHERE id = :id
            """),
            {"id": comment_id},
        ).fetchone()
        if not row or row[2]:
            raise HTTPException(status_code=404, detail="Comment not found")

        case_id = row[0]
        role = require_case_member(db, case_id, user.user_id, roles=_WRITE_ROLES)
        is_author = row[1] == user.user_id
        is_admin = role == "admin"
        if not is_author and not is_admin:
            raise HTTPException(
                status_code=403,
                detail="Only the author or case admin can delete this comment",
            )

        db.execute(
            text("UPDATE case_comments SET deleted = true WHERE id = :id"),
            {"id": comment_id},
        )
        append_audit(
            db,
            case_id=case_id,
            actor_user_id=user.user_id,
            action="comment.deleted",
            payload={"comment_id": str(comment_id)},
        )
        db.commit()

    return {"status": "deleted"}
