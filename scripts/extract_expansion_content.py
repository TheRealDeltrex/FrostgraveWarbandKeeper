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
import os
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

# Documented example only — set FWK_REFERENCE_DIR to point at your own copy of
# these hand-compiled reference docs; they aren't part of the repo.
REFERENCE_DIR = Path(os.environ.get("FWK_REFERENCE_DIR", r"E:/RPG/Tabletop/Frostgrave"))
DEFAULT_SUPPLEMENTS = REFERENCE_DIR / "Frostgrave Expansion Reference.html"
DEFAULT_GHOST = REFERENCE_DIR / "Ghost Archipelago Reference.html"
# Second wave of supplements + the magazine, added in a later pass than the
# above two docs (see build_expansion_rules_2 / build_magic_items_2 / BOOKS_2 /
# SPELLCASTER_ISSUES below) — kept as separate documents/functions rather than
# folded into the originals since their HTML uses different section-id schemes
# per book (no shared "{prefix}-treasure" convention).
DEFAULT_SUPPLEMENTS_2 = REFERENCE_DIR / "Frostgrave Expansion Reference 2.html"
DEFAULT_SPELLCASTER = REFERENCE_DIR / "Spellcaster Magazine Reference.html"
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

# Book ids in Frostgrave Expansion Reference 2.html.
BOOKS_2 = {
    "folio": "The Frostgrave Folio",
    "gravemut": "Grave Mutations",
    "blood": "Blood Legacy",
    "fire": "Fireheart",
    "wild": "The Wildwoods",
}

# Issue ids in Spellcaster Magazine Reference.html -> all fold into one source
# book (the user's call: treat the magazine as a single expansion, not 7 toggles).
SPELLCASTER_BOOK = "Spellcaster Magazine"
SPELLCASTER_ISSUES = ["i1", "i2", "i3", "i4", "i5", "i6", "i7"]


def _card_name(c: dict) -> str:
    """cards() folds a card's price/charge <span class="tag"> straight into
    "name" too (clean() strips the tags but keeps the inner text) — strip that
    trailing tag text back off when a card's <h4> carries one."""
    name = c["name"]
    tag = c.get("tag") or ""
    if tag and name.endswith(tag):
        name = name[: -len(tag)]
    return name.strip()


def build_magic_items_spellcaster(doc: str) -> list[dict]:
    """Treasure/magic items from Spellcaster Magazine Reference.html, all
    folded into the single "Spellcaster Magazine" source book."""
    items: list[dict] = []

    # Issue 1: magic arrows.
    ch = section(doc, "i1-items")
    for c in cards(ch):
        items.append({"name": _card_name(c), "source": SPELLCASTER_BOOK, "effect": c["text"]})

    # Issue 3: rangifer treasure cards + the one-off auction items.
    for anchor in ("i3-rangifer", "i3-auction"):
        ch = section(doc, anchor)
        for c in cards(ch):
            items.append({"name": _card_name(c), "source": SPELLCASTER_BOOK, "effect": c["text"]})

    # Issue 4: frost-giant items + the Potion of Regeneration.
    ch = section(doc, "i4-giants")
    for c in cards(ch):
        items.append({"name": _card_name(c), "source": SPELLCASTER_BOOK, "effect": c["text"]})
    giants_notes = notes(ch)
    if len(giants_notes) > 1:
        items.append(
            {
                "name": "Potion of Regeneration",
                "source": SPELLCASTER_BOOK,
                "effect": (
                    "200gc. Bought and used in contact with a Healing Well: revives a fallen "
                    "warband member, placed adjacent, inactive that turn, with a permanent "
                    "-2 Health penalty (cumulative). Still counts as \"dead\" for the post-game "
                    "survival roll, but that roll may be rerolled once (must keep the second "
                    "result)."
                ),
            }
        )

    return items


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


