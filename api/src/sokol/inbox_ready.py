"""Detect inbox files that are still being copied.

A UFDR is a ZIP; the central directory is at the end. While `cp`/`rsync`
writes a multi-GB file, `zipfile.is_zipfile` is false. After the copy
finishes, it becomes true. Partial suffixes (.part, .crdownload) are
never ingestible.

Author: Matheus C. Pestana
"""

from __future__ import annotations

import time
import zipfile
from pathlib import Path

_PARTIAL_SUFFIXES = {
    ".part",
    ".tmp",
    ".temp",
    ".crdownload",
    ".filepart",
    ".download",
    ".partial",
}
_WRITE_GRACE_SECONDS = 2.0


def inbox_file_status(path: Path, source_type: str = "ufdr") -> tuple[bool, str | None]:
    """Return (ready, reason). Directories are not ready to ingest as a file."""
    if not path.is_file():
        return False, "não é um arquivo"
    name = path.name.lower()
    if any(name.endswith(suf) for suf in _PARTIAL_SUFFIXES):
        return False, "nome de cópia incompleta (.part / .tmp / .crdownload)"
    try:
        st = path.stat()
    except OSError as exc:
        return False, str(exc)
    age = time.time() - st.st_mtime
    if age < _WRITE_GRACE_SECONDS:
        return False, "ainda sendo escrito (mtime recente)"
    stype = (source_type or "ufdr").lower()
    suffix = path.suffix.lower()
    if stype == "ufdr" or suffix == ".ufdr":
        if st.st_size < 22:
            return False, "ZIP pequeno demais (cópia incompleta)"
        if not zipfile.is_zipfile(path):
            return False, "ZIP incompleto — a cópia ainda não terminou"
    return True, None
