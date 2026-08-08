"""Regenerate the @font-face block that carries the heading typeface in static/style.css.

Headings (the brand, hero <h1>, and every .card-title / .ref-panel summary) are set in
Spectral SemiBold, self-hosted. The font is embedded as a base64 data URI *inside*
static/style.css rather than shipped as its own file under static/fonts/, because
scripts/build_browser_bundle.py's collect() reads every bundled file with
read_text(encoding="utf-8") — bundle.json is a text-only channel, so a binary .woff
cannot travel through STATIC_FILES at all. Riding inside style.css means the font
reaches all four delivery channels (dev server, PyInstaller, Pyodide, docs/ preview)
for free, with no new entry in STATIC_FILES, renderPage(), or either .spec.

This script writes NOTHING. It prints the finished @font-face block to stdout, to be
pasted into static/style.css once. That is deliberate: a script that rewrote style.css
in place would silently revert hand-tuning on every re-run — the same hazard CLAUDE.md
documents for scripts/extract_*.py. The arguments below are the provenance record.

Usage (from the repo root, with the venv active):
    python scripts/build_display_font.py > font-face.txt

Requires fontTools (in .venv) and curl. Deliberately shells out to curl rather than
using urllib: this machine's Python SSL trust store rejects the GitHub chain
(CERTIFICATE_VERIFY_FAILED), while curl goes through the Windows schannel store and
works. Outputs WOFF, not WOFF2, because writing WOFF2 needs the brotli module, which
is not installed; WOFF uses stdlib zlib and is universally supported.
"""

from __future__ import annotations

import base64
import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

# The family name style.css references via --font-display. Deliberately generic
# rather than "Spectral": swapping the face later means re-running this script
# with a different SOURCE_URL, not editing every rule that names a font.
CSS_FAMILY = "FWK Display"

SOURCE_URL = "https://raw.githubusercontent.com/google/fonts/main/ofl/spectral/Spectral-SemiBold.ttf"
LICENSE_URL = "https://raw.githubusercontent.com/google/fonts/main/ofl/spectral/OFL.txt"
CSS_WEIGHT = 600

# Latin-1 + Latin Extended-A, plus the punctuation the templates actually emit.
# NOT trimmed to ASCII on purpose: the hero <h1> renders the user's own warband
# name and .card-title renders wizard names, so a player typing "Sødergaard" or
# "Élise" must not get a fallback face mid-word.
UNICODES = ",".join([
    "U+0020-007E",  # ASCII
    "U+00A0-00FF",  # Latin-1 Supplement (covers · × ÷ ° ± ¼ ½ and accented letters)
    "U+0100-017F",  # Latin Extended-A
    "U+2013", "U+2014",                        # – —
    "U+2018", "U+2019", "U+201C", "U+201D",    # ‘ ’ “ ”
    "U+2026",                                  # …
    "U+2212", "U+2264", "U+2265",              # − ≤ ≥
    "U+2032", "U+2033",                        # ′ ″
    "U+2020",                                  # †
])

# Name IDs 0/13/14 are the copyright and license fields — keeping them embeds the
# OFL notice in the .woff itself, alongside the verbatim text in static/fonts/.
NAME_IDS = "0,1,2,3,4,5,6,13,14"


def _curl(url: str, dest: Path) -> None:
    result = subprocess.run(
        ["curl", "-sS", "-L", "--fail", "--max-time", "60", "-o", str(dest), url],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise SystemExit(f"curl failed for {url}:\n{result.stderr.strip()}")


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="fwk-font-") as tmp:
        work = Path(tmp)
        ttf = work / "source.ttf"
        woff = work / "subset.woff"

        _curl(SOURCE_URL, ttf)

        # Spectral ships static instances, so there is nothing to pin. A variable
        # source would need fontTools.varLib.instancer at CSS_WEIGHT first —
        # headings use exactly one weight, and dropping fvar/gvar is the single
        # biggest size win.
        subprocess.run(
            [
                sys.executable, "-m", "fontTools.subset", str(ttf),
                f"--unicodes={UNICODES}",
                "--layout-features=kern,liga,calt",
                f"--name-IDs={NAME_IDS}",
                "--no-hinting",  # safe: nothing below 0.98rem uses this face
                "--flavor=woff",
                f"--output-file={woff}",
            ],
            check=True,
            capture_output=True,
        )

        payload = base64.b64encode(woff.read_bytes()).decode("ascii")
        raw_kb = woff.stat().st_size / 1024
        b64_kb = len(payload) / 1024

    # Output stays strictly ASCII. Python writes stdout in the console's locale
    # encoding (cp1252 here), so an em dash in this comment lands as a lone 0x97
    # byte in the redirected file — and style.css is read back as UTF-8 by
    # build_browser_bundle.py, which would then fail or corrupt the bundle.
    print(
        f"/* {CSS_FAMILY} = Spectral SemiBold, subset to Latin-1 + Latin Ext-A.\n"
        f"   Embedded rather than linked because bundle.json is a text-only channel:\n"
        f"   see scripts/build_display_font.py, which regenerates this block.\n"
        f"   SIL Open Font License 1.1, full text in static/fonts/OFL-Spectral.txt. */"
    )
    print("@font-face {")
    print(f"  font-family: \"{CSS_FAMILY}\";")
    print("  font-style: normal;")
    print(f"  font-weight: {CSS_WEIGHT};")
    print("  font-display: block;")
    print(f"  src: url(data:font/woff;base64,{payload}) format(\"woff\");")
    print("}")
    print(
        f"\n/* woff {raw_kb:.1f} KB -> base64 {b64_kb:.1f} KB */",
        file=sys.stderr,
    )
    print(f"license: {LICENSE_URL}", file=sys.stderr)


if __name__ == "__main__":
    main()
