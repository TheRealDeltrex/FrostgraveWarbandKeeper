"""Auto-shutdown for the frozen, windowless build.

The packaged .exe has no window and no console (see frostgrave.spec,
console=False) — closing the browser tab alone doesn't stop it, since
waitress just keeps serving in the background with nothing left to close.
This module tracks whether any page is still open and exits the process once
none is, so the app doesn't linger unwanted after the last tab closes.

Two signals feed it (see the /heartbeat and /heartbeat/closing routes in
app.py, and the matching JS in base.html):
- A periodic "still open" ping from every loaded page.
- An immediate "closing" signal (navigator.sendBeacon on pagehide) fired
  when a page unloads — which also happens on ordinary in-app navigation, so
  it only triggers a shutdown if no fresh ping follows within a short grace
  period (i.e. a new page in the app didn't pick it right back up).

A generous no-heartbeat-at-all fallback also covers the browser/process
being killed outright, where pagehide never gets a chance to fire.
"""

from __future__ import annotations

import os
import threading
import time

_HEARTBEAT_TIMEOUT = 180.0
_CLOSING_GRACE = 3.0
_POLL_INTERVAL = 1.0

_lock = threading.Lock()
_last_heartbeat = time.time()
_closing_at: float | None = None


def note_heartbeat() -> None:
    global _last_heartbeat, _closing_at
    with _lock:
        _last_heartbeat = time.time()
        _closing_at = None


def note_closing() -> None:
    global _closing_at
    with _lock:
        _closing_at = time.time()


def _should_shutdown() -> bool:
    with _lock:
        now = time.time()
        if _closing_at is not None and now - _closing_at > _CLOSING_GRACE:
            return True
        return now - _last_heartbeat > _HEARTBEAT_TIMEOUT


def start() -> None:
    def _loop():
        while True:
            time.sleep(_POLL_INTERVAL)
            if _should_shutdown():
                os._exit(0)

    threading.Thread(target=_loop, daemon=True).start()
