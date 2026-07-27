#!/usr/bin/env python3
"""Bundle the app's Python modules, Jinja templates and reference data into a
single JSON file that the in-browser (Pyodide) build unpacks into its virtual
filesystem.

The browser build (docs/app/index.html) loads Pyodide, installs Flask, writes
these files into an in-memory filesystem, sets FWK_BROWSER=1 and points
FWK_DATA_DIR at an in-memory dir, then drives the *real* Flask app through its
test client — so the online version runs the exact same rules engine as the
desktop app, with nothing persisted between sessions.

Re-run this after changing any bundled source file, then commit the refreshed
docs/app/bundle.json on the `main` branch (same cross-branch flow as the
preview pages and docs/index.html).

    python scripts/build_browser_bundle.py
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "docs" / "app" / "bundle.json"

# Python modules the Flask app needs at import time (pdf_export is imported
# lazily and only bundled so the file exists; it is never imported in-browser).
PY_MODULES = [
    "app.py",
    "paths.py",
    "frostgrave_data.py",
    "game_content.py",
    "warband_store.py",
    "idle_watchdog.py",
    "pdf_export.py",
]

# Reference data read by game_content / the reference page.
DATA_FILES = [
    "data/bestiary.json",
    "data/spell_descriptions.json",
    "data/potions.json",
    "data/potion_descriptions.json",
    "data/standard_items.json",
]

# Loaded once and inlined into every rendered page by the shell (the in-browser
# app has no real static-file server).
STATIC_FILES = [
    "static/style.css",
    "static/item_slots.js",
]


def collect() -> dict[str, str]:
    files: dict[str, str] = {}

    for rel in PY_MODULES:
        files[rel] = (ROOT / rel).read_text(encoding="utf-8")

    for tpl in sorted((ROOT / "templates").glob("*.html")):
        files[f"templates/{tpl.name}"] = tpl.read_text(encoding="utf-8")

    for rel in DATA_FILES:
        files[rel] = (ROOT / rel).read_text(encoding="utf-8")

    for rel in STATIC_FILES:
        files[rel] = (ROOT / rel).read_text(encoding="utf-8")

    return files


def main() -> None:
    files = collect()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "generated": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "files": files,
    }
    OUT.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    total = sum(len(v) for v in files.values())
    print(f"Wrote {OUT} — {len(files)} files, {total/1024:.0f} KB uncompressed.")
    for name in files:
        print(f"  {name}")


if __name__ == "__main__":
    main()
