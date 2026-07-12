"""PDF report generation for forensic investigations."""

import hashlib
from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import text

from .auth import CurrentUser, get_current_user, require_case_member
from .db import get_session_factory

router = APIRouter(prefix="/reports", tags=["reports"])


class ReportRequest(BaseModel):
    title: str = "Forensic Investigation Report"


class ReportResponse(BaseModel):
    report_id: str
    case_id: str
    created_at: str
    status: str
    file_size: int


def _generate_html_report(case_id: str, case_title: str, events: list, detections: dict, created_by: str) -> str:
    """Generate HTML report (basis for PDF conversion)."""
    html = f"""
    <!DOCTYPE html>
    <html lang="pt-BR">
    <head>
        <meta charset="UTF-8">
        <title>{case_title} - Report</title>
        <style>
            body {{ font-family: Arial, sans-serif; color: #333; line-height: 1.6; }}
            .header {{ background: #667eea; color: white; padding: 40px; text-align: center; }}
            .header h1 {{ margin: 0; font-size: 32px; }}
            .metadata {{ background: #f5f5f5; padding: 20px; border-bottom: 1px solid #ddd; }}
            .metadata-row {{ margin: 8px 0; font-size: 13px; }}
            .section {{ padding: 30px; page-break-inside: avoid; }}
            .section h2 {{ color: #667eea; border-bottom: 2px solid #667eea; padding-bottom: 10px; }}
            .event-item {{ background: #f9f9f9; padding: 15px; margin: 10px 0; border-left: 4px solid #667eea; }}
            .event-time {{ font-weight: bold; color: #667eea; font-size: 12px; }}
            .detection-card {{ display: inline-block; background: #f5f5f5; padding: 10px; margin: 5px; border-radius: 4px; }}
            .footer {{ background: #333; color: white; padding: 20px; text-align: center; font-size: 11px; }}
        </style>
    </head>
    <body>
        <div class="header">
            <h1>🔎 SOKOL</h1>
            <p>{case_title}</p>
        </div>

        <div class="metadata">
            <div class="metadata-row"><strong>Case ID:</strong> {case_id}</div>
            <div class="metadata-row"><strong>Created by:</strong> {created_by}</div>
            <div class="metadata-row"><strong>Created at:</strong> {datetime.now(timezone.utc).isoformat()}</div>
            <div class="metadata-row"><strong>Events:</strong> {len(events)}</div>
            <div class="metadata-row"><strong>Detections:</strong> {detections.get('total', 0)}</div>
        </div>

        <div class="section">
            <h2>📋 Executive Summary</h2>
            <p>This report contains the complete timeline and detected objects for the investigation.</p>
        </div>

        <div class="section">
            <h2>📅 Timeline (Last 50 events)</h2>
    """

    for event in events[:50]:
        ts = event.get('ts', 'Unknown')
        kind = event.get('kind', '?').upper()
        summary = event.get('summary', 'N/A')
        html += f"""
            <div class="event-item">
                <div class="event-time">{ts}</div>
                <div><strong>{kind}</strong></div>
                <div style="margin-top: 5px;">{summary}</div>
            </div>
        """

    html += """
        </div>

        <div class="section">
            <h2>🔍 Detections</h2>
    """

    if detections.get("yolo", 0) > 0:
        html += f"<p><strong>YOLO Objects:</strong> {detections['yolo']}</p>"
    if detections.get("faces", 0) > 0:
        html += f"<p><strong>Faces Detected:</strong> {detections['faces']}</p>"
    if detections.get("plates", 0) > 0:
        html += f"<p><strong>License Plates:</strong> {detections['plates']}</p>"

    html += f"""
        </div>

        <div class="footer">
            <p>SOKOL Forensic Investigation Platform — Confidential</p>
            <p>Generated: {datetime.now(timezone.utc).isoformat()}</p>
        </div>
    </body>
    </html>
    """

    return html


