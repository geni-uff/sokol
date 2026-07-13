"""SOKOL UFDR parser — ZIP inventory + report.xml streaming + member classification.

Processes a .ufdr (ZIP) file:
1. Inventory ZIP members without full extraction
2. Stream report.xml with iterparse (memory efficient)
3. Classify files by tag (Image, Audio, Video, etc.)
4. Delegate decoded models to type-specific parsers
5. Populate messages, events, and artifacts in the database
"""

from __future__ import annotations

import hashlib
import json
import os
import xml.etree.ElementTree as ET
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID, uuid4

from .parsers import PARSERS
from .parsers.contract import ParseResult, ParseError, ParsedEntity, ParsedEntityLink

# Cellebrite namespace
NS = "http://pa.cellebrite.com/report/2.0"
NS_MAP = {"cel": NS}


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _md5_bytes(data: bytes) -> str:
    return hashlib.md5(data).hexdigest()


def _append_audit(db, *, case_id, actor_user_id, action, payload):
    """Audit append — inline to avoid circular imports."""
    from sqlalchemy import text
    import json as _json

    audit_id = uuid4()
    now = datetime.now(timezone.utc)
    db.execute(
        text("""
            INSERT INTO audit_log (id, case_id, actor_user_id, action, payload, hash, created_at)
            VALUES (:id, :cid, :actor, :action, :payload, :hash, :now)
        """),
        {
            "id": audit_id,
            "cid": case_id,
            "actor": actor_user_id,
            "action": action,
            "payload": _json.dumps(payload, default=str),
            "hash": hashlib.sha256(
                _json.dumps(payload, default=str).encode()
            ).hexdigest(),
            "now": now,
        },
    )


def _parse_ts(raw: str | None) -> datetime | None:
    if not raw:
        return None
    try:
        clean = raw.replace("+00:00", "").replace(".000", "")
        return datetime.fromisoformat(clean).replace(tzinfo=timezone.utc)
    except (ValueError, TypeError):
        return None


def _extract_model_fields(model_el: ET.Element) -> dict:
    """Convert an XML <model> element to a plain dict for parsers."""
    result = {
        "id": model_el.get("id", ""),
        "type": model_el.get("type", ""),
        "deleted_state": model_el.get("deleted_state", ""),
        "decoding_confidence": model_el.get("decoding_confidence", ""),
        "fields": [],
        "multiModelFields": [],
        "modelFields": [],
    }

    for field_el in model_el.findall(f"{{{NS}}}field"):
        name = field_el.get("name", "")
        ftype = field_el.get("type", "")
        value_el = field_el.find(f"{{{NS}}}value")
        if value_el is not None:
            # Handle formattedTimestamp attribute (TimeStamp type)
            fmt_ts = value_el.get("formattedTimestamp", "")
            if fmt_ts:
                value = fmt_ts
            else:
                value = value_el.text if value_el.text else ""
        else:
            # Handle <empty /> elements
            value = ""
        # Strip CDATA wrappers if present
        if value and value.startswith("<![CDATA[") and value.endswith("]]>"):
            value = value[9:-3]
        result["fields"].append({"name": name, "type": ftype, "value": value})

    for mf_el in model_el.findall(f"{{{NS}}}modelField"):
        mf_name = mf_el.get("name", "")
        mf_type = mf_el.get("type", "")
        nested_model_el = mf_el.find(f"{{{NS}}}model")
        nested = (
            _extract_model_fields(nested_model_el)
            if nested_model_el is not None
            else {}
        )
        result["modelFields"].append(
            {
                "name": mf_name,
                "type": mf_type,
                "model": nested,
            }
        )
        # Flatten nested fields into parent with dot notation
        for nf in nested.get("fields", []):
            result["fields"].append(
                {
                    "name": f"{mf_name}.{nf['name']}",
                    "type": nf["type"],
                    "value": nf["value"],
                }
            )

    for mmf_el in model_el.findall(f"{{{NS}}}multiModelField"):
        mmf_name = mmf_el.get("name", "")
        mmf_type = mmf_el.get("type", "")
        sub_models = []
        for sub in mmf_el.findall(f"{{{NS}}}model"):
            sub_models.append(_extract_model_fields(sub))
        result["multiModelFields"].append(
            {
                "name": mmf_name,
                "type": mmf_type,
                "models": sub_models,
            }
        )

    return result


