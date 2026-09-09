"""Extract the supplement treasure tables' prices into data/supplement_item_prices.json.

The Core Rules' priced tables live in data/common_items.json
(scripts/extract_common_items.py). This is the same job for the supplements, and
it is a separate file with a separate extractor for two reasons: the entries are
keyed by (source, name) rather than by name, and a re-run of
extract_expansion_content.py must not be able to clobber the prices.

**Keyed by (source, name), never by name alone.** Two books print "Book of the
Construct" and two print "Construct Hammer", at *different prices* -- the Folio's
Construct Hammer is 200gc, Fireheart's is 125gc. A name key would silently give
one of each pair the other's price.

Sale prices: the four newest books (The Red King, Blood Legacy, Fireheart, The
Wildwoods) print a Sale Price column. The four older ones (Thaw of the Lich Lord,
Forgotten Pacts, The Maze of Malcor, The Perilous Dark) print a Purchase Price
column and nothing else, so an item from them would be findable and buyable but
impossible to sell. Those get a sale price of a third of purchase, rounded down
to the nearest 5gc, flagged `"sale_estimated": true` so the Shop can label it as
the house rule it is. That fraction is a maintainer's decision, not a printed
value; it sits roughly below the 40-50% the newer books actually print.

Two books contribute no prices at all and are absent from the output by design:
Into the Breeding Pits and The Wizards' Conclave describe their items in prose
with no price table anywhere. Spellcaster Magazine items are likewise unpriced.
Their entries in data/magic_items.json stay unbuyable, which is correct -- there
is no price to record.

Regenerates the file wholesale, so hand edits to the JSON are lost on the next
run -- put corrections here, not there.

    .venv/Scripts/python.exe scripts/extract_supplement_prices.py

Reads the source PDFs directly; the HTML references are unreliable (CLAUDE.md).
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import fitz  # PyMuPDF

PDF_DIR = Path("E:/RPG/Tabletop/Frostgrave")
OUT = Path(__file__).resolve().parent.parent / "data" / "supplement_item_prices.json"

# The books that print a Sale Price column. The rest get an estimate; see the
# module docstring.
SALE_FRACTION = 3
SALE_ROUNDING = 5

# A die-roll cell opening a row: "1", "19-20", "1\u201310", "20+".
DIE = re.compile(r"^(\d+)(?:\s*[\u2012-\u2015-]\s*\d+)?\+?$")
# A price cell, inline or on its own line. "1,000gc", "500gc." (the trailing
# period is dirt in more than one of these tables, not a format).
PRICE = re.compile(r"([\d,]+)\s*gc\.?")
# Artefacts are priceless and the tables print "X" in both columns for them.
NO_PRICE = re.compile(r"^[X\u2012-\u2015?-]$")


def _lines(doc: fitz.Document, pages: list[int]) -> list[str]:
    out: list[str] = []
    for page in pages:
        out += [ln.strip() for ln in doc[page].get_text().splitlines() if ln.strip()]
    return out


# The extracted name on the left, the data/magic_items.json spelling on the
# right. The two files have to join: the price file is looked up from a vault
# entry, and a vault entry's name comes from the item picker, which reads
# magic_items.json. Every one of these is the same object printed two ways --
# a count moved into the name ("Vial of Starlight (10)" in the table, plain in
# the item list), or a capital that drifted.
ALIASES = {
    ("Blood Legacy", "Two-headed Wand"): "Two-Headed Wand",
    ("The Maze of Malcor", "Tookroot (5)"): "Tookroot (x5 doses)",
    ("The Maze of Malcor", "Wand of Casting (10)"): "Wand of Casting",
    ("The Maze of Malcor", "Wand of Lost Magic (3)"): "Wand of Lost Magic",
    ("The Red King", "Enchanted Scroll Wax (6)"): "Enchanted Scroll Wax (6 uses)",
    ("The Red King", "Enchanted Vials (6)"): "Enchanted Vials (6 uses)",
    ("The Red King", "Golden Fangs (6)"): "Golden Fangs (6 uses)",
    ("The Red King", "The Feather Blade"): "Feather Blade",
    ("Thaw of the Lich Lord", "Vial of Starlight (10)"): "Vial of Starlight",
    # The Wildwoods prices light and heavy separately at the same figures;
    # magic_items.json carries the one merged entry the descriptions use.
    ("The Wildwoods", "Mystically-honed Light Armour"): "Mystically-honed Armour",
    ("The Wildwoods", "Mystically-honed Heavy Armour"): "Mystically-honed Armour",
    # The table cell carries a cross-reference, the item list does not.
    (
        "The Wildwoods",
        "Light Armour with Elemental Absorption (see Frostgrave, page 97)",
    ): "Light Armour with Elemental Absorption",
}


def _rows(lines: list[str], source: str, start: str, stop: str | None, columns: str) -> list[dict]:
    """Rows between the `start` heading and `stop`, as {name, purchase, sale}.

    One scanner covers every book because the layouts differ in only one way: a
    row's cells are sometimes one per line ("1" / "Wraithbottle" / "200gc") and
    sometimes run together ("1" / "Blood Beetle 250gc 75gc"), and a long name
    wraps across several lines. So a row is "everything between one die-roll line
    and the next", its trailing gc figures are the price columns, and whatever
    text is left is the name.
    """
    i = next(n for n, ln in enumerate(lines) if ln.startswith(start)) + 1
    end = len(lines)
    if stop:
        end = next(n for n, ln in enumerate(lines[i:], i) if ln.startswith(stop))

    chunks: list[list[str]] = []
    for ln in lines[i:end]:
        if DIE.match(ln):
            chunks.append([])
        elif chunks:
            chunks[-1].append(ln)

    rows = []
    for chunk in chunks:
        text = " ".join(chunk)
        found = PRICE.findall(text)
        if not found:
            # An artefact row, or a sub-table heading that slipped past the die
            # pattern. Either way there is no price to record.
            continue
        wanted = 2 if columns == "purchase+sale" else 1
        if len(found) < wanted:
            raise ValueError(f"{start}: expected {wanted} prices in {text!r}, got {found}")
        # The artefact table's rows end in a bare unlock number rather than a
        # price, so only the gc figures are taken and the leftovers stripped.
        name = PRICE.sub("", text)
        name = " ".join(w for w in name.split() if not NO_PRICE.match(w) and not w.isdigit())
        name = name.replace("\u2019", "'").strip(" .\u2012-\u2015")
        name = " ".join(name.split())
        rows.append(
            {
                "name": ALIASES.get((source, name), name),
                "purchase": None if columns == "sale" else int(found[0].replace(",", "")),
                "sale": int(found[-1].replace(",", "")) if columns != "purchase" else None,
            }
        )
    return rows


# Each entry: the PDF, and the tables to read out of it as
# (heading, stop-heading or None, pages, which price columns the table prints).
#
# Fireheart's Construct Modification Table (p.12) is deliberately not here. It
# is priced, but it prices construct upgrades, which this app does not model at
# all -- reading it would put twenty rows in the Shop matching nothing in the
# vault. It is also where the "Construct Hammer" and "Construct Oil" name
# collisions with The Frostgrave Folio come from.
BOOKS: dict[str, tuple[str, list[tuple[str, str | None, list[int], str]]]] = {
    "Thaw of the Lich Lord": (
        "FG2E 02 2015 Thaw of the Lich Lord.pdf",
        [("Lich Lord Treasure Table", None, [46], "purchase")],
    ),
    "Forgotten Pacts": (
        "FG2E 04 2016 Forgotten Pacts.pdf",
        [
            ("Forgotten Pacts Treasure Table", "Whenever a player rolls", [71], "purchase"),
            ("Magic Ammunition Table", None, [71], "purchase"),
        ],
    ),
    "The Frostgrave Folio": (
        "FG2E 05 2017 The Frostgrave Folio.pdf",
        [("The Hunt for the Golem Treasure Table", "BOOK OF THE CONSTRUCT", [16], "purchase")],
    ),
    "The Maze of Malcor": (
        "FG2E 06 2018 The Maze of Malcor.pdf",
        [("Maze of Malcor Treasure Table", None, [87, 88], "purchase")],
    ),
    "The Perilous Dark": (
        "FG2E 08 2019 Perilous Dark.pdf",
        [("Perilous Dark Treasure Table", None, [79], "purchase")],
    ),
    "The Red King": (
        "FG2E 09 2020 The Red King.pdf",
        [
            ("Red King Treasure Table", "AMULET OF ELEMENTAL", [65, 66, 67], "purchase+sale"),
            # "Artefacts may never be bought, unless one player is buying it
            # from another player. They may be sold for the listed price if a
            # wizard has unlocked it" (p.78) -- so the single gc column here is
            # the *sale* price, and the bare number after it is the unlock
            # target, not money. Recorded the way the Core Rules' unbuyable
            # potions are: listed, sell-only, purchase None.
            ("Red King Artefact Table", None, [78, 79], "sale"),
        ],
    ),
    "Blood Legacy": (
        "FG2E 10 2021 Blood Legacy.pdf",
        [("Blood Legacy Treasure Table", None, [65, 66], "purchase+sale")],
    ),
    "Fireheart": (
        "FG2E 11 2022 Fireheart.pdf",
        [("Fireheart Treasure Table", None, [70, 71], "purchase+sale")],
    ),
    "The Wildwoods": (
        "FG2E 13 2023 The Wildwoods.pdf",
        [
            ("Wildwoods Magic Weapon/Armour Table", None, [59], "purchase+sale"),
            ("Wildwoods Magic Item Table", None, [63, 64], "purchase+sale"),
        ],
    ),
}


def _superseded_by_core() -> set[str]:
    """Names the 2nd-edition Core Rules reprints, at its own prices.

    Three items out of the 1st-edition-era books were pulled into the 2020 Core
    Rules and repriced there: Construct Oil (300gc in The Frostgrave Folio,
    100gc as a Core lesser potion), Construct Hammer and Ring of Transference.
    The newer printing wins, so the superseded rows are left out of this file
    entirely rather than sitting in the Shop under the old book's shelf at the
    old price. Read from data/common_items.json so a Core re-extraction that
    adds another such item takes effect here without an edit."""
    core = json.loads((OUT.parent / "common_items.json").read_text(encoding="utf-8"))
    return {row["name"] for row in core}


def _estimated_sale(purchase: int) -> int:
    return (purchase // SALE_FRACTION) // SALE_ROUNDING * SALE_ROUNDING


def main() -> int:
    items: list[dict] = []
    superseded = _superseded_by_core()
    for source, (filename, tables) in BOOKS.items():
        path = PDF_DIR / filename
        if not path.exists():
            print(f"source PDF not found: {path}", file=sys.stderr)
            return 1
        doc = fitz.open(path)
        for heading, stop, pages, columns in tables:
            for row in _rows(_lines(doc, pages), source, heading, stop, columns):
                if row["name"] in superseded:
                    print(f"  skipping {source}: {row['name']} — repriced by the Core Rules")
                    continue
                row["source"] = source
                row["table"] = heading
                row["sale_estimated"] = row["sale"] is None
                if row["sale"] is None:
                    row["sale"] = _estimated_sale(row["purchase"])
                items.append(row)
        doc.close()

    # (source, name) is the lookup key, so it has to be unique per book. Two
    # rows collapsing onto one name is only allowed where they were the same
    # price anyway (The Wildwoods prices light and heavy mystically-honed
    # armour separately at identical figures); anything else is a parse error.
    seen: dict[tuple[str, str], dict] = {}
    deduped: list[dict] = []
    for item in items:
        key = (item["source"], item["name"])
        prior = seen.get(key)
        if prior is not None:
            if (prior["purchase"], prior["sale"]) != (item["purchase"], item["sale"]):
                raise ValueError(f"{key} priced twice, differently: {prior} vs {item}")
            continue
        seen[key] = item
        deduped.append(item)
    items = deduped

    OUT.write_text(json.dumps(items, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"wrote {len(items)} priced items to {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
