"""Load standard items and spell descriptions for UI tooltips/lists."""

from __future__ import annotations

import json
import logging
from functools import lru_cache

import paths

DATA = paths.bundle_dir() / "data"
logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def load_standard_items() -> list[dict]:
    """Full list including armour (kept for later / reference).

    Unlike spells/soldiers/magic items, standard items are deliberately NOT
    filtered by enabled_sources — mundane gear (e.g. Ghost Archipelago's
    Throwing Knife) is available regardless of which source books are
    switched on for a warband. The `source` field here is informational only
    for those. The black-powder firearms and their upgrades (the only
    entries with a `cost`) are the exception: they're real source- and
    purchase-gated items — see warband_store.buy_standard_item() and
    CLAUDE.md — this loader still returns them unfiltered since it also
    backs the unconditional Lexicon reference list."""
    path = DATA / "standard_items.json"
    if not path.is_file():
        return []
    items = json.loads(path.read_text(encoding="utf-8"))
    for it in items:
        it.setdefault("slot_cost", 1)
        it.setdefault("kind", "simple")
        it.setdefault("spellcaster_allowed", True)
        it.setdefault("caster_only", False)
        it.setdefault("source", "Core Rules")
        it.setdefault("issued_only", False)
        it.setdefault("compatible_bases", [])
    return items


def load_spellcaster_items() -> list[dict]:
    """Items shown on wizard/apprentice slots (no armour/shield; unarmed not listed)."""
    return [it for it in load_standard_items() if it.get("spellcaster_allowed", True)]


def load_soldier_capable_items() -> list[dict]:
    """Items shown on captain/soldier slots — the full catalog (armour/shield
    included, unlike load_spellcaster_items()) minus anything marked
    caster_only (the Spell Component Bag: only a wizard or apprentice has
    anywhere to put its contents, so it's meaningless gear for a captain or
    soldier to carry)."""
    return [it for it in load_standard_items() if not it.get("caster_only")]


@lru_cache(maxsize=1)
def load_potion_choices() -> list[str]:
    path = DATA / "potions.json"
    if path.is_file():
        return json.loads(path.read_text(encoding="utf-8"))
    return []


@lru_cache(maxsize=1)
def load_potion_descriptions() -> dict[str, str]:
    path = DATA / "potion_descriptions.json"
    if not path.is_file():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def load_potion_choices_detailed() -> list[dict]:
    """Potions with a derived category label and rules description, for the reference page."""
    descs = load_potion_descriptions()
    out = []
    for name in load_potion_choices():
        kind = name.split(" of ")[0] if " of " in name else name.split()[-1]
        out.append({
            "name": name,
            "kind": kind,
            "description": descs.get(name, "") or "No description available.",
        })
    return out


@lru_cache(maxsize=1)
def load_bestiary() -> list[dict]:
    path = DATA / "bestiary.json"
    if not path.is_file():
        return []
    return json.loads(path.read_text(encoding="utf-8"))


OTHER_CREATURE_ROW = {
    "monster": "Other Creature",
    "rules": "",
    "source": "Other origin",
    "xp": 5,
    "bestiary_name": None,
    "prize": {"name": None, "kind": "none", "target": None, "gold": 0, "known": True},
}


