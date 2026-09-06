#!/usr/bin/env bash
# Install the systemd service + timer on this WSL2 box (needs sudo once). Idempotent.
set -euo pipefail
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
UNIT_DIR=/etc/systemd/system

cat <<'EOF'
WSL2 prerequisites (one-time, outside this script):
  1. Enable systemd:  add to /etc/wsl.conf      [boot]
                                                systemd=true
     then from Windows:  wsl --shutdown   (and reopen the distro)
  2. Keep WSL alive so the 06:30 timer can fire: Windows Task Scheduler, "At log on", run
        wsl.exe -d <your-distro> -- sleep infinity
     (or any always-open terminal). Persistent=true also fires a missed run when WSL wakes up.
  3. Clock drift after Windows sleep:  sudo hwclock -s   (or add it to the same keep-alive task)
  4. Chromium runtime deps:  playwright install chromium  (add --with-deps if the launch fails)
EOF

if ! systemctl is-system-running >/dev/null 2>&1 && [ "$(systemctl is-system-running 2>/dev/null || true)" = "offline" ]; then
  echo "systemd is not running in this WSL2 distro yet (see prerequisite 1). Units were NOT installed." >&2
  exit 1
fi

sudo install -m 0644 "$PROJECT_DIR/scripts/flight-scraper.service" "$UNIT_DIR/flight-scraper.service"
sudo install -m 0644 "$PROJECT_DIR/scripts/flight-scraper.timer" "$UNIT_DIR/flight-scraper.timer"
chmod +x "$PROJECT_DIR/scripts/run_daily.sh"
sudo systemctl daemon-reload
sudo systemctl enable --now flight-scraper.timer
echo
systemctl list-timers flight-scraper.timer --no-pager
echo
echo "Manual run:      sudo systemctl start flight-scraper.service && journalctl -u flight-scraper -f"
echo "Dry run by hand: FS_DRY_RUN=1 scripts/run_daily.sh --source google_flights --route YUL-CDG --pax 1a"
