FROM python:3.12-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /data/project

# Install uv for fast dependency installation
RUN pip install --no-cache-dir uv

# Copy requirements
COPY worker/requirements.txt ./worker/requirements.txt
RUN uv pip install --system -r worker/requirements.txt

# Keep package layout so `python -m worker.ingest_worker` resolves relative imports.
COPY worker/ ./worker/

ENV PYTHONPATH=/data/project

# Default entrypoint: run as a package (not `python ingest_worker.py`).
CMD ["python", "-m", "worker.ingest_worker", "1", "1"]
