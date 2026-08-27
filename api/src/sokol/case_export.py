"""Case export — ZIP and bulk formats (CSV / VCard / KML)."""

from __future__ import annotations

import csv
import json
import zipfile
from collections.abc import Iterator
from datetime import datetime
from io import BytesIO, StringIO
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import text
from sqlalchemy.orm import Session

from .audit import append_audit
from .auth import CurrentUser, get_current_user, require_case_member
from .contact_materialize import list_agenda_contacts
from .db import get_session_factory
from .export_formats import (
    TIMELINE_CSV_HEADER,
    format_kml_document,
    format_timeline_csv_row,
    format_vcard,
)

router = APIRouter(tags=["export"])

# Re-export formatters for callers that import from this module
__all__ = [
    "router",
    "TIMELINE_CSV_HEADER",
    "format_kml_document",
    "format_timeline_csv_row",
    "format_vcard",
]


# ── Helpers ───────────────────────────────────────────────────────────────


def _case_tz(db: Session, case_id: UUID) -> str:
    row = db.execute(
        text("SELECT reference_timezone FROM cases WHERE id = :id"),
        {"id": case_id},
    ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Case not found")
    return row[0] or "America/Sao_Paulo"


def _audit_export(
    db: Session,
    *,
    case_id: UUID,
    user_id: UUID,
    export_kind: str,
    extra: dict | None = None,
) -> None:
    payload = {"export_kind": export_kind, **(extra or {})}
    append_audit(
        db,
        case_id=case_id,
        actor_user_id=user_id,
        action="case.exported",
        payload=payload,
    )
    db.commit()


def _load_contacts(db: Session, case_id: UUID) -> list[dict]:
    """One Contact per person entity, with linked phones/emails via contact_of."""
    return list_agenda_contacts(db, case_id)


# ── Existing ZIP export ───────────────────────────────────────────────────


@router.get("/cases/{case_id}/export")
def export_case_zip(
    case_id: UUID,
    user: CurrentUser = Depends(get_current_user),
):
    """Export case as ZIP with all data."""
    factory = get_session_factory()

    with factory() as db:
        require_case_member(db, case_id, user.user_id)

        case = db.execute(
            text("SELECT * FROM cases WHERE id = :id"),
            {"id": case_id},
        ).mappings().first()

        if not case:
            raise HTTPException(status_code=404, detail="Case not found")

        zip_buffer = BytesIO()
        with zipfile.ZipFile(zip_buffer, "w") as zf:
            manifest = {
                "case_id": str(case_id),
                "case_title": case.get("title") or case.get("name"),
                "exported_at": datetime.now().isoformat(),
            }
            zf.writestr("manifest.json", json.dumps(manifest, indent=2))

            events = db.execute(
                text("SELECT * FROM events WHERE case_id = :cid"),
                {"cid": case_id},
            ).mappings().all()

            for event in events:
                event_dict = dict(event)
                event_dict["id"] = str(event_dict["id"])
                event_dict["case_id"] = str(event_dict["case_id"])
                # geography/vector are not JSON-serializable
                event_dict.pop("geo", None)
                event_dict.pop("embedding", None)
                if event_dict.get("ref_id") is not None:
                    event_dict["ref_id"] = str(event_dict["ref_id"])
                if event_dict.get("ts") is not None:
                    event_dict["ts"] = event_dict["ts"].isoformat()
                zf.writestr(f"events/{event_dict['id']}.json", json.dumps(event_dict, default=str))

            detections = {
                "yolo": db.execute(
                    text("SELECT COUNT(*) FROM image_detections WHERE case_id = :cid"),
                    {"cid": case_id},
                ).scalar(),
                "faces": db.execute(
                    text("SELECT COUNT(*) FROM face_embeddings WHERE case_id = :cid"),
                    {"cid": case_id},
                ).scalar(),
                "plates": db.execute(
                    text("SELECT COUNT(*) FROM plate_detections WHERE case_id = :cid"),
                    {"cid": case_id},
                ).scalar(),
            }
            zf.writestr("detections.json", json.dumps(detections))

        _audit_export(
            db,
            case_id=case_id,
            user_id=user.user_id,
            export_kind="zip",
        )

        zip_buffer.seek(0)
        return StreamingResponse(
            iter([zip_buffer.getvalue()]),
            media_type="application/zip",
            headers={"Content-Disposition": f'attachment; filename="case_{case_id}.zip"'},
        )


# ── Bulk exports (v2-10) ──────────────────────────────────────────────────


@router.get("/export/{case_id}/timeline.csv")
def export_timeline_csv(
    case_id: UUID,
    start_date: str | None = Query(None),
    end_date: str | None = Query(None),
    user: CurrentUser = Depends(get_current_user),
):
    """Stream timeline events as CSV (safe for large cases)."""
    factory = get_session_factory()

    with factory() as db:
        require_case_member(db, case_id, user.user_id)
        tz = _case_tz(db, case_id)
        _audit_export(
            db,
            case_id=case_id,
            user_id=user.user_id,
            export_kind="timeline.csv",
            extra={"start_date": start_date, "end_date": end_date},
        )

    def generate() -> Iterator[str]:
        yield TIMELINE_CSV_HEADER + "\n"
        with factory() as db:
            conditions = ["e.case_id = :cid"]
            bind: dict = {"cid": case_id, "tz": tz}
            if start_date:
                conditions.append("e.ts >= :start_date")
                bind["start_date"] = start_date
            if end_date:
                conditions.append("e.ts <= :end_date")
                bind["end_date"] = end_date
            where = " AND ".join(conditions)

            result = db.execute(
                text(f"""
                    SELECT
                        e.ts AS ts_utc,
                        to_char(e.ts AT TIME ZONE :tz, 'YYYY-MM-DD HH24:MI:SS') AS ts_case_tz,
                        e.kind,
                        e.app,
                        e.summary AS description,
                        e.ref_table,
                        e.ref_id
                    FROM events e
                    WHERE {where}
                    ORDER BY e.ts ASC NULLS LAST
                """).execution_options(stream_results=True, yield_per=2000),
                bind,
            )
            for row in result.mappings():
                yield format_timeline_csv_row(
                    {
                        "ts_utc": row["ts_utc"].isoformat() if row["ts_utc"] else "",
                        "ts_case_tz": row["ts_case_tz"] or "",
                        "kind": row["kind"] or "",
                        "app": row["app"] or "",
                        "description": row["description"] or "",
                        "ref_table": row["ref_table"] or "",
                        "ref_id": str(row["ref_id"]) if row["ref_id"] else "",
                    }
                ) + "\n"

    return StreamingResponse(
        generate(),
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="case_{case_id}_timeline.csv"',
        },
    )


