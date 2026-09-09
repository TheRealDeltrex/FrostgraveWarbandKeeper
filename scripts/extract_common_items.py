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
# The potion write-ups (pp.89-93), and the flat Scroll/Grimoire rules (p.95).
# Each entry is an ALL-CAPS name followed by its paragraphs, so the shop can
# show what a potion actually does instead of just its price.
DESCRIPTION_PAGES = [89, 90, 91, 92, 93]
SCROLL_GRIMOIRE_PAGE = 95
# The Magic Weapon and Armour table names this effect but explains it only in
# the p.97 prose above the table, which has no heading for descriptions() to
# find. Quoted verbatim from there. The wording is generic ("an item with
# Elemental Absorption"), so The Wildwoods' own elemental-absorption armour
# borrows it too — see game_content.SHOP_NAME_ALIASES.
ELEMENTAL_ABSORPTION_EFFECT = (
    "If a figure is wearing an item with Elemental Absorption, then any elemental damage "
    "they take (such as from the Elemental Bolt or Elemental Ball spells) is halved, "
    "rounding up."
)

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


# A description heading: the item name in capitals on its own line. Digits and
# an apostrophe appear in a few ("PHILTRE OF FAIRY DUST", "WIZARD'S GRIMOIRE"),
# so the test is "no lowercase letters" rather than str.isupper() on a slice.
_HEADING = re.compile(r"^[A-Z][A-Z'’ /-]{3,44}$")


def descriptions(doc: fitz.Document, pages: list[int]) -> dict[str, str]:
    """{NAME: paragraph} for every write-up on `pages`.

    The extracted text is one wrapped line per line, so a heading ends the
    previous entry and everything up to the next heading is its body. Page
    numbers and the odd running header sit on their own line and are dropped
    by the same "must look like a heading" test that finds the names."""
    out: dict[str, str] = {}
    name = None
    body: list[str] = []
    for line in [ln for page in pages for ln in _lines(doc, page)]:
        if _HEADING.match(line):
            if name and body:
                out[name] = " ".join(body).strip()
            name, body = line, []
        elif name:
            body.append(line)
    if name and body:
        out[name] = " ".join(body).strip()
    return out


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
    # Every potion's write-up, plus the p.95 rules for what a scroll and a
    # grimoire are, so the Shop and the vault can show what a row does rather
    # than only what it costs. Matched by upper-cased name; a row the book has
    # no write-up for (the Magic Weapon and Armour table, whose names already
    # state their effect) simply gets no "effect" key.
    text = descriptions(doc, DESCRIPTION_PAGES)
    text.update(descriptions(doc, [SCROLL_GRIMOIRE_PAGE]))
    unmatched = []
    for item in items:
        item["source"] = "Core Rules"
        # "Scroll"/"Grimoire" are single rows against the book's plural heading.
        if item.get("effect") == "Elemental Absorption":
            item["effect"] = ELEMENTAL_ABSORPTION_EFFECT
        body = text.get(item["name"].upper()) or text.get(item["name"].upper() + "S")
        # The SCROLLS write-up opens on the Treasure Table's "how many are
        # found" sentence, which says nothing about what a scroll is. Dropped
        # rather than reworded — the rest is the book's text, verbatim.
        if body and item["name"] == "Scroll":
            body = body.split(". ", 1)[1] if body.startswith("The number in brackets") else body
        if body:
            item["effect"] = body
        elif item["category"] in ("Potion", "Scroll", "Grimoire"):
            unmatched.append(item["name"])
    if unmatched:
        print(f"no write-up found for: {', '.join(unmatched)}", file=sys.stderr)
    OUT.write_text(json.dumps(items, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"wrote {len(items)} items to {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
