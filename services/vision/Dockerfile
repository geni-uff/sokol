FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 \
    libglib2.0-0 \
    git \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml .
RUN pip install --no-cache-dir \
    fastapi "uvicorn[standard]" python-multipart \
    "ultralytics>=8.4.123" pillow httpx huggingface_hub \
    "transformers>=4.40.0" timm ftfy \
    "git+https://github.com/ultralytics/CLIP.git"

COPY src/ ./src/

ENV SOKOL_MODEL_DIR=/data/models/vision
ENV SOKOL_VISION_CONF=0.20
ENV SOKOL_VISION_WORLD_CONF=0.15
ENV SOKOL_VISION_DINO_CONF=0.25
ENV SOKOL_VISION_IMGSZ=1024
ENV SOKOL_VISION_DINO=1
ENV SOKOL_VISION_CLIP=1
ENV YOLO_CONFIG_DIR=/data/models/vision
ENV HF_HOME=/data/models/vision/hf-home
ENV HF_HUB_DISABLE_TELEMETRY=1

EXPOSE 8007

CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8007"]
