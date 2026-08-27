"""Unit tests for embed URL assembly (no LM Studio, no Postgres).

Author: Matheus C. Pestana
"""

from worker.embed_index import CHUNK_BATCH, make_embed_fn, _embed_urls


def test_chunk_batch_is_smaller_than_event_batch() -> None:
    assert CHUNK_BATCH <= 16


def test_make_embed_fn_posts_to_v1_embeddings(monkeypatch) -> None:
    captured: dict = {}

    class _Resp:
        is_success = True
        status_code = 200
        text = ""

        def json(self) -> dict:
            return {"data": [{"embedding": [0.0] * 1024}, {"embedding": [1.0] * 1024}]}

    def fake_post(url, json, timeout):
        captured["url"] = url
        captured["json"] = json
        captured["timeout"] = timeout
        return _Resp()

    monkeypatch.setattr("worker.embed_index.httpx.post", fake_post)
    fn = make_embed_fn("http://localhost:1234/v1", "text-embedding-qwen3-embedding-0.6b", 1024)
    out = fn(["olá", ""])
    assert captured["url"] == "http://localhost:1234/v1/embeddings"
    assert captured["json"]["input"] == ["olá", "."]
    assert captured["timeout"] == 180.0
    assert len(out) == 2
    assert len(out[0]) == 1024


def test_embed_urls_appends_sokol_embed_fallback(monkeypatch) -> None:
    monkeypatch.delenv("SOKOL_EMBED_FALLBACK_URL", raising=False)
    urls = _embed_urls("http://localhost:1234/v1")
    assert urls == [
        "http://localhost:1234/v1/embeddings",
        "http://localhost:8001/v1/embeddings",
    ]


def test_make_embed_fn_falls_back_when_primary_returns_400(monkeypatch) -> None:
    calls: list[str] = []

    class _Resp:
        def __init__(self, url: str, ok: bool) -> None:
            self.url = url
            self.status_code = 200 if ok else 400
            self.is_success = ok
            self.text = "Failed to load model" if not ok else ""
            self.request = None

        def json(self) -> dict:
            return {"data": [{"embedding": [0.1] * 1024}]}

    def fake_post(url, json, timeout):
        calls.append(url)
        return _Resp(url, ok=url.endswith(":8001/v1/embeddings"))

    monkeypatch.delenv("SOKOL_EMBED_FALLBACK_URL", raising=False)
    monkeypatch.setattr("worker.embed_index.httpx.post", fake_post)
    fn = make_embed_fn(
        "http://localhost:1234/v1", "text-embedding-qwen3-embedding-0.6b", 1024
    )
    out = fn(["olá"])
    assert calls == [
        "http://localhost:1234/v1/embeddings",
        "http://localhost:8001/v1/embeddings",
    ]
    assert len(out[0]) == 1024
