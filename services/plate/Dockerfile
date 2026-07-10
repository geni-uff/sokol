FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 libglib2.0-0 libglu1-mesa && \
    rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir uv

COPY pyproject.toml ./
RUN uv venv && uv pip install ultralytics paddlepaddle paddleocr opencv-python-headless fastapi "uvicorn[standard]"

COPY src/ ./src/

ENV PATH="/app/.venv/bin:$PATH"
ENV SOKOL_PLATE_PORT=8010

EXPOSE 8010

CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8010"]
