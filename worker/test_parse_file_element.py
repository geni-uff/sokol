"""UFED 7.x omits the name attribute on <file>; derive it from Local Path."""

from __future__ import annotations

import xml.etree.ElementTree as ET

from worker.ufdr_parser import NS, _parse_file_element


def _file_xml(*, name: str | None, path: str, local_path: str, file_id: str = "f1") -> ET.Element:
    name_attr = f' name="{name}"' if name is not None else ""
    raw = f"""
    <file xmlns="{NS}" id="{file_id}" path="{path}" size="12"{name_attr}>
      <metadata section="File">
        <item name="Local Path">{local_path}</item>
        <item name="SHA256">abc</item>
        <item name="Tags">Image</item>
      </metadata>
    </file>
    """
    return ET.fromstring(raw.strip())


def test_ufed7_missing_name_uses_local_path_basename() -> None:
    el = _file_xml(
        name=None,
        path=r"files\Image\IMG_1346.HEIC",
        local_path=r"files\Image\IMG_1346.HEIC",
    )
    parsed = _parse_file_element(el)
    assert parsed is not None
    assert parsed["name"] == "IMG_1346.HEIC"
    assert parsed["sha256"] == "abc"
    assert parsed["tag"] == "Image"


def test_named_file_keeps_attribute() -> None:
    el = _file_xml(
        name="Document.tar",
        path="files/Archives/Document.tar",
        local_path="files/Archives/Document.tar",
    )
    parsed = _parse_file_element(el)
    assert parsed is not None
    assert parsed["name"] == "Document.tar"


def test_empty_file_without_id_or_path_is_dropped() -> None:
    raw = f'<file xmlns="{NS}" size="0"></file>'
    assert _parse_file_element(ET.fromstring(raw)) is None