def classify_zip_members(ufdr_path: str | Path) -> dict:
    """Inventory ZIP members and classify by category."""
    ufdr_path = Path(ufdr_path)
    members = {
        "report.xml": None,
        "settings.json": None,
        "database.json": None,
        "files": {},
        "other": [],
    }

    with zipfile.ZipFile(ufdr_path, "r") as zf:
        for info in zf.infolist():
            name = info.filename
            # Find report.xml (could be in subdirectory)
            if name.endswith("report.xml"):
                members["report.xml"] = name
            elif name.endswith("settings.json"):
                members["settings.json"] = name
            elif name.endswith("database.json"):
                members["database.json"] = name
            elif "/files/" in name or name.startswith("files/"):
                # Classify by directory
                parts = name.split("/")
                try:
                    files_idx = next(i for i, p in enumerate(parts) if p == "files")
                    if files_idx + 1 < len(parts):
                        category = parts[files_idx + 1]
                        members["files"].setdefault(category, []).append(name)
                except StopIteration:
                    members["other"].append(name)
            else:
                members["other"].append(name)

    return members


def inventory_media(ufdr_path: str | Path, members: dict) -> list[dict]:
    """Read file metadata from report.xml <taggedFiles> without full extraction."""
    ufdr_path = Path(ufdr_path)
    media = []

    report_key = members.get("report.xml")
    if not report_key:
        return media

    with zipfile.ZipFile(ufdr_path, "r") as zf:
        with zf.open(report_key) as f:
            # Stream taggedFiles section
            for event, elem in ET.iterparse(f, events=("end",)):
                tag = elem.tag.replace(f"{{{NS}}}", "")
                if tag == "file":
                    file_entry = _parse_file_element(elem)
                    if file_entry:
                        media.append(file_entry)
                    elem.clear()
                elif tag == "taggedFiles":
                    # Done with this section, but we need to keep going for decodedData
                    pass

    return media


def _parse_file_element(file_el: ET.Element) -> dict | None:
    """Parse a <file> element from taggedFiles."""
    name = file_el.get("name", "")
    size = int(file_el.get("size", "0"))
    file_id = file_el.get("id", "")
    path = file_el.get("path", "")

    # Extract metadata
    sha256 = None
    md5 = None
    local_path = None
    tag = None
    timestamps = {}

    for meta in file_el.findall(f"{{{NS}}}metadata"):
        section = meta.get("section", "")
        if section == "File":
            for item in meta.findall(f"{{{NS}}}item"):
                item_name = item.get("name", "")
                item_val = item.text or ""
                if item_val.startswith("<![CDATA[") and item_val.endswith("]]>"):
                    item_val = item_val[9:-3]
                if item_name == "SHA256":
                    sha256 = item_val
                elif item_name == "MD5":
                    md5 = item_val
                elif item_name == "Local Path":
                    local_path = item_val
                elif item_name == "Tags":
                    tag = item_val

    # Extract timestamps
    for ai in file_el.findall(f"{{{NS}}}accessInfo"):
        for ts in ai.findall(f"{{{NS}}}timestamp"):
            ts_name = ts.get("name", "")
            ts_val = ts.get("formattedTimestamp", "") or (ts.text or "")
            timestamps[ts_name] = ts_val

    if not name:
        return None

    return {
        "file_id": file_id,
        "name": name,
        "size": size,
        "path": path,
        "sha256": sha256,
        "md5": md5,
        "local_path": local_path,
        "tag": tag,
        "timestamps": timestamps,
    }