def numbered_rows(chunk: str) -> list[tuple[str, str]]:
    """Rows of a 3-column <table class="data"> shaped like Grave Mutations'
    d1000 table: '#', name, effect. Returns (name, effect) with the roll number
    folded into the name (e.g. "1. Crystalline Body") so a d1000 lookup table
    keeps its roll order and number when rendered as {name, text} rows."""
    out = []
    for row in re.findall(r"<tr>(.*?)</tr>", chunk, re.S):
        if "<th" in row:
            continue
        cells = [clean(c) for c in re.findall(r"<td[^>]*>(.*?)</td>", row, re.S)]
        if len(cells) != 3:
            continue
        n, name, effect = cells
        out.append((f"{n}. {name}", effect))
    return out


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


def build_expansion_rules_2(doc: str) -> dict:
    """Reference-only rules from Frostgrave Expansion Reference 2.html. Filled in
    incrementally, one book at a time, per the implementation-order plan —
    currently just Grave Mutations, whose entire content is one flat table."""
    out: dict[str, list[dict]] = {book: [] for book in BOOKS_2.values()}

    def add(book: str, title: str, blurb: str = "", rows=None, entries=None):
        payload = {"title": title, "blurb": blurb}
        if rows:
            payload["rows"] = [{"name": n, "text": t} for n, t in rows]
        if entries:
            payload["entries"] = entries
        if payload.get("rows") or payload.get("entries"):
            out[book].append(payload)

    # --- The Frostgrave Folio ---
    # The Captain hireling and the potion tables are hand-authored elsewhere
    # (warband_store.py / data/potions.json — potions.json already covered every
    # Folio potion before this project even started). This just captures the two
    # treasure roll tables and the errata note as reference text.
    ch = section(doc, "folio-magic")
    magic_notes = notes(ch)
    add(
        "The Frostgrave Folio",
        "Hunt for the Golem / Dark Alchemy Treasure Tables",
        "",
        rows=[("Roll tables", magic_notes[-1])] if magic_notes else [],
    )
    ch = section(doc, "folio-base")
    add(
        "The Frostgrave Folio",
        "Errata",
        "",
        rows=[("Errata", notes(ch)[-1])] if notes(ch) else [],
    )

    # --- Blood Legacy ---
    # The Vampire Wizard / Fire Giant Wizard progressions themselves, the
    # Grimoire's fail-tracking, and the High-Level Wizards level buckets are all
    # deferred mechanics (see the implementation plan) — captured here as
    # detailed reference text rather than built as live rules.
    ch = section(doc, "blood-vampires")
    add(
        "Blood Legacy",
        "Vampire Wizard (deferred mechanic — reference only)",
        "",
        rows=[("Creating & running a Vampire", " ".join(notes(ch)))],
    )
    ch = section(doc, "blood-giants")
    add(
        "Blood Legacy",
        "Fire Giant Wizard (deferred mechanic — reference only)",
        "",
        rows=[("Creating & running a Fire Giant Wizard", " ".join(notes(ch)))],
    )
    ch = section(doc, "blood-soldiers")
    giant_blooded_notes = notes(ch)
    add(
        "Blood Legacy",
        "Giant-Blooded (soldier modification — deferred mechanic)",
        "",
        rows=[("Giant-Blooded", giant_blooded_notes[0])] if giant_blooded_notes else [],
    )
    ch = section(doc, "blood-highlevel")
    add(
        "Blood Legacy",
        "High-Level Wizards (deferred mechanic — reference only)",
        "",
        rows=[("Optional rules", " ".join(notes(ch)))],
    )
    ch = section(doc, "blood-warband")
    add(
        "Blood Legacy",
        "Vampire Warband Creation & Play (reference only)",
        "",
        rows=[("NPC vampire warbands", " ".join(notes(ch)))],
    )
    ch = section(doc, "blood-ambush")
    ambush_notes = notes(ch)
    add(
        "Blood Legacy",
        "Ambush Cards (24-card generic deck)",
        ambush_notes[0] if ambush_notes else "",
        entries=cards(ch),
    )
    ch = section(doc, "blood-grimoire")
    add(
        "Blood Legacy",
        "The Grimoire of Fin Dalka (deferred mechanic — reference only)",
        "",
        rows=[("Deciphering the grimoire", " ".join(notes(ch)))],
    )
    ch = section(doc, "blood-bestiary")
    bl_bestiary_notes = notes(ch)
    add(
        "Blood Legacy",
        "New Attributes (Bestiary)",
        "",
        rows=[("New Attributes", bl_bestiary_notes[-1])] if bl_bestiary_notes else [],
    )

    # --- Fireheart ---
    # Construct Modification (the 39-entry table) and Animated Prosthetics are
    # both deferred mechanics (see the implementation plan) — captured as
    # detailed reference text, including the 7 injury-gated Prosthetic Upgrade
    # items (kept as reference rather than real treasure, since the gating
    # mechanic itself isn't built yet).
    ch = section(doc, "fire-animation")
    anim_notes = notes(ch)
    add(
        "Fireheart",
        "Construct Modification (deferred mechanic — reference only)",
        anim_notes[0] if anim_notes else "",
        entries=cards(ch),
        rows=([("Construct Modification rules", anim_notes[1])] if len(anim_notes) > 1 else [])
        + ([("Animated Prosthetics", anim_notes[2])] if len(anim_notes) > 2 else [])
        + two_col_rows(ch)
        + ([("Upgrade rules", anim_notes[3])] if len(anim_notes) > 3 else []),
    )
    ch = section(doc, "fire-terrain")
    terrain_notes = notes(ch)
    add(
        "Fireheart",
        "Interactive Terrain (20 generic hazards — reference only)",
        terrain_notes[0] if terrain_notes else "",
        entries=cards(ch),
        rows=([("Random Creature Type Table", terrain_notes[1])] if len(terrain_notes) > 1 else []),
    )
    ch = section(doc, "fire-bestiary")
    fire_bestiary_notes = notes(ch)
    add(
        "Fireheart",
        "Random Encounter Table & New Traits",
        "",
        rows=[(t, n) for t, n in zip(
            ["Fireheart Random Encounter Table (d20)", "New Traits", "Swarm (generic trait)"],
            fire_bestiary_notes,
        )],
    )

    # --- Grave Mutations ---
    ch = section(doc, "gm-table")
    add(
        "Grave Mutations",
        "The Grave Mutations Table (d1000)",
        " ".join(notes(ch)),
        rows=numbered_rows(ch),
    )

    # --- The Wildwoods ---
    # Environmental/scenario rules with no per-character state (matches how The
    # Perilous Dark's toolkit is stored) — the 11 terrain cards plus 4 longer
    # rules notes (Terrain Effect Bonus Table, Spells in the Wilderness, Water
    # Hazards, Small Boats), kept as separate rows rather than one giant blurb.
    ch = section(doc, "wild-rules")
    rules_notes = notes(ch)
    add(
        "The Wildwoods",
        "Chapter One: Rules of the Wild",
        rules_notes[0] if rules_notes else "",
        entries=cards(ch),
        rows=list(
            zip(
                ["Terrain Effect Bonus Table", "Spells in the Wilderness", "Water Hazards", "Small Boats"],
                rules_notes[1:5],
            )
        ),
    )

    # Supply Points economy + the Cargo Transport unit are deferred mechanics
    # (see the implementation plan) — stored as detailed reference text only.
    ch = section(doc, "wild-supplies")
    supply_notes = notes(ch)
    add(
        "The Wildwoods",
        "Supplies & Cargo Transports (deferred mechanic — reference only)",
        "",
        rows=(
            [("Supply Points (sp)", supply_notes[0])] if len(supply_notes) > 0 else []
        )
        + ([("Cargo Transport", supply_notes[1])] if len(supply_notes) > 1 else [])
        + two_col_rows(ch)
        + ([("Inclement Weather Table", supply_notes[2])] if len(supply_notes) > 2 else []),
    )

    # New traits referenced by the Wildwoods bestiary entries.
    ch = section(doc, "wild-bestiary")
    bestiary_notes = notes(ch)
    add(
        "The Wildwoods",
        "New Traits (Bestiary)",
        bestiary_notes[0] if bestiary_notes else "",
        rows=[("New Traits", bestiary_notes[-1])] if len(bestiary_notes) > 1 else [],
    )

    return out


