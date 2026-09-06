"""Browser plumbing — the only module (besides the live adapter) that imports Playwright.

* ``open_context(settings, source_id)`` — persistent headless Chromium context (``profiles/<source>``),
  en-CA locale, America/Toronto, images/fonts/media blocked (never scripts or XHR).
  ``FS_BROWSER_ENGINE=patchright`` swaps the import; ``FS_HEADED=1`` shows the window.
* ``check_block(page, response)`` — 403/429, ``/sorry/``, ``consent.google.com``, "unusual traffic",
  reCAPTCHA iframe → ``BlockedError``. A block is a data point; nothing here ever interacts with a
  captcha or a consent dialog.
* ``BrowserArtifacts`` — ``artifacts/<run_id>/<search_key>/{page.html, page.png, url.txt, reason.txt}``.
"""

from __future__ import annotations

import contextlib
import logging
import re
import shutil
import time
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from .adapters.base import ArtifactSaver, BlockedError
from .config import Settings

log = logging.getLogger(__name__)

BLOCKED_STATUSES = frozenset({403, 429})
BLOCK_URL_RE = re.compile(r"/sorry/|consent\.google\.com|/recaptcha/", re.I)
BLOCK_TEXT_RE = re.compile(
    r"unusual traffic from your computer network|our systems have detected unusual traffic|"
    r"confirm you(?:'re| are) not a robot|verify (?:that )?you are human",
    re.I,
)
BLOCKED_RESOURCE_TYPES = frozenset({"image", "media", "font"})
DEFAULT_TIMEOUT_MS = 45_000


def _playwright_module(engine: str):
    if engine == "patchright":
        from patchright.sync_api import sync_playwright  # type: ignore[import-not-found]
    else:
        from playwright.sync_api import sync_playwright
    return sync_playwright


def _route_handler(route: Any) -> None:
    try:
        if route.request.resource_type in BLOCKED_RESOURCE_TYPES:
            route.abort()
        else:
            route.continue_()
    except Exception:  # noqa: BLE001 - the page may already be closing
        with contextlib.suppress(Exception):
            route.continue_()


@contextlib.contextmanager
def open_context(settings: Settings, source_id: str = "google_flights") -> Iterator[Any]:
    """Yield a Playwright ``Page`` from a persistent context; closes everything on exit."""
    sync_playwright = _playwright_module(settings.browser_engine)
    user_data_dir = settings.profiles_dir / source_id
    user_data_dir.mkdir(parents=True, exist_ok=True)
    pw = sync_playwright().start()
    ctx = None
    try:
        launch_kwargs: dict[str, Any] = dict(
            user_data_dir=str(user_data_dir),
            headless=not settings.headed,
            locale="en-CA",
            timezone_id="America/Toronto",
            viewport={"width": 1366, "height": 900},
        )
        if settings.browser_engine == "patchright":
            launch_kwargs["no_viewport"] = True  # patchright README: keep the real window size
            launch_kwargs.pop("viewport")
        log.info(
            "launching %s chromium (%s, profile %s)",
            settings.browser_engine,
            "headed" if settings.headed else "headless",
            user_data_dir,
        )
        ctx = pw.chromium.launch_persistent_context(**launch_kwargs)
        ctx.set_default_timeout(DEFAULT_TIMEOUT_MS)
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        page.route("**/*", _route_handler)
        yield page
    finally:
        if ctx is not None:
            with contextlib.suppress(Exception):
                ctx.close()
        with contextlib.suppress(Exception):
            pw.stop()


# ------------------------------------------------------------------ block detection
def body_text(page: Any, limit: int = 20_000, timeout_ms: int = 5_000) -> str:
    try:
        return page.locator("body").inner_text(timeout=timeout_ms)[:limit]
    except Exception:  # noqa: BLE001 - a page mid-navigation has no body yet
        return ""


def check_block(page: Any, response: Any = None, *, text: str | None = None) -> None:
    """Raise ``BlockedError`` on any block marker; otherwise return silently."""
    status = getattr(response, "status", None)
    if status in BLOCKED_STATUSES:
        raise BlockedError(f"http {status} on {page.url[:120]}")
    url = page.url or ""
    if BLOCK_URL_RE.search(url):
        raise BlockedError(f"block/consent page: {url[:120]}")
    try:
        if page.locator('iframe[src*="recaptcha"]').count():
            raise BlockedError("recaptcha iframe present")
    except BlockedError:
        raise
    except Exception:  # noqa: BLE001
        pass
    sample = text if text is not None else body_text(page)
    m = BLOCK_TEXT_RE.search(sample)
    if m:
        raise BlockedError(f"block text: {m.group(0)!r}")


# ------------------------------------------------------------------ artifacts
def _safe(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.+-]+", "_", name)[:120]


class BrowserArtifacts(ArtifactSaver):
    """Screenshot + HTML + url + reason under ``artifacts/<run_id>/<search_key>/``."""

    def __init__(self, root: Path, run_id: str) -> None:
        self.root = Path(root)
        self.run_id = run_id
        self.saved: list[Path] = []

    def save(self, page: Any, search_key: str, reason: str) -> Path | None:
        if page is None:
            return None
        target = self.root / self.run_id / _safe(search_key)
        if target.exists():  # second artifact for the same search: suffix with the time
            target = target.with_name(target.name + "_" + time.strftime("%H%M%S"))
        try:
            target.mkdir(parents=True, exist_ok=True)
            (target / "url.txt").write_text(page.url or "", encoding="utf-8")
            (target / "reason.txt").write_text(reason, encoding="utf-8")
            with contextlib.suppress(Exception):
                (target / "page.html").write_text(page.content(), encoding="utf-8")
            with contextlib.suppress(Exception):
                page.screenshot(path=str(target / "page.png"), full_page=False)
            self.saved.append(target)
            log.warning("artifacts saved to %s (%s)", target, reason)
            return target
        except OSError as exc:
            log.warning("could not save artifacts: %s", exc)
            return None


def prune_artifacts(root: Path, days: int, now: datetime | None = None) -> list[Path]:
    """Delete ``artifacts/<run_id>`` directories older than ``days`` (by mtime); returns what was removed."""
    root = Path(root)
    if not root.exists():
        return []
    cutoff = (now or datetime.now(UTC)) - timedelta(days=days)
    removed: list[Path] = []
    for child in root.iterdir():
        if not child.is_dir():
            continue
        mtime = datetime.fromtimestamp(child.stat().st_mtime, tz=UTC)
        if mtime < cutoff:
            shutil.rmtree(child, ignore_errors=True)
            removed.append(child)
    return removed


__all__ = ["BrowserArtifacts", "body_text", "check_block", "open_context", "prune_artifacts"]
