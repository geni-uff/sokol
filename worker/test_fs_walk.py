from __future__ import annotations

import io
import sqlite3
import zipfile
from pathlib import Path

from worker.fs_walk import inventory_fs_media, probe_zip_members, walk_ufdr_filesystem


def _minimal_ufdr(path: Path) -> None:
    eml = (
        b"From: a@x.com\r\nTo: b@y.com\r\nSubject: Hello\r\n\r\nBody text\r\n"
    )
    jpeg = b"\xff\xd8\xff\xd9"
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr("report.xml", '<project extractionType="FileSystem"></project>')
        zf.writestr("files/Exchange/msg.eml", eml)
        zf.writestr(
            "files/Text/AAAAAAAA-BBBB-CCCC-DDDD-EEEEEEEEEEEE.txt",
            "Lista de rádios\n",
        )
        zf.writestr("files/Image/photo.jpg", jpeg)

        nested = io.BytesIO()
        with zipfile.ZipFile(nested, "w") as inner:
            inner.writestr(
                "inbox/inner.eml",
                b"From: c@z.com\r\nTo: d@z.com\r\nSubject: Nested\r\n\r\nHi\r\n",
            )
        zf.writestr("files/Archives/mail.zip", nested.getvalue())

        db_path = path.parent / "loc.sqlite"
        conn = sqlite3.connect(db_path)
        conn.execute("CREATE TABLE locations (latitude REAL, longitude REAL, timestamp TEXT)")
        conn.execute(
            "INSERT INTO locations VALUES ( -23.55, -46.63, '2024-01-01T12:00:00Z')"
        )
        conn.execute("CREATE TABLE message (text TEXT)")
        conn.execute("INSERT INTO message VALUES ('oi do sms')")
        conn.commit()
        conn.close()
        zf.write(db_path, "files/Database/sms.db")


def test_fs_walk_reads_eml_and_uuid_notes(tmp_path: Path) -> None:
    ufdr = tmp_path / "mini.ufdr"
    _minimal_ufdr(ufdr)
    result, stats = walk_ufdr_filesystem(ufdr, device_id="d1")
    assert stats["emails_eml"] >= 2
    assert stats["notes"] == 1
    assert stats["nested_archives"] == 1
    assert any(m.app == "email" for m in result.messages)
    assert any(e.kind == "note" for e in result.events)
    assert any(e.kind == "location" for e in result.events)
    assert any(m.app == "sms" for m in result.messages)


def test_inventory_fs_media_hashes_jpeg_without_loading_archive(tmp_path: Path) -> None:
    ufdr = tmp_path / "mini.ufdr"
    _minimal_ufdr(ufdr)
    extra, stats = inventory_fs_media(ufdr, existing_paths=set())
    assert stats["media_members"] == 1
    assert stats["media_hashed"] == 1
    assert extra[0]["name"] == "photo.jpg"
    assert extra[0]["sha256"]
    probe = probe_zip_members(ufdr)
    assert probe["media_image"] == 1
    assert probe["eml"] >= 1