@router.post("/", response_model=ReportResponse, status_code=201)
def generate_report(
    case_id: UUID,
    request: ReportRequest,
    user: CurrentUser = Depends(get_current_user),
):
    """Generate PDF report for a case."""
    factory = get_session_factory()

    with factory() as db:
        require_case_member(db, case_id, user.user_id)

        # Get case metadata
        case = db.execute(
            text("SELECT id, title FROM cases WHERE id = :id"),
            {"id": case_id},
        ).mappings().first()

        if not case:
            raise HTTPException(status_code=404, detail="Case not found")

        # Get events
        events = db.execute(
            text("""
                SELECT ts, kind, summary FROM events 
                WHERE case_id = :cid ORDER BY ts DESC LIMIT 50
            """),
            {"cid": case_id},
        ).mappings().all()

        # Get detection counts
        yolo_count = db.execute(
            text("SELECT COUNT(*) FROM image_detections WHERE case_id = :cid"),
            {"cid": case_id},
        ).scalar() or 0

        face_count = db.execute(
            text("SELECT COUNT(*) FROM face_embeddings WHERE case_id = :cid"),
            {"cid": case_id},
        ).scalar() or 0

        plate_count = db.execute(
            text("SELECT COUNT(*) FROM plate_detections WHERE case_id = :cid"),
            {"cid": case_id},
        ).scalar() or 0

        detections = {
            "yolo": yolo_count,
            "faces": face_count,
            "plates": plate_count,
            "total": yolo_count + face_count + plate_count,
        }

        # Generate HTML
        html_content = _generate_html_report(
            str(case_id), 
            case["title"] or "Report",
            events,
            detections,
            user.email
        )

        # Store in documents table
        from uuid import uuid4
        report_id = uuid4()

        db.execute(
            text("""
                INSERT INTO documents (id, case_id, title, source_type, status, created_at)
                VALUES (:id, :cid, :title, 'report', 'generated', :now)
            """),
            {
                "id": report_id,
                "cid": case_id,
                "title": f"Report: {case['title']}",
                "now": datetime.now(timezone.utc),
            },
        )
        db.commit()

        html_bytes = html_content.encode("utf-8")

        return ReportResponse(
            report_id=str(report_id),
            case_id=str(case_id),
            created_at=datetime.now(timezone.utc).isoformat(),
            status="ready",
            file_size=len(html_bytes),
        )


@router.get("/", response_model=list[ReportResponse])
def list_reports(
    case_id: UUID,
    user: CurrentUser = Depends(get_current_user),
):
    """List reports for a case."""
    factory = get_session_factory()

    with factory() as db:
        require_case_member(db, case_id, user.user_id)

        reports = db.execute(
            text("""
                SELECT id, case_id, created_at
                FROM documents WHERE case_id = :cid AND source_type = 'report'
                ORDER BY created_at DESC
            """),
            {"cid": case_id},
        ).mappings().all()

        return [
            ReportResponse(
                report_id=str(r["id"]),
                case_id=str(r["case_id"]),
                created_at=r["created_at"].isoformat() if r["created_at"] else "",
                status="ready",
                file_size=0,
            )
            for r in reports
        ]


@router.get("/{report_id}/download", response_class=None)
def download_report(
    report_id: UUID,
    case_id: UUID,
    user: CurrentUser = Depends(get_current_user),
):
    """Download report as HTML/PDF."""
    from fastapi.responses import FileResponse, StreamingResponse
    
    factory = get_session_factory()

    with factory() as db:
        require_case_member(db, case_id, user.user_id)

        report = db.execute(
            text("""
                SELECT id, title, created_at FROM documents 
                WHERE id = :id AND case_id = :cid AND source_type = 'report'
            """),
            {"id": report_id, "cid": case_id},
        ).mappings().first()

        if not report:
            raise HTTPException(status_code=404, detail="Report not found")

        # Get case and events for re-generating HTML
        case = db.execute(
            text("SELECT title FROM cases WHERE id = :id"),
            {"id": case_id},
        ).mappings().first()

        events = db.execute(
            text("""
                SELECT ts, kind, summary FROM events 
                WHERE case_id = :cid ORDER BY ts DESC LIMIT 50
            """),
            {"cid": case_id},
        ).mappings().all()

        yolo_count = db.execute(
            text("SELECT COUNT(*) FROM image_detections WHERE case_id = :cid"),
            {"cid": case_id},
        ).scalar() or 0

        face_count = db.execute(
            text("SELECT COUNT(*) FROM face_embeddings WHERE case_id = :cid"),
            {"cid": case_id},
        ).scalar() or 0

        plate_count = db.execute(
            text("SELECT COUNT(*) FROM plate_detections WHERE case_id = :cid"),
            {"cid": case_id},
        ).scalar() or 0

        detections = {
            "yolo": yolo_count,
            "faces": face_count,
            "plates": plate_count,
            "total": yolo_count + face_count + plate_count,
        }

        # Generate fresh HTML
        html_content = _generate_html_report(
            str(case_id),
            case["title"] or "Report",
            events,
            detections,
            user.email
        )

        html_bytes = html_content.encode("utf-8")
        
        return StreamingResponse(
            iter([html_bytes]),
            media_type="text/html",
            headers={"Content-Disposition": f'attachment; filename="{report["title"]}.html"'},
        )