@lru_cache(maxsize=1)
def load_monster_hunting() -> list[dict]:
    """The Master Monster Table (Spellcaster Magazine, Issue 5): per-monster
    XP and harvestable prize, {monster, rules, source, xp, bestiary_name,
    prize: {name, kind, target, gold, known}}. Built from the source PDF by
    scripts/extract_monster_hunting.py — see that script's docstring for why
    the HTML reference other supplement content is extracted from can't be
    used for this table. Prepends OTHER_CREATURE_ROW, a catch-all for a kill
    that isn't actually on the book's table — 5 XP (the table's own lowest
    tier), no prize — kept here rather than in the extracted JSON so the
    extractor never silently drops it."""
    path = DATA / "monster_hunting.json"
    if not path.is_file():
        return [OTHER_CREATURE_ROW]
    return [OTHER_CREATURE_ROW] + json.loads(path.read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def load_traits() -> list[dict]:
    """Creature traits glossary (Undead, Burrowing, Large, ...), {name, text}.
    Transcribed from the Core Rules' "Creature Traits" appendix. Reference
    only — not simulated."""
    path = DATA / "traits.json"
    if not path.is_file():
        return []
    return json.loads(path.read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def load_quick_reference() -> list[dict]:
    """The Core Rules' own Quick Reference appendix (turn sequence, actions,
    combat/shooting/casting procedures, post-game checklist), transcribed
    directly. Reference only — not simulated."""
    path = DATA / "quick_reference.json"
    if not path.is_file():
        return []
    return json.loads(path.read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def load_core_rules() -> list[dict]:
    """Core rulebook content the Quick Reference's cheat-sheet doesn't spell
    out in full: stat-line/equipment rules, warband composition, the
    post-game Survival Roll + Permanent Injury tables, XP/leveling, and
    spending treasure. Deliberately doesn't repeat the Treasure Table (Loot
    tables card) or Base Locations/Resources (already frostgrave_data.BASE_
    LOCATIONS/BASE_RESOURCES, rendered in the Lexicon from that same source
    the app plays from, not a separate transcription). Reference only."""
    path = DATA / "core_rules.json"
    if not path.is_file():
        return []
    return json.loads(path.read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def load_magic_items() -> list[dict]:
    """Supplement treasure, {name, source, effect}. Built by
    scripts/extract_expansion_content.py from the local reference documents."""
    path = DATA / "magic_items.json"
    if not path.is_file():
        return []
    return json.loads(path.read_text(encoding="utf-8"))


def magic_items_for_sources(sources) -> list[dict]:
    """Treasure from the books this warband has switched on."""
    return [it for it in load_magic_items() if it.get("source") in sources]


def group_magic_items(items: list[dict]) -> list[dict]:
    """[{"source": ..., "rows": [...]}] in SOURCE_BOOKS order, for the Lexicon.

    The list is keyed "rows", not "items": in Jinja `group.items` resolves to
    dict.items, the method, so a template would silently get something unusable.
    """
    from frostgrave_data import source_book_order

    groups: dict[str, list[dict]] = {}
    for it in items:
        groups.setdefault(it.get("source", ""), []).append(it)
    return [
        {"source": src, "rows": sorted(rows, key=lambda r: r["name"].lower())}
        for src, rows in sorted(groups.items(), key=lambda kv: source_book_order(kv[0]))
    ]


@lru_cache(maxsize=1)
def load_expansion_rules() -> dict:
    """In-game table rules per source book (traps, demonic attributes, the
    optional Malcor core-rule updates...). Shown, not simulated."""
    path = DATA / "expansion_rules.json"
    if not path.is_file():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def load_grave_mutation_meta() -> dict[int, dict]:
    """Authored per-mutation PDF summary + optional mechanical stat_delta,
    keyed by mutation number. Kept separate from expansion_rules.json's
    verbatim rulebook transcription."""
    path = DATA / "grave_mutation_meta.json"
    if not path.is_file():
        return {}
    raw = json.loads(path.read_text(encoding="utf-8"))
    return {int(k): v for k, v in raw.items()}


@lru_cache(maxsize=1)
def load_grave_mutations() -> list[dict]:
    """The Grave Mutations d1000 table, same hundred/twenty nesting as
    /reference, with each row's "N. Title" split into a real number + bare
    name for the mutation-picker dropdowns."""
    sections = load_expansion_rules().get("Grave Mutations", [])
    out = []
    for sec in sections:
        if "subsections" not in sec:
            continue  # intro prose section, no rows
        subs = []
        for sub in sec["subsections"]:
            rows = []
            for row in sub.get("rows", []):
                name = row.get("name", "")
                number_str, _, bare_name = name.partition(". ")
                try:
                    number = int(number_str)
                except ValueError:
                    continue
                rows.append({"number": number, "name": bare_name, "text": row.get("text", "")})
            subs.append({"label": sub.get("title", ""), "rows": rows})
        out.append({"label": sec.get("title", ""), "subsections": subs})
    return out


@lru_cache(maxsize=1)
def grave_mutations_by_number() -> dict[int, dict]:
    """Every Grave Mutations row keyed by number, merged with its authored
    PDF-summary/stat_delta metadata. Falls back to a truncated version of the
    full text if a number is somehow missing from the meta file."""
    meta = load_grave_mutation_meta()
    out = {}
    for sec in load_grave_mutations():
        for sub in sec["subsections"]:
            for row in sub["rows"]:
                n = row["number"]
                m = meta.get(n) or {}
                fallback_text = row["text"][:80] + "…" if len(row["text"]) > 80 else row["text"]
                short = m.get("short") or f"{row['name']}: {fallback_text}"
                out[n] = {
                    "number": n,
                    "name": row["name"],
                    "text": row["text"],
                    "short": short,
                    "stat_delta": m.get("stat_delta"),
                }
    return out


@lru_cache(maxsize=1)
def load_construct_modification_meta() -> dict[str, dict]:
    """Authored per-modification stat_delta (+ any hard size restriction),
    keyed by modification name. Kept separate from expansion_rules.json's
    verbatim rulebook transcription.

    A stat_delta means "this permanently changes the printed stat line", so
    only an unconditional numeric effect earns one (Armour Plating's "+1
    Armour", Construct Oil's "+1 Move"). Anything qualified by circumstance
    stays text-only, however numeric it looks — a trailing "vs. <target>"
    governs the whole entry, so Projectile Shield's "+2 Armour, +2 Fight vs.
    bow/crossbow/javelin" applies only against projectiles and must not touch
    Armour; likewise "while" clauses (Drillhead's -1 Move while burrowing) and
    per-roll bonuses (Mind Shield's +5 Will vs. mind control). Damage, Survival
    Rolls and casting-roll modifiers are never stat-line stats at all. Same
    convention as Grave Mutations."""
    path = DATA / "construct_modification_meta.json"
    if not path.is_file():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def construct_modifications() -> list[dict]:
    """The Fireheart Construct Modification table, flattened out of
    expansion_rules.json's verbatim transcription for the modification picker:
    each entry as {name, text, no_penalty, stat_delta, disallow_types,
    forces_specialist}. Unlike Grave Mutations these aren't numbered — a
    modification is picked by name, not rolled."""
    meta = load_construct_modification_meta()
    sections = load_expansion_rules().get("Fireheart", [])
    for sec in sections:
        if sec.get("title", "").startswith("Construct Modification"):
            out = []
            for e in sec.get("entries", []):
                m = meta.get(e["name"]) or {}
                out.append({
                    "name": e["name"],
                    "text": e["text"],
                    "no_penalty": "no modification penalty" in e["text"].lower(),
                    "stat_delta": m.get("stat_delta"),
                    "disallow_types": set(m.get("disallow_types") or ()),
                    # Projectile Weapon: "small/medium constructs become
                    # specialist soldiers" — Large is already a specialist in
                    # the catalog, so this only ever matters for those two.
                    "forces_specialist": bool(m.get("forces_specialist")),
                })
            return out
    return []


@lru_cache(maxsize=1)
def load_random_encounters() -> dict:
    """Random encounter tables per source book (core + any supplement with a
    standalone table). Reference only — the app doesn't roll these."""
    path = DATA / "random_encounters.json"
    if not path.is_file():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def load_loot_tables() -> dict:
    """The top-level "roll to see what category of treasure you found" tables
    per source book. Named magic items themselves live in load_magic_items()."""
    path = DATA / "loot_tables.json"
    if not path.is_file():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def load_ghost_archipelago() -> dict:
    """Ghost Archipelago: a separate Osprey ruleset, carried for reference only.
    No source toggle, nothing hireable — see the Lexicon."""
    path = DATA / "ghost_archipelago.json"
    if not path.is_file():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def load_spell_names() -> list[str]:
    try:
        from frostgrave_data import SPELLS

        names = [sp["name"] for _, sps in SPELLS.items() for sp in sps]
        return sorted(set(names), key=str.lower)
    except (ImportError, KeyError) as exc:
        logger.warning("Could not load spell names: %s", exc)
        return []


@lru_cache(maxsize=1)
def load_spell_descriptions() -> dict[str, str]:
    path = DATA / "spell_descriptions.json"
    if not path.is_file():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def enrich_spells_with_descriptions(spells: list[dict]) -> list[dict]:
    """Attach each spell's description text, looked up by name.

    A handful of supplement spells across different books happen to share a
    core spell's name or each other's (e.g. Blood Legacy's "Pyre" and
    Spellcaster Magazine's Rangifer "Pyre" are unrelated effects) — those are
    stored under a "School::Name" compound key instead, checked first here,
    falling back to the plain name lookup every other spell uses.
    """
    descs = load_spell_descriptions()
    out = []
    for sp in spells:
        row = dict(sp)
        name = sp.get("name", "")
        school = sp.get("school", "")
        text = descs.get(f"{school}::{name}") or descs.get(name, "")
        row["description"] = text or "No description available."
        out.append(row)
    return out


def equipment_bonuses(slots: list) -> dict:
    """Sum the Armour/Move bonuses granted by known Armour-category items (Shield,
    Light Armour, Heavy Armour) sitting in these item slots. Matches by exact
    catalog name (case-insensitive), same idiom as item_slot_cost() below."""
    bonus = {"armour": 0, "move": 0}
    for raw in slots or []:
        name = (raw or "").strip().lower()
        if not name:
            continue
        for it in load_standard_items():
            if it["name"].lower() == name:
                bonus["armour"] += int(it.get("armour_bonus", 0))
                bonus["move"] -= int(it.get("move_penalty", 0))
                break
    return bonus


def item_slot_cost(name: str) -> int:
    """How many item slots this equipment uses (default 1)."""
    n = (name or "").strip().lower()
    if not n:
        return 1
    for it in load_standard_items():
        if it["name"].lower() == n:
            return int(it.get("slot_cost", 1))
    # Kept in sync by hand with isTwoHandedName() in static/item_slots.js (B5.5) —
    # that JS does the same detection client-side for instant slot-count feedback
    # before the form posts here.
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
    if v in potions or v.lower().startswith("potion of "):
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
