#!/usr/bin/env python3
"""Bundle the app's Python modules, Jinja templates and reference data into a
single JSON file that the in-browser (Pyodide) build unpacks into its virtual
filesystem.

The browser build (docs/app/index.html) loads Pyodide, installs Flask, writes
these files into an in-memory filesystem, sets FWK_BROWSER=1 and points
FWK_DATA_DIR at an in-memory dir, then drives the *real* Flask app through its
test client — so the online version runs the exact same rules engine as the
desktop app. That filesystem dies with the tab, so the shell snapshots it to
localStorage after each mutating request and restores it at boot; warbands
persist per-browser, not per-session.

Also mirrors static/portraits/*.png to docs/app/static/portraits/ as plain
sibling files (default character art; served relatively, not bundled — see
PORTRAITS_SRC/PORTRAITS_OUT below).

Re-run this after changing any bundled source file. The output is NOT meant to
be committed onto `main` by hand: .github/workflows/deploy-pages.yml runs this
script against `devversion` and deploys docs/ to Pages directly. The old flow
hand-copied bundle.json to `main`, where index.html lived as a second,
independently-maintained copy — the two diverged unnoticed and `main`'s shell
shipped without the localStorage code for several releases, making the online
app look like it saved nothing. Build from one branch, in CI.

    python scripts/build_browser_bundle.py
"""
from __future__ import annotations

import hashlib
import json
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "docs" / "app" / "bundle.json"
SHELL = ROOT / "docs" / "app" / "index.html"

# F2: matches the shell's bundle.json fetch URL regardless of what's currently
# there — a first-run placeholder ("__BUNDLE_VERSION__") or a previous build's
# hash — so this substitution is idempotent across repeated builds without
# needing separate template/output copies of index.html.
BUNDLE_VERSION_RE = re.compile(r'(bundle\.json\?v=)[^"]*')

# Python modules the Flask app needs at import time (pdf_export is imported
# lazily by the /pdf route, but does get imported in-browser — fpdf2 is
# micropip-installed at boot specifically so PDF export works there too).
PY_MODULES = [
    "app.py",
    "paths.py",
    "frostgrave_data.py",
    "game_content.py",
    "expansions.py",
    "warband_store.py",
    "idle_watchdog.py",
    "pdf_export.py",
]

# Reference data read by game_content / the reference page. Globbed rather
# than hand-listed (B6) — this exact list used to be maintained by hand here
# and in both PyInstaller specs, and has desynced and shipped broken twice.
DATA_FILES = [f"data/{p.name}" for p in sorted((ROOT / "data").glob("*.json"))]

# Loaded once and inlined into every rendered page by the shell (the in-browser
# app has no real static-file server).
# Every <script>/<link> base.html pulls from static/ has to be listed here AND
# given an inlining rule in the shell's renderPage(), or the browser resolves
# the tag's absolute "/static/..." URL against the site root and 404s — silently,
# since the callers are all `if (window.fgInitFilter)`-guarded. filter.js shipped
# broken online that way, leaving every search box (warband list, Lexicon, hire
# catalog) inert.
STATIC_FILES = [
    "static/style.css",
    "static/item_slots.js",
    "static/filter.js",
]

# Default character artwork is mirrored as real sibling files next to
# docs/app/index.html (NOT put through the text-based bundle.json channel —
# bundle.json is re-fetched on every cold boot, and these PNGs would add a few
# MB to every load for no benefit since they're static). The shell rewrites
# "/static/portraits/..." <img> srcs to a plain relative "static/portraits/...".
PORTRAITS_SRC = ROOT / "static" / "portraits"
PORTRAITS_OUT = ROOT / "docs" / "app" / "static" / "portraits"


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

    # paths.app_version() reads this the same way in every build (dev,
    # PyInstaller-frozen, and here) — see CLAUDE.md's single-sourced-version rule.
    files["pyproject.toml"] = (ROOT / "pyproject.toml").read_text(encoding="utf-8")

    # Empty placeholders, NOT the real image bytes (see PORTRAITS_SRC/PORTRAITS_OUT
    # above) — warband_store.default_portrait_name() decides whether a character
    # has default art by checking the file exists on disk (Path.is_file()), so
    # without a same-named stand-in here that check always fails in Pyodide's
    # MEMFS and every character would show the "no picture" placeholder instead
    # of default art, even though the real PNG is right there being served to the
    # outer page from docs/app/static/portraits/.
    for png in sorted(PORTRAITS_SRC.glob("*.png")):
        files[f"static/portraits/{png.name}"] = ""

    return files


def mirror_portraits() -> int:
    if PORTRAITS_OUT.exists():
        shutil.rmtree(PORTRAITS_OUT)
    PORTRAITS_OUT.mkdir(parents=True, exist_ok=True)
    n = 0
    for png in sorted(PORTRAITS_SRC.glob("*.png")):
        shutil.copyfile(png, PORTRAITS_OUT / png.name)
        n += 1
    return n


def update_bundle_version(bundle_bytes: bytes) -> str:
    """F2: stamps the shell's bundle.json fetch URL with a content hash instead
    of Date.now(), so GitHub Pages' HTTP caching actually works — repeat visits
    between builds re-fetch nothing, and the URL only changes when the bundle's
    content does."""
    version = hashlib.sha256(bundle_bytes).hexdigest()[:12]
    html = SHELL.read_text(encoding="utf-8")
    new_html, n = BUNDLE_VERSION_RE.subn(rf"\g<1>{version}", html)
    if n == 0:
        raise RuntimeError(f"Could not find the bundle.json version placeholder in {SHELL}")
    SHELL.write_text(new_html, encoding="utf-8")
    return version


def main() -> None:
    files = collect()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "generated": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "files": files,
    }
    bundle_bytes = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    OUT.write_bytes(bundle_bytes)

    total = sum(len(v) for v in files.values())
    print(f"Wrote {OUT} — {len(files)} files, {total/1024:.0f} KB uncompressed.")
    for name in files:
        print(f"  {name}")

    version = update_bundle_version(bundle_bytes)
    print(f"Stamped {SHELL} with bundle version {version}")

    n_portraits = mirror_portraits()
    print(f"Mirrored {n_portraits} default portrait(s) to {PORTRAITS_OUT}")


if __name__ == "__main__":
    main()