def parse_report_xml(
    ufdr_path: str | Path,
    progress_callback=None,
) -> tuple[dict, list[dict], list[dict]]:
    """
    Stream parse report.xml to extract:
    - project info (case metadata)
    - decoded models (Chat, Call, Contact, etc.)
    - file entries from taggedFiles

    Returns (project_info, decoded_models, file_entries).
    """
    ufdr_path = Path(ufdr_path)

    # Find report.xml
    report_key = None
    with zipfile.ZipFile(ufdr_path, "r") as zf:
        for info in zf.infolist():
            if info.filename.endswith("report.xml"):
                report_key = info.filename
                break

    if not report_key:
        raise FileNotFoundError("report.xml not found in UFDR")

    project_info = {}
    decoded_models = []
    file_entries = []
    current_model_type = None

    with zipfile.ZipFile(ufdr_path, "r") as zf:
        with zf.open(report_key) as f:
            for event, elem in ET.iterparse(f, events=("end",)):
                tag = elem.tag.replace(f"{{{NS}}}", "")

                if tag == "project":
                    project_info = {
                        "id": elem.get("id", ""),
                        "name": elem.get("name", ""),
                        "reportVersion": elem.get("reportVersion", ""),
                        "NodeCount": elem.get("NodeCount", ""),
                        "ModelCount": elem.get("ModelCount", ""),
                    }
                    # Extract case information
                    ci = elem.find(f"{{{NS}}}caseInformation")
                    if ci is not None:
                        for field_el in ci.findall(f"{{{NS}}}field"):
                            field_type = field_el.get("fieldType", "")
                            value = field_el.text or ""
                            project_info[f"case_{field_type}"] = value

                    # Extract metadata
                    for md in elem.findall(f"{{{NS}}}metadata"):
                        for item in md.findall(f"{{{NS}}}item"):
                            item_name = item.get("name", "")
                            item_val = item.text or ""
                            project_info[f"meta_{item_name}"] = item_val

                elif tag == "modelType":
                    current_model_type = elem.get("type", "")
                    # Collect all models in this modelType
                    for model_el in elem.findall(f"{{{NS}}}model"):
                        model_dict = _extract_model_fields(model_el)
                        model_dict["_modelType"] = current_model_type
                        decoded_models.append(model_dict)
                    elem.clear()

                elif tag == "file":
                    file_entry = _parse_file_element(elem)
                    if file_entry:
                        file_entries.append(file_entry)

                elif tag == "decodedData":
                    pass  # Will be handled by modelType children

    return project_info, decoded_models, file_entries


