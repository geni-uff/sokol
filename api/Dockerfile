FROM python:3.12-slim

# postgresql-client: pg_isready; pango/cairo/gdk: WeasyPrint PDF rendering
RUN apt-get update && apt-get install -y --no-install-recommends \
    postgresql-client \
    libpango-1.0-0 \
    libpangoft2-1.0-0 \
    libharfbuzz-subset0 \
    libcairo2 \
    libgdk-pixbuf-2.0-0 \
    libffi-dev \
    shared-mime-info \
    fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*

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
    "psutil>=6.0" \
    "weasyprint>=62.0"

# Copy API source
COPY api/src/ ./api/src/

# Model registry (Admin switch persists when this path is mounted)
COPY config/ ./config/

# Copy migrations
COPY db/migrations/ ./migrations/

# Copy alembic.ini
COPY db/alembic.ini ./

# Copy entrypoint (strip CRLF — checkout no Windows quebra o shebang:
# "exec ./entrypoint.sh: no such file or directory")
COPY api/entrypoint.sh ./
RUN sed -i 's/\r$//' entrypoint.sh && chmod +x entrypoint.sh

ENV PATH="/app/api/.venv/bin:$PATH"

EXPOSE 8000

ENTRYPOINT ["/bin/bash", "/app/entrypoint.sh"]
CMD ["uvicorn", "api.src.sokol.main:app", "--host", "0.0.0.0", "--port", "8000"]
