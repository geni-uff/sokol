"""Unit tests for bulk export formatters (v2-10)."""

from __future__ import annotations

from sokol.export_formats import (
    TIMELINE_CSV_HEADER,
    format_kml_document,
    format_timeline_csv_row,
    format_vcard,
)


def test_vcard_30_has_required_fields_and_phone_email():
    card = format_vcard(
        name="Ana Paula Santos",
        phones=["+5511988776655"],
        emails=["ana@example.com"],
    )
    assert "BEGIN:VCARD" in card
    assert "VERSION:3.0" in card
    assert "FN:Ana Paula Santos" in card
    assert "TEL;TYPE=CELL:+5511988776655" in card
    assert "EMAIL;TYPE=INTERNET:ana@example.com" in card
    assert card.strip().endswith("END:VCARD")


def test_vcard_escapes_special_chars_in_name():
    card = format_vcard(name="Foo;Bar,Baz\\Qux", phones=[], emails=[])
    assert "FN:Foo\\;Bar\\,Baz\\\\Qux" in card


def test_kml_uses_lon_lat_order():
    kml = format_kml_document(
        [
            {"name": "2024-01-15 10:30:00", "lon": -43.1729, "lat": -22.9068},
        ]
    )
    assert '<?xml version="1.0"' in kml
    assert "<kml xmlns=" in kml
    assert "<Placemark>" in kml
    assert "<name>2024-01-15 10:30:00</name>" in kml
    # KML is lon,lat[,alt] — never lat,lon
    assert "<coordinates>-43.1729,-22.9068,0</coordinates>" in kml
    assert "<coordinates>-22.9068,-43.1729" not in kml


def test_timeline_csv_header_and_row_escaping():
    assert TIMELINE_CSV_HEADER == (
        "ts_utc,ts_case_tz,kind,app,description,ref_table,ref_id"
    )
    row = format_timeline_csv_row(
        {
            "ts_utc": "2024-01-15T13:30:00+00:00",
            "ts_case_tz": "2024-01-15 10:30:00",
            "kind": "message",
            "app": "WhatsApp",
            "description": 'Said "hello", then bye',
            "ref_table": "messages",
            "ref_id": "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
        }
    )
    assert row.startswith("2024-01-15T13:30:00+00:00,2024-01-15 10:30:00,message,WhatsApp,")
    assert '"Said ""hello"", then bye"' in row
    assert row.endswith(",messages,aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee")
