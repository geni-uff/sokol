"""Match Cellebrite Source values without requiring exact case.

Timeline filter `whatsapp` must hit stored `WhatsApp`. LIKE metacharacters
in the user value are escaped so they stay literal.

Author: Matheus C. Pestana
"""

from __future__ import annotations


def app_filter_sql(column: str, param: str = "app") -> str:
    return f"{column} ILIKE :{param} ESCAPE '\\'"


def app_filter_value(raw: str) -> str:
    escaped = (
        raw.strip().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    )
    return f"%{escaped}%"
