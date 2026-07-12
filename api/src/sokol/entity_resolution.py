"""Entity Resolution — non-destructive identity matching within a case."""
import unicodedata
from datetime import datetime, timezone
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import text

from .auth import CurrentUser, get_current_user
from .audit import append_audit
from .cases import require_case_member
from .db import get_session_factory

router = APIRouter(prefix="/entities", tags=["entity-resolution"])


# ── Pydantic models ────────────────────────────────────────────────────────

class ResolutionSuggestion(BaseModel):
    entity_a: str
    entity_b: str
    kind_a: str
    kind_b: str
    display_a: str | None
    display_b: str | None
    reason: str
    confidence: float
    indicator_note: str = (
        "Sugestão automática (Indicator) — confirme manualmente antes de vincular."
    )


class ResolveSuggestionsResponse(BaseModel):
    case_id: str
    suggestions: list[ResolutionSuggestion]
    total: int


class ResolveToRequest(BaseModel):
    identity_id: UUID
    confirmed_by_user: bool


class RejectSuggestionRequest(BaseModel):
    entity_b_id: UUID


class MergeRequest(BaseModel):
    other_identity_id: UUID


# ── Helpers ────────────────────────────────────────────────────────────────

def _normalize(s: str) -> str:
    s = s.lower().strip()
    return "".join(
        c for c in unicodedata.normalize("NFD", s)
        if unicodedata.category(c) != "Mn"
    )


