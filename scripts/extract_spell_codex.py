"""Extractor: Advanced Spellcraft's Codified Spell List into data/spell_codex.json.

Per core spell: flourishes, notes and Casting Roll Criticals from Advanced
Spellcraft (pp.17-93), with Spellcaster Magazine Issue 7's criticals (printed
pp.38-57) alongside. Where Issue 7 differs only in wording, the entry is stored
once with both books as sources and Advanced Spellcraft's wording; where the
meaning changed (CHANGED_CRITICALS, judged by hand from a word diff) both
versions are kept. The same applies to the spell text itself against the Core
Rules (CHANGED_DESCRIPTIONS).

Writes the whole file; hand edits belong in this script.
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
AS_PDF = REF / "MGT2E - Advanced Spellcraft.pdf"
I7_PDF = REF / "FG - Magazine - Spellcaster - Issue 7.pdf"
OUT = ROOT / "data" / "spell_codex.json"
RULES_OUT = ROOT / "data" / "spellcraft_rules.json"

AS = "Advanced Spellcraft"
SM = "Spellcaster Magazine"

SCHOOLS = (
    "Chronomancer|Elementalist|Enchanter|Illusionist|Necromancer|"
    "Sigilist|Soothsayer|Summoner|Thaumaturge|Witch"
)

# Spells whose critical success/failure changed in meaning between Issue 7 and
# Advanced Spellcraft. Every other spell differs in wording only.
CHANGED_CRITICALS = {
    "Absorb Knowledge", "Animal Companion", "Awareness", "Banish", "Call Storm",
    "Combat Awareness", "Control Demon", "Decay", "Destroy Undead",
    "Elemental Ball", "Elemental Bolt", "Elemental Hammer", "Enchant Armour",
    "Enchant Weapon", "Explosive Rune", "Familiar", "Fast Act", "Furious Quill",
    "Heal", "Illusionary Soldier", "Imp", "Leap", "Mind Control", "Planar Tear",
    "Plane Walk", "Power Word", "Push", "Raise Zombie", "Scatter Shot", "Shield",
    "Steal Health", "Telekinesis", "Wizard Eye",
}

# Spells whose main text changed in meaning against the Core Rules.
CHANGED_DESCRIPTIONS = {"Brew Potion", "Miraculous Cure", "Wizard Eye"}

# Both books print "Stealth Health"; the Core Rules spell is Steal Health.
NAME_FIX = {"Stealth Health": "Steal Health", "Spelleater": "Spell Eater"}

# Each PDF page carries a purchaser line; never let it into data/.
WATERMARK = re.compile(r"This ebook belongs to .*")
# Captions and the watermark use these fonts; rules text never does.
SKIP_FONTS = ("UniversLTStd", "Helvetica")


def _name(raw: str) -> str:
    n = re.sub(r"\s+", " ", raw.replace("T ime", "Time")).strip().replace("'", "’")
    return NAME_FIX.get(n, n)


def _clean(t: str) -> str:
    return re.sub(r"\s+", " ", t.replace("­", "")).strip()


def as_lines(doc) -> list[tuple[int, str, bool]]:
    """(printed page, line, is note-size text). The PDF's page index equals the
    printed page number."""
    out = []
    for pg in range(17, 94):
        for b in doc[pg].get_text("dict")["blocks"]:
            for ln in b.get("lines", []):
                spans = [s for s in ln["spans"] if not s["font"].startswith(SKIP_FONTS)]
                text = "".join(s["text"] for s in spans)
                if not text.strip() or WATERMARK.search(text):
                    continue
                small = all(round(s["size"]) == 9 for s in spans if s["text"].strip())
                out.append((pg, text.rstrip(), small))
    return out


def parse_as(doc) -> tuple[dict, list]:
    header = re.compile(rf"^\s*({SCHOOLS})\s*/\s*(\d+)\s*/\s*(.+?)\s*$")
    spells: dict[str, dict] = {}
    boxes: list[dict] = []
    cur = None
    sec = "body"
    lines = as_lines(doc)
    for i, (pg, ln, small) in enumerate(lines):
        if header.match(ln):
            name = _name(lines[i - 1][1])
            if sec == "BOX":
                boxes[-1]["lines"].pop()  # the name line of this spell
            elif cur is not None:
                cur[sec].pop()
            # The book prints Invisibility twice (pp.61-62); keep the complete copy.
            cur = {"page": pg, "body": [], "FLOURISH": [], "CRITICAL": [], "NOTES": [], "BOX": []}
            spells[name] = cur
            sec = "body"
            continue
        if cur is None:
            continue
        s = ln.strip()
        if s in ("FLOURISH", "CRITICAL", "NOTES"):
            sec = s
            continue
        if re.fullmatch(r"\d{1,3}", s):
            continue
        if s == "CONTROL SPELLS":
            boxes.append({"title": "Control Spells", "page": pg, "lines": []})
            sec = "BOX"
            continue
        if sec == "BOX":
            boxes[-1]["lines"].append(ln)
            continue
        if sec == "CRITICAL" and small:
            sec = "NOTES"  # NOTES heading missing on a few pages; note text is 9pt
        cur[sec].append(ln)
    for box in boxes:
        box["text"] = _clean("\n".join(box.pop("lines")))
    return spells, boxes


def bullets(lines: list[str]) -> list[str]:
    parts = re.split(r"\s*[•�]\s*", "\n".join(lines))
    return [_clean(p) for p in parts if p.strip()]


def i7_criticals(doc) -> dict[str, dict]:
    def fix(t: str) -> str:
        for lig, rep in (("ﬁ ", "fi"), ("ﬂ ", "fl"), ("ﬀ ", "ff"), ("ﬁ", "fi"), ("ﬂ", "fl"), ("ﬀ", "ff")):
            t = t.replace(lig, rep)
        # The "Th" ligature extracts as "T" plus a space.
        return re.sub(r"\bT (?=[a-z])", "Th", t)

    res: dict[str, dict] = {}
    cur = key = None
    for idx in range(39, 59):
        lines = fix(doc[idx].get_text()).split("\n")[2:]  # running head, page no.
        for ln in lines:
            ln = ln.strip()
            if ln.startswith("Acknowledgements"):
                cur = None
                continue
            m = re.match(r"Critical (Success|Failure):\s*(.*)", ln)
            if m and cur:
                key = "success" if m.group(1) == "Success" else "failure"
                res[cur][key] = m.group(2)
            elif cur and key and ln and not _looks_like_name(ln):
                res[cur][key] += " " + ln
            elif _looks_like_name(ln):
                cur = _name(ln)
                res[cur] = {"page": idx - 1, "success": "", "failure": ""}
                key = None
    for v in res.values():
        v["success"], v["failure"] = _clean(v["success"]), _clean(v["failure"])
    return res


_KNOWN: set[str] = set()


def _looks_like_name(ln: str) -> bool:
    return _name(ln) in _KNOWN


def core_descriptions() -> dict[str, str]:
    return json.loads((ROOT / "data" / "spell_descriptions.json").read_text(encoding="utf-8"))


# Chapter One's optional rules (pp.9-15), as (id, printed heading).
OPTIONAL_RULES = [
    ("blaze_of_glory", "BLAZE OF GLORY"),
    ("casting_roll_criticals", "CASTING ROLL CRITICALS"),
    ("draining_magical_items", "DRAINING MAGICAL ITEMS"),
    ("flourishes", "FLOURISHES"),
    ("holding_a_spell", "HOLDING A SPELL"),
    ("no_market_for_created_items", "NO MARKET FOR CREATED ITEMS"),
    ("out_of_game_empowering", "OUT OF GAME EMPOWERING"),
    ("out_of_game_spellcasting_limits", "OUT OF GAME SPELLCASTING LIMITS"),
    ("forgetting_spells", "FORGETTING SPELLS"),
]


def optional_rules(doc) -> list[dict]:
    """Each rule's full text with its page; headings may wrap onto two lines."""
    lines: list[tuple[int, str]] = []
    for pg in range(9, 16):
        for b in doc[pg].get_text("dict")["blocks"]:
            for ln in b.get("lines", []):
                spans = [sp for sp in ln["spans"] if not sp["font"].startswith(SKIP_FONTS)]
                s = "".join(sp["text"] for sp in spans).strip()
                if s and not WATERMARK.search(s) and s != str(pg):
                    lines.append((pg, s))
    text_at: list[tuple[int, str]] = []
    i = 0
    while i < len(lines):
        pg, s = lines[i]
        joined = s if i + 1 >= len(lines) else f"{s} {lines[i + 1][1]}"
        hit = next((h for _, h in OPTIONAL_RULES if s == h), None)
        if hit is None:
            hit = next((h for _, h in OPTIONAL_RULES if joined == h), None)
            if hit:
                i += 1
        text_at.append((pg, "\x00" + hit) if hit else (pg, s))
        i += 1
    out, cur = [], None
    for pg, s in text_at:
        if s.startswith("\x00"):
            rid = next(r for r, h in OPTIONAL_RULES if h == s[1:])
            cur = {"id": rid, "title": s[1:].title().replace(" Of ", " of ").replace(" A ", " a ")
                   .replace(" For ", " for "), "page": pg, "lines": []}
            out.append(cur)
        elif cur:
            cur["lines"].append(s)
    for r in out:
        r["text"] = _clean(" ".join(r.pop("lines")))
    if [r["id"] for r in out] != [r for r, _ in OPTIONAL_RULES]:
        sys.exit(f"optional rules parse problem: {[r['id'] for r in out]}")
    return out


