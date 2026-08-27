#!/bin/bash
set -e

echo "SOKOL: Running database migrations..."

# Parse DATABASE_URL to get connection details
# Format: postgresql://user:pass@host:port/dbname
if [ -n "$DATABASE_URL" ]; then
  # Extract host and port from DATABASE_URL
  DB_HOST=$(echo "$DATABASE_URL" | sed -n 's|.*@\([^:]*\):\([0-9]*\)/.*|\1|p')
  DB_PORT=$(echo "$DATABASE_URL" | sed -n 's|.*@\([^:]*\):\([0-9]*\)/.*|\2|p')
  POSTGRES_USER=$(echo "$DATABASE_URL" | sed -n 's|.*//\([^:]*\):.*|\1|p')
else
  DB_HOST="${DB_HOST:-localhost}"
  DB_PORT="${DB_PORT:-5432}"
  POSTGRES_USER="${POSTGRES_USER:-sokol}"
fi

# Wait for postgres
echo "SOKOL: Waiting for PostgreSQL at $DB_HOST:$DB_PORT..."
until pg_isready -h "$DB_HOST" -p "$DB_PORT" -U "$POSTGRES_USER" 2>/dev/null; do
  sleep 2
done
echo "SOKOL: PostgreSQL is ready."

# Run migrations
alembic upgrade head

echo "SOKOL: Ensuring bootstrap admin user..."
python -c "from api.src.sokol.ensure_admin import main; raise SystemExit(main())"

echo "SOKOL: Migrations complete. Starting API..."

exec "$@"
