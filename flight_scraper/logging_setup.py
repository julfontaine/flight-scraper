"""Console + rotating file logging with the run id in every record (journald gets stdout)."""

from __future__ import annotations

import logging
import logging.handlers
from pathlib import Path

FORMAT = "%(asctime)s %(levelname)s [%(run_id)s] %(name)s: %(message)s"
MAX_BYTES = 5 * 1024 * 1024
BACKUP_COUNT = 5


class RunIdFilter(logging.Filter):
    """Injects ``run_id`` into every record so the format never fails."""

    def __init__(self, run_id: str = "-") -> None:
        super().__init__()
        self.run_id = run_id

    def filter(self, record: logging.LogRecord) -> bool:
        if not hasattr(record, "run_id"):
            record.run_id = self.run_id
        return True


_filter = RunIdFilter()


def setup_logging(level: str = "INFO", logs_dir: Path | None = None, run_id: str | None = None) -> None:
    """Idempotent: reconfigures the root logger; a second call only updates level / run id."""
    root = logging.getLogger()
    root.setLevel(level.upper())
    if run_id:
        _filter.run_id = run_id
    if getattr(root, "_flight_scraper_configured", False):
        return
    fmt = logging.Formatter(FORMAT)
    console = logging.StreamHandler()
    console.setFormatter(fmt)
    console.addFilter(_filter)
    root.addHandler(console)
    if logs_dir is not None:
        try:
            logs_dir.mkdir(parents=True, exist_ok=True)
            fh = logging.handlers.RotatingFileHandler(
                logs_dir / "flight-scraper.log",
                maxBytes=MAX_BYTES,
                backupCount=BACKUP_COUNT,
                encoding="utf-8",
            )
            fh.setFormatter(fmt)
            fh.addFilter(_filter)
            root.addHandler(fh)
        except OSError as exc:  # read-only or missing dir must not stop a run
            root.warning("file logging disabled: %s", exc)
    root._flight_scraper_configured = True  # type: ignore[attr-defined]


def set_run_id(run_id: str) -> None:
    _filter.run_id = run_id
