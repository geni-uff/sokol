FROM python:3.12-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install uv for fast dependency installation
RUN pip install --no-cache-dir uv

# Copy requirements
COPY worker/requirements.txt ./
RUN uv pip install -r requirements.txt

# Copy worker code
COPY worker/ ./

# Default entrypoint: run worker process
# Usage: docker run sokol-worker python ingest_worker.py [worker_id] [num_workers]
CMD ["python", "ingest_worker.py", "1", "1"]
