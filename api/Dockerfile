FROM python:3.12-slim

# Install postgresql-client for pg_isready
RUN apt-get update && apt-get install -y postgresql-client && rm -rf /var/lib/apt/lists/*

WORKDIR /app

RUN pip install --no-cache-dir uv

# Install dependencies
COPY api/pyproject.toml ./api/pyproject.toml
RUN cd api && uv venv && uv pip install -e ".[dev]" 2>/dev/null || uv pip install fastapi "uvicorn[standard]" httpx argon2-cffi sqlalchemy psycopg2-binary alembic

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
