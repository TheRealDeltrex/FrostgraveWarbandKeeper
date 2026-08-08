#!/usr/bin/env python3
"""Stamps docs/index.html's per-download version badges (Online/Windows/
Linux) so the landing page always shows what a viewer would actually get.

The three don't always ship in lockstep — a CI hiccup can leave, say, the
Linux binary attached to an older release than Windows even though
pyproject.toml has already moved on for the next one. So:

- Online reflects THIS build's pyproject.toml version, since docs/app/
  bundle.json is built from the very same checkout (see
  build_browser_bundle.py) — always accurate by construction.
- Windows/Linux each look up the most recent GitHub Release that actually
  has their asset attached, via the REST API, rather than assuming
  "latest release" has both.

Substitution is by a stable `data-version-badge="<key>"` marker (regex, not
a one-shot placeholder string) so it's idempotent across repeated runs —
same idiom as build_browser_bundle.py's update_bundle_version().

Run as part of .github/workflows/deploy-pages.yml, after build_browser_bundle.py:
    python scripts/stamp_landing_page_versions.py
"""
from __future__ import annotations

import json
import os
import re
import sys
import tomllib
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SHELL = ROOT / "docs" / "index.html"
REPO = "TheRealDeltrex/FrostgraveWarbandKeeper"

WIN_ASSET = "FrostgraveWarbandKeeper-win64.zip"
LINUX_ASSET = "FrostgraveWarbandKeeper-linux-x64.tar.gz"


def online_version() -> str:
    data = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    return str(data["project"]["version"])


def _fetch_releases() -> list[dict]:
    req = urllib.request.Request(f"https://api.github.com/repos/{REPO}/releases?per_page=30")
    req.add_header("Accept", "application/vnd.github+json")
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read())


def latest_version_with_asset(asset_name: str, releases: list[dict]) -> str:
    for rel in releases:
        if rel.get("draft"):
            continue
        if any(a.get("name") == asset_name for a in rel.get("assets", [])):
            return str(rel.get("tag_name", "")).removeprefix("v")
    return "?"


def stamp(html: str, key: str, value: str) -> str:
    pattern = re.compile(rf'(data-version-badge="{key}">)[^<]*(</span>)')
    new_html, n = pattern.subn(rf"\g<1>v{value}\g<2>", html)
    if n == 0:
        print(f"warning: no data-version-badge=\"{key}\" marker found in {SHELL}", file=sys.stderr)
        return html
    return new_html


def main() -> None:
    # Online comes from this checkout's pyproject.toml and needs no network, so
    # it is stamped even when the API call fails. Returning early on a hiccup
    # used to leave all three reading "vDEV" — the placeholder is what ships in
    # the committed file, so an unstamped badge is a visibly wrong version
    # rather than a merely stale one.
    values = {"online": online_version()}
    try:
        releases = _fetch_releases()
    except OSError as err:
        print(
            f"warning: couldn't fetch releases ({err}); "
            "stamping online only, leaving windows/linux as-is",
            file=sys.stderr,
        )
    else:
        values["windows"] = latest_version_with_asset(WIN_ASSET, releases)
        values["linux"] = latest_version_with_asset(LINUX_ASSET, releases)

    html = SHELL.read_text(encoding="utf-8")
    for key, value in values.items():
        html = stamp(html, key, value)
    SHELL.write_text(html, encoding="utf-8")
    print(f"Stamped {SHELL}: " + ", ".join(f"{k}=v{v}" for k, v in values.items()))


if __name__ == "__main__":
    main()
