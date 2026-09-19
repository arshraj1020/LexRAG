#!/usr/bin/env bash
# =============================================================
# LexRAG — Backend test database bootstrap
#
# backend/src/main/resources/application-test.yml (@ActiveProfiles("test"))
# expects a PostgreSQL server on localhost:5432 with:
#   role:     lexrag      (TEST_DATABASE_USERNAME, default "lexrag")
#   password: changeme    (TEST_DATABASE_PASSWORD, default "changeme")
#   database: lexrag_test (TEST_DATABASE_URL,      default ".../lexrag_test")
# and a Redis server on localhost:6379 (db 1, no auth).
#
# NOTE: on this machine, port 5432 on "localhost" is already owned by a
# native Homebrew PostgreSQL service (bound specifically to 127.0.0.1/::1),
# which takes priority over anything Docker publishes on the wildcard
# address for that same port. So this script provisions the role/database
# in THAT native Postgres directly, via `psql`.
#
# The schema migration (V1__init_schema.sql) also does:
#   CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
#   CREATE EXTENSION IF NOT EXISTS vector;
# "uuid-ossp" is trusted and any role can create it. "vector" (pgvector)
# is NOT a trusted extension, so creating it requires either superuser,
# or that it already exists in the target database. This script grants
# the test-only "lexrag" role SUPERUSER locally (safe: this is a
# throwaway local test role/db, not anything shipped or shared) so Flyway
# can create both extensions during the test run.
# =============================================================
set -euo pipefail

if ! command -v psql >/dev/null 2>&1; then
  echo "psql is required. Install/start your local PostgreSQL (e.g. 'brew services start postgresql@17')." >&2
  exit 1
fi

echo "Using native PostgreSQL on localhost:5432 (psql: $(psql --version))"

PSQL="psql -h localhost -p 5432 -d postgres -v ON_ERROR_STOP=1"

echo "Ensuring role 'lexrag' exists (password 'changeme', SUPERUSER for local pgvector setup)..."
$PSQL -tAc "SELECT 1 FROM pg_roles WHERE rolname='lexrag'" | grep -q 1 || \
  $PSQL -c "CREATE ROLE lexrag WITH LOGIN PASSWORD 'changeme';"
$PSQL -c "ALTER ROLE lexrag WITH LOGIN PASSWORD 'changeme' SUPERUSER CREATEDB;"

echo "Ensuring database 'lexrag_test' exists, owned by 'lexrag'..."
$PSQL -tAc "SELECT 1 FROM pg_database WHERE datname='lexrag_test'" | grep -q 1 || \
  $PSQL -c "CREATE DATABASE lexrag_test OWNER lexrag;"

echo "Checking the pgvector extension is available on this Postgres install..."
HAS_VECTOR=$($PSQL -tAc "SELECT 1 FROM pg_available_extensions WHERE name='vector'" || true)
if [ "$HAS_VECTOR" != "1" ]; then
  echo ""
  echo "pgvector is not installed for this native Postgres. Install it, e.g.:"
  echo "  brew install pgvector"
  echo "  # then restart postgres: brew services restart postgresql@17  (match your installed version)"
  echo "and re-run this script." >&2
  exit 1
fi

echo "Verifying: connecting as lexrag to lexrag_test over TCP..."
PGPASSWORD=changeme psql -h localhost -p 5432 -U lexrag -d lexrag_test -c '\conninfo'

# --- Redis --------------------------------------------------------
REDIS_CONTAINER=lexrag-test-redis
if command -v docker >/dev/null 2>&1; then
  if ! docker exec "$REDIS_CONTAINER" redis-cli ping >/dev/null 2>&1; then
    docker rm -f "$REDIS_CONTAINER" >/dev/null 2>&1 || true
    echo "Starting $REDIS_CONTAINER on localhost:6379..."
    docker run -d --name "$REDIS_CONTAINER" -p 6379:6379 redis:7-alpine >/dev/null
  else
    echo "$REDIS_CONTAINER already running."
  fi
else
  echo "docker not found — make sure a Redis instance is reachable at localhost:6379 (test profile uses db 1, no auth)." >&2
fi

docker rm -f lexrag-test-postgres >/dev/null 2>&1 || true

echo ""
echo "Done. Role 'lexrag' / db 'lexrag_test' is up on localhost:5432 (native Postgres), Redis on localhost:6379."
echo "You can now run: cd backend && mvn clean test"
