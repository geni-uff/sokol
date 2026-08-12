"""Pure formatters for bulk case export (CSV / VCard / KML)."""

from __future__ import annotations

import csv
from io import StringIO
from xml.sax.saxutils import escape as xml_escape

TIMELINE_CSV_HEADER = "ts_utc,ts_case_tz,kind,app,description,ref_table,ref_id"


def _vcard_escape(value: str) -> str:
    """Escape text for vCard 3.0 (RFC 2426)."""
    return (
        value.replace("\\", "\\\\")
        .replace(";", "\\;")
        .replace(",", "\\,")
        .replace("\n", "\\n")
    )


def format_vcard(*, name: str, phones: list[str], emails: list[str]) -> str:
    """Build a single vCard 3.0 block."""
    lines = [
        "BEGIN:VCARD",
        "VERSION:3.0",
        f"FN:{_vcard_escape(name)}",
        f"N:{_vcard_escape(name)};;;",
    ]
    for phone in phones:
        if phone:
            lines.append(f"TEL;TYPE=CELL:{_vcard_escape(phone)}")
    for email in emails:
        if email:
            lines.append(f"EMAIL;TYPE=INTERNET:{_vcard_escape(email)}")
    lines.append("END:VCARD")
    return "\n".join(lines) + "\n"


def format_kml_document(placemarks: list[dict]) -> str:
    """Build a KML 2.2 document. Coordinates are lon,lat,alt (never lat,lon)."""
    parts = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<kml xmlns="http://www.opengis.net/kml/2.2">',
        "<Document>",
    ]
    for pm in placemarks:
        name = xml_escape(str(pm["name"]))
        lon = float(pm["lon"])
        lat = float(pm["lat"])
        parts.append(
            "<Placemark>"
            f"<name>{name}</name>"
            "<Point>"
            f"<coordinates>{lon},{lat},0</coordinates>"
            "</Point>"
            "</Placemark>"
        )
    parts.extend(["</Document>", "</kml>"])
    return "\n".join(parts) + "\n"


def format_timeline_csv_row(row: dict) -> str:
    """Serialize one timeline export row as a CSV line (no trailing newline)."""
    buf = StringIO()
    writer = csv.writer(buf, lineterminator="")
    writer.writerow(
        [
            row.get("ts_utc") or "",
            row.get("ts_case_tz") or "",
            row.get("kind") or "",
            row.get("app") or "",
            row.get("description") or "",
            row.get("ref_table") or "",
            row.get("ref_id") or "",
        ]
    )
    return buf.getvalue()
