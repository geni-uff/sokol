from sokol.pipeline import EmbedJobStatus


def test_embed_job_status_defaults() -> None:
    s = EmbedJobStatus(status="idle")
    assert s.chunks_embedded == 0
    assert s.job_id is None