def process_ufdr(
    db,
    ufdr_path: str | Path,
    case_id: UUID,
    document_id: UUID,
    device_id: str = "",
    progress_callback=None,
) -> dict:
    """
    Main entry point: parse UFDR and populate database tables.
    Returns stats dict.
    """
    from sqlalchemy import text

    ufdr_path = Path(ufdr_path)

    def emit(stage: str, progress: float, message: str = ""):
        if progress_callback:
            progress_callback(stage, progress, message)

    # Phase 1: Inventory
    emit("inventory", 0.05, "Classifying ZIP members...")
    members = classify_zip_members(ufdr_path)

    # Phase 2: Stream report.xml
    emit("parse_xml", 0.10, "Streaming report.xml...")
    project_info, decoded_models, file_entries = parse_report_xml(ufdr_path)

    if not device_id:
        device_id = project_info.get("id", "unknown")

    emit(
        "parse_xml",
        0.30,
        f"Parsed {len(decoded_models)} models, {len(file_entries)} files",
    )

    # Phase 3: Create artifacts from file entries
    emit("artifacts", 0.35, "Creating artifacts...")
    file_id_map = {}  # file_id -> artifact_id
    artifact_count = 0

    for fe in file_entries:
        artifact_id = uuid4()
        now = datetime.now(timezone.utc)
        tag = fe.get("tag", "Uncategorized")
        kind_map = {
            "Image": "image",
            "Audio": "audio",
            "Video": "video",
            "Text": "document",
            "Document": "document",
            "Database": "database",
            "Archives": "archive",
            "Configuration": "config",
            "Exchange": "email",
            "Uncategorized": "other",
        }
        kind = kind_map.get(tag, "other")

        # Determine mime type from extension
        ext = Path(fe["name"]).suffix.lower()
        mime_map = {
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".png": "image/png",
            ".heic": "image/heic",
            ".webp": "image/webp",
            ".opus": "audio/opus",
            ".m4a": "audio/mp4",
            ".mp3": "audio/mpeg",
            ".mp4": "video/mp4",
            ".mov": "video/quicktime",
            ".pdf": "application/pdf",
            ".txt": "text/plain",
            ".csv": "text/csv",
            ".html": "text/html",
            ".json": "application/json",
        }
        mime_type = mime_map.get(ext, "application/octet-stream")

        db.execute(
            text("""
                INSERT INTO artifacts (id, case_id, document_id, kind, source_member,
                                       media_hash, mime_type, size_bytes, status, meta)
                VALUES (:id, :cid, :did, :kind, :member, :hash, :mime, :size, 'ready', :meta)
            """),
            {
                "id": artifact_id,
                "cid": case_id,
                "did": document_id,
                "kind": kind,
                "member": fe.get("local_path") or fe["name"],
                "hash": fe.get("sha256"),
                "mime": mime_type,
                "size": fe["size"],
                "meta": json.dumps(
                    {
                        "file_id": fe["file_id"],
                        "original_path": fe["path"],
                        "md5": fe.get("md5"),
                        "tag": tag,
                        "timestamps": fe.get("timestamps", {}),
                    }
                ),
            },
        )
        file_id_map[fe["file_id"]] = artifact_id
        artifact_count += 1

    db.commit()
    emit("artifacts", 0.40, f"Created {artifact_count} artifacts")

    # Phase 4: Parse decoded models
    emit("parse_models", 0.45, f"Parsing {len(decoded_models)} decoded models...")
    total = len(decoded_models)
    parsed_result = ParseResult()
    model_type_counts = {}

    for i, model in enumerate(decoded_models):
        model_type = model.get("_modelType", model.get("type", ""))
        model_type_counts[model_type] = model_type_counts.get(model_type, 0) + 1

        parser_fn = PARSERS.get(model_type)
        if parser_fn:
            try:
                result = parser_fn(model, device_id=device_id)
                parsed_result.messages.extend(result.messages)
                parsed_result.events.extend(result.events)
                parsed_result.errors.extend(result.errors)
                parsed_result.artifact_hashes.extend(result.artifact_hashes)
                if hasattr(result, "entities"):
                    parsed_result.entities.extend(result.entities)
                if hasattr(result, "entity_links"):
                    parsed_result.entity_links.extend(result.entity_links)
            except Exception as e:
                parsed_result.errors.append(
                    ParseError(
                        model_id=model.get("id", ""),
                        model_type=model_type,
                        error=str(e),
                        recoverable=True,
                    )
                )

        if (i + 1) % 100 == 0 or i + 1 == total:
            progress = 0.45 + (i + 1) / total * 0.30
            emit("parse_models", progress, f"Parsed {i + 1}/{total} models")

    # Phase 4.5: Link messages to their events (1:1 by construction)
    msg_idx = 0
    for evt in parsed_result.events:
        if evt.ref_table == "messages":
            if msg_idx < len(parsed_result.messages):
                evt.ref_id = uuid4()  # placeholder — set to actual msg_id below
                msg_idx += 1

    # Phase 5: Insert messages
    emit(
        "insert_messages", 0.75, f"Inserting {len(parsed_result.messages)} messages..."
    )
    msg_ids = []  # track inserted message IDs in order
    msg_count = 0
    for msg in parsed_result.messages:
        msg_id = uuid4()
        msg_ids.append(msg_id)
        now = datetime.now(timezone.utc)
        db.execute(
            text("""
                INSERT INTO messages (id, case_id, device_id, app, chat_id, sender,
                                      counterpart, ts, direction, text, media_hash,
                                      is_forwarded, meta)
                VALUES (:id, :cid, :did, :app, :chat, :sender, :cp, :ts, :dir, :text,
                        :media, :fwd, :meta)
            """),
            {
                "id": msg_id,
                "cid": case_id,
                "did": msg.device_id or device_id,
                "app": msg.app,
                "chat": msg.chat_id,
                "sender": msg.sender,
                "cp": msg.counterpart,
                "ts": msg.ts,
                "dir": msg.direction,
                "text": msg.text,
                "media": msg.media_hash,
                "fwd": msg.is_forwarded,
                "meta": json.dumps(msg.meta),
            },
        )
        msg_count += 1

    # Now link events to their actual message IDs
    msg_evt_idx = 0
    for evt in parsed_result.events:
        if evt.ref_table == "messages" and msg_evt_idx < len(msg_ids):
            evt.ref_id = msg_ids[msg_evt_idx]
            msg_evt_idx += 1

    db.commit()
    emit("insert_messages", 0.80, f"Inserted {msg_count} messages")

    # Phase 5.5: Insert entities (deduplicated by kind+value)
    emit(
        "insert_entities", 0.82, f"Inserting {len(parsed_result.entities)} entities..."
    )
    entity_id_map = {}  # (kind, value) -> entity_id
    entity_count = 0

    for ent in parsed_result.entities:
        # Accept both ParsedEntity objects and plain dicts
        if isinstance(ent, dict):
            e_kind = ent.get("kind", "")
            e_value = ent.get("value", "")
            e_name = ent.get("display_name")
            e_meta = ent.get("meta", {})
        else:
            e_kind = ent.kind
            e_value = ent.value
            e_name = ent.display_name
            e_meta = ent.meta

        key = (e_kind, e_value)
        if key in entity_id_map:
            continue  # skip duplicate

        entity_id = uuid4()
        entity_id_map[key] = entity_id
        now = datetime.now(timezone.utc)
        db.execute(
            text("""
                INSERT INTO entities (id, case_id, kind, value, display_name, meta, created_at)
                VALUES (:id, :cid, :kind, :value, :name, :meta, :now)
                ON CONFLICT DO NOTHING
            """),
            {
                "id": entity_id,
                "cid": case_id,
                "kind": e_kind,
                "value": e_value,
                "name": e_name,
                "meta": json.dumps(e_meta),
                "now": now,
            },
        )
        entity_count += 1

    # Insert entity links
    link_count = 0
    for link in parsed_result.entity_links:
        if isinstance(link, dict):
            l_src_kind = link.get("src_kind", "")
            l_src_value = link.get("src_value", "")
            l_dst_kind = link.get("dst_kind", "")
            l_dst_value = link.get("dst_value", "")
            l_kind = link.get("kind", "")
            l_weight = link.get("weight", 1.0)
            l_meta = link.get("meta", {})
        else:
            l_src_kind = link.src_kind
            l_src_value = link.src_value
            l_dst_kind = link.dst_kind
            l_dst_value = link.dst_value
            l_kind = link.kind
            l_weight = link.weight
            l_meta = link.meta

        src_id = entity_id_map.get((l_src_kind, l_src_value))
        dst_id = entity_id_map.get((l_dst_kind, l_dst_value))

        if src_id and dst_id and src_id != dst_id:
            now = datetime.now(timezone.utc)
            db.execute(
                text("""
                    INSERT INTO entity_links (id, case_id, src_id, dst_id, kind, weight, meta, created_at)
                    VALUES (:id, :cid, :src, :dst, :kind, :weight, :meta, :now)
                """),
                {
                    "id": uuid4(),
                    "cid": case_id,
                    "src": src_id,
                    "dst": dst_id,
                    "kind": l_kind,
                    "weight": l_weight,
                    "meta": json.dumps(l_meta),
                    "now": now,
                },
            )
            link_count += 1

    db.commit()
    emit(
        "insert_entities", 0.84, f"Inserted {entity_count} entities, {link_count} links"
    )

    # Phase 5.6: Populate media table from artifacts with SHA-256
    emit("insert_media", 0.85, "Populating media table...")
    media_count = 0
    for fe in file_entries:
        sha256 = fe.get("sha256")
        if not sha256:
            continue
        ext = Path(fe["name"]).suffix.lower()
        mime_map = {
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".png": "image/png",
            ".heic": "image/heic",
            ".webp": "image/webp",
            ".opus": "audio/opus",
            ".m4a": "audio/mp4",
            ".mp3": "audio/mpeg",
            ".mp4": "video/mp4",
            ".mov": "video/quicktime",
        }
        mime = mime_map.get(ext, "application/octet-stream")
        now = datetime.now(timezone.utc)
        db.execute(
            text("""
                INSERT INTO media (hash, mime_type, size_bytes, storage_ref, created_at)
                VALUES (:hash, :mime, :size, :ref, :now)
                ON CONFLICT (hash) DO NOTHING
            """),
            {
                "hash": sha256,
                "mime": mime,
                "size": fe["size"],
                "ref": json.dumps(
                    {"file_id": fe["file_id"], "local_path": fe.get("local_path")}
                ),
                "now": now,
            },
        )
        media_count += 1

    db.commit()
    emit("insert_media", 0.87, f"Populated {media_count} media entries")

    # Phase 5.7: Vision detection on images
    vision_detection_count = 0
    image_files = [
        fe
        for fe in file_entries
        if fe.get("sha256")
        and Path(fe["name"]).suffix.lower()
        in {".jpg", ".jpeg", ".png", ".webp", ".heic"}
    ]
    if image_files:
        emit(
            "vision_detect",
            0.875,
            f"Running vision detection on {len(image_files)} images...",
        )
        try:
            import os as _os
            import asyncio
            from .vision_client import VisionClient

            vision_url = _os.getenv("SOKOL_VISION_API_URL", "http://localhost:8007")
            vision_client = VisionClient(base_url=vision_url)

            # Check if vision service is available
            health = asyncio.get_event_loop().run_until_complete(vision_client.health())
            if health == "ok":
                # Get image paths from extracted files
                ufdr_extract_dir = Path(
                    _os.getenv("SOKOL_UFDR_EXTRACT_DIR", "/data/ufdr-extract")
                )
                image_paths = []
                image_hashes = []

                for fe in image_files:
                    sha256 = fe.get("sha256")
                    local_path = fe.get("local_path")
                    if not local_path:
                        continue

                    # Find the actual file on disk
                    for child in ufdr_extract_dir.rglob(Path(local_path).name):
                        if child.is_file():
                            image_paths.append(str(child))
                            image_hashes.append(sha256)
                            break

                if image_paths:
                    # Run batch detection
                    results = asyncio.get_event_loop().run_until_complete(
                        vision_client.detect_batch(
                            image_paths=image_paths,
                            image_ids=image_hashes,
                            models=["coco", "firearm", "threat"],
                        )
                    )

                    # Insert detections into database
                    for result in results:
                        image_id = result.get("image_id")
                        for det in result.get("detections", []):
                            db.execute(
                                text("""
                                    INSERT INTO image_detections 
                                    (case_id, media_hash, model_name, class_name, class_id, confidence, bbox, pipeline_version)
                                    VALUES (:case_id, :media_hash, :model, :class, :cls_id, :conf, :bbox, :version)
                                """),
                                {
                                    "case_id": case_id,
                                    "media_hash": image_id,
                                    "model": det["model"],
                                    "class": det["class_name"],
                                    "cls_id": det["class_id"],
                                    "conf": det["confidence"],
                                    "bbox": json.dumps(det["bbox"]),
                                    "version": "yolov8n-v1",
                                },
                            )
                            vision_detection_count += 1

                    db.commit()

            emit(
                "vision_detect",
                0.88,
                f"Vision detection: {vision_detection_count} objects found",
            )
        except Exception as e:
            # Vision detection failure shouldn't block ingestion
            emit("vision_detect", 0.88, f"Vision detection skipped: {e}")

    # Phase 6: Insert events
    emit("insert_events", 0.88, f"Inserting {len(parsed_result.events)} events...")
    evt_count = 0
    evt_ids = []
    for evt in parsed_result.events:
        evt_id = uuid4()
        evt_ids.append(evt_id)
        now = datetime.now(timezone.utc)

        geo_sql = "NULL"
        geo_params = {}
        if evt.geo_lat is not None and evt.geo_lon is not None:
            geo_sql = "ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)::geography"
            geo_params = {"lat": evt.geo_lat, "lon": evt.geo_lon}

        db.execute(
            text(f"""
                INSERT INTO events (id, case_id, device_id, ts, tz_original, kind,
                                    actor, counterpart, app, ref_table, ref_id,
                                    summary, geo, meta)
                VALUES (:id, :cid, :did, :ts, :tz, :kind, :actor, :cp, :app,
                        :ref_table, :ref_id, :summary, {geo_sql}, :meta)
            """),
            {
                "id": evt_id,
                "cid": case_id,
                "did": evt.device_id or device_id,
                "ts": evt.ts,
                "tz": evt.tz_original,
                "kind": evt.kind,
                "actor": evt.actor,
                "cp": evt.counterpart,
                "app": evt.app,
                "ref_table": evt.ref_table,
                "ref_id": evt.ref_id or evt_id,
                "summary": evt.summary,
                "meta": json.dumps(evt.meta),
                **geo_params,
            },
        )
        evt_count += 1

    db.commit()
    emit("insert_events", 0.92, f"Inserted {evt_count} events")

    # Phase 6.2: Realtime watchlist scan on the rows just inserted (v2-07).
    # Engine lives in the API tree; load it by path so worker needs no package dep.
    try:
        import importlib.util

        engine_path = (
            Path(__file__).resolve().parent.parent
            / "api" / "src" / "sokol" / "watchlist_engine.py"
        )
        spec = importlib.util.spec_from_file_location("watchlist_engine", engine_path)
        wl_engine = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(wl_engine)

        wl_hits = wl_engine.scan_rows(
            db, str(case_id), event_ids=evt_ids, message_ids=msg_ids
        )
        db.commit()
        if wl_hits:
            emit("watchlist", 0.925, f"⚠ {wl_hits} watchlist hit(s) detectado(s)")
        else:
            emit("watchlist", 0.925, "Watchlists: sem hits")
    except Exception as e:
        emit("watchlist", 0.925, f"Watchlist scan skipped: {e}")

    # Phase 6.5: Create chunks from messages for semantic search
    chunk_count = 0
    if msg_count > 0:
        emit("chunking", 0.93, f"Creating chunks from {msg_count} messages...")
        try:
            from .chunker import chunk_messages
            import os
            import httpx as _httpx

            embed_base_url = os.getenv(
                "SOKOL_EMBED_BASE_URL", "http://localhost:1234/v1"
            )
            embed_model_id = os.getenv(
                "SOKOL_ACTIVE_EMBED_MODEL", "text-embedding-qwen3-embedding-0.6b"
            )
            embed_dim = int(os.getenv("SOKOL_EMBED_DIM", "1024"))

            def _embed_batch(texts: list[str]) -> list[list[float]]:
                """Embed a batch of texts via LM Studio."""
                embed_url = (
                    f"{embed_base_url}/embeddings"
                    if embed_base_url.endswith("/v1")
                    else f"{embed_base_url}/v1/embeddings"
                )
                resp = _httpx.post(
                    embed_url,
                    json={"input": texts, "model": embed_model_id},
                    timeout=120.0,
                )
                resp.raise_for_status()
                data = resp.json()
                return [item["embedding"] for item in data["data"]]

            chunk_count = chunk_messages(
                db=db,
                case_id=case_id,
                embedding_model_id=embed_model_id,
                embedding_dim=embed_dim,
                embed_fn=_embed_batch,
            )
            emit("chunking", 0.95, f"Created {chunk_count} chunks")
        except Exception as e:
            # Chunking failure shouldn't block ingestion
            emit("chunking", 0.95, f"Chunking skipped: {e}")

    # Phase 6.6: Embed event summaries for semantic search
    event_embed_count = 0
    if evt_count > 0:
        emit("embed_events", 0.96, f"Embedding {evt_count} events...")
        try:
            import os
            import httpx as _httpx
            from .event_embedder import embed_events

            embed_base_url = os.getenv(
                "SOKOL_EMBED_BASE_URL", "http://localhost:1234/v1"
            )
            embed_model_id = os.getenv(
                "SOKOL_ACTIVE_EMBED_MODEL", "text-embedding-qwen3-embedding-0.6b"
            )
            embed_dim = int(os.getenv("SOKOL_EMBED_DIM", "1024"))

            def _embed_batch_events(texts: list[str]) -> list[list[float]]:
                embed_url = (
                    f"{embed_base_url}/embeddings"
                    if embed_base_url.endswith("/v1")
                    else f"{embed_base_url}/v1/embeddings"
                )
                resp = _httpx.post(
                    embed_url,
                    json={"input": texts, "model": embed_model_id},
                    timeout=120.0,
                )
                resp.raise_for_status()
                data = resp.json()
                return [item["embedding"] for item in data["data"]]

            event_embed_count = embed_events(
                db=db,
                case_id=case_id,
                embedding_model_id=embed_model_id,
                embedding_dim=embed_dim,
                embed_fn=_embed_batch_events,
            )
            emit("embed_events", 0.97, f"Embedded {event_embed_count} events")
        except Exception as e:
            emit("embed_events", 0.97, f"Event embedding skipped: {e}")

    # Phase 7: Audit
    emit("audit", 0.95, "Writing audit log...")
    _append_audit(
        db,
        case_id=case_id,
        actor_user_id=None,
        action="ingest.ufdr_completed",
        payload={
            "document_id": str(document_id),
            "device_id": device_id,
            "model_types": model_type_counts,
            "messages_inserted": msg_count,
            "events_inserted": evt_count,
            "entities_inserted": entity_count,
            "entity_links_inserted": link_count,
            "media_populated": media_count,
            "artifacts_created": artifact_count,
            "errors": len(parsed_result.errors),
        },
    )
    db.commit()

    emit("done", 1.0, "Ingestion complete")

    return {
        "device_id": device_id,
        "project_info": project_info,
        "model_type_counts": model_type_counts,
        "messages_inserted": msg_count,
        "events_inserted": evt_count,
        "entities_inserted": entity_count,
        "entity_links_inserted": link_count,
        "media_populated": media_count,
        "artifacts_created": artifact_count,
        "chunks_created": chunk_count if msg_count > 0 else 0,
        "parse_errors": len(parsed_result.errors),
        "error_details": [
            {"model_id": e.model_id, "type": e.model_type, "error": e.error}
            for e in parsed_result.errors[:50]
        ],
    }
