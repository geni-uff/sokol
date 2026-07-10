FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml .
RUN pip install --no-cache-dir fastapi uvicorn ultralytics pillow httpx huggingface_hub python-multipart

COPY src/ ./src/

ENV SOKOL_MODEL_DIR=/data/models/vision
ENV SOKOL_VISION_CONF=0.25

EXPOSE 8007

CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8007"]
