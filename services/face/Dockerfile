FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

RUN pip install --no-cache-dir uv

COPY pyproject.toml .
RUN uv venv && uv pip install -e . 2>/dev/null || uv pip install \
    fastapi "uvicorn[standard]" insightface onnxruntime \
    opencv-python-headless numpy pillow httpx

COPY src/ ./src/

EXPOSE 8011

CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8011"]
