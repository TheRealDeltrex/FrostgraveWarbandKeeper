"""Load standard items and spell descriptions for UI tooltips/lists."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

DATA = Path(__file__).resolve().parent / "data"


@lru_cache(maxsize=1)
def load_standard_items() -> list[dict]:
    """Full list including armour (kept for later / reference)."""
    path = DATA / "standard_items.json"
    if not path.is_file():
        return []
    items = json.loads(path.read_text(encoding="utf-8"))
    for it in items:
        it.setdefault("slot_cost", 1)
        it.setdefault("kind", "simple")
        it.setdefault("spellcaster_allowed", True)
    return items


def load_spellcaster_items() -> list[dict]:
    """Items shown on wizard/apprentice slots (no armour/shield; unarmed not listed)."""
    return [it for it in load_standard_items() if it.get("spellcaster_allowed", True)]


@lru_cache(maxsize=1)
def load_potion_choices() -> list[str]:
    path = DATA / "potions.json"
    if path.is_file():
        return json.loads(path.read_text(encoding="utf-8"))
    return []


@lru_cache(maxsize=1)
def load_spell_names() -> list[str]:
    try:
        from frostgrave_data import SPELLS

        names = [sp["name"] for _, sps in SPELLS.items() for sp in sps]
        return sorted(set(names), key=str.lower)
    except Exception:
        return []


@lru_cache(maxsize=1)
def load_spell_descriptions() -> dict[str, str]:
    path = DATA / "spell_descriptions.json"
    if not path.is_file():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def spell_description(name: str) -> str:
    return load_spell_descriptions().get(name, "") or "No description available."


def enrich_spells_with_descriptions(spells: list[dict]) -> list[dict]:
    descs = load_spell_descriptions()
    out = []
    for sp in spells:
        row = dict(sp)
        row["description"] = descs.get(sp.get("name", ""), "") or "No description available."
        out.append(row)
    return out


def item_slot_cost(name: str) -> int:
    """How many item slots this equipment uses (default 1)."""
    n = (name or "").strip().lower()
    if not n:
        return 1
    for it in load_standard_items():
        if it["name"].lower() == n:
            return int(it.get("slot_cost", 1))
    if any(k in n for k in ("two-handed", "two handed", "2h ", "2-handed", "2 handed")):
        return 2
    return 1


def parse_item_selection(value: str) -> tuple[str, str]:
    """
    Map a stored slot value to (main_pick, detail_value).
    main_pick is the primary dropdown value (Potion/Scroll/Grimoire/Hand Weapon/...).
    detail_value is potion name or spell name for the secondary dropdown, or '' for free text.
    """
    v = (value or "").strip()
    if not v:
        return "", ""

    # Exact main item (simple arms etc.)
    for it in load_standard_items():
        if it["name"] == v and it.get("kind", "simple") == "simple":
            return v, ""

    potions = load_potion_choices()
    if v in potions or v.lower().startswith("potion of ") or v in {
        "Poison",
        "Explosive Cocktail",
        "Construct Oil",
        "Elixir of Speed",
        "Elixir of the Chameleon",
        "Elixir of Life",
        "Cordial of Clearsight",
        "Cordial of Empowerment",
        "Philtre of Fury",
        "Philtre of Fairy Dust",
        "Bottle of Burrowing",
        "Bottle of Darkness",
        "Bottle of Dreams and Nightmares",
        "Bottle of Null",
        "Ethereal Vacuum",
        "Shatterstar Draught",
        "Shrinking Potion",
    }:
        return "Potion", v

    if v.startswith("Scroll of "):
        return "Scroll", v[len("Scroll of ") :]
    if v == "Scroll":
        return "Scroll", ""

    if v.startswith("Grimoire of "):
        return "Grimoire", v[len("Grimoire of ") :]
    if v == "Grimoire":
        return "Grimoire", ""

    # Known simple name
    for it in load_standard_items():
        if it["name"] == v:
            return v, ""

    # Free-text / vault custom
    return "", v
