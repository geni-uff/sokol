"""Case export to ZIP format."""

import json
import zipfile
from io import BytesIO
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy import text
from .auth import CurrentUser, get_current_user, require_case_member
from .db import get_session_factory

router = APIRouter(prefix="/cases", tags=["cases"])


@router.get("/{case_id}/export")
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
        
        # Create ZIP
        zip_buffer = BytesIO()
        with zipfile.ZipFile(zip_buffer, 'w') as zf:
            # Manifest
            manifest = {
                "case_id": str(case_id),
                "case_title": case["title"],
                "exported_at": __import__("datetime").datetime.now().isoformat(),
            }
            zf.writestr("manifest.json", json.dumps(manifest, indent=2))
            
            # Events
            events = db.execute(
                text("SELECT * FROM events WHERE case_id = :cid"),
                {"cid": case_id},
            ).mappings().all()
            
            for event in events:
                event_dict = dict(event)
                event_dict["id"] = str(event_dict["id"])
                event_dict["case_id"] = str(event_dict["case_id"])
                zf.writestr(f"events/{event_dict['id']}.json", json.dumps(event_dict))
            
            # Detections summary
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
        
        zip_buffer.seek(0)
        return StreamingResponse(
            iter([zip_buffer.getvalue()]),
            media_type="application/zip",
            headers={"Content-Disposition": f'attachment; filename="case_{case_id}.zip"'},
        )
