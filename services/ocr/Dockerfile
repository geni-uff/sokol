FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 libglib2.0-0 libgomp1 && \
    rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir uv

COPY pyproject.toml ./
RUN uv venv && uv pip install paddlepaddle paddleocr fastapi "uvicorn[standard]" python-multipart

COPY src/ ./src/

ENV PATH="/app/.venv/bin:$PATH"
ENV SOKOL_OCR_PORT=8008

EXPOSE 8008

CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8008"]
