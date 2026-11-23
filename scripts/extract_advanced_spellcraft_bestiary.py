"""Extractor: Advanced Spellcraft's Bestiary chapter (pp.143-159).

Adds, never replaces:
    data/bestiary.json  creatures new to the app, plus Advanced Spellcraft's
                        version of reprinted creatures whose rules changed
                        (REPRINTED_CHANGED) beside the original. Reprints that
                        are unchanged (REPRINTED_SAME) get a `sources` list
                        naming both books instead.
    data/traits.json    the creature traits (pp.153-159); a trait whose text
                        matches an existing entry gets `sources`, a reworded
                        one is added beside it.

Reprints were judged against each original book's stat block and trait list
(PDFs): same stats and traits -> same; any difference -> changed.

    FWK_REFERENCE_DIR=... .venv/Scripts/python.exe scripts/extract_advanced_spellcraft_bestiary.py
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
BESTIARY = ROOT / "data" / "bestiary.json"
TRAITS = ROOT / "data" / "traits.json"
SOURCE = "Advanced Spellcraft"

# AS name -> (app bestiary name, original book).
REPRINTED_SAME = {
    "Blood Crow": ("Blood Crow", "Thaw of the Lich Lord"),
    "Chilopendra": ("Chilopendra", "Forgotten Pacts"),
    "Failing Wretch": ("Failing Wretch", "Forgotten Pacts"),
    "Leechwolf": ("Leechwolf", "Blood Legacy"),
}
# Fireheart: Construct Spikes (AS: Horns). Maze: 3 Item Slots (AS: its own
# trait). Perilous Dark: Limited Spell Immunity, See Invisible (AS: a spell
# list, no See Invisible). Breeding Pits: Immune to Poison, Spell Immunity (AS:
# Poison, Fungus).
REPRINTED_CHANGED = {"Blade-Dog", "Collegium Porter", "Chronohounds", "Violent Fungus"}

WATERMARK = "This ebook belongs to"
HEADING = "JSL-AncientItalic"
STATS = ("Move", "Fight", "Shoot", "Armour", "Will", "Health")
CATEGORIES = ("Animal", "Construct", "Demon", "Undead")


def _clean(t: str) -> str:
    return re.sub(r"\s+", " ", t).replace("T h", "Th").strip()


def _norm(t: str) -> str:
    t = t.replace("’", "'").replace("“", '"').replace("”", '"').replace("–", "-")
    return re.sub(r"\s+", " ", t).strip().lower()


def sections(doc, pages) -> list[tuple[str, list[tuple[str, str]]]]:
    """[(heading, [(font, line), ...])] in reading order, captions dropped."""
    out: list[tuple[str, list]] = []
    for pg in pages:
        for b in doc[pg].get_text("dict")["blocks"]:
            for ln in b.get("lines", []):
                spans = [s for s in ln["spans"] if s["text"].strip()]
                text = "".join(s["text"] for s in spans)
                if not spans or WATERMARK in text or spans[0]["font"] == "UniversLTStd-Cn":
                    continue
                if spans[0]["font"] == HEADING:
                    out.append((_clean(text), []))
                elif out and not (spans[0]["font"].startswith("Leander") and text.strip().isdigit()):
                    out[-1][1].append((spans[0]["font"], text))
    return out


def creatures(doc) -> list[dict]:
    res = []
    for name, lines in sections(doc, range(144, 153)):
        flavor = _clean(" ".join(t for f, t in lines if f.startswith("Berling")))
        cells = [t.strip() for f, t in lines if not f.startswith("Berling")]
        # Each stat table: its title, the seven column heads, six values, notes.
        i = 0
        while i < len(cells):
            if cells[i + 1 : i + 8] != [*STATS, "Notes"]:
                i += 1
                continue
            title, vals = cells[i], cells[i + 8 : i + 14]
            j = i + 14
            notes = []
            while j < len(cells) and cells[j + 1 : j + 2] != ["Move"]:
                notes.append(cells[j])
                j += 1
            notes_text = _clean(" ".join(notes)).rstrip(",")
            res.append({
                "as_name": name, "name": title, "flavor": flavor,
                "stats": " · ".join(f'{s} {v}{chr(34) if s == "Move" else ""}' for s, v in zip(STATS, vals)),
                "notes": notes_text,
                "page": None,
            })
            i = j
    return res


def traits(doc) -> list[dict]:
    out = []
    for name, lines in sections(doc, range(153, 160)):
        body = []
        for _, t in lines:
            body.append(t)
        text = _clean(" ".join(body)).replace(" • ", "\n• ")
        out.append({"name": name, "text": text})
    return out


def _insert(path: Path, items: list[dict], indent: int) -> None:
    raw = path.read_bytes().decode("utf-8")
    nl = "\r\n" if "\r\n" in raw else "\n"
    pad = " " * indent
    block = ("," + nl).join(
        pad + json.dumps(it, ensure_ascii=False, indent=indent).replace("\n", nl + pad) for it in items
    )
    body = raw.rstrip()
    assert body.endswith("]")
    path.write_bytes((body[:-1].rstrip() + "," + nl + block + nl + "]" + nl).encode("utf-8"))


def _add_sources(path: Path, name: str, source: str) -> bool:
    """Textually add a `sources` line after the matching entry's source line."""
    raw = path.read_bytes().decode("utf-8")
    pat = re.compile(
        r'("name": ' + re.escape(json.dumps(name, ensure_ascii=False)) + r',(?:\r?\n[^\n}]*?)*?'
        r'(\r?\n)(\s*)"source": ' + re.escape(json.dumps(source)) + r')(,?)'
    )
    m = pat.search(raw)
    if not m or '"sources"' in raw[m.end() : m.end() + 80]:
        return False
    line = f'{m.group(2)}{m.group(3)}"sources": {json.dumps([source, SOURCE])}'
    new = raw[: m.end(1)] + "," + line + (m.group(4) or "") + raw[m.end() :]
    path.write_bytes(new.encode("utf-8"))
    return True


