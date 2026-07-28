"""One-off extractor: supplement rules content out of the local reference HTML.

Sources are two hand-compiled distillations kept outside the repo — one for the
five Frostgrave supplements, one for Ghost Archipelago (a separate Osprey
ruleset, reference-only here). Parsing them beats transcribing ~130 treasure
items and 20 trap results by hand, and re-running the script is how you pick up
edits to those documents.

Writes three files the app loads at runtime:

    data/magic_items.json       supplement treasure, {name, source, effect}
    data/expansion_rules.json   the in-game table rules, grouped per book
    data/ghost_archipelago.json Lexicon-only content for the sister ruleset

Usage:
    python scripts/extract_expansion_content.py [SUPPLEMENTS_HTML] [GHOST_HTML]
"""

from __future__ import annotations

import html
import json
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

REFERENCE_DIR = Path(r"E:/RPG/Tabletop/Frostgrave")
DEFAULT_SUPPLEMENTS = REFERENCE_DIR / "Frostgrave X-Y Supplements Reference.html"
DEFAULT_GHOST = REFERENCE_DIR / "FG2E - Ghost Archipelago Reference.html"
DATA = REPO_ROOT / "data"

# Section id prefix in the reference -> the source-book name the app already uses
# in SOURCE_BOOKS. Ghost Archipelago is deliberately not one of them: it is a
# separate ruleset with no warband, so it gets no toggle and nothing hireable.
BOOKS = {
    "pacts": "Forgotten Pacts",
    "pits": "Into the Breeding Pits",
    "malcor": "The Maze of Malcor",
    "lich": "Thaw of the Lich Lord",
    "dark": "The Perilous Dark",
}


def clean(raw: str) -> str:
    """Strip tags and normalise entities/whitespace to plain text."""
    text = re.sub(r"<[^>]+>", "", raw)
    text = html.unescape(text)
    text = text.replace("\u2212", "-").replace("\xa0", " ")
    return re.sub(r"\s+", " ", text).strip()


def section(doc: str, anchor: str) -> str:
    """The chunk of the document from one <h3 id=...> up to the next h3 or </section>."""
    start = doc.find(f'id="{anchor}"')
    if start < 0:
        return ""
    rest = doc[start:]
    end = min(
        (i for i in (rest.find('<h3 class="subhead"', 1), rest.find("</section>")) if i > 0),
        default=len(rest),
    )
    return rest[:end]


def two_col_rows(chunk: str) -> list[tuple[str, str]]:
    """Rows of a <table class="data"> as (name, description) pairs.

    Wider tables (the crew stat blocks are nine columns) keep their meaning by
    borrowing the table's own <th> labels — otherwise a row collapses to
    "6 - +2 - +0 - 10 - ? - ?", which tells the reader nothing.
    """
    rows = re.findall(r"<tr>(.*?)</tr>", chunk, re.S)
    headers: list[str] = []
    for row in rows:
        if "<th" in row:
            headers = [clean(c) for c in re.findall(r"<th[^>]*>(.*?)</th>", row, re.S)]
            break

    out = []
    for row in rows:
        if "<th" in row:
            continue
        cells = [clean(c) for c in re.findall(r"<td[^>]*>(.*?)</td>", row, re.S)]
        if len(cells) < 2:
            continue
        name, values = cells[0], cells[1:]
        if len(values) > 1 and len(headers) == len(cells):
            parts = [
                f"{label} {value}" if label else value
                for label, value in zip(headers[1:], values)
                if value
            ]
            body = " · ".join(parts)
        else:
            body = " - ".join(v for v in values if v)
        if name and body:
            out.append((name, body))
    return out


def cards(chunk: str) -> list[dict]:
    """The <div class="card"> blocks used for rules summaries."""
    out = []
    for block in re.findall(r'<div class="card">(.*?)</div>', chunk, re.S):
        tag = re.search(r'<span class="tag">(.*?)</span>', block)
        head = re.search(r"<h4>(.*?)</h4>", block, re.S)
        body = re.search(r"<p>(.*?)</p>", block, re.S)
        if not head:
            continue
        out.append(
            {
                "name": clean(head.group(1)),
                "tag": clean(tag.group(1)) if tag else "",
                "text": clean(body.group(1)) if body else "",
            }
        )
    return out


def notes(chunk: str) -> list[str]:
    return [clean(p) for p in re.findall(r'<p class="subhead-note">(.*?)</p>', chunk, re.S)]


# --------------------------------------------------------------------------


def build_magic_items(doc: str) -> list[dict]:
    items = []
    for prefix, book in BOOKS.items():
        chunk = section(doc, f"{prefix}-treasure")
        for name, effect in two_col_rows(chunk):
            items.append({"name": name, "source": book, "effect": effect})
    items.sort(key=lambda it: (it["source"], it["name"].lower()))
    return items


