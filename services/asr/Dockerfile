FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg && \
    rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir uv

COPY pyproject.toml ./
RUN uv venv && uv pip install faster-whisper fastapi "uvicorn[standard]"

COPY src/ ./src/

ENV PATH="/app/.venv/bin:$PATH"
ENV SOKOL_ASR_MODEL=base
ENV SOKOL_ASR_DEVICE=cpu
ENV SOKOL_ASR_PORT=8009

EXPOSE 8009

CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8009"]