def main() -> None:
    doc = fitz.open(str(PDF))
    beasts = creatures(doc)
    if len(beasts) != 16:
        sys.exit(f"parse problem: {len(beasts)} stat tables")
    for b in beasts:
        b["page"] = next(pg for pg in range(144, 153) if b["as_name"] in doc[pg].get_text())

    have = json.loads(BESTIARY.read_text(encoding="utf-8"))
    have_keys = {(c["name"], c["source"]) for c in have}
    added, tagged = [], []
    for b in beasts:
        if b["as_name"] in REPRINTED_SAME:
            app_name, orig = REPRINTED_SAME[b["as_name"]]
            if _add_sources(BESTIARY, app_name, orig):
                tagged.append(app_name)
            continue
        name = "Chronohound" if b["name"] == "Chronohounds" else b["name"]
        if (name, SOURCE) in have_keys:
            continue
        first = b["notes"].split(",")[0].strip()
        added.append({
            "name": name,
            "category": first if first in CATEGORIES else "Miscellaneous",
            "source": SOURCE,
            "stats": b["stats"],
            "description": f"{b['flavor']} {b['notes']}. (p.{b['page']})",
        })
    if added:
        _insert(BESTIARY, added, 1)
    print(f"bestiary.json: added {len(added)}, tagged {len(tagged)}: {', '.join(tagged)}")

    existing = json.loads(TRAITS.read_text(encoding="utf-8"))
    by_name = {}
    for t in existing:
        by_name.setdefault(t["name"].lower(), []).append(t)
    new_traits, both = [], []
    for t in traits(doc):
        prior = by_name.get(t["name"].lower(), [])
        if any(p.get("source") == SOURCE or SOURCE in p.get("sources", []) for p in prior):
            continue
        same = next((p for p in prior if _norm(p["text"]) == _norm(t["text"])), None)
        if same and _add_sources(TRAITS, same["name"], same["source"]):
            both.append(t["name"])
        elif not same:
            new_traits.append({"name": t["name"], "text": t["text"], "source": SOURCE})
    if new_traits:
        _insert(TRAITS, new_traits, 2)
    print(f"traits.json: added {len(new_traits)}, tagged {len(both)}: {', '.join(both)}")


if __name__ == "__main__":
    main()
