"""Extractor: Advanced Spellcraft's Bibliosepulchre setting, tomb rules and
Tomb Table (pp.96-101), and its Random Encounter Table (p.143). Scenarios are
left out, as for every other book.

Adds, never replaces (each book key is written once and then left alone):
    data/expansion_rules.json    "Advanced Spellcraft": the setting and tomb
                                 rules, and the Tomb Table
    data/random_encounters.json  "Advanced Spellcraft": the three-level
                                 Bibliosepulchre Random Encounter Table

Text is the book's own; captions and the purchaser stamp are dropped. Both
files are appended to textually, never round-tripped through json.dumps().

    FWK_REFERENCE_DIR=... .venv/Scripts/python.exe scripts/extract_advanced_spellcraft_campaign.py
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
RULES = ROOT / "data" / "expansion_rules.json"
ENCOUNTERS = ROOT / "data" / "random_encounters.json"
SOURCE = "Advanced Spellcraft"

WATERMARK = "This ebook belongs to"
CAPTION = "UniversLTStd-Cn"
TABLE = "UniversLTStd-LightCn"
DIE = re.compile(r"^\d+(?:\s*[–-]\s*\d+)?\+?$")


def _clean(t: str) -> str:
    return re.sub(r"\s+", " ", t).replace("T h", "Th").strip()


def page_lines(doc, pg: int) -> list[tuple[str, float, str]]:
    """(font, size, text) per line on a page, minus captions, stamp and folio."""
    out = []
    for b in doc[pg].get_text("dict")["blocks"]:
        for ln in b.get("lines", []):
            spans = [s for s in ln["spans"] if s["text"].strip()]
            text = "".join(s["text"] for s in spans).strip()
            if not spans or WATERMARK in text or spans[0]["font"].startswith(CAPTION):
                continue
            if spans[0]["font"] == "Leander" and text == str(pg):
                continue
            out.append((spans[0]["font"], round(spans[0]["size"]), text))
    return out


def table_rows(lines: list[str]) -> list[dict]:
    """A die-roll table set as one cell per line: a roll, then its text."""
    rows: list[dict] = []
    for t in lines:
        if DIE.match(t):
            rows.append({"name": t, "text": ""})
        elif rows:
            rows[-1]["text"] = _clean(f"{rows[-1]['text']} {t}")
    return rows


def blocks(doc, pages) -> list[dict]:
    """Headed blocks: {heading, page, parts: [("text"|"table", [str])]}."""
    out: list[dict] = []
    for pg in pages:
        for font, size, text in page_lines(doc, pg):
            heading = font.startswith(("JSL", "Leander-SC", "RomanAntique")) or (
                font == "Leander" and size >= 19
            )
            if heading:
                out.append({"heading": _clean(text), "page": pg, "font": font, "parts": []})
                continue
            if not out:
                continue
            kind = "table" if font.startswith(TABLE) else "text"
            parts = out[-1]["parts"]
            if parts and parts[-1][0] == kind:
                parts[-1][1].append(text)
            else:
                parts.append((kind, [text]))
    return out


def campaign(doc) -> list[dict]:
    """The setting and tomb rules plus the Tomb Table."""
    setting = []
    tomb_rows: list[dict] = []
    for b in blocks(doc, range(96, 102)):
        if b["heading"] in ("THE BIBLIOSEPULCHRE", "Creating the Bibliosepulchre in Miniature", "THE TOMBS"):
            text = _clean(" ".join(" ".join(ls) for k, ls in b["parts"] if k == "text"))
            name = b["heading"].title() if b["heading"].isupper() else b["heading"]
            setting.append({"name": name, "tag": f"p.{b['page']}", "text": text})
        if b["heading"] == "THE TOMBS":
            for k, ls in b["parts"]:
                if k == "table":
                    first = next((i for i, t in enumerate(ls) if DIE.match(t)), len(ls))
                    tomb_rows += table_rows(ls[first:])
    if len(setting) != 3 or len(tomb_rows) != 20:
        sys.exit(f"parse problem: {len(setting)} setting sections, {len(tomb_rows)} Tomb Table rows")
    return [
        {"title": "The Bibliosepulchre", "blurb": "", "entries": setting},
        {"title": "Bibliosepulchre Tomb Table", "blurb": "(pp.99-101)", "rows": tomb_rows},
    ]


def encounters(doc) -> list[dict]:
    """p.143's grid: a second-roll column then one column per level."""
    cells: dict[int, dict[int, str]] = {}
    for b in doc[143].get_text("dict")["blocks"]:
        for ln in b.get("lines", []):
            t = "".join(s["text"] for s in ln["spans"]).strip()
            if t and ln["spans"][0]["font"].startswith(TABLE):
                row = round((ln["bbox"][1] - 314) / 14.15) + 1
                col = {162: 1, 255: 2, 349: 3}.get(round(ln["bbox"][0]))
                if col and 1 <= row <= 20:
                    cells.setdefault(col, {})[row] = t
    if any(len(cells.get(c, {})) != 20 for c in (1, 2, 3)):
        sys.exit("encounter table parse problem")
    out = []
    for col, first in ((1, "1–12"), (2, "13–18"), (3, "19–20")):
        out.append({
            "title": f"Bibliosepulchre Random Encounter Table – Level {col} (first roll {first})",
            "blurb": "(p.143)",
            "rows": [{"name": str(r), "text": cells[col][r]} for r in range(1, 21)],
        })
    return out


def _append_key(path: Path, key: str, value) -> bool:
    data = json.loads(path.read_text(encoding="utf-8"))
    if key in data:
        return False
    raw = path.read_bytes().decode("utf-8")
    nl = "\r\n" if "\r\n" in raw else "\n"
    m = re.search(r'\n( +)"', raw)
    pad = m.group(1) if m else "  "
    block = f'{pad}"{key}": ' + json.dumps(value, ensure_ascii=False, indent=len(pad)).replace("\n", nl + pad)
    body = raw.rstrip()
    assert body.endswith("}")
    path.write_bytes((body[:-1].rstrip() + "," + nl + block + nl + "}" + nl).encode("utf-8"))
    return True


def main() -> None:
    doc = fitz.open(str(PDF))
    for path, value in ((RULES, campaign(doc)), (ENCOUNTERS, encounters(doc))):
        print(f"{path.name}:", "added" if _append_key(path, SOURCE, value) else "already there")


if __name__ == "__main__":
    main()