def build_magic_items_2(doc: str) -> list[dict]:
    """Treasure/magic items from Frostgrave Expansion Reference 2.html. Filled in
    incrementally, one book at a time — empty until a book with new treasure is
    reached (Grave Mutations has none)."""
    items: list[dict] = []

    # --- The Frostgrave Folio ---
    ch = section(doc, "folio-magic")
    for c in cards(ch):
        items.append({"name": c["name"], "source": "The Frostgrave Folio", "effect": c["text"]})

    # --- Blood Legacy ---
    ch = section(doc, "blood-treasure")
    for c in cards(ch):
        items.append({"name": c["name"], "source": "Blood Legacy", "effect": c["text"]})

    # --- Fireheart ---
    ch = section(doc, "fire-treasure")
    for c in cards(ch):
        items.append({"name": c["name"], "source": "Fireheart", "effect": c["text"]})

    # --- The Wildwoods --- (both card-grids under wild-treasure)
    ch = section(doc, "wild-treasure")
    for c in cards(ch):
        items.append({"name": c["name"], "source": "The Wildwoods", "effect": c["text"]})

    return items


def build_expansion_rules_spellcaster(doc: str) -> dict:
    """Frostgrave-relevant reference text from Spellcaster Magazine Reference.html
    (Ghost-Archipelago-only sections go through build_ghost_spellcaster instead).
    Almost everything here is a deferred mechanic per the implementation plan —
    firearms, mounted combat, Knightly Orders, Underworld Favours, the Monster
    Hunting harvest economy, and the 1st-edition Casting Roll Criticals table
    (superseded by the 2nd-edition one, which IS the "live" reference below).
    """
    out: dict[str, list[dict]] = {SPELLCASTER_BOOK: []}

    def add(title: str, blurb: str = "", rows=None, entries=None):
        payload = {"title": title, "blurb": blurb}
        if rows:
            payload["rows"] = [{"name": n, "text": t} for n, t in rows]
        if entries:
            payload["entries"] = entries
        if payload.get("rows") or payload.get("entries"):
            out[SPELLCASTER_BOOK].append(payload)

    # --- Issue 1 ---
    ch = section(doc, "i1-firearms")
    fa_notes = notes(ch)
    add(
        "Black Powder Firearms (Issue 1 — deferred mechanic, reference only)",
        fa_notes[0] if fa_notes else "",
        rows=two_col_rows(ch) + ([("Weather variant", fa_notes[1])] if len(fa_notes) > 1 else []),
    )
    ch = section(doc, "i1-horses")
    horse_notes = notes(ch)
    add(
        "Horses in Frostgrave (Issue 1 — deferred mechanic, reference only)",
        horse_notes[0] if horse_notes else "",
        rows=two_col_rows(ch) + [(f"Note {i + 2}", n) for i, n in enumerate(horse_notes[1:])],
    )
    ch = section(doc, "i1-knights")
    knight_notes = notes(ch)
    add(
        "Knightly Orders (Issue 1 — deferred mechanic, reference only)",
        knight_notes[0] if knight_notes else "",
        rows=two_col_rows(ch) + ([("Custom orders", knight_notes[1])] if len(knight_notes) > 1 else []),
    )
    ch = section(doc, "i1-hazards")
    hz_notes = notes(ch)
    add(
        "Dungeon Hazards (Issue 1 — reusable GM toolkit, reference only)",
        hz_notes[0] if hz_notes else "",
        entries=cards(ch),
    )

    # --- Issue 2 --- (dragon age tiers/Gremolean/Bone Bat are in the bestiary;
    # the Weakness table and the falling ruling are the remaining reference text)
    ch = section(doc, "i2-dragons")
    add("Dragon Weakness Table (Issue 2, roll once)", "", rows=two_col_rows(ch)[-10:])
    ch = section(doc, "i2-rulings")
    ruling = re.search(r'<div class="note-box">(.*?)</div>', ch, re.S)
    add(
        "Rulings (Issue 2)",
        "",
        rows=[("Falling onto stairs or slopes", clean(ruling.group(1)))] if ruling else [],
    )

    # --- Issue 3 ---
    ch = section(doc, "i3-rangifer")
    rf_notes = notes(ch)
    add(
        "Rangifer Shaman (Issue 3 — deferred mechanic, reference only)",
        "",
        rows=(
            [("Rangifer cultural traits & the Shaman", rf_notes[0])] if rf_notes else []
        )
        + ([("Shaman leveling", rf_notes[1])] if len(rf_notes) > 1 else [])
        + ([("Book of the Rangifer", rf_notes[-1])] if len(rf_notes) > 2 else []),
    )
    ch = section(doc, "i3-underworld")
    add(
        "Underworld Favours: A Debt Economy (Issue 3 — deferred mechanic, reference only)",
        "",
        rows=two_col_rows(ch) + [(f"Note {i + 1}", n) for i, n in enumerate(notes(ch))],
    )

    # --- Issue 4 ---
    ch = section(doc, "i4-criticals")
    crit_notes = notes(ch)
    add(
        "Casting Roll Criticals — 1st Edition (Issue 4, superseded by Issue 7's 2E table)",
        crit_notes[0] if crit_notes else "",
    )

    # --- Issue 5 --- Monster Hunting is implemented: the 92-row Master Monster
    # Table lives in data/monster_hunting.json (built from the source PDF by
    # scripts/extract_monster_hunting.py — this HTML reference has the Special
    # column shifted by one row from partway through the table, so it can't be
    # used for that part). The harvesting/component rules below are hand-
    # transcribed from the PDF rather than pulled from `ch`, since this doc's
    # prose for them doesn't match the published wording closely enough to
    # extract programmatically.
    add(
        "Monster Hunting: For Fun and Profit (Issue 5 — implemented)",
        "Assigns an individual XP value to every published Frostgrave monster, replacing the "
        "flat +5 XP from Experience Table II (Maze of Malcor) — this does not replace "
        "scenario-specific XP rewards, which are usually higher. The full 92-row Master "
        "Monster Table lives on the reference page rather than here; this panel covers the "
        "harvesting and component rules it depends on.",
        rows=[
            (
                "Harvesting a kill",
                "If a figure kills a monster, it may immediately claim the listed item as a "
                "free action, so long as it is not in combat with any other figure. If it "
                "doesn't (or can't), the body stays on the table; any figure may claim the "
                "item later by moving into contact and spending an action, so long as it is "
                "not in combat. Once claimed, the item is removed and never takes an item slot.",
            ),
            ("gc-value items", "Items listed with a gc value can be sold for that amount after the game."),
            (
                "Spell and potion components",
                "Items listed with a +1 are spell or potion components. If a spellcaster "
                "attempts to cast a spell (or, using the Frostgrave Folio's optional potion "
                "rules, brew a potion) for which he has a matching component, he may declare "
                "he is using it before the Casting Roll and gains +1 to that roll; a matching "
                "potion component also reduces that potion's component cost by 25gc. A figure "
                "can gain a maximum of one dose of any component per kill, and a maximum of "
                "one component may be used on any single Casting Roll.",
            ),
            (
                "Carrying components",
                "Components picked up during a game never take an item slot. Each spellcaster "
                "has a component pouch that holds three of them for free. A Spell Component "
                "Bag (5gc, purchased after any scenario, 1 item slot) holds up to 10 more in "
                "addition to the pouch. Non-spellcasters may only carry components they "
                "personally pick up during a game.",
            ),
            (
                "Errata (Issue 7)",
                "* Errata (Issue 7, Second Edition): Monstrous Form no longer exists in Second "
                "Edition — the Chilopendra Horn's effect changes to +10gc instead. † Rangifer's "
                "0 XP is intentional (killing one is a detriment, not a reward). Source codes: "
                "FRB=Rulebook, TLL=Thaw of the Lich Lord, IBP=Into the Breeding Pits, "
                "FP=Forgotten Pacts, FF=The Frostgrave Folio, MM=Maze of Malcor, PD=Perilous Dark.",
            ),
        ],
    )

    # --- Issue 7 ---
    ch = section(doc, "i7-outtakes")
    outtake_notes = notes(ch)
    add(
        "The Maze of Malcor Outtakes (Issue 7)",
        outtake_notes[0] if outtake_notes else "",
        entries=cards(ch),
        rows=two_col_rows(ch),
    )
    ch = section(doc, "i7-wyrm")
    wyrm_notes = notes(ch)
    add(
        "The Great Wyrm — AI & the Reveal incantation (Issue 7)",
        wyrm_notes[0] if wyrm_notes else "",
        rows=(
            ([("AI priority (unplayed)", wyrm_notes[1])] if len(wyrm_notes) > 1 else [])
            + ([("Reveal incantation", wyrm_notes[2])] if len(wyrm_notes) > 2 else [])
        ),
    )
    ch = section(doc, "i7-errata")
    add("Second Edition Errata (Issue 7)", "", entries=cards(ch))
    ch = section(doc, "i7-criticals")
    crit2_notes = notes(ch)
    add(
        "Casting Roll Criticals — 2nd Edition (Issue 7, current for 2E play)",
        crit2_notes[0] if crit2_notes else "",
        rows=two_col_rows(ch),
    )

    return out


