# flight-scraper — common commands (install `just`: cargo install just / apt install just)
set dotenv-load := true

default:
    @just --list

# Start the local PostgreSQL (first start applies the migration automatically)
up:
    docker compose up -d --wait

# Stop it (data volume is kept)
down:
    docker compose down

# Stop it and delete the data volume
clean:
    docker compose down -v

# Tail database logs
logs:
    docker compose logs -f db

# Re-apply the migration (idempotent): use after pulling schema changes
migrate:
    docker compose exec -T db psql -v ON_ERROR_STOP=1 -U "${POSTGRES_USER:-postgres}" -d "${POSTGRES_DB:-flights}" < docker/postgres/initdb/01_roles.sql
    docker compose exec -T db psql -v ON_ERROR_STOP=1 -U "${POSTGRES_USER:-postgres}" -d "${POSTGRES_DB:-flights}" < supabase/migrations/0001_init.sql

# psql shell into the local database
psql:
    docker compose exec db psql -U "${POSTGRES_USER:-postgres}" -d "${POSTGRES_DB:-flights}"

# Connectivity + row counts + last runs against whichever backend .env selects
db-check:
    .venv/bin/python -m flight_scraper.cli db-check

# Health of the last run (exit 1 when unhealthy)
health:
    .venv/bin/python -m flight_scraper.cli health

# Scrape and upsert into the configured database (extra args pass through, e.g. just run --route YUL-CDG)
run *ARGS:
    scripts/run_daily.sh {{ARGS}}

# Scrape into out/<run_id>.json only
dry-run *ARGS:
    FS_DRY_RUN=1 scripts/run_daily.sh {{ARGS}}

# Unit tests + lint
test:
    .venv/bin/python -m pytest -q
    .venv/bin/ruff check flight_scraper tests

# Live round-trip against the local PostgreSQL (needs `just up` and DATABASE_URL in .env)
test-live-db:
    .venv/bin/python -m pytest -q -m live tests/live/test_postgres_live.py
