"""Regenerate the logo blocks that carry the app's emblem in static/style.css and
templates/base.html.

static/logo.webp is the master (512px, transparent). The landing page and the
preview pages link it as a real file, but the app itself cannot: bundle.json is a
text-only channel, so a binary image cannot travel through STATIC_FILES at all
(same constraint the heading typeface hits — see scripts/build_display_font.py).
So the app carries the emblem as base64 data URIs instead, which reach all four
delivery channels (dev server, PyInstaller, Pyodide, docs/ preview) for free with
no new entry in STATIC_FILES, renderPage(), or either .spec.

Two derivatives are printed:
  * --logo, a 224px copy used as a background-image by .brand-mark (40px in the
    nav) and .home-hero-logo (up to ~170px on the warband list).
  * the <link rel="icon"> for templates/base.html, small enough (a few KB) that
    repeating it in every rendered page costs nothing.

This script writes NOTHING. It prints both blocks to stdout, to be pasted in
once — a script that rewrote style.css in place would silently revert hand-tuning
on every re-run, the same hazard CLAUDE.md documents for scripts/extract_*.py.

Usage (from the repo root, with the venv active):
    python scripts/build_logo_asset.py > logo-blocks.txt

To swap the artwork, replace static/logo.webp (square, transparent background)
and re-run.
"""

from __future__ import annotations

import base64
import io
import sys
from pathlib import Path

from PIL import Image

REPO_ROOT = Path(__file__).resolve().parent.parent
MASTER = REPO_ROOT / "static" / "logo.webp"

# 224px covers the largest in-app use (.home-hero-logo) at 1x with a little to
# spare; going bigger costs base64 weight in a render-blocking stylesheet for a
# detail nobody reads at that size.
CSS_SIZE = 224
CSS_QUALITY = 80

FAVICON_SIZE = 48
FAVICON_QUALITY = 88


def _data_uri(size: int, quality: int) -> tuple[str, float]:
    im = Image.open(MASTER).convert("RGBA").resize((size, size), Image.LANCZOS)
    buf = io.BytesIO()
    im.save(buf, format="WEBP", quality=quality, method=6)
    raw = buf.getvalue()
    return "data:image/webp;base64," + base64.b64encode(raw).decode("ascii"), len(raw) / 1024


def main() -> None:
    if not MASTER.is_file():
        raise SystemExit(f"missing master image: {MASTER}")

    css_uri, css_kb = _data_uri(CSS_SIZE, CSS_QUALITY)
    fav_uri, fav_kb = _data_uri(FAVICON_SIZE, FAVICON_QUALITY)

    # Output stays strictly ASCII: Python writes stdout in the console's locale
    # encoding (cp1252 here), so a stray em dash would land as a lone 0x97 byte in
    # the redirected file, and style.css is read back as UTF-8 by
    # build_browser_bundle.py.
    print("  /* The app emblem, inlined for the same reason the font above is:")
    print("     see scripts/build_logo_asset.py, which regenerates this line from")
    print("     static/logo.webp. */")
    print(f"  --logo: url({css_uri});")
    print()
    print(f'    <link rel="icon" href="{fav_uri}" />')

    print(
        f"\n/* css {CSS_SIZE}px {css_kb:.1f} KB, favicon {FAVICON_SIZE}px {fav_kb:.1f} KB */",
        file=sys.stderr,
    )


if __name__ == "__main__":
    main()