def main() -> None:
    as_doc = fitz.open(str(AS_PDF))
    rules = optional_rules(as_doc)
    RULES_OUT.write_text(json.dumps(rules, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    spells, boxes = parse_as(as_doc)
    _KNOWN.update(spells)
    i7 = i7_criticals(fitz.open(str(I7_PDF)))
    missing = sorted(set(spells) - set(i7))
    if len(spells) != 80 or missing:
        sys.exit(f"parse problem: {len(spells)} spells, no Issue 7 entry for {missing}")

    core = core_descriptions()
    out: dict[str, dict] = {}
    for name, sp in sorted(spells.items()):
        crit = bullets(sp["CRITICAL"])
        cs = next(c.split(":", 1)[1].strip() for c in crit if c.startswith("Critical Success"))
        cf = next(c.split(":", 1)[1].strip() for c in crit if c.startswith("Critical Failure"))
        page = f"p.{sp['page']}"
        old = i7[name]
        old_page = f"Issue 7, p.{old['page']}"
        if name in CHANGED_CRITICALS:
            criticals = [
                {"sources": [AS], "pages": {AS: page}, "success": cs, "failure": cf},
                {
                    "sources": [SM], "pages": {SM: old_page},
                    "success": old["success"], "failure": old["failure"],
                },
            ]
        else:
            pages = {SM: old_page, AS: page}
            criticals = [{"sources": [SM, AS], "pages": pages, "success": cs, "failure": cf}]
        flourishes = []
        for f in bullets(sp["FLOURISH"]):
            m = re.match(r"(.+?)\s*\(([-+]\d+)\):\s*(.*)", f)
            if not m:
                sys.exit(f"flourish parse problem in {name}: {f!r}")
            flourishes.append({"name": m.group(1), "modifier": int(m.group(2)), "text": m.group(3)})
        entry = {
            "page": sp["page"],
            "criticals": criticals,
            "flourishes": flourishes,
            "notes": [_clean("\n".join(sp["NOTES"]))] if sp["NOTES"] else [],
        }
        core_key = name.replace("’", "'")
        if name in CHANGED_DESCRIPTIONS:
            text = _clean("\n".join(sp["body"]))
            entry["description"] = {"sources": [AS], "pages": {AS: page}, "text": text}
        elif core_key in core or name in core:
            entry["description_sources"] = ["Core Rules", AS]
        out[name] = entry
    for box in boxes:
        names = [n for n in out if n.startswith("Control ") or n == "Mind Control"]
        for n in names:
            out[n].setdefault("boxes", []).append(dict(box))
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"wrote {len(out)} spells to {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
