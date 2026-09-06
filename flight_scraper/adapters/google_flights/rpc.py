"""Optional RPC cross-check (Phase 5, behind ``--capture-rpc``): capture Google's
``GetShoppingResults`` / ``GetBookingResults`` responses, decode the batchexecute envelope and compare
with the DOM parse. The DOM stays the source of truth; nothing here changes what is stored."""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)

XSSI_PREFIX = ")]}'"
RPC_RE = re.compile(r"/(GetShoppingResults|GetBookingResults)\b")


def strip_xssi(body: str) -> str:
    body = body.lstrip()
    if body.startswith(XSSI_PREFIX):
        body = body[len(XSSI_PREFIX) :]
    return body.lstrip()


def decode_batchexecute(body: str) -> list[Any]:
    """batchexecute bodies: ``)]}'`` + a JSON array of chunks ``["wrb.fr", <rpc>, "<json string>", …]``.
    Returns the decoded inner payloads (already JSON-parsed where possible)."""
    text = strip_xssi(body)
    payloads: list[Any] = []
    try:
        outer = json.loads(text)
    except json.JSONDecodeError:
        # some builds emit length-prefixed chunks: "123\n[[...]]\n45\n[[...]]"
        for chunk in re.split(r"^\d+\n", text, flags=re.M):
            chunk = chunk.strip()
            if not chunk:
                continue
            try:
                outer = json.loads(chunk)
            except json.JSONDecodeError:
                continue
            payloads.extend(_inner(outer))
        return payloads
    payloads.extend(_inner(outer))
    return payloads


def _inner(outer: Any) -> list[Any]:
    out: list[Any] = []
    if isinstance(outer, list):
        for item in outer:
            if isinstance(item, list) and item and item[0] == "wrb.fr":
                for cell in item[1:]:
                    if isinstance(cell, str) and cell.startswith("["):
                        try:
                            out.append(json.loads(cell))
                        except json.JSONDecodeError:
                            pass
            elif isinstance(item, list):
                out.extend(_inner(item))
    return out


def numbers_in(payload: Any) -> set[int]:
    """Every integer in a decoded payload (prices are plain integers in CAD on the results RPC)."""
    found: set[int] = set()
    stack = [payload]
    while stack:
        x = stack.pop()
        if isinstance(x, bool):
            continue
        if isinstance(x, int):
            found.add(x)
        elif isinstance(x, float) and x.is_integer():
            found.add(int(x))
        elif isinstance(x, list):
            stack.extend(x)
        elif isinstance(x, dict):
            stack.extend(x.values())
    return found


def cross_check(bodies: list[str], dom_prices: list[float]) -> dict[str, Any]:
    """Discrepancy report: are the DOM prices (min and max) present anywhere in the RPC payloads?"""
    nums: set[int] = set()
    decoded = 0
    for body in bodies:
        payloads = decode_batchexecute(body)
        decoded += len(payloads)
        for p in payloads:
            nums |= numbers_in(p)
    report: dict[str, Any] = {"bodies": len(bodies), "payloads": decoded, "dom_rows": len(dom_prices)}
    if dom_prices:
        lo, hi = int(min(dom_prices)), int(max(dom_prices))
        report["dom_min_in_rpc"] = lo in nums
        report["dom_max_in_rpc"] = hi in nums
        if nums and (not report["dom_min_in_rpc"] or not report["dom_max_in_rpc"]):
            log.warning("RPC cross-check: DOM min/max price %s/%s not both found in RPC payloads", lo, hi)
    return report


class RpcRecorder:
    """Collects response bodies of the two RPCs; ``save`` writes them under ``artifacts/<run_id>/rpc/``."""

    def __init__(self, page: Any) -> None:
        self.bodies: list[tuple[str, str]] = []
        page.on("response", self._on_response)

    def _on_response(self, response: Any) -> None:
        m = RPC_RE.search(getattr(response, "url", "") or "")
        if not m:
            return
        try:
            self.bodies.append((m.group(1), response.text()))
        except Exception as exc:  # noqa: BLE001 - bodies of aborted responses are unavailable
            log.debug("rpc body unavailable: %s", exc)

    def take(self, name: str) -> list[str]:
        out = [b for n, b in self.bodies if n == name]
        self.bodies = [(n, b) for n, b in self.bodies if n != name]
        return out

    @staticmethod
    def save(target: Path, name: str, bodies: list[str]) -> None:
        target.mkdir(parents=True, exist_ok=True)
        for i, body in enumerate(bodies):
            (target / f"{name}_{i}.txt").write_text(body, encoding="utf-8")
