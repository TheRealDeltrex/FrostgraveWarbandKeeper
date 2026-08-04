"""One-off extractor: the Master Monster Table from Spellcaster Magazine Issue 5
("Monster Hunting: For Fun and Profit").

Unlike the other supplement content (extract_expansion_content.py), this table
cannot be read from the hand-compiled "Spellcaster Magazine Reference.html" —
that document's Special-item column is shifted by one row against the Monster
column starting at the Ballista II/Banshee row, and seven Exp. Points values
are dropped outright. It was evidently transcribed as two independent lists
rather than extracted, so this script reads the original PDF instead, where
the table is a well-formed 4-column grid (Monster | Rules | Exp. Points |
Special) that PyMuPDF pulls out cleanly.

Writes:
    data/monster_hunting.json   the 92-row Master Monster Table

Usage:
    python scripts/extract_monster_hunting.py [ISSUE_5_PDF]
"""

from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

import fitz  # noqa: E402  (PyMuPDF)

from frostgrave_data import SPELLS  # noqa: E402
from game_content import load_bestiary, load_potion_choices  # noqa: E402

REFERENCE_DIR = Path(os.environ.get("FWK_REFERENCE_DIR", r"E:/RPG/Tabletop/Frostgrave"))
DEFAULT_PDF = REFERENCE_DIR / "FG - Magazine - Spellcaster - Issue 5.pdf"
DATA = REPO_ROOT / "data"

# Table spans PDF pages 17-20 (0-indexed 16-19) in this printing.
TABLE_PAGES = (16, 17, 18, 19)

# Two-or-three-letter source code -> the book name SOURCE_BOOKS/enabled_sources
# use. FRB is the core rulebook, always on, so it maps to "Core Rules" rather
# than one of the toggleable supplements.
CODE_TO_SOURCE = {
    "FRB": "Core Rules",
    "TLL": "Thaw of the Lich Lord",
    "IBP": "Into the Breeding Pits",
    "FP": "Forgotten Pacts",
    "FF": "The Frostgrave Folio",
    "MM": "The Maze of Malcor",
    "PD": "The Perilous Dark",
}

# The article's own printing errors — verified against the surrounding prose
# and against the bestiary/spell data these targets are supposed to point at.
SPECIAL_FIXES = {
    ("Two-Headed Troll", "Troll fur. +1 Strengh"): "Troll fur. +1 Strength",
    ("Vampire", "Vampire fangs. +1 Stealth Health"): "Vampire fangs. +1 Steal Health",
    ("White Gorilla", "Gorillia fur. +1 Control Animal"): "Gorilla fur. +1 Control Animal",
    ("Sewer Slime", "Sewer slime slime. +1 Construct Oil"): "Sewer slime. +1 Construct Oil",
    ("Bloodwave", "Waveblood. Heal +1"): "Waveblood. +1 Heal",
    # Issue 7, Second Edition errata (data/expansion_rules.json's "Second
    # Edition Errata (Issue 7)" section): Monstrous Form no longer exists in
    # 2E, so the Chilopendra Horn's effect changes to a flat gc value instead.
    ("Chilopendra", "Chilopendra horn. +1 Monstrous Form"): "Chilopendra horn. +10gc",
}

# Magazine spelling -> this app's bestiary.json name. Verified against the
# source PDFs (Maze of Malcor, Into the Breeding Pits, Perilous Dark, The
# Frostgrave Folio, Forgotten Pacts) that these are the *same* creature under
# a longer/shorter name, not a missing entry.
BESTIARY_ALIASES = {
    "Cronohound": "Chronohound",
    "Ambronax": "Ambronnax, Endower of Senescence",
    "Fireflinger": "Fire-Flinger",
    "Alchemical Monstrosity": "The Alchemical Monstrosity",
    "Balkren": "Balkren, Barbarian Summoner",
    "Ghoul King": "The Ghoul King",
    "Kornovik": "Kornovik, Barbarian Outcast",
    "Lourrent": "Lourrent, Vampiric Chronomancer",
    "Wraith of Malcor": "The Wraith of Malcor",
    "Alentha Lemedes": "Alentha Lemedes, Spiritualist (Wizard Shade)",
    "Florissa Undine": "Florissa Undine, Sonancer (Wizard Shade)",
    "Kalish Kareen": "Kalish Kareen, Distortionist (Wizard Shade)",
    "Ordovacer Nords": "Ordovacer Nords, Fatecaster (Wizard Shade)",
    "Tuvith Reginold": "Tuvith Reginold, Astromancer (Wizard Shade)",
    "Vapour Snake (small)": "Vapour Snake (small)",
    "Vapour Snake Large": "Vapour Snake (large)",
    # "Gnoll" is deliberately NOT aliased: Into the Breeding Pits (p.71) states
    # standard gnoll troop types share their corresponding human soldier's
    # stats — there is no unique "Gnoll" stat block to point at, only Gnoll
    # Chieftain/Shaman, which are a different (higher) creature. Left
    # unresolved (bestiary_name: null) rather than invented.
}

SKIP_LINES = {
    "Monster Hunting",
    "Master Monster Table",
    "Monster",
    "Rules",
    "Exp. Points",
    "Special",
    "Spellcaster: The Frostgrave Magazine Issue 5",
}
STOP_LINE = "Spell and Potion Components"
CODE_RE = re.compile(r"^(FRB|TLL|IBP|FP|FF|MM|PD)\s?\d*$")
PAGENUM_RE = re.compile(r"\s+\d{1,3}$")
GOLD_RE = re.compile(r"\+(\d+)gc", re.IGNORECASE)
COMPONENT_RE = re.compile(r"\+1\s+(.+)$")


