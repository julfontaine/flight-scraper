#!/usr/bin/env bash
# Daily wrapper used by the systemd timer (and runnable by hand).
#   exit 0 = ok/partial, 2 = blocked, 3 = failed / nothing scraped, 4 = setup error
# Env passthrough: FS_DRY_RUN=1 → --dry-run; FS_HEADED=1 → headed Chromium under xvfb-run.
set -u
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_DIR" || exit 4

if [ -f .env ]; then
  set -a; . ./.env; set +a
fi
if [ -f .venv/bin/activate ]; then
  # shellcheck disable=SC1091
  . .venv/bin/activate
else
  echo "run_daily: .venv missing — create it with: uv venv && uv pip install -e .[dev] && playwright install chromium" >&2
  exit 4
fi
mkdir -p logs out artifacts

ARGS=(run)
[ "${FS_DRY_RUN:-0}" = "1" ] && ARGS+=(--dry-run)
ARGS+=("$@")

if [ "${FS_HEADED:-0}" = "1" ] && command -v xvfb-run >/dev/null 2>&1; then
  exec xvfb-run -a python -m flight_scraper.cli "${ARGS[@]}"
fi
exec python -m flight_scraper.cli "${ARGS[@]}"
