"""Extract the Core Rules' priced, buyable item tables into data/common_items.json.

"Common items" are the Core Rules entries a wizard can buy or sell that are
*not* already reachable through data/magic_items.json's Magic Item Table:
the Lesser and Greater Potion tables (Core Rules pp.86-87) and the Magic
Weapon and Armour table (p.98). Grimoires and scrolls are priced by a flat
rule rather than a table (p.104), so they are written from that rule, with the
specific spell chosen by a dropdown rather than enumerated here.

The p.100 Magic Item Table is extracted too, under category "Magic Item", but
only for its prices: those 20 items are already in data/magic_items.json and
already reachable through the item picker, so the vault's Common Items section
filters them back out.

Regenerates the file wholesale, so hand edits to data/common_items.json are
lost on the next run — put corrections here, not there. Prices for supplement
items are a separate job (see todo.md) and deliberately not in this file:
they need keying by (source, name), because item names collide across books.

    .venv/Scripts/python.exe scripts/extract_common_items.py

Reads the source PDF directly; the HTML references are unreliable (CLAUDE.md).
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import fitz  # PyMuPDF

CORE_PDF = Path("E:/RPG/Tabletop/Frostgrave/FG2E 01 2020 Core Rules.pdf")
OUT = Path(__file__).resolve().parent.parent / "data" / "common_items.json"

# PDF page indices happen to equal the printed page numbers in this file.
LESSER_POTIONS_PAGE = 86
GREATER_POTIONS_PAGE = 87
MAGIC_ARMS_PAGE = 98
MAGIC_ITEMS_PAGE = 100

# "500gc" / "1,500gc" / "—" (never purchasable).
# The trailing period is a typo in the Greater Potion Table ingredient
# column ("500gc."), not a format worth preserving.
PRICE = re.compile(r"^(?:([\d,]+)gc\.?|[?\u2013\u2014-])$")


def _price(token: str) -> int | None:
    """A price cell as an int, or None where the book prints a dash — those
    items can be found or brewed but never bought (Core Rules p.90: the elixir
    of life "can never be bought")."""
    m = PRICE.match(token.strip())
    if not m:
        raise ValueError(f"unparsed price cell: {token!r}")
    return int(m.group(1).replace(",", "")) if m.group(1) else None


def _lines(doc: fitz.Document, page: int) -> list[str]:
    return [ln.strip() for ln in doc[page].get_text().splitlines() if ln.strip()]


def _rows_after(lines: list[str], header: str, width: int, stop: str | None = None) -> list[list[str]]:
    """Rows of `width` cells following the column headings under `header`.

    The extracted text is one cell per line, so a table is a flat run: find the
    heading, skip its column labels, then take cells `width` at a time until a
    row's first cell stops looking like a die roll ("1", "19-20")."""
    start = lines.index(header) + 1
    while not re.match(r"^\d+(?:[?\u2013\u2014-]\d+)?$", lines[start]):
        start += 1
    rows: list[list[str]] = []
    i = start
    while i + width <= len(lines):
        if not re.match(r"^\d+(?:[?\u2013\u2014-]\d+)?$", lines[i]):
            break
        if stop and lines[i + 1].startswith(stop):
            break
        rows.append(lines[i : i + width])
        i += width
    return rows


def lesser_potions(doc: fitz.Document) -> list[dict]:
    """Rows 1-18; 19-20 is "roll again on the Greater Potion Table", not an item."""
    out = []
    for _die, name, buy, sell in _rows_after(
        _lines(doc, LESSER_POTIONS_PAGE), "Lesser Potion Table", 4, stop="Roll on the Greater"
    ):
        out.append(
            {
                "name": name.strip(),
                "category": "Potion",
                "tier": "lesser",
                "purchase": _price(buy),
                "sale": _price(sell),
            }
        )
    return out


def greater_potions(doc: fitz.Document) -> list[dict]:
    out = []
    for die, name, buy, sell, ingredients in _rows_after(
        _lines(doc, GREATER_POTIONS_PAGE), "Greater Potion Table", 5
    ):
        # The die range is kept because two rules index back into this table
        # by number rather than by name: the "19-20 roll again" result on the
        # Lesser table, and the Alchemical Workshop's potion-mixing roll.
        nums = re.findall(r"\d+", die)
        out.append(
            {
                "name": name.strip(),
                "category": "Potion",
                "tier": "greater",
                "die_low": int(nums[0]),
                "die_high": int(nums[-1]),
                "purchase": _price(buy),
                "sale": _price(sell),
                # Brew Potion (p.114) charges this before the -4 casting roll,
                # and loses it on a failure.
                "ingredients": _price(ingredients),
            }
        )
    return out


def magic_arms(doc: fitz.Document) -> list[dict]:
    """The p.98 table's Magic Weapon/Armour and Effects columns together name
    the item — "Hand Weapon" alone appears three times at three prices."""
    out = []
    for _die, item, effect, buy, sell in _rows_after(
        _lines(doc, MAGIC_ARMS_PAGE), "Magic Weapon and Armour Table", 5
    ):
        out.append(
            {
                "name": f"{item.strip()}, {effect.strip()}",
                "category": "Magic Weapon or Armour",
                "base_item": item.strip(),
                "effect": effect.strip(),
                "purchase": _price(buy),
                "sale": _price(sell),
            }
        )
    return out


def magic_items(doc: fitz.Document) -> list[dict]:
    """The p.100 Magic Item Table. These 20 names already exist in
    data/magic_items.json (name/source/effect), which carries no prices — the
    Shop needs them, so they are extracted here and matched back by name. They
    are deliberately marked category "Magic Item" so the vault's Common Items
    section can leave them out: they are already reachable through the ordinary
    item picker."""
    out = []
    for _die, name, buy, sell in _rows_after(
        _lines(doc, MAGIC_ITEMS_PAGE), "Magic Item Table", 4
    ):
        out.append(
            {
                "name": name.strip(),
                "category": "Magic Item",
                "purchase": _price(buy),
                "sale": _price(sell),
            }
        )
    return out


def flat_priced() -> list[dict]:
    """Core Rules p.104. Both take a spell name, so they are one entry plus a
    dropdown rather than one entry per spell in the game."""
    return [
        {
            "name": "Grimoire",
            "category": "Grimoire",
            "variant": "spell",
            "purchase": 500,
            "sale": 200,
            # "no wizard may ever sell a grimoire containing a spell they do
            # not already know" (p.104) — warned about, never blocked.
            "sale_requires_known_spell": True,
        },
        {
            "name": "Scroll",
            "category": "Scroll",
            "variant": "spell",
            "purchase": 250,
            "sale": 30,
        },
    ]


def main() -> int:
    if not CORE_PDF.exists():
        print(f"Core Rules PDF not found at {CORE_PDF}", file=sys.stderr)
        return 1
    doc = fitz.open(CORE_PDF)
    items = (
        lesser_potions(doc)
        + greater_potions(doc)
        + magic_arms(doc)
        + magic_items(doc)
        + flat_priced()
    )
    for item in items:
        item["source"] = "Core Rules"
    OUT.write_text(json.dumps(items, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"wrote {len(items)} items to {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
