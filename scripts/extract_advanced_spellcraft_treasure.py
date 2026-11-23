"""Extractor: Advanced Spellcraft's Bibliosepulchre treasure (pp.125-142).

Adds, never replaces:
    data/magic_items.json   the 40 items, effect = the book's own item text
    data/loot_tables.json   the Bibliosepulchre Treasure Table (d20, then d20)

Prices go through scripts/extract_supplement_prices.py like every other book.
Both files are hand-compacted in places, so additions are textual insertions
before the closing bracket rather than a json.dumps() round trip.

    FWK_REFERENCE_DIR=... .venv/Scripts/python.exe scripts/extract_advanced_spellcraft_treasure.py
"""

from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

import fitz

ROOT = Path(__file__).resolve().parents[1]
REF = Path(os.environ.get("FWK_REFERENCE_DIR", ROOT / "reference"))
PDF = REF / "MGT2E - Advanced Spellcraft.pdf"
ITEMS = ROOT / "data" / "magic_items.json"
LOOT = ROOT / "data" / "loot_tables.json"
SOURCE = "Advanced Spellcraft"
TABLE = "Bibliosepulchre Treasure Table"

WATERMARK = re.compile(r"This ebook belongs to")
HEADING_FONT = "JSL-AncientItalic"
BODY_FONTS = ("BerlingLTStd",)
# The Ring of Transformation's own sub-table is set in the table fonts.
TABLE_FONTS = ("UniversLTStd-LightCn", "Leander")


def _clean(t: str) -> str:
    return re.sub(r"\s+", " ", t).strip()


def table_rows(doc) -> list[dict]:
    """Rows of the p.125-126 table as {first, second, name, cost, sell}."""
    lines = []
    for pg in (125, 126):
        lines += [ln.strip() for ln in doc[pg].get_text().splitlines() if ln.strip()]
    i = lines.index("Sell") + 1
    rows = []
    die_range = re.compile(r"^(\d+)\s*[–-]\s*(\d+)$")
    while i < len(lines):
        ln = lines[i]
        if WATERMARK.search(ln) or ln == "126":
            i += 1
            continue
        if die_range.match(ln):  # the merged first-roll cell; placed from row order below
            i += 1
            continue
        if not ln.isdigit():
            break
        name, cost, sell = lines[i + 1], lines[i + 2], lines[i + 3]
        first = "1–10" if len(rows) < 20 else "11–20"
        rows.append({"first": first, "second": int(ln), "name": _clean(name).replace("’", "'"),
                     "cost": cost, "sell": sell})
        i += 4
    return rows


def descriptions(doc) -> dict[str, str]:
    out: dict[str, list[str]] = {}
    cur = None
    for pg in range(126, 143):
        for b in doc[pg].get_text("dict")["blocks"]:
            for ln in b.get("lines", []):
                spans = [s for s in ln["spans"] if s["text"].strip()]
                if not spans or WATERMARK.search("".join(s["text"] for s in spans)):
                    continue
                if spans[0]["font"] == HEADING_FONT:
                    cur = _clean("".join(s["text"] for s in spans)).replace("T h", "Th")
                    out[cur] = []
                    continue
                if cur is None:
                    continue
                if all(s["font"].startswith(BODY_FONTS) for s in spans):
                    out[cur].append("".join(s["text"] for s in spans))
                elif all(s["font"].startswith(TABLE_FONTS) for s in spans):
                    text = "".join(s["text"] for s in spans).strip()
                    if not text.isdigit() or len(out[cur]) and out[cur][-1].startswith("\x00"):
                        out[cur].append("\x00" + text)
    res = {}
    for name, lines in out.items():
        body = _clean(" ".join(ln for ln in lines if not ln.startswith("\x00")))
        table = [ln[1:] for ln in lines if ln.startswith("\x00")]
        if table:
            # "Ring of Transformation Table", "Die Roll", "Transform Into", then pairs.
            title, pairs = table[0], table[3:]
            body += f" {title}: " + "; ".join(f"{a} {b}" for a, b in zip(pairs[::2], pairs[1::2])) + "."
        res[name] = body
    return res


def _insert(path: Path, block: str) -> None:
    raw = path.read_bytes().decode("utf-8")
    nl = "\r\n" if "\r\n" in raw else "\n"
    block = block.replace("\n", nl)
    head, close = raw.rstrip().rsplit(raw.rstrip()[-1], 1)[0].rstrip(), raw.rstrip()[-1]
    path.write_bytes((head + "," + nl + block + nl + close + nl).encode("utf-8"))


def main() -> None:
    doc = fitz.open(str(PDF))
    rows = table_rows(doc)
    descs = descriptions(doc)
    if len(rows) != 40 or len(descs) != 40:
        sys.exit(f"parse problem: {len(rows)} table rows, {len(descs)} descriptions")

    def desc_for(name: str) -> str:
        name = name.replace("'", "’")
        return descs.get(name) or descs[re.sub(r"\s*\(\d+\)$", "", name)]

    have = {(it["source"], it["name"]) for it in json.loads(ITEMS.read_text(encoding="utf-8"))}
    new = [
        {"name": r["name"], "source": SOURCE, "effect": desc_for(r["name"])}
        for r in sorted(rows, key=lambda r: r["name"])
        if (SOURCE, r["name"]) not in have
    ]
    if new:
        _insert(ITEMS, ",\n".join(
            " " + json.dumps(it, ensure_ascii=False, indent=1).replace("\n", "\n ") for it in new
        ))
    print(f"magic_items.json: added {len(new)}")

    loot = json.loads(LOOT.read_text(encoding="utf-8"))
    if SOURCE in loot:
        print("loot_tables.json: already has Advanced Spellcraft")
        return
    lines = [ln.strip() for ln in doc[125].get_text().splitlines()]
    start = lines.index("The Bibliosepulchre had a unique culture within the magical city of ancient")
    blurb = _clean(" ".join(lines[start:lines.index("BIBLIOSEPULCHRE TREASURE")]))
    table = [{
        "title": TABLE,
        "blurb": f"{blurb} (p.125)",
        "rows": [
            {
                "name": f"{r['first']}, then {r['second']}",
                "text": f"{r['name']} — {r['cost']} (sell {r['sell']})",
            }
            for r in rows
        ],
    }]
    block = f'  "{SOURCE}": ' + json.dumps(table, ensure_ascii=False, indent=2).replace("\n", "\n  ")
    _insert(LOOT, block)
    print("loot_tables.json: added the Bibliosepulchre Treasure Table")


if __name__ == "__main__":
    main()
