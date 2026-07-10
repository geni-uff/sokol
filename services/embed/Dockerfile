FROM pytorch/pytorch:2.3.1-cuda12.1-cudnn8-runtime

WORKDIR /app

RUN pip install --no-cache-dir uv

COPY pyproject.toml ./
RUN uv venv && uv pip install fastapi "uvicorn[standard]" sentence-transformers

COPY src/ ./src/

ENV PATH="/app/.venv/bin:$PATH"
ENV TRANSFORMERS_CACHE=/data/models
ENV HF_HOME=/data/models

EXPOSE 8001

CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8001"]