def _levenshtein(a: str, b: str) -> int:
    if len(a) < len(b):
        a, b = b, a
    if not b:
        return len(a)
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        curr = [i]
        for j, cb in enumerate(b, 1):
            curr.append(min(prev[j] + 1, curr[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = curr
    return prev[-1]


def _already_linked(db, case_id: UUID, id_a: UUID, id_b: UUID, kinds: list[str]) -> bool:
    row = db.execute(
        text("""
            SELECT 1 FROM entity_links
            WHERE case_id = :cid
              AND kind = ANY(:kinds)
              AND (
                (src_id = :a AND dst_id = :b)
                OR (src_id = :b AND dst_id = :a)
              )
            LIMIT 1
        """),
        {"cid": case_id, "kinds": kinds, "a": id_a, "b": id_b},
    ).fetchone()
    return row is not None


# ── Endpoints ──────────────────────────────────────────────────────────────

@router.post("/resolve", response_model=ResolveSuggestionsResponse)
def suggest_resolutions(
    case_id: UUID,
    user: CurrentUser = Depends(get_current_user),
):
    """Return resolution suggestions within a case. Nothing is written."""
    factory = get_session_factory()
    with factory() as db:
        require_case_member(db, case_id, user.user_id)

        rows = db.execute(
            text("""
                SELECT id, kind, value, display_name
                FROM entities
                WHERE case_id = :cid
                ORDER BY kind, value
            """),
            {"cid": case_id},
        ).fetchall()

    entities = [{"id": r[0], "kind": r[1], "value": r[2], "display_name": r[3]} for r in rows]

    with factory() as db:
        # Already confirmed or rejected — skip these pairs
        skip_rows = db.execute(
            text("""
                SELECT src_id, dst_id FROM entity_links
                WHERE case_id = :cid
                  AND kind IN ('resolves_to', 'resolution_rejected')
            """),
            {"cid": case_id},
        ).fetchall()

    skip_pairs = {(str(r[0]), str(r[1])) for r in skip_rows} | {(str(r[1]), str(r[0])) for r in skip_rows}

    suggestions: list[ResolutionSuggestion] = []
    seen: set[tuple[str, str]] = set()

    for i, ea in enumerate(entities):
        for eb in entities[i + 1 :]:
            pair = (str(ea["id"]), str(eb["id"]))
            if pair in seen or pair in skip_pairs:
                continue
            seen.add(pair)

            confidence: float | None = None
            reason: str | None = None

            if ea["kind"] == eb["kind"] and ea["kind"] in ("phone", "email"):
                va = (ea["value"] or "").strip().lower()
                vb = (eb["value"] or "").strip().lower()
                if va and vb and va == vb:
                    confidence = 0.97
                    reason = f"Mesmo {ea['kind']}: {va}"

            if confidence is None and ea["kind"] == "person" and eb["kind"] == "person":
                na = _normalize(ea["display_name"] or ea["value"] or "")
                nb = _normalize(eb["display_name"] or eb["value"] or "")
                if na and nb:
                    dist = _levenshtein(na, nb)
                    if dist <= 2:
                        confidence = max(0.5, 1.0 - dist * 0.2)
                        reason = f"Nomes similares (distância {dist}): '{ea['display_name']}' vs '{eb['display_name']}'"

            if confidence is not None and reason is not None:
                suggestions.append(
                    ResolutionSuggestion(
                        entity_a=str(ea["id"]),
                        entity_b=str(eb["id"]),
                        kind_a=ea["kind"],
                        kind_b=eb["kind"],
                        display_a=ea["display_name"],
                        display_b=eb["display_name"],
                        reason=reason,
                        confidence=round(confidence, 3),
                    )
                )

    return ResolveSuggestionsResponse(
        case_id=str(case_id),
        suggestions=suggestions,
        total=len(suggestions),
    )


@router.post("/{entity_id}/resolve-to", status_code=201)
def confirm_resolution(
    entity_id: UUID,
    body: ResolveToRequest,
    user: CurrentUser = Depends(get_current_user),
):
    """Confirm: entity_id resolves to identity_id. Creates a resolves_to edge."""
    if not body.confirmed_by_user:
        raise HTTPException(status_code=400, detail="confirmed_by_user must be true")

    factory = get_session_factory()
    with factory() as db:
        # Verify both entities exist and get case_id from entity_id
        src_row = db.execute(
            text("SELECT case_id FROM entities WHERE id = :id"),
            {"id": entity_id},
        ).fetchone()
        if not src_row:
            raise HTTPException(status_code=404, detail="Entity not found")

        case_id = src_row[0]
        require_case_member(db, case_id, user.user_id, roles=["admin", "analista"])

        dst_row = db.execute(
            text("SELECT id FROM entities WHERE id = :id AND case_id = :cid"),
            {"id": body.identity_id, "cid": case_id},
        ).fetchone()
        if not dst_row:
            raise HTTPException(status_code=404, detail="Target identity not found in same case")

        if _already_linked(db, case_id, entity_id, body.identity_id, ["resolves_to"]):
            raise HTTPException(status_code=409, detail="Already linked")

        link_id = uuid4()
        now = datetime.now(timezone.utc)
        db.execute(
            text("""
                INSERT INTO entity_links (id, case_id, src_id, dst_id, kind, confidence, meta, created_at)
                VALUES (:id, :cid, :src, :dst, 'resolves_to', 1.0, '{}', :now)
            """),
            {"id": link_id, "cid": case_id, "src": entity_id, "dst": body.identity_id, "now": now},
        )
        append_audit(
            db,
            case_id=case_id,
            actor_user_id=user.user_id,
            action="entity.resolve_to",
            payload={"entity_id": str(entity_id), "identity_id": str(body.identity_id)},
        )
        db.commit()

    return {"link_id": str(link_id), "status": "created"}


@router.post("/{entity_id}/reject-resolution", status_code=201)
def reject_resolution(
    entity_id: UUID,
    body: RejectSuggestionRequest,
    user: CurrentUser = Depends(get_current_user),
):
    """Reject a resolution suggestion so it doesn't reappear."""
    factory = get_session_factory()
    with factory() as db:
        src_row = db.execute(
            text("SELECT case_id FROM entities WHERE id = :id"),
            {"id": entity_id},
        ).fetchone()
        if not src_row:
            raise HTTPException(status_code=404, detail="Entity not found")

        case_id = src_row[0]
        require_case_member(db, case_id, user.user_id, roles=["admin", "analista"])

        if _already_linked(db, case_id, entity_id, body.entity_b_id, ["resolves_to", "resolution_rejected"]):
            raise HTTPException(status_code=409, detail="Already linked or rejected")

        link_id = uuid4()
        now = datetime.now(timezone.utc)
        db.execute(
            text("""
                INSERT INTO entity_links (id, case_id, src_id, dst_id, kind, confidence, meta, created_at)
                VALUES (:id, :cid, :src, :dst, 'resolution_rejected', 0.0, '{}', :now)
            """),
            {"id": link_id, "cid": case_id, "src": entity_id, "dst": body.entity_b_id, "now": now},
        )
        db.commit()

    return {"status": "rejected"}


@router.patch("/{identity_id}/merge")
def merge_identities(
    identity_id: UUID,
    body: MergeRequest,
    user: CurrentUser = Depends(get_current_user),
):
    """Merge other_identity_id into identity_id. Reroutes edges; nothing deleted."""
    factory = get_session_factory()
    with factory() as db:
        primary_row = db.execute(
            text("SELECT case_id, kind FROM entities WHERE id = :id"),
            {"id": identity_id},
        ).fetchone()
        if not primary_row:
            raise HTTPException(status_code=404, detail="Primary identity not found")

        case_id, primary_kind = primary_row
        require_case_member(db, case_id, user.user_id, roles=["admin"])

        other_row = db.execute(
            text("SELECT kind FROM entities WHERE id = :id AND case_id = :cid"),
            {"id": body.other_identity_id, "cid": case_id},
        ).fetchone()
        if not other_row:
            raise HTTPException(status_code=404, detail="Other identity not found in same case")

        if identity_id == body.other_identity_id:
            raise HTTPException(status_code=400, detail="Cannot merge entity with itself")

        now = datetime.now(timezone.utc)

        # Reroute src edges from other → primary
        db.execute(
            text("""
                UPDATE entity_links
                SET src_id = :primary
                WHERE case_id = :cid AND src_id = :other
                  AND kind != 'merged_into'
            """),
            {"primary": identity_id, "cid": case_id, "other": body.other_identity_id},
        )

        # Reroute dst edges from other → primary
        db.execute(
            text("""
                UPDATE entity_links
                SET dst_id = :primary
                WHERE case_id = :cid AND dst_id = :other
                  AND kind != 'merged_into'
            """),
            {"primary": identity_id, "cid": case_id, "other": body.other_identity_id},
        )

        # Mark the other as merged (non-destructive)
        merge_link_id = uuid4()
        db.execute(
            text("""
                INSERT INTO entity_links (id, case_id, src_id, dst_id, kind, confidence, meta, created_at)
                VALUES (:id, :cid, :other, :primary, 'merged_into', 1.0,
                        '{"merged_by": ":actor"}', :now)
            """),
            {
                "id": merge_link_id,
                "cid": case_id,
                "other": body.other_identity_id,
                "primary": identity_id,
                "now": now,
            },
        )
        append_audit(
            db,
            case_id=case_id,
            actor_user_id=user.user_id,
            action="entity.merge",
            payload={
                "primary_id": str(identity_id),
                "merged_id": str(body.other_identity_id),
            },
        )
        db.commit()

    return {"status": "merged", "primary_id": str(identity_id), "merged_id": str(body.other_identity_id)}
