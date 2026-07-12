FROM python:3.12-slim

# Install postgresql-client for pg_isready
RUN apt-get update && apt-get install -y postgresql-client && rm -rf /var/lib/apt/lists/*

WORKDIR /app

RUN pip install --no-cache-dir uv

# Install dependencies (layer cached on pyproject.toml changes)
COPY api/pyproject.toml ./api/pyproject.toml
RUN uv venv api/.venv && uv pip install --python api/.venv \
    "fastapi>=0.115" \
    "uvicorn[standard]>=0.34" \
    "httpx>=0.28" \
    "argon2-cffi>=23.1" \
    "sqlalchemy>=2.0" \
    "psycopg2-binary>=2.9" \
    "alembic>=1.13" \
    "redis>=5.0" \
    "psutil>=6.0"

# Copy API source
COPY api/src/ ./api/src/

# Copy migrations
COPY db/migrations/ ./migrations/

# Copy alembic.ini
COPY db/alembic.ini ./

# Copy entrypoint
COPY api/entrypoint.sh ./
RUN chmod +x entrypoint.sh

ENV PATH="/app/api/.venv/bin:$PATH"

EXPOSE 8000

ENTRYPOINT ["./entrypoint.sh"]
CMD ["uvicorn", "api.src.sokol.main:app", "--host", "0.0.0.0", "--port", "8000"]
