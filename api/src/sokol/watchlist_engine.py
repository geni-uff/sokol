"""SOKOL — watchlist scan engine, shared between API and ingest worker.

Standalone on purpose: no relative imports, only stdlib + sqlalchemy.text,
so the worker can load it via importlib from the mounted repo without
pulling the whole sokol package.

Match rules:
- phone: digit-normalized exact match (strips +55/0 prefixes, spaces, hyphens)
- cpf/cnpj/plate/email: exact after cleanup
- name: exact after accent-fold, or Levenshtein <= 1 (fuzzy)
- keyword/other: case-insensitive substring (regex)
"""

from __future__ import annotations

import re
import unicodedata

from sqlalchemy import text

EXACT_TYPES = {"cpf", "cnpj", "plate", "email", "entity"}


def normalize_phone(s: str) -> str:
    digits = re.sub(r"\D", "", s or "")
    if digits.startswith("55") and len(digits) > 10:
        digits = digits[2:]
    return digits.lstrip("0")


def normalize_text(s: str) -> str:
    s = (s or "").lower().strip()
    return "".join(
        c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn"
    )


def levenshtein(a: str, b: str) -> int:
    if len(a) < len(b):
        a, b = b, a
    if not b:
        return len(a)
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        curr = [i]
        for j, cb in enumerate(b, 1):
            curr.append(min(prev[j] + 1, curr[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = curr
    return prev[-1]


def match_pattern(watch_type: str, pattern: str, candidate: str):
    """Return (match_type, confidence) or None."""
    if not pattern or not candidate:
        return None

    if watch_type == "phone":
        p, c = normalize_phone(pattern), normalize_phone(candidate)
        if p and len(p) >= 8 and p in c:
            return ("exact", 1.0)
        return None

    if watch_type in EXACT_TYPES:
        p = re.sub(r"[\s.\-/]", "", pattern.lower())
        c = re.sub(r"[\s.\-/]", "", candidate.lower())
        if p and p in c:
            return ("exact", 1.0)
        return None

    if watch_type == "name":
        p, c = normalize_text(pattern), normalize_text(candidate)
        if not p:
            return None
        if p in c:
            return ("exact", 1.0)
        # fuzzy only against individual words of similar length
        for word in c.split():
            if abs(len(word) - len(p)) <= 1 and levenshtein(p, word) <= 1:
                return ("fuzzy", 0.85)
        return None

    # keyword / fallback: case-insensitive substring
    if re.search(re.escape(pattern), candidate, re.IGNORECASE):
        return ("regex", 0.9)
    return None


def scan_rows(db, case_id, event_ids=None, message_ids=None) -> int:
    """Scan active watchlists (case-scoped or global) against events/messages.

    If event_ids/message_ids are given, only those rows are scanned
    (incremental post-ingest scan); otherwise the whole case is scanned.
    Dedup: (watchlist_id, pattern, event_id/message_id) never inserted twice.
    Returns the number of hits created.
    """
    watchlists = db.execute(
        text("""
            SELECT id, watch_type, patterns FROM watchlists
            WHERE is_active = true AND (case_id = :cid OR is_global = true)
        """),
        {"cid": case_id},
    ).fetchall()
    if not watchlists:
        return 0

    ev_where = "case_id = :cid"
    msg_where = "case_id = :cid"
    bind_ev: dict = {"cid": case_id}
    bind_msg: dict = {"cid": case_id}
    if event_ids is not None:
        ev_where += " AND id = ANY(:ids)"
        bind_ev["ids"] = [str(i) for i in event_ids]
    if message_ids is not None:
        msg_where += " AND id = ANY(:ids)"
        bind_msg["ids"] = [str(i) for i in message_ids]

    events = (
        []
        if event_ids == []
        else db.execute(
            text(f"SELECT id, summary, actor, counterpart FROM events WHERE {ev_where}"),
            bind_ev,
        ).fetchall()
    )
    messages = (
        []
        if message_ids == []
        else db.execute(
            text(f"SELECT id, text, sender, counterpart FROM messages WHERE {msg_where}"),
            bind_msg,
        ).fetchall()
    )

    existing = db.execute(
        text("""
            SELECT wh.watchlist_id, wh.matched_pattern, wh.event_id, wh.message_id
            FROM watchlist_hits wh
            JOIN watchlists w ON w.id = wh.watchlist_id
            WHERE w.case_id = :cid OR w.is_global = true
        """),
        {"cid": case_id},
    ).fetchall()
    seen = {
        (str(r[0]), r[1], str(r[2] or ""), str(r[3] or "")) for r in existing
    }

    hits = 0
    for wl in watchlists:
        wl_id, watch_type, patterns = str(wl[0]), wl[1], wl[2]
        if not isinstance(patterns, list):
            continue

        for row, is_event in [(e, True) for e in events] + [(m, False) for m in messages]:
            row_id = str(row[0])
            searchable = " ".join(str(v) for v in row[1:] if v)
            if not searchable:
                continue
            for pattern in patterns:
                result = match_pattern(watch_type, pattern, searchable)
                if not result:
                    continue
                match_type, confidence = result
                key = (
                    wl_id,
                    pattern,
                    row_id if is_event else "",
                    "" if is_event else row_id,
                )
                if key in seen:
                    continue
                db.execute(
                    text("""
                        INSERT INTO watchlist_hits
                            (id, watchlist_id, case_id, event_id, message_id,
                             matched_pattern, matched_text, confidence, match_type)
                        VALUES (gen_random_uuid(), :wid, :cid,
                                :eid, :mid, :pat, :txt, :conf, :mtype)
                    """),
                    {
                        "wid": wl_id,
                        "cid": case_id,
                        "eid": row_id if is_event else None,
                        "mid": None if is_event else row_id,
                        "pat": pattern,
                        "txt": searchable[:500],
                        "conf": confidence,
                        "mtype": match_type,
                    },
                )
                seen.add(key)
                hits += 1
    return hits