def _extract_lines(pdf_path: Path) -> list[str]:
    doc = fitz.open(pdf_path)
    lines: list[str] = []
    for page_index in TABLE_PAGES:
        stopped = False
        for raw in doc[page_index].get_text().split("\n"):
            ln = raw.strip()
            if not ln or ln in SKIP_LINES:
                continue
            if ln == STOP_LINE:
                stopped = True
                break
            lines.append(ln)
        if stopped:
            break
    return lines


def _parse_rows(lines: list[str]) -> list[tuple[str, str, int, str]]:
    """(monster, rules_code, xp, special_text) — see module docstring for why
    this reads the PDF's line stream positionally rather than via a table
    parser: PyMuPDF has no column/cell awareness, only a flat reading order,
    but that order is exactly Monster, Rules, Exp.Points, Special, repeated."""
    starts = [
        i
        for i in range(len(lines) - 1)
        if CODE_RE.match(lines[i]) and re.fullmatch(r"\d+", lines[i + 1])
    ]
    rows = []
    for k, i in enumerate(starts):
        name = lines[i - 1]
        end = starts[k + 1] - 1 if k + 1 < len(starts) else len(lines)
        special = " ".join(lines[i + 2 : end]).strip()
        # A running-header page number occasionally bleeds onto the end of a
        # "None" entry (the last text on that PDF page before the next one
        # starts) — strip a lone trailing 1-3 digit number.
        special = PAGENUM_RE.sub("", special)
        rows.append((name, lines[i].replace(" ", ""), int(lines[i + 1]), special))
    return rows


def _classify_prize(monster: str, special: str, known_spells: set, known_potions: set) -> dict:
    special = SPECIAL_FIXES.get((monster, special), special)
    if special.strip().rstrip(".").lower() == "none":
        return {"name": None, "kind": "none", "target": None, "gold": 0, "known": True}

    # "<item name>. <effect>" — the item name is everything before the first
    # period; the effect is a gc bonus or a +1 component target.
    item_name, _, effect = special.partition(".")
    item_name = item_name.strip()
    effect = effect.strip().rstrip(".")

    gold_match = GOLD_RE.search(effect)
    if gold_match:
        return {
            "name": item_name,
            "kind": "gold",
            "target": None,
            "gold": int(gold_match.group(1)),
            "known": True,
        }

    comp_match = COMPONENT_RE.search(effect)
    if comp_match:
        target = comp_match.group(1).strip().rstrip(".")
        if target in known_spells:
            kind = "spell"
        elif target in known_potions:
            kind = "potion"
        else:
            kind = "spell"  # most unmatched targets are 1E-only spells
        return {
            "name": item_name,
            "kind": kind,
            "target": target,
            "gold": 0,
            "known": target in known_spells or target in known_potions,
        }

    # Shouldn't happen given the table's format, but fail soft rather than
    # dropping a row silently.
    return {"name": item_name or None, "kind": "none", "target": None, "gold": 0, "known": True}


def build_monster_hunting(pdf_path: Path) -> list[dict]:
    lines = _extract_lines(pdf_path)
    raw_rows = _parse_rows(lines)
    assert len(raw_rows) == 92, f"expected 92 Master Monster Table rows, parsed {len(raw_rows)}"

    known_spells = {s["name"] for spells in SPELLS.values() for s in spells}
    known_potions = set(load_potion_choices())
    bestiary_names = {c["name"] for c in load_bestiary()}

    out = []
    for monster, code, xp, special in raw_rows:
        code_prefix = re.match(r"[A-Z]+", code).group(0)
        source = CODE_TO_SOURCE.get(code_prefix, "Spellcaster Magazine")
        bestiary_name = BESTIARY_ALIASES.get(monster, monster)
        if bestiary_name not in bestiary_names:
            bestiary_name = None
        prize = _classify_prize(monster, special, known_spells, known_potions)
        out.append(
            {
                "monster": monster,
                "rules": code,
                "source": source,
                "xp": xp,
                "bestiary_name": bestiary_name,
                "prize": prize,
            }
        )
    return out


def main() -> None:
    pdf_path = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_PDF
    if not pdf_path.is_file():
        print(f"Reference PDF not found: {pdf_path}", file=sys.stderr)
        print("Set FWK_REFERENCE_DIR or pass the path explicitly.", file=sys.stderr)
        sys.exit(1)

    rows = build_monster_hunting(pdf_path)
    out_path = DATA / "monster_hunting.json"
    out_path.write_text(json.dumps(rows, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")

    unresolved_bestiary = [r["monster"] for r in rows if r["bestiary_name"] is None]
    unresolved_targets = [
        f"{r['monster']}: {r['prize']['target']}"
        for r in rows
        if r["prize"]["kind"] in ("spell", "potion") and not r["prize"]["known"]
    ]
    print(f"Wrote {len(rows)} rows to {out_path}")
    print(f"{len(unresolved_bestiary)} monsters have no bestiary match: {unresolved_bestiary}")
    print(f"{len(unresolved_targets)} components target an unknown spell/potion (kept as 1E-only):")
    for t in unresolved_targets:
        print(f"  {t}")


if __name__ == "__main__":
    main()