def build_expansion_rules(doc: str) -> dict:
    """Per-book reference sections: the in-game table rules the app shows but
    does not simulate."""
    out: dict[str, list[dict]] = {book: [] for book in BOOKS.values()}

    def add(book: str, title: str, blurb: str = "", rows=None, entries=None):
        payload = {"title": title, "blurb": blurb}
        if rows:
            payload["rows"] = [{"name": n, "text": t} for n, t in rows]
        if entries:
            payload["entries"] = entries
        if payload.get("rows") or payload.get("entries"):
            out[book].append(payload)

    # --- Forgotten Pacts ---
    ch = section(doc, "pacts-attributes")
    add(
        "Forgotten Pacts",
        "Demonic Attributes",
        " ".join(notes(ch)),
        entries=cards(ch),
    )
    ch = section(doc, "pacts-spells")
    add(
        "Forgotten Pacts",
        "Mystic Brands",
        " ".join(notes(ch)),
        entries=cards(ch),
    )

    # --- Into the Breeding Pits ---
    ch = section(doc, "pits-underground")
    add("Into the Breeding Pits", "Underground exploration", " ".join(notes(ch)), entries=cards(ch))
    ch = section(doc, "pits-traps")
    add(
        "Into the Breeding Pits",
        "Traps & secret passages",
        " ".join(notes(ch)),
        rows=two_col_rows(ch),
    )

    # --- The Maze of Malcor ---
    ch = section(doc, "malcor-rules")
    add("The Maze of Malcor", "Optional core rule updates", " ".join(notes(ch)), entries=cards(ch))
    ch = section(doc, "malcor-pentangle")
    add(
        "The Maze of Malcor",
        "The Pentangle — five lost schools",
        " ".join(notes(ch)),
        rows=[(n, t) for n, t in two_col_rows(ch)],
    )
    ch = section(doc, "malcor-spells")
    add("The Maze of Malcor", "Lost Spells", " ".join(notes(ch)), entries=cards(ch))

    # --- Thaw of the Lich Lord ---
    ch = section(doc, "lich-lichdom")
    add(
        "Thaw of the Lich Lord",
        "Lichdom — failing the cast",
        " ".join(notes(ch)),
        rows=two_col_rows(ch),
    )

    # --- The Perilous Dark ---
    # No new spells or soldiers in this one: it is a solo/co-op and dungeon-
    # generation toolkit, so everything it adds is reference material.
    ch = section(doc, "dark-mechanics")
    add("The Perilous Dark", "Solo & co-op toolkit", " ".join(notes(ch)), entries=cards(ch))
    ch = section(doc, "dark-dungeon")
    add("The Perilous Dark", "Dungeon crawl systems", " ".join(notes(ch)), entries=cards(ch))

    return out


def build_ghost(doc: str) -> dict:
    """Ghost Archipelago is a separate ruleset (Heritor + Warden lead a Crew), so
    it is reference-only: no source toggle, nothing hireable."""
    intro = re.search(r'<p class="book-intro">(.*?)</p>', doc, re.S)
    out = {
        "intro": clean(intro.group(1)) if intro else "",
        "sections": [],
    }
    for anchor, title in [
        ("ghost-mechanics", "New core mechanics"),
        ("ghost-abilities", "Heritor Abilities"),
        ("ghost-spells", "Warden branches & spells"),
        ("ghost-crew", "Crew types & gear"),
        ("ghost-treasure", "Treasure"),
        ("ghost-bestiary", "Bestiary"),
        ("ghost-other", "Ships & campaign systems"),
    ]:
        ch = section(doc, anchor)
        entry = {
            "title": title,
            "blurb": " ".join(notes(ch)),
            "entries": cards(ch),
            "rows": [{"name": n, "text": t} for n, t in two_col_rows(ch)],
        }
        # The bestiary uses <details> summaries rather than cards or tables.
        for summary, body in re.findall(
            r"<summary>(.*?)</summary><div class=\"body\">(.*?)</div>", ch, re.S
        ):
            entry["entries"].append({"name": clean(summary), "tag": "", "text": clean(body)})
        if entry["entries"] or entry["rows"]:
            out["sections"].append(entry)
    return out


def main() -> int:
    supplements = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_SUPPLEMENTS
    ghost = Path(sys.argv[2]) if len(sys.argv) > 2 else DEFAULT_GHOST
    for path in (supplements, ghost):
        if not path.is_file():
            print(f"Reference document not found: {path}")
            return 1
    doc = supplements.read_text(encoding="utf-8", errors="replace")
    ghost_doc = ghost.read_text(encoding="utf-8", errors="replace")
    DATA.mkdir(parents=True, exist_ok=True)

    for name, payload in [
        ("magic_items.json", build_magic_items(doc)),
        ("expansion_rules.json", build_expansion_rules(doc)),
        ("ghost_archipelago.json", build_ghost(ghost_doc)),
    ]:
        path = DATA / name
        path.write_text(json.dumps(payload, indent=1, ensure_ascii=False), encoding="utf-8")
        if isinstance(payload, list):
            count = len(payload)
        elif "sections" in payload:
            count = len(payload["sections"])
        else:
            count = sum(len(v) for v in payload.values())
        print(f"wrote {path.relative_to(REPO_ROOT)} ({count} entries, {path.stat().st_size // 1024} KiB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
