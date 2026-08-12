"""Unit tests for restore directory helper and staging policy."""

from __future__ import annotations

from pathlib import Path

from sokol.backup_service import replace_directory_contents


def test_replace_directory_contents(tmp_path: Path):
    src = tmp_path / "src"
    dest = tmp_path / "dest"
    src.mkdir()
    dest.mkdir()
    (src / "a.txt").write_text("new")
    (dest / "old.txt").write_text("stale")
    (dest / "nested").mkdir()
    (dest / "nested" / "x").write_text("gone")

    stats = replace_directory_contents(src, dest)
    assert stats["copied"] is True
    assert (dest / "a.txt").read_text() == "new"
    assert not (dest / "old.txt").exists()
    assert not (dest / "nested").exists()


def test_replace_directory_missing_source(tmp_path: Path):
    dest = tmp_path / "dest"
    dest.mkdir()
    stats = replace_directory_contents(tmp_path / "nope", dest)
    assert stats["copied"] is False
