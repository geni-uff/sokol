from sokol.app_filter import app_filter_sql, app_filter_value


def test_app_filter_wraps_ilike() -> None:
    assert "ILIKE" in app_filter_sql("e.app")
    assert app_filter_value("whatsapp") == "%whatsapp%"


def test_app_filter_escapes_like_metacharacters() -> None:
    assert app_filter_value("100%") == r"%100\%%"
    assert app_filter_value("a_b") == r"%a\_b%"
