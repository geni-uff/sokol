from sokol.plates_transcriptions import _file_name, _posix, _whatsapp_id


def test_posix_normalizes_windows_separators() -> None:
    assert _posix(r"files\Audio\note.opus") == "files/Audio/note.opus"


def test_file_name_prefers_source_member() -> None:
    assert (
        _file_name(r"files\Audio\abc.opus", "/Message/Media/x/abc.opus") == "abc.opus"
    )


def test_whatsapp_id_from_original_path() -> None:
    path = "/Message/Media/5521976707918@s.whatsapp.net/6/a/note.opus"
    assert _whatsapp_id(path) == "5521976707918"
    assert _whatsapp_id("files/Audio/note.opus") is None
