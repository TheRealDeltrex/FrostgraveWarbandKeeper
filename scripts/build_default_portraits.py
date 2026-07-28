"""Normalize the shipped default character portraits into static/portraits/.

Source art lives outside the repo (one PNG per character, mixed sizes from ~160px
up to 784px). This bakes it down to uniform 256x256 PNGs named after the thing they
illustrate, so the app can find a default with a plain filename lookup and no fuzzy
matching at runtime:

    static/portraits/wizard.png
    static/portraits/apprentice.png
    static/portraits/captain.png
    static/portraits/<soldier type_key>.png      e.g. thug.png, companion_bear.png

256px covers the largest on-screen use (96px, so still crisp at 2x) and the PDF
roster's portrait boxes.

Usage:
    python scripts/build_default_portraits.py [SOURCE_DIR]
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

from PIL import Image

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from frostgrave_data import SOLDIERS  # noqa: E402

DEFAULT_SOURCE = Path(r"E:/ClaudeCodeFolder/Default Profile Pictures")
OUT_DIR = REPO_ROOT / "static" / "portraits"
SIZE = 256

# Source art arrives in whatever format it was drawn/exported in; everything is
# re-encoded to PNG below regardless, so the input extension only decides what
# we pick up off disk.
SOURCE_EXTS = ("*.png", "*.jpg", "*.jpeg", "*.webp")

# Source files whose name doesn't slugify straight onto a soldier name.
ALIASES = {
    "wizard": "wizard",
    "wizard_s_apprentice": "apprentice",
    "captain": "captain",
    "construct_small": "small_construct",
    "construct_medium": "medium_construct",
    "construct_large": "large_construct",
}


def slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")


def target_key(stem: str) -> str | None:
    """Map a source filename stem onto the asset name the app looks up."""
    s = slug(stem)
    if s in ALIASES:
        return ALIASES[s]
    by_name = {slug(info["name"]): key for key, info in SOLDIERS.items()}
    return by_name.get(s)


def normalize(src: Path, dest: Path) -> int:
    """Center-crop to square, resize to SIZE, write an optimized PNG.

    The art is ink-drawing style with a faint colour wash, so a dithered
    256-colour palette is visually indistinguishable from full RGB here while
    being less than half the size — worth it across 35 files inside the exe.
    JPEG would be smaller still, but rings badly on this much fine hatching.
    """
    with Image.open(src) as im:
        im = im.convert("RGB")
        w, h = im.size
        side = min(w, h)
        left = (w - side) // 2
        top = (h - side) // 2
        im = im.crop((left, top, left + side, top + side))
        im = im.resize((SIZE, SIZE), Image.LANCZOS)
        im = im.convert("P", palette=Image.ADAPTIVE, colors=256)
        im.save(dest, "PNG", optimize=True)
    return dest.stat().st_size


def main() -> int:
    source = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_SOURCE
    if not source.is_dir():
        print(f"Source folder not found: {source}")
        return 1

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    written: dict[str, int] = {}
    source_of: dict[str, str] = {}
    unmatched: list[str] = []
    clashes: list[str] = []

    files = sorted(
        (p for pattern in SOURCE_EXTS for p in source.glob(pattern)),
        key=lambda p: p.name.lower(),
    )
    for src in files:
        key = target_key(src.stem)
        if not key:
            unmatched.append(src.name)
            continue
        # Two source files claiming the same character (say boar.png and
        # boar.jpg) would silently leave whichever sorted last. Say so instead.
        if key in source_of:
            clashes.append(f"{key}: {source_of[key]} vs {src.name}")
            continue
        source_of[key] = src.name
        written[key] = normalize(src, OUT_DIR / f"{key}.png")

    missing = sorted(k for k in SOLDIERS if k not in written)
    for role in ("wizard", "apprentice", "captain"):
        if role not in written:
            missing.append(role)

    total = sum(written.values())
    print(f"wrote {len(written)} portraits to {OUT_DIR} ({total / 1024:.0f} KiB total)")
    if unmatched:
        print("  source files with no matching character: " + ", ".join(unmatched))
    if clashes:
        print("  more than one source file for the same character: " + "; ".join(clashes))
    if missing:
        print("  characters left without a default picture: " + ", ".join(missing))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
