import os
import zipfile
from pathlib import Path

from sokol.inbox_ready import inbox_file_status


def test_complete_zip_is_ready(tmp_path: Path) -> None:
    zpath = tmp_path / "evidence.ufdr"
    with zipfile.ZipFile(zpath, "w") as zf:
        zf.writestr("report.xml", "<project/>")
    os.utime(zpath, (0, 0))
    ready, reason = inbox_file_status(zpath, "ufdr")
    assert ready is True
    assert reason is None


def test_truncated_zip_is_not_ready(tmp_path: Path) -> None:
    zpath = tmp_path / "evidence.ufdr"
    zpath.write_bytes(b"PK\x03\x04" + b"\x00" * 64)
    os.utime(zpath, (0, 0))
    ready, reason = inbox_file_status(zpath, "ufdr")
    assert ready is False
    assert reason is not None


def test_partial_suffix_is_not_ready(tmp_path: Path) -> None:
    p = tmp_path / "evidence.ufdr.part"
    p.write_bytes(b"x" * 100)
    ready, reason = inbox_file_status(p, "ufdr")
    assert ready is False
    assert "incompleta" in (reason or "")