def build_ghost_spellcaster(doc: str) -> list[dict]:
    """Ghost-Archipelago-only sections from Spellcaster Magazine Reference.html
    (plus the standalone Mech War variant, filed alongside GA content per the
    implementation plan) — appended to ghost_archipelago.json's own sections,
    matching its existing reference-only pattern exactly."""
    sections = []
    for anchor, title in [
        ("i2-traps", "Traps in Ghost Archipelago (Spellcaster Issue 2)"),
        ("i2-mechwar", "Frostgrave Mech War (Spellcaster Issue 2)"),
        ("i3-ulterior", "Ulterior Motives in Ghost Archipelago (Spellcaster Issue 3)"),
        ("i5-heritors", "High-Level Heritors (Spellcaster Issue 5)"),
        ("i5-ulterior", "Ulterior Motives III (Spellcaster Issue 5)"),
        ("i6-tortoises", "Giant Tortoises (Spellcaster Issue 6)"),
        ("i7-ulterior", "Ulterior Motives (Spellcaster Issue 7)"),
    ]:
        ch = section(doc, anchor)
        entry = {
            "title": title,
            "blurb": " ".join(notes(ch)),
            "entries": cards(ch),
            "rows": [{"name": n, "text": t} for n, t in two_col_rows(ch)],
        }
        if entry["entries"] or entry["rows"] or entry["blurb"]:
            sections.append(entry)
    return sections