@router.get("/export/{case_id}/contacts.vcf")
def export_contacts_vcf(
    case_id: UUID,
    user: CurrentUser = Depends(get_current_user),
):
    """Export contacts as vCard 3.0."""
    factory = get_session_factory()
    with factory() as db:
        require_case_member(db, case_id, user.user_id)
        _case_tz(db, case_id)  # 404 if case missing
        contacts = _load_contacts(db, case_id)
        _audit_export(
            db,
            case_id=case_id,
            user_id=user.user_id,
            export_kind="contacts.vcf",
            extra={"count": len(contacts)},
        )

    def generate() -> Iterator[str]:
        for c in contacts:
            yield format_vcard(name=c["name"], phones=c["phones"], emails=c["emails"])

    return StreamingResponse(
        generate(),
        media_type="text/vcard; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="case_{case_id}_contacts.vcf"',
        },
    )


@router.get("/export/{case_id}/contacts.csv")
def export_contacts_csv(
    case_id: UUID,
    user: CurrentUser = Depends(get_current_user),
):
    """Export contacts as CSV (same base as vCard)."""
    factory = get_session_factory()
    with factory() as db:
        require_case_member(db, case_id, user.user_id)
        _case_tz(db, case_id)
        contacts = _load_contacts(db, case_id)
        _audit_export(
            db,
            case_id=case_id,
            user_id=user.user_id,
            export_kind="contacts.csv",
            extra={"count": len(contacts)},
        )

    def generate() -> Iterator[str]:
        yield "name,phones,emails\n"
        for c in contacts:
            buf = StringIO()
            writer = csv.writer(buf, lineterminator="")
            writer.writerow(
                [
                    c["name"],
                    ";".join(c["phones"]),
                    ";".join(c["emails"]),
                ]
            )
            yield buf.getvalue() + "\n"

    return StreamingResponse(
        generate(),
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="case_{case_id}_contacts.csv"',
        },
    )


@router.get("/export/{case_id}/locations.kml")
def export_locations_kml(
    case_id: UUID,
    user: CurrentUser = Depends(get_current_user),
):
    """Export location events as KML Placemarks (coordinates: lon,lat)."""
    factory = get_session_factory()
    with factory() as db:
        require_case_member(db, case_id, user.user_id)
        tz = _case_tz(db, case_id)

        rows = db.execute(
            text("""
                SELECT
                    to_char(e.ts AT TIME ZONE :tz, 'YYYY-MM-DD HH24:MI:SS') AS ts_label,
                    ST_Y(e.geo::geometry) AS lat,
                    ST_X(e.geo::geometry) AS lon
                FROM events e
                WHERE e.case_id = :cid
                  AND e.kind = 'location'
                  AND e.geo IS NOT NULL
                ORDER BY e.ts ASC NULLS LAST
            """),
            {"cid": case_id, "tz": tz},
        ).mappings().all()

        placemarks = [
            {
                "name": r["ts_label"] or "unknown",
                "lon": float(r["lon"]),
                "lat": float(r["lat"]),
            }
            for r in rows
        ]

        _audit_export(
            db,
            case_id=case_id,
            user_id=user.user_id,
            export_kind="locations.kml",
            extra={"count": len(placemarks)},
        )

    body = format_kml_document(placemarks)
    return StreamingResponse(
        iter([body]),
        media_type="application/vnd.google-earth.kml+xml",
        headers={
            "Content-Disposition": f'attachment; filename="case_{case_id}_locations.kml"',
        },
    )
