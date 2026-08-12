"""SOKOL reports — HTML laudo + PDF via WeasyPrint (issue v2-09).

Facts/Bookmarks as assertions; ML detections only as labeled Indicators (ADR-0004).
Comments (case_comments) are never included.
"""

from __future__ import annotations

import hashlib
import html as html_lib
import json
from datetime import datetime, timezone
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.orm import Session

from .audit import append_audit
from .auth import CurrentUser, get_current_user, require_case_member
from .db import get_session_factory

router = APIRouter(prefix="/reports", tags=["reports"])

_DOW_LABELS = ["Dom", "Seg", "Ter", "Qua", "Qui", "Sex", "Sáb"]


class ReportRequest(BaseModel):
    title: str = "Laudo investigativo"


class BookmarkCreate(BaseModel):
    case_id: UUID
    label: str
    event_id: UUID | None = None
    note: str | None = None
    color: str = "blue"


class ReportResponse(BaseModel):
    report_id: str
    case_id: str
    created_at: str
    status: str
    file_size: int


# ── SVG charts (server-side, no JS) ─────────────────────────────────────────

def _escape(s: object) -> str:
    return html_lib.escape(str(s) if s is not None else "")


def _activity_heatmap_svg(cells: list[dict], timezone: str) -> str:
    """7×24 activity heatmap as static SVG."""
    grid: dict[tuple[int, int], int] = {(c["dow"], c["hour"]): c["count"] for c in cells}
    max_c = max(grid.values()) if grid else 1
    cell_w, cell_h = 18, 18
    left, top = 48, 28
    width = left + 24 * cell_w + 16
    height = top + 7 * cell_h + 36

    rects = []
    for dow in range(7):
        for hour in range(24):
            count = grid.get((dow, hour), 0)
            intensity = count / max_c if max_c else 0
            # light → teal
            r = int(245 - intensity * 180)
            g = int(248 - intensity * 80)
            b = int(250 - intensity * 40)
            x = left + hour * cell_w
            y = top + dow * cell_h
            title = f"{_DOW_LABELS[dow]} {hour:02d}h: {count}"
            rects.append(
                f'<rect x="{x}" y="{y}" width="{cell_w - 1}" height="{cell_h - 1}" '
                f'fill="rgb({r},{g},{b})" stroke="#ddd" stroke-width="0.5">'
                f"<title>{_escape(title)}</title></rect>"
            )

    hour_labels = "".join(
        f'<text x="{left + h * cell_w + 4}" y="{top - 8}" font-size="8" fill="#666">{h}</text>'
        for h in range(0, 24, 3)
    )
    dow_labels = "".join(
        f'<text x="4" y="{top + d * cell_h + 13}" font-size="10" fill="#444">{_DOW_LABELS[d]}</text>'
        for d in range(7)
    )

    return f"""
    <svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">
      <text x="{left}" y="14" font-size="12" font-weight="bold" fill="#222">
        Heatmap de atividade ({_escape(timezone)})
      </text>
      {hour_labels}
      {dow_labels}
      {"".join(rects)}
    </svg>
    """


def _contact_bar_svg(contacts: list[dict]) -> str:
    """Horizontal bar chart for top contacts."""
    if not contacts:
        return '<p class="muted">Sem contatos suficientes para gráfico.</p>'

    top = contacts[:12]
    max_total = max(c["total"] for c in top) or 1
    row_h = 22
    left = 160
    bar_max = 320
    height = 28 + len(top) * row_h
    width = left + bar_max + 60

    rows = []
    for i, c in enumerate(top):
        y = 24 + i * row_h
        bar_w = int(bar_max * (c["total"] / max_total))
        label = (c["counterpart"] or "?")[:28]
        rows.append(
            f'<text x="4" y="{y + 12}" font-size="10" fill="#333">{_escape(label)}</text>'
            f'<rect x="{left}" y="{y}" width="{bar_w}" height="14" fill="#2a6f6f"/>'
            f'<text x="{left + bar_w + 6}" y="{y + 12}" font-size="10" fill="#444">{c["total"]}</text>'
        )

    return f"""
    <svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">
      <text x="4" y="14" font-size="12" font-weight="bold" fill="#222">Top contatos</text>
      {"".join(rows)}
    </svg>
    """