def main() -> int:
    supplements = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_SUPPLEMENTS
    ghost = Path(sys.argv[2]) if len(sys.argv) > 2 else DEFAULT_GHOST
    supplements_2 = Path(sys.argv[3]) if len(sys.argv) > 3 else DEFAULT_SUPPLEMENTS_2
    spellcaster = Path(sys.argv[4]) if len(sys.argv) > 4 else DEFAULT_SPELLCASTER
    for path in (supplements, ghost, supplements_2, spellcaster):
        if not path.is_file():
            print(f"Reference document not found: {path}")
            return 1
    doc = supplements.read_text(encoding="utf-8", errors="replace")
    ghost_doc = ghost.read_text(encoding="utf-8", errors="replace")
    doc2 = supplements_2.read_text(encoding="utf-8", errors="replace")
    doc3 = spellcaster.read_text(encoding="utf-8", errors="replace")
    DATA.mkdir(parents=True, exist_ok=True)

    merged_rules = {
        **build_expansion_rules(doc),
        **build_expansion_rules_2(doc2),
        **build_expansion_rules_spellcaster(doc3),
    }
    merged_items = (
        build_magic_items(doc) + build_magic_items_2(doc2) + build_magic_items_spellcaster(doc3)
    )
    merged_items.sort(key=lambda it: (it["source"], it["name"].lower()))

    ghost_payload = build_ghost(ghost_doc)
    ghost_payload["sections"].extend(build_ghost_spellcaster(doc3))

    for name, payload in [
        ("magic_items.json", merged_items),
        ("expansion_rules.json", merged_rules),
        ("ghost_archipelago.json", ghost_payload),
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