# ── Data gathering ─────────────────────────────────────────────────────────

def _username(db: Session, user_id: UUID) -> str:
    row = db.execute(
        text("SELECT username FROM users WHERE id = :id"),
        {"id": user_id},
    ).fetchone()
    return row[0] if row else str(user_id)


def _gather_report_data(db: Session, case_id: UUID, generated_by: UUID) -> dict:
    case = db.execute(
        text("""
            SELECT id, name, legal_ref, reference_timezone, created_at
            FROM cases WHERE id = :id
        """),
        {"id": case_id},
    ).mappings().first()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")

    period = db.execute(
        text("""
            SELECT MIN(ts) AS start_ts, MAX(ts) AS end_ts, COUNT(*) AS event_count
            FROM events WHERE case_id = :cid AND ts IS NOT NULL
        """),
        {"cid": case_id},
    ).mappings().first()

    documents = db.execute(
        text("""
            SELECT id, title, sha256, source_type, status, created_at
            FROM documents
            WHERE case_id = :cid
            ORDER BY created_at ASC
        """),
        {"cid": case_id},
    ).mappings().all()

    jobs = db.execute(
        text("""
            SELECT id, kind, status, created_at, updated_at, error
            FROM jobs
            WHERE case_id = :cid
            ORDER BY created_at ASC
        """),
        {"cid": case_id},
    ).mappings().all()

    bookmarks = db.execute(
        text("""
            SELECT b.id, b.label, b.note, b.color, b.event_id, b.created_at,
                   e.ts AS event_ts, e.summary AS event_summary, e.kind AS event_kind
            FROM bookmarks b
            LEFT JOIN events e ON e.id = b.event_id
            WHERE b.case_id = :cid
            ORDER BY b.created_at ASC
        """),
        {"cid": case_id},
    ).mappings().all()

    # Resolved pendências treated as human-confirmed Facts
    facts = db.execute(
        text("""
            SELECT id, title, description, priority, resolved_at
            FROM pendencias
            WHERE case_id = :cid AND status = 'resolved'
            ORDER BY resolved_at ASC NULLS LAST
        """),
        {"cid": case_id},
    ).mappings().all()

    # Indicators (never as bare assertions)
    yolo = db.execute(
        text("SELECT COUNT(*) FROM image_detections WHERE case_id = :cid"),
        {"cid": case_id},
    ).scalar() or 0
    faces = db.execute(
        text("SELECT COUNT(*) FROM face_embeddings WHERE case_id = :cid"),
        {"cid": case_id},
    ).scalar() or 0
    plates = db.execute(
        text("SELECT COUNT(*) FROM plate_detections WHERE case_id = :cid"),
        {"cid": case_id},
    ).scalar() or 0

    tz = case["reference_timezone"] or "America/Sao_Paulo"
    heatmap_rows = db.execute(
        text("""
            SELECT
                EXTRACT(DOW FROM ts AT TIME ZONE :tz)::int AS dow,
                EXTRACT(HOUR FROM ts AT TIME ZONE :tz)::int AS hour,
                COUNT(*) AS count
            FROM events
            WHERE case_id = :cid AND ts IS NOT NULL
            GROUP BY 1, 2
        """),
        {"cid": case_id, "tz": tz},
    ).mappings().all()

    contact_rows = db.execute(
        text("""
            SELECT counterpart, COUNT(*) AS total
            FROM events
            WHERE case_id = :cid
              AND counterpart IS NOT NULL AND counterpart <> ''
              AND kind IN ('message', 'call')
            GROUP BY counterpart
            ORDER BY total DESC
            LIMIT 15
        """),
        {"cid": case_id},
    ).mappings().all()

    return {
        "case": dict(case),
        "period": dict(period) if period else {},
        "documents": [dict(d) for d in documents],
        "jobs": [dict(j) for j in jobs],
        "bookmarks": [dict(b) for b in bookmarks],
        "facts": [dict(f) for f in facts],
        "indicators": {"yolo": yolo, "faces": faces, "plates": plates},
        "heatmap_cells": [dict(r) for r in heatmap_rows],
        "contacts": [dict(r) for r in contact_rows],
        "timezone": tz,
        "generated_by": _username(db, generated_by),
        "generated_at": datetime.now(timezone.utc),
    }


def _fmt_ts(ts) -> str:
    if ts is None:
        return "—"
    if hasattr(ts, "isoformat"):
        return ts.isoformat()
    return str(ts)


def _generate_html_report(data: dict, title: str) -> str:
    case = data["case"]
    period = data["period"]
    gen_at = _fmt_ts(data["generated_at"])
    start_ts = _fmt_ts(period.get("start_ts"))
    end_ts = _fmt_ts(period.get("end_ts"))
    event_count = period.get("event_count") or 0

    heatmap_svg = _activity_heatmap_svg(data["heatmap_cells"], data["timezone"])
    contacts_svg = _contact_bar_svg(data["contacts"])

    custody_rows = []
    for doc in data["documents"]:
        sha = doc.get("sha256") or "—"
        custody_rows.append(f"""
          <tr>
            <td>{_escape(doc.get("title") or doc["id"])}</td>
            <td class="mono">{_escape(sha)}</td>
            <td>{_escape(_fmt_ts(doc.get("created_at")))}</td>
            <td>{_escape(doc.get("source_type"))} / {_escape(doc.get("status"))}</td>
          </tr>
        """)

    jobs_list = "".join(
        f"<li><strong>{_escape(j['kind'])}</strong> — {_escape(j['status'])} "
        f"({_escape(_fmt_ts(j.get('created_at')))})</li>"
        for j in data["jobs"]
    ) or "<li>Nenhum job registrado.</li>"

    bookmark_items = "".join(
        f"""
        <div class="fact-item">
          <div class="fact-label">{_escape(b['label'])}</div>
          <div class="muted">{_escape(b.get('note') or '')}</div>
          <div class="muted">Evento: {_escape(_fmt_ts(b.get('event_ts')))} —
            {_escape(b.get('event_kind') or '')} — {_escape(b.get('event_summary') or '')}</div>
        </div>
        """
        for b in data["bookmarks"]
    ) or '<p class="muted">Nenhum bookmark (Fact) registrado.</p>'

    fact_items = "".join(
        f"""
        <div class="fact-item">
          <div class="fact-label">{_escape(f['title'])}</div>
          <div>{_escape(f.get('description') or '')}</div>
          <div class="muted">Resolvido em {_escape(_fmt_ts(f.get('resolved_at')))}</div>
        </div>
        """
        for f in data["facts"]
    ) or '<p class="muted">Nenhuma Pendência resolvida (Fact) registrada.</p>'

    ind = data["indicators"]
    indicators_html = f"""
      <div class="indicator-box">
        <strong>Indício não confirmado (Indicator)</strong> — não constitui fato;
        exige validação humana antes de uso em laudo formal.
        <ul>
          <li>Detecções YOLO (objetos): {ind['yolo']}</li>
          <li>Faces detectadas: {ind['faces']}</li>
          <li>Placas detectadas: {ind['plates']}</li>
        </ul>
      </div>
    """

    return f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
  <meta charset="UTF-8"/>
  <title>{_escape(title)}</title>
  <style>
    @page {{ size: A4; margin: 18mm 16mm; }}
    body {{ font-family: DejaVu Sans, Helvetica, Arial, sans-serif; color: #222; font-size: 11pt; line-height: 1.45; }}
    h1 {{ font-size: 22pt; margin: 0 0 8px; }}
    h2 {{ font-size: 14pt; color: #1a4a4a; border-bottom: 1.5px solid #1a4a4a; padding-bottom: 4px; margin-top: 28px; }}
    .cover {{ text-align: center; padding: 48px 12px 36px; page-break-after: always; }}
    .cover .brand {{ font-size: 13pt; letter-spacing: 0.2em; color: #1a4a4a; margin-bottom: 24px; }}
    .meta {{ background: #f4f6f6; padding: 14px 16px; border: 1px solid #dde3e3; }}
    .meta-row {{ margin: 4px 0; font-size: 10pt; }}
    .mono {{ font-family: DejaVu Sans Mono, monospace; font-size: 8.5pt; word-break: break-all; }}
    table.custody {{ width: 100%; border-collapse: collapse; font-size: 9pt; }}
    table.custody th, table.custody td {{ border: 1px solid #ccc; padding: 6px 8px; text-align: left; vertical-align: top; }}
    table.custody th {{ background: #e8eeee; }}
    .fact-item {{ border-left: 3px solid #1a4a4a; padding: 8px 12px; margin: 8px 0; background: #f9fbfb; }}
    .fact-label {{ font-weight: bold; }}
    .indicator-box {{ border: 1px dashed #b8860b; background: #fffbeb; padding: 12px 14px; margin: 12px 0; }}
    .muted {{ color: #666; font-size: 9.5pt; }}
    .chart {{ margin: 12px 0; overflow: hidden; }}
    .footer {{ margin-top: 36px; font-size: 8.5pt; color: #666; border-top: 1px solid #ddd; padding-top: 8px; }}
  </style>
</head>
<body>
  <section class="cover">
    <div class="brand">SOKOL</div>
    <h1>{_escape(title)}</h1>
    <p style="font-size:14pt;margin:16px 0 28px">{_escape(case["name"])}</p>
    <div class="meta" style="text-align:left;display:inline-block;min-width:70%">
      <div class="meta-row"><strong>Caso (ID):</strong> {_escape(case["id"])}</div>
      <div class="meta-row"><strong>Referência legal:</strong> {_escape(case.get("legal_ref") or "—")}</div>
      <div class="meta-row"><strong>Período coberto:</strong> {start_ts} → {end_ts}</div>
      <div class="meta-row"><strong>Fuso do caso:</strong> {_escape(data["timezone"])}</div>
      <div class="meta-row"><strong>Gerado em:</strong> {gen_at}</div>
      <div class="meta-row"><strong>Gerado por:</strong> {_escape(data["generated_by"])}</div>
      <div class="meta-row"><strong>Eventos no período:</strong> {event_count}</div>
    </div>
  </section>

  <section>
    <h2>Sumário executivo</h2>
    <p>
      Este laudo reúne a cadeia de custódia dos Documents ingeridos, Facts confirmados
      (Bookmarks e Pendências resolvidas) e visualizações estáticas de atividade.
      Detecções automáticas aparecem apenas como <em>Indicators</em> rotulados —
      nunca como afirmação factual (ADR-0004). Anotações internas de trabalho
      (comentários) não fazem parte deste documento.
    </p>
    <p class="muted">
      Bookmarks: {len(data["bookmarks"])} · Facts (pendências resolvidas): {len(data["facts"])} ·
      Documents: {len(data["documents"])} · Jobs: {len(data["jobs"])}
    </p>
  </section>

  <section>
    <h2>Cadeia de custódia</h2>
    <table class="custody">
      <thead>
        <tr>
          <th>Document</th>
          <th>SHA-256</th>
          <th>Ingestão</th>
          <th>Tipo / status</th>
        </tr>
      </thead>
      <tbody>
        {"".join(custody_rows) or '<tr><td colspan="4">Nenhum Document neste caso.</td></tr>'}
      </tbody>
    </table>
    <h3 style="font-size:11pt;margin-top:16px">Jobs de processamento (caso)</h3>
    <ul>{jobs_list}</ul>
  </section>

  <section>
    <h2>Gráficos</h2>
    <div class="chart">{heatmap_svg}</div>
    <div class="chart">{contacts_svg}</div>
  </section>

  <section>
    <h2>Facts — Bookmarks</h2>
    {bookmark_items}
  </section>

  <section>
    <h2>Facts — Pendências resolvidas</h2>
    {fact_items}
  </section>

  <section>
    <h2>Indicators (indícios não confirmados)</h2>
    {indicators_html}
  </section>

  <div class="footer">
    SOKOL — documento confidencial · gerado em {gen_at} por {_escape(data["generated_by"])}
  </div>
</body>
</html>
"""


def _html_to_pdf(html_content: str) -> bytes:
    try:
        from weasyprint import HTML
    except ImportError as exc:
        raise HTTPException(
            status_code=503,
            detail="WeasyPrint não disponível neste ambiente",
        ) from exc
    return HTML(string=html_content).write_pdf()


def _store_and_respond(
    db: Session,
    *,
    case_id: UUID,
    user_id: UUID,
    title: str,
    html_content: str,
) -> ReportResponse:
    report_id = uuid4()
    now = datetime.now(timezone.utc)
    html_bytes = html_content.encode("utf-8")
    digest = hashlib.sha256(html_bytes).hexdigest()
    content = {
        "html": html_content,
        "title": title,
        "format_version": 2,
    }

    db.execute(
        text("""
            INSERT INTO reports (id, case_id, title, content, generated_by, sha256, generated_at)
            VALUES (:id, :cid, :title, CAST(:content AS jsonb), :uid, :sha, :now)
        """),
        {
            "id": report_id,
            "cid": case_id,
            "title": title,
            "content": json.dumps(content),
            "uid": user_id,
            "sha": digest,
            "now": now,
        },
    )
    append_audit(
        db,
        case_id=case_id,
        actor_user_id=user_id,
        action="report.generated",
        payload={"report_id": str(report_id), "title": title, "sha256": digest},
    )
    db.commit()

    return ReportResponse(
        report_id=str(report_id),
        case_id=str(case_id),
        created_at=now.isoformat(),
        status="ready",
        file_size=len(html_bytes),
    )


# ── Endpoints ──────────────────────────────────────────────────────────────

@router.post("", response_model=ReportResponse, status_code=201)
@router.post("/", response_model=ReportResponse, status_code=201)
def generate_report(
    request: ReportRequest,
    case_id: UUID = Query(...),
    user: CurrentUser = Depends(get_current_user),
):
    """Generate HTML laudo for a case (PDF available on download)."""
    factory = get_session_factory()
    with factory() as db:
        require_case_member(db, case_id, user.user_id)
        data = _gather_report_data(db, case_id, user.user_id)
        html_content = _generate_html_report(data, request.title)
        return _store_and_respond(
            db,
            case_id=case_id,
            user_id=user.user_id,
            title=request.title,
            html_content=html_content,
        )


@router.get("", response_model=list[ReportResponse])
@router.get("/", response_model=list[ReportResponse])
def list_reports(
    case_id: UUID = Query(...),
    user: CurrentUser = Depends(get_current_user),
):
    factory = get_session_factory()
    with factory() as db:
        require_case_member(db, case_id, user.user_id)
        rows = db.execute(
            text("""
                SELECT id, case_id, generated_at, sha256, content
                FROM reports
                WHERE case_id = :cid
                ORDER BY generated_at DESC
            """),
            {"cid": case_id},
        ).mappings().all()

        out: list[ReportResponse] = []
        for r in rows:
            content = r["content"] or {}
            if isinstance(content, str):
                content = json.loads(content)
            html = content.get("html", "") if isinstance(content, dict) else ""
            out.append(
                ReportResponse(
                    report_id=str(r["id"]),
                    case_id=str(r["case_id"]),
                    created_at=r["generated_at"].isoformat() if r["generated_at"] else "",
                    status="ready",
                    file_size=len(html.encode("utf-8")) if html else 0,
                )
            )
        return out


@router.get("/bookmarks/{case_id}")
def list_bookmarks(
    case_id: UUID,
    user: CurrentUser = Depends(get_current_user),
):
    """List bookmarks for a case (used by Bookmarks tab)."""
    factory = get_session_factory()
    with factory() as db:
        require_case_member(db, case_id, user.user_id)
        rows = db.execute(
            text("""
                SELECT id, case_id, event_id, label, note, color, created_at
                FROM bookmarks
                WHERE case_id = :cid
                ORDER BY created_at DESC
            """),
            {"cid": case_id},
        ).mappings().all()
        return [
            {
                "id": str(r["id"]),
                "case_id": str(r["case_id"]),
                "event_id": str(r["event_id"]) if r["event_id"] else None,
                "label": r["label"],
                "note": r["note"],
                "color": r["color"],
                "created_at": r["created_at"].isoformat() if r["created_at"] else "",
            }
            for r in rows
        ]


@router.post("/bookmarks")
def create_bookmark(
    body: BookmarkCreate,
    user: CurrentUser = Depends(get_current_user),
):
    factory = get_session_factory()
    with factory() as db:
        require_case_member(db, body.case_id, user.user_id, roles=["admin", "analista"])
        bid = uuid4()
        now = datetime.now(timezone.utc)
        db.execute(
            text("""
                INSERT INTO bookmarks (id, case_id, event_id, label, note, color, created_by, created_at)
                VALUES (:id, :cid, :eid, :label, :note, :color, :uid, :now)
            """),
            {
                "id": bid,
                "cid": body.case_id,
                "eid": body.event_id,
                "label": body.label,
                "note": body.note,
                "color": body.color,
                "uid": user.user_id,
                "now": now,
            },
        )
        append_audit(
            db,
            case_id=body.case_id,
            actor_user_id=user.user_id,
            action="bookmark.created",
            payload={"bookmark_id": str(bid), "label": body.label},
        )
        db.commit()
        return {"id": str(bid), "status": "created"}


@router.get("/{report_id}/download")
def download_report(
    report_id: UUID,
    case_id: UUID = Query(...),
    format: str = Query("html", pattern="^(html|pdf)$"),
    user: CurrentUser = Depends(get_current_user),
):
    """Download report as HTML (default) or PDF (`?format=pdf`)."""
    factory = get_session_factory()
    with factory() as db:
        require_case_member(db, case_id, user.user_id)
        row = db.execute(
            text("""
                SELECT id, title, content FROM reports
                WHERE id = :id AND case_id = :cid
            """),
            {"id": report_id, "cid": case_id},
        ).mappings().first()
        if not row:
            raise HTTPException(status_code=404, detail="Report not found")

        content = row["content"] or {}
        if isinstance(content, str):
            content = json.loads(content)
        html_content = content.get("html") if isinstance(content, dict) else None
        if not html_content:
            # Regenerate if legacy/empty
            data = _gather_report_data(db, case_id, user.user_id)
            html_content = _generate_html_report(data, row["title"] or "Laudo")

        safe_name = "".join(c if c.isalnum() or c in "-_" else "_" for c in (row["title"] or "report"))[:80]

        append_audit(
            db,
            case_id=case_id,
            actor_user_id=user.user_id,
            action="report.downloaded",
            payload={"report_id": str(report_id), "format": format},
        )
        db.commit()

        if format == "pdf":
            pdf_bytes = _html_to_pdf(html_content)
            return Response(
                content=pdf_bytes,
                media_type="application/pdf",
                headers={
                    "Content-Disposition": f'attachment; filename="{safe_name}.pdf"',
                },
            )

        return Response(
            content=html_content.encode("utf-8"),
            media_type="text/html; charset=utf-8",
            headers={
                "Content-Disposition": f'attachment; filename="{safe_name}.html"',
            },
        )
