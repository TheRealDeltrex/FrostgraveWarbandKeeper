"""Load / save Frostgrave warbands, portraits, leveling, loot."""

from __future__ import annotations

import json
import logging
import math
import os
import random
import re
import shutil
import uuid
from collections.abc import Callable, Iterable
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, TypedDict

import expansions
import paths
from frostgrave_data import (
    ALIGNED_SCHOOL_SPELLS,
    APPRENTICE_BASE,
    APPRENTICE_COST,
    APPRENTICE_ITEM_SLOTS,
    BASE_LOCATIONS,
    BASE_RESOURCES,
    CAPTAIN_BASE,
    CAPTAIN_HIRING_COST,
    CAPTAIN_ITEM_SLOTS,
    CAPTAIN_MAX_LEVEL,
    CAPTAIN_MIND_CONTROL_DEFAULT,
    CAPTAIN_MIND_CONTROL_OPTIONS,
    CAPTAIN_MODE_DEFAULT,
    CAPTAIN_MODE_OPTIONS,
    CAPTAIN_STARTING_TRICKS,
    CAPTAIN_STAT_ABSOLUTE_LIMITS,
    CAPTAIN_STAT_CAPS,
    CAPTAIN_TRICK_BY_ID,
    CAPTAIN_TRICK_IDS,
    CAPTAIN_TRICKS,
    FIRE_GIANT_WIZARD_BASE,
    GIANT_BLOODED_COST,
    GIANT_BLOODED_STAT_DELTA,
    VAMPIRE_MIN_MAX_SOLDIERS,
    KNIGHTLY_ORDER_BY_ID,
    KNIGHTLY_ORDER_ELIGIBLE,
    KNIGHTLY_ORDER_IDS,
    LEVELUP_STATS,
    MAX_SOLDIERS,
    MAX_SPECIALISTS,
    MAX_WIZARD_LEVEL,
    OWN_SCHOOL_SPELLS,
    PENTANGLE_SCHOOLS,
    PERMANENT_INJURY_BY_ID,
    PROMOTE_CAPTAIN_BONUS,
    PROMOTE_CAPTAIN_COST,
    PROMOTE_CAPTAIN_ITEM_SLOTS,
    PROMOTE_CAPTAIN_TRICKS,
    SCHOOL_RELATIONS,
    SCHOOLS,
    SOLDIER_MAX_LEVELS,
    SOLDIER_STAT_CAPS,
    SOLDIERS,
    SOURCE_BOOK_BY_SLUG,
    SOURCE_BOOKS,
    STANDARD_CONSTRUCT_TYPE_KEYS,
    STARTING_GOLD,
    STARTING_SPELL_COUNT,
    TEMPORARY_MEMBER_LIMIT,
    WIZARD_BASE,
    WIZARD_ITEM_SLOTS,
    WIZARD_MIN_CASTING_NUMBER_DEFAULT,
    WIZARD_STAT_LIMITS_DEFAULT,
    XP_PER_LEVEL,
    animal_companion_type_keys,
    bonus_choice_amount,
    cn_penalty,
    construct_type_keys,
    find_spell,
    get_soldier,
    giant_blooded_eligible_type_keys,
    illusion_source_choices,
    level_from_xp,
    school_relation,
    xp_to_next_level,
)
from game_content import construct_modifications, equipment_bonuses, grave_mutations_by_number

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    # Only used for type hints — this module otherwise stays framework-
    # agnostic (it just duck-types "has .filename / .save()" / "has .get()").
    from werkzeug.datastructures import FileStorage, ImmutableMultiDict


class Warband(TypedDict, total=False):
    """Shape of the dict built by create_warband() (E3). total=False since
    every key is optional in principle — old files pre-migration, or a dict
    mid-construction, may be missing some. Sub-entities (wizard/apprentice/
    captain/soldier/vault item/base) aren't broken out into their own
    TypedDicts — the value here is documenting the warband's top-level shape
    for IDE support, not chasing full static coverage."""

    id: str
    schema_version: int
    name: str
    created: str
    updated: str
    gold: int
    notes: str
    wizard: dict
    apprentice: dict | None
    captain: dict | None
    homerules: dict
    soldiers: list[dict]
    vault_items: list[dict]
    base: dict
    history: list[dict]


def warband_dir() -> Path:
    """Writable warbands folder — resolved (and created) fresh on every call
    rather than once at import time (B4), so changing the data folder under
    /settings takes effect without an app restart, and importing this module
    has no filesystem side effects (handy for scripts/tests)."""
    d = paths.user_data_dir() / "warbands"
    d.mkdir(parents=True, exist_ok=True)
    return d


def portraits_root_dir() -> Path:
    """Writable portraits folder — same lazy-resolution reasoning as warband_dir()."""
    d = paths.user_data_dir() / "portraits"
    d.mkdir(parents=True, exist_ok=True)
    return d

ALLOWED_IMAGE_EXT = {".jpg", ".jpeg", ".png", ".gif", ".webp"}

# Artwork shipped with the app, shown for anyone who hasn't uploaded their own
# picture. Named after what it depicts — "wizard", "apprentice", or a soldier
# type_key — see scripts/build_default_portraits.py.
DEFAULT_PORTRAIT_DIR = paths.bundle_dir() / "static" / "portraits"


def default_portrait_name(kind: str, type_key: str | None = None) -> str | None:
    """Filename under static/portraits/ for a character with no custom picture,
    or None if nothing suitable ships with the app."""
    if kind == "soldier":
        stems = [type_key]
    elif kind == "captain":
        # A promoted captain keeps the look of the soldier they were promoted
        # from; a hired one falls back to the generic captain artwork.
        stems = [type_key, "captain"]
    else:
        stems = [kind]
    for stem in stems:
        if not stem:
            continue
        name = f"{stem}.png"
        if (DEFAULT_PORTRAIT_DIR / name).is_file():
            return name
    return None


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _slug(name: str) -> str:
    s = re.sub(r"[^a-zA-Z0-9]+", "-", (name or "warband").strip().lower()).strip("-")
    return s[:40] or "warband"


def new_warband_id(name: str) -> str:
    return f"{_slug(name)}-{uuid.uuid4().hex[:8]}"


def empty_slots(n: int) -> list[str]:
    return [""] * n


def _default_item_slots(defaults: list[str], n: int) -> list[str]:
    """`defaults` filled into the first slots, padded with blanks to length n
    (or truncated if there are more defaults than slots)."""
    slots = list(defaults[:n])
    slots += [""] * (n - len(slots))
    return slots


# Starting gear for a freshly created wizard/apprentice/hired captain. Still
# fully editable afterward via the normal item-slot inputs.
WIZARD_DEFAULT_GEAR = ["Staff", "Hand Weapon"]
CAPTAIN_DEFAULT_GEAR = ["Light Armour", "Shield", "Hand Weapon", "Crossbow", "Quiver"]


def empty_base() -> dict:
    return {
        "location": "laboratory",  # key in BASE_LOCATIONS — still changeable any time
        "resources": [],  # list of BASE_RESOURCES keys
        "notes": "",
    }


def normalize_item_slots(raw: Iterable[str], n: int) -> list[str]:
    """Convert legacy item formats into a fixed-length list of slot strings."""
    slots: list[str] = []
    if isinstance(raw, list):
        for entry in raw:
            if isinstance(entry, dict):
                slots.append(str(entry.get("name") or "").strip())
            else:
                slots.append(str(entry or "").strip())
    elif isinstance(raw, str):
        slots = [line.strip() for line in raw.splitlines() if line.strip()]
    # pad / trim
    if len(slots) < n:
        slots.extend([""] * (n - len(slots)))
    return slots[:n]


def empty_wizard(name: str = "", school: str = "Elementalist") -> dict:
    stats = deepcopy(FIRE_GIANT_WIZARD_BASE if school == "Fire Giant" else WIZARD_BASE)
    return {
        "name": name,
        "school": school,
        "level": 0,
        "xp": 0,
        "stats": stats,
        "item_slots": _default_item_slots(WIZARD_DEFAULT_GEAR, WIZARD_ITEM_SLOTS),
        "has_dagger": True,  # free slot (2e: first dagger takes no slot), so on by default
        "spells": [],
        "mutations": [],
        "permanent_injuries": [],
        "notes": "",
        "portrait": None,
        "level_history": [],
        # Lich / Beastcrafter / pact-holder. See expansions.py.
        "state": expansions.default_wizard_state(),
    }


def empty_apprentice(name: str = "") -> dict:
    stats = deepcopy(APPRENTICE_BASE)
    return {
        "name": name,
        "level": 0,
        "stats": stats,
        "item_slots": _default_item_slots(WIZARD_DEFAULT_GEAR, APPRENTICE_ITEM_SLOTS),
        "has_dagger": True,
        "mutations": [],
        "permanent_injuries": [],
        "notes": "",
        "portrait": None,
    }


def default_homerules() -> dict:
    """Optional house rules, off by default. See frostgrave_data.CAPTAIN_* etc. for context."""
    return {
        # Roster caps, settable at creation for a group that wants a bigger
        # (or smaller) warband than the 2e default — see expansions.max_soldiers/
        # max_specialists, which add their usual bonuses (Chilopendra Soldier,
        # Increased Specialist Soldier Allowance) on top of these.
        "max_soldiers": MAX_SOLDIERS,
        "max_specialists": MAX_SPECIALISTS,
        "captain_mode": CAPTAIN_MODE_DEFAULT,  # "off" | "hire" | "promote" | "both"
        "captain_hiring_cost": CAPTAIN_HIRING_COST,
        "captain_item_slots": CAPTAIN_ITEM_SLOTS,
        "captain_base_stats": deepcopy(CAPTAIN_BASE),
        "captain_bonus_choice_enabled": True,
        "captain_stat_caps": deepcopy(CAPTAIN_STAT_CAPS),
        "captain_stat_absolute_limits": deepcopy(CAPTAIN_STAT_ABSOLUTE_LIMITS),
        "captain_max_level": CAPTAIN_MAX_LEVEL,
        "captain_mind_control": CAPTAIN_MIND_CONTROL_DEFAULT,
        "captain_starting_tricks": CAPTAIN_STARTING_TRICKS,
        "soldier_leveling_enabled": False,
        # Whether summoned animal companions / constructs may level up when
        # Soldier Leveling is on. Off by default — a group opts summons in
        # rather than out.
        "soldier_leveling_animal_companions": False,
        "soldier_leveling_constructs": False,
        # Off by default: the Permanent Injury Table (page 77) is written for
        # the wizard/apprentice/captain's Survival Roll. Soldiers instead die
        # or are dismissed on a failed roll — a group that wants ordinary
        # soldiers to shrug off a Survival Roll with a lasting injury instead
        # ticks this on.
        "soldier_permanent_injuries_enabled": False,
        "soldier_max_levels": SOLDIER_MAX_LEVELS,
        "soldier_stat_caps": deepcopy(SOLDIER_STAT_CAPS),
        "promote_captain_cost": PROMOTE_CAPTAIN_COST,
        "promote_captain_bonus": deepcopy(PROMOTE_CAPTAIN_BONUS),
        "promote_captain_bonus_choice_enabled": True,
        "promote_captain_item_slots": PROMOTE_CAPTAIN_ITEM_SLOTS,
        "promote_captain_tricks": PROMOTE_CAPTAIN_TRICKS,
        # Off by default: restricts promote_soldier_to_captain to soldiers
        # already counted as specialists (see _soldier_is_specialist) — a
        # group that wants "only your best troops make Captain" ticks this on.
        "promote_captain_specialist_only": False,
        # Per-source-book content toggles (soldiers/creatures/rules from the
        # supplements). On by default — most groups play with everything
        # available rather than opting in book by book.
        "enabled_sources": {book: True for book in SOURCE_BOOKS},
        # The Maze of Malcor says the Pentangle schools are scroll-only, then
        # gives rules for playing them properly "if a group agrees". Off by
        # default; needs The Maze of Malcor switched on to have any effect.
        "pentangle_schools_playable": False,
        # Blood Legacy's Fire Giant Wizard (Chapter Three) — the book frames
        # it as a build for very hard/large encounters rather than balanced
        # campaign play, so it's opt-in like Pentangle. Off by default; needs
        # Blood Legacy switched on to have any effect. Only affects newly
        # created warbands — see playable_schools()/create_warband().
        "fire_giant_wizard_playable": False,
        # Blood Legacy's Vampire Wizard (Chapter Three) — the book frames it
        # as a GM/NPC villain build "or PC by group agreement", so it's
        # opt-in the same way. Off by default; needs Blood Legacy switched
        # on to have any effect. Only affects newly created warbands.
        "vampire_wizard_playable": False,
        # Blood Legacy's Giant-Blooded soldier modification (Chapter Three):
        # one soldier per warband may take it (+50gc, -1 Move, -2 Will,
        # +2 Health, Giant-Blooded trait). Off by default; needs Blood Legacy
        # switched on to have any effect. See giant_blooded_eligible_type_keys()
        # and set_soldier_giant_blooded() below.
        "giant_blooded_enabled": False,
        # House correction for six supplement soldiers costed closer to 1st
        # edition than the rest of the 2e tables. On by default; see
        # expansions.EDITION_2_SOLDIER_COSTS.
        "edition2_soldier_costs": True,
        # Spellcaster Magazine's troop stat lines read as unbalanced; this lets
        # a warband keep the book's spells/items/bestiary switched on while
        # dropping just its hireable soldiers. Off by default — a group opts
        # in to the soldiers rather than opting out.
        "spellcaster_magazine_soldiers": False,
        # Knightly Orders (Spellcaster Magazine, Issue 1). Needs Spellcaster
        # Magazine switched on in enabled_sources too.
        "knightly_orders_enabled": True,
        # Blood Legacy's "High-Level Wizards" optional rules (Chapter Three).
        # Each needs Blood Legacy switched on in enabled_sources *and* its own
        # toggle here — the book insists each is agreed to separately. On by
        # default, alongside Blood Legacy itself. See expansions.py's
        # "Blood Legacy: High-Level Wizards" section for what each one does.
        "hlw_specialist_allowance": True,
        "hlw_item_slots": True,
        "hlw_max_health": True,
        "hlw_casting_min": True,
        "hlw_alt_xp": True,
        # Wizard stat limits: the hard ceilings a wizard's level-ups run into.
        # Level is unlimited by default (2e core doesn't actually cap it — the
        # 40 figure below is only the starting point if a group ticks a limit
        # on); Fight/Shoot/Will/Health/min Casting Number default to the 2e
        # core caps. Blood Legacy's Increased Maximum Health and Lower Casting
        # Number Minimum stack their bonuses on top of whatever is set here —
        # see expansions.wizard_stat_caps() / casting_number_minimum().
        "wizard_level_cap": {"limit": MAX_WIZARD_LEVEL, "unlimited": True},
        "wizard_stat_limits": deepcopy(WIZARD_STAT_LIMITS_DEFAULT),
        "wizard_min_casting_number": WIZARD_MIN_CASTING_NUMBER_DEFAULT,
    }


def playable_schools(wb: dict | None = None) -> list[str]:
    """Schools a wizard may actually be. The five Pentangle schools join the ten
    core ones only when The Maze of Malcor is on and the group has agreed to the
    homerule that makes them playable; Fire Giant and Vampire join the same way,
    each gated on Blood Legacy and its own "playable" homerule."""
    hr = (wb or {}).get("homerules") or {}
    es = hr.get("enabled_sources") or {}
    schools = list(SCHOOLS)
    if hr.get("pentangle_schools_playable") and es.get("The Maze of Malcor"):
        schools += list(PENTANGLE_SCHOOLS)
    if hr.get("fire_giant_wizard_playable") and es.get("Blood Legacy"):
        schools.append("Fire Giant")
    if hr.get("vampire_wizard_playable") and es.get("Blood Legacy"):
        schools.append("Vampire")
    return schools


def enabled_sources(wb: dict) -> set[str]:
    """Source-book names whose extra content is switched on for this warband
    (Core Rules is always implicitly included)."""
    hr = wb.get("homerules") or {}
    es = hr.get("enabled_sources") or {}
    return {"Core Rules"} | {book for book in SOURCE_BOOKS if es.get(book)}


def soldier_from_book_enabled(wb: dict, source: str) -> bool:
    """Whether soldiers from a source book may be hired, beyond the book
    itself being switched on. Only Spellcaster Magazine has its own
    soldiers-only toggle so far — see default_homerules()."""
    if source == "Spellcaster Magazine":
        hr = wb.get("homerules") or {}
        return hr.get("spellcaster_magazine_soldiers", True)
    return True


def soldier_source_allowed(wb: dict, type_key: str) -> bool:
    """Whether a soldier type may be hired given this warband's source toggles."""
    info = get_soldier(type_key)
    if not info:
        return False
    src = info.get("source", "Core Rules")
    return src in enabled_sources(wb) and soldier_from_book_enabled(wb, src)


def empty_captain(name: str = "", homerules: dict | None = None, origin: str = "hired") -> dict:
    hr = homerules or default_homerules()
    stats = deepcopy(hr.get("captain_base_stats") or CAPTAIN_BASE)
    n = int(hr.get("captain_item_slots", CAPTAIN_ITEM_SLOTS))
    return {
        "name": name,
        "stats": stats,
        "bonus_extra_stat": None,  # one of LEVELUP_STATS | None (hire/promote +1 pick)
        "item_slots": _default_item_slots(CAPTAIN_DEFAULT_GEAR, n),
        "has_dagger": True,
        "notes": "",
        "portrait": None,
        "xp": 0,
        "level": 0,
        "levelup_counts": {s: 0 for s in LEVELUP_STATS},
        "level_history": [],
        "origin": origin,  # "hired" | "promoted"
        "known_tricks": [],  # list of CAPTAIN_TRICK ids
        "mutations": [],
        "permanent_injuries": [],
    }


def captain_effective_stats(cap: dict) -> dict:
    """Base captain stats plus Armour/Move bonuses from equipped Shield/Armour items.
    Computed fresh from item_slots every time rather than stored — Armour and Move
    aren't level-up stats, so there's no persisted value that could drift out of
    sync with whatever the captain currently has equipped."""
    stats = dict(cap.get("stats") or {})
    bonus = equipment_bonuses(cap.get("item_slots") or [])
    stats["armour"] = int(stats.get("armour", 0)) + bonus["armour"]
    stats["move"] = int(stats.get("move", 0)) + bonus["move"]
    return stats


def wizard_effective_stats(wb: dict) -> dict:
    """The wizard's stats as they play, with any wizard-state bonus folded in
    (e.g. Beastcrafter III's Fast/Scales animal feature). Lives here rather than
    in app.py (G6) so pdf_export.py can use the same numbers the web UI shows,
    instead of reading raw stats and printing a wrong roster."""
    stats = dict((wb.get("wizard") or {}).get("stats") or {})
    for stat, amount in expansions.wizard_state_stat_bonus(wb).items():
        stats[stat] = int(stats.get(stat, 0)) + amount
    return stats


def sync_apprentice(wb: dict) -> None:
    """Apprentice stats from wizard (2e p.27): M same, F-2, S same, A10, W-2, H-2."""
    ap = wb.get("apprentice")
    wiz = wb.get("wizard") or {}
    if not ap or not wiz:
        return
    wstats = wiz.get("stats") or WIZARD_BASE
    wiz_h = int(wstats.get("health", 14))
    ap_stats = {
        "move": int(wstats.get("move", 6)),
        "fight": int(wstats.get("fight", 2)) - 2,
        "shoot": int(wstats.get("shoot", 0)),
        "armour": 10,
        "will": int(wstats.get("will", 4)) - 2,
        "health": max(1, wiz_h - 2),  # starting: 14-2 = 12
    }
    # Re-apply each grave mutation's recorded stat offset on top of the derived
    # base (G1) — without this, add_apprentice_mutation()'s effect is discarded
    # the moment sync_apprentice() runs again on the next save.
    for m in ap.get("mutations") or []:
        for stat, offset in (m.get("stat_offsets") or {}).items():
            if stat in ap_stats:
                ap_stats[stat] += offset
    for stat in ap_stats:
        ap_stats[stat] = max(1, ap_stats[stat]) if stat == "health" else max(0, ap_stats[stat])
    ap["stats"] = ap_stats
    ap["level"] = int(wiz.get("level", 0)) // 2
    ap.setdefault("has_dagger", True)
    ap["item_slots"] = normalize_item_slots(
        ap.get("item_slots", ap.get("items")), expansions.apprentice_item_slots(wb)
    )


def spells_from_keys(keys: list[str], wizard_school: str) -> list[dict]:
    """Build spell list with base CN and effective CN for this wizard."""
    spells = []
    for key in keys:
        sp = find_spell(key)
        if not sp:
            continue
        base = int(sp["cn"])
        pen = cn_penalty(wizard_school, sp["school"])
        spells.append(
            {
                "id": sp["id"],
                "name": sp["name"],
                "school": sp["school"],
                "base_cn": base,
                "cn_penalty": pen,
                "cn": base + pen,  # effective casting number for this wizard
                "type": sp["type"],
                "relation": school_relation(wizard_school, sp["school"]),
            }
        )
    return spells


def recompute_spell_cns(wb: dict) -> None:
    """Refresh effective CN if school changed or spells improved."""
    wiz = wb.get("wizard") or {}
    school = wiz.get("school") or "Elementalist"
    for s in wiz.get("spells") or []:
        base = int(s.get("base_cn", s.get("cn", 10)))
        # If spell was improved, base_cn is original, cn may be lower than base+penalty
        # Store improvements as cn_bonus (negative reduction)
        pen = cn_penalty(school, s.get("school", school))
        improve = int(s.get("cn_improve", 0))  # number of -1 improvements
        s["cn_penalty"] = pen
        s["relation"] = school_relation(school, s.get("school", school))
        s["base_cn"] = base
        s["cn"] = max(expansions.casting_number_minimum(wb), base + pen - improve)


def validate_starting_spells(
    school: str, spell_keys: list[str], sources: set[str] | None = None
) -> tuple[bool, str]:
    """2e Choosing Spells p.24: 3 own, 1 each aligned, 2 neutral (diff schools), no opposed.

    `sources` is the set of source books switched on for the warband being created;
    supplement spells from a book that is off cannot be taken. Defaults to Core
    Rules only. Spell-only schools (Beastcrafter) are excluded automatically by the
    own/aligned/neutral check further down.
    """
    if len(spell_keys) != STARTING_SPELL_COUNT:
        return False, f"Pick exactly {STARTING_SPELL_COUNT} spells (got {len(spell_keys)})."
    if len(set(spell_keys)) != len(spell_keys):
        return False, "Duplicate spells selected."

    rel = SCHOOL_RELATIONS.get(school)
    if not rel:
        return False, "Invalid school."

    allowed_sources = sources or {"Core Rules"}
    by_school: dict[str, int] = {}
    for key in spell_keys:
        sp = find_spell(key)
        if not sp:
            return False, f"Unknown spell: {key}"
        if sp["source"] not in allowed_sources:
            return False, (
                f"{sp['name']} is from {sp['source']}; switch that source book on to take it."
            )
        by_school[sp["school"]] = by_school.get(sp["school"], 0) + 1

    # No opposed
    opp = rel["opposed"]
    bad_opp = [o for o in opp if by_school.get(o, 0) > 0]
    if bad_opp:
        return False, f"Starting wizards cannot take spells from opposed school(s) ({', '.join(bad_opp)})."

    # Own: exactly 3
    own_n = by_school.get(school, 0)
    if own_n != OWN_SCHOOL_SPELLS:
        return False, f"Need exactly {OWN_SCHOOL_SPELLS} spells from {school} (have {own_n})."

    # Each aligned: exactly 1
    for al in rel["aligned"]:
        n = by_school.get(al, 0)
        if n != ALIGNED_SCHOOL_SPELLS:
            return False, f"Need exactly 1 spell from aligned school {al} (have {n})."

    # Neutrals: whatever is left of the 8, one each from different schools.
    # Derived rather than hardcoded to NEUTRAL_SPELLS because a Pentangle school
    # has two aligned schools where a core school has three — so playing one
    # leaves three neutral picks instead of two, still totalling 8.
    n_neutral = STARTING_SPELL_COUNT - OWN_SCHOOL_SPELLS - len(rel["aligned"]) * ALIGNED_SCHOOL_SPELLS
    neutral_picks = {s: n for s, n in by_school.items() if s in rel["neutral"]}
    total_neutral = sum(neutral_picks.values())
    if total_neutral != n_neutral:
        return False, f"Need exactly {n_neutral} spells from neutral schools (have {total_neutral})."
    if any(n != 1 for n in neutral_picks.values()) or len(neutral_picks) != n_neutral:
        return False, f"Pick the {n_neutral} neutral spells from {n_neutral} different neutral schools."

    # No extras
    allowed = {school, *rel["aligned"], *rel["neutral"]}
    for s in by_school:
        if s not in allowed:
            return False, f"Spell school {s} is not allowed at creation."

    return True, "OK"


def create_warband(
    warband_name: str,
    wizard_name: str,
    school: str,
    spell_keys: list[str],
    with_apprentice: bool = False,
    apprentice_name: str = "",
    soldiers: list[dict] | None = None,
    enabled_sources_map: dict | None = None,
    pentangle_playable: bool = False,
    fire_giant_playable: bool = False,
    vampire_playable: bool = False,
    starting_gold: int | None = None,
    wizard_starting_xp: int = 0,
    max_soldiers: int | None = None,
    max_specialists: int | None = None,
) -> tuple[Warband | None, str]:
    """
    soldiers: optional list of {type_key, name} hired at creation (costs deducted).
    enabled_sources_map: {book name: bool} source books to switch on for the new
        warband, so supplement spells and soldiers can be picked at creation.
    pentangle_playable: allow one of the five Pentangle schools as the wizard's
        own school (needs The Maze of Malcor switched on).
    fire_giant_playable: allow Fire Giant as the wizard's own school (needs
        Blood Legacy switched on) — Blood Legacy's Fire Giant Wizard build.
    vampire_playable: allow Vampire as the wizard's own school (needs Blood
        Legacy switched on) — Blood Legacy's Vampire Wizard build.
    starting_gold: house-ruled starting gold; defaults to STARTING_GOLD (400).
    wizard_starting_xp: house-ruled starting XP for the wizard; defaults to 0.
    max_soldiers: house-ruled roster cap; defaults to MAX_SOLDIERS (8).
    max_specialists: house-ruled specialist cap; defaults to MAX_SPECIALISTS (4).
    """
    homerules = default_homerules()
    if max_soldiers is not None:
        homerules["max_soldiers"] = max(1, int(max_soldiers))
    if max_specialists is not None:
        homerules["max_specialists"] = max(0, int(max_specialists))
    if enabled_sources_map:
        homerules["enabled_sources"] = {
            book: bool(enabled_sources_map.get(book)) for book in SOURCE_BOOKS
        }
        if homerules["enabled_sources"].get("Blood Legacy"):
            # Turning Blood Legacy on defaults its whole High-Level Wizards
            # chapter on too — matches the same auto-tick the homerules page
            # does when the book is switched on after creation.
            for key in (
                "hlw_specialist_allowance", "hlw_item_slots", "hlw_max_health",
                "hlw_casting_min", "hlw_alt_xp",
            ):
                homerules[key] = True
    homerules["pentangle_schools_playable"] = bool(pentangle_playable)
    homerules["fire_giant_wizard_playable"] = bool(fire_giant_playable)
    homerules["vampire_wizard_playable"] = bool(vampire_playable)
    if school not in playable_schools({"homerules": homerules}):
        if school in PENTANGLE_SCHOOLS:
            return None, (
                f"{school} is a Pentangle school — switch on The Maze of Malcor and the "
                "'Pentangle schools playable' homerule to use it."
            )
        if school == "Fire Giant":
            return None, (
                "Fire Giant is Blood Legacy's Fire Giant Wizard build — switch on Blood Legacy "
                "and the 'Fire Giant Wizard playable' homerule to use it."
            )
        if school == "Vampire":
            return None, (
                "Vampire is Blood Legacy's Vampire Wizard build — switch on Blood Legacy "
                "and the 'Vampire Wizard playable' homerule to use it."
            )
        return None, "Invalid school."
    picked_sources = {"Core Rules"} | {
        book for book, on in homerules["enabled_sources"].items() if on
    }
    ok, msg = validate_starting_spells(school, spell_keys, picked_sources)
    if not ok:
        return None, msg
    if school == "Fire Giant":
        # "can't learn/use Chronomancer spells or Write Scroll" — Chronomancer
        # itself is already excluded (it's Fire Giant's one opposed school,
        # so validate_starting_spells above already rejects it), but Write
        # Scroll is offered by every other school too and needs its own check.
        if any((find_spell(k) or {}).get("name") == "Write Scroll" for k in spell_keys):
            return None, "A Fire Giant Wizard cannot take Write Scroll as a starting spell (Blood Legacy)."
        if with_apprentice:
            return None, "A Fire Giant Wizard has no apprentice (Blood Legacy)."
    if school == "Vampire":
        # Thaumaturge is Vampire's one opposed school (never learnable), so
        # validate_starting_spells above already rejects it as a starting pick.
        if with_apprentice:
            return None, "A Vampire Wizard has no apprentice (Blood Legacy)."
        # "9 soldiers (4 specialist)" — a floor, not a suggestion; never
        # lowers a bigger cap the group asked for of their own.
        homerules["max_soldiers"] = max(homerules["max_soldiers"], VAMPIRE_MIN_MAX_SOLDIERS)

    gold = STARTING_GOLD if starting_gold is None else int(starting_gold)
    apprentice = None
    if with_apprentice:
        if gold < APPRENTICE_COST:
            return None, f"Not enough gold for apprentice ({APPRENTICE_COST} gc)."
        gold -= APPRENTICE_COST
        apprentice = empty_apprentice(apprentice_name or "Apprentice")

    # Validate soldiers before committing
    hired: list[dict] = []
    specs = 0
    soldier_cap = homerules["max_soldiers"]
    spec_cap = homerules["max_specialists"]
    if soldiers:
        if len(soldiers) > soldier_cap:
            return None, f"Max {soldier_cap} soldiers."
        for entry in soldiers:
            type_key = entry.get("type_key") or ""
            info = get_soldier(type_key)
            if not info:
                return None, f"Unknown soldier type: {type_key}"
            src = info.get("source", "Core Rules")
            if src not in picked_sources:
                return None, f"{info['name']} is from {src}; switch that source book on to hire it."
            if info["category"] == "specialist":
                specs += 1
                if specs > spec_cap:
                    return None, f"Max {spec_cap} specialists."
            cost = int(info["cost"])
            if gold < cost:
                return None, f"Not enough gold for {info['name']} (need {cost} gc)."
            gold -= cost
            hired.append(
                {
                    "id": uuid.uuid4().hex[:10],
                    "type_key": type_key,
                    "name": (entry.get("name") or info["name"]).strip(),
                    "status": "active",
                    "items": [],
                    "notes": "",
                    "portrait": None,
                    **_new_soldier_leveling_fields(info),
                }
            )

    wb = {
        "id": new_warband_id(warband_name),
        "schema_version": SCHEMA_VERSION,
        "name": warband_name.strip() or "Unnamed Warband",
        "created": _now(),
        "updated": _now(),
        "gold": gold,
        "notes": "",
        "wizard": empty_wizard(wizard_name.strip() or "Wizard", school),
        "apprentice": apprentice,
        "captain": None,
        "homerules": homerules,
        "soldiers": hired,
        "vault_items": [],
        "base": empty_base(),
        "history": [],
    }
    wb["wizard"]["spells"] = spells_from_keys(spell_keys, school)
    if wizard_starting_xp:
        wb["wizard"]["xp"] = int(wizard_starting_xp)
    if apprentice:
        sync_apprentice(wb)
    parts = [f"Warband founded with {gold} gc remaining"]
    if with_apprentice:
        parts.append("apprentice hired")
    if hired:
        parts.append(f"{len(hired)} soldiers recruited")
    wb["history"].append({"when": _now(), "text": "; ".join(parts) + "."})
    return wb, "Created."


def reorder_spells(wb: dict, spell_ids_in_order: list[str]) -> tuple[bool, str]:
    wiz = wb.get("wizard") or {}
    spells = wiz.get("spells") or []
    by_id = {s.get("id"): s for s in spells}
    if set(spell_ids_in_order) != set(by_id.keys()) or len(spell_ids_in_order) != len(spells):
        return False, "Spell list does not match known spells."
    wiz["spells"] = [by_id[i] for i in spell_ids_in_order]
    return True, "Spell order updated."


def reorder_soldiers(wb: dict, soldier_ids_in_order: list[str]) -> tuple[bool, str]:
    soldiers = wb.get("soldiers") or []
    by_id = {s.get("id"): s for s in soldiers}
    if set(soldier_ids_in_order) != set(by_id.keys()) or len(soldier_ids_in_order) != len(soldiers):
        return False, "Soldier list does not match roster."
    wb["soldiers"] = [by_id[i] for i in soldier_ids_in_order]
    return True, "Soldier order updated."


def list_unreadable_warbands() -> list[dict]:
    """Warband files that exist on disk but fail to parse, for a home-page warning."""
    unreadable = []
    for path in warband_dir().glob("*.warbands"):
        try:
            json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            logger.warning("Warband file %s could not be read: %s", path, exc)
            unreadable.append({"filename": path.name, "path": str(path), "error": str(exc)})
    return unreadable


def list_warbands() -> list[dict]:
    items = []
    for path in sorted(
        warband_dir().glob("*.warbands"), key=lambda p: p.stat().st_mtime, reverse=True
    ):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        items.append(
            {
                "id": data.get("id", path.stem),
                "name": data.get("name", path.stem),
                "wizard": (data.get("wizard") or {}).get("name", "—"),
                "school": (data.get("wizard") or {}).get("school", "—"),
                "level": (data.get("wizard") or {}).get("level", 0),
                "gold": data.get("gold", 0),
                "soldiers": len(
                    [s for s in (data.get("soldiers") or []) if s.get("status") != "dead"]
                ),
                "updated": data.get("updated", ""),
                "portrait": (data.get("wizard") or {}).get("portrait"),
            }
        )
    return items


def _sanitize_filename(s: str) -> str:
    """Strip everything but the safe filename charset, for building paths out
    of user-supplied ids/roles (warband id, portrait role)."""
    return re.sub(r"[^a-zA-Z0-9._-]", "", s)


def warband_path(warband_id: str) -> Path:
    """Warband files use a .warbands extension; the content is plain JSON."""
    safe = _sanitize_filename(warband_id)
    return warband_dir() / f"{safe}.warbands"


def portrait_dir(warband_id: str) -> Path:
    safe = _sanitize_filename(warband_id)
    d = portraits_root_dir() / safe
    d.mkdir(parents=True, exist_ok=True)
    return d


SCHEMA_VERSION = 1
# Bump this and append a new (version, function) pair to MIGRATIONS whenever a
# future format change needs one-time cleanup on old files. Each migration
# only runs once per file: files with no "schema_version" are treated as
# version 0 (run everything), then get stamped with SCHEMA_VERSION so later
# loads skip work they've already done (B3).


def _migrate_wizard_health_2e(wb: dict) -> None:
    """Pre-2e health base was 10; 2e starting wizard is 14."""
    wstats = wb["wizard"]["stats"]
    if int(wstats.get("health", 14)) == 10:
        wstats["health"] = 14


def _migrate_item_slots(wb: dict) -> None:
    """items (freeform list) -> item_slots (fixed-length slot list), wizard + apprentice."""
    wiz = wb["wizard"]
    wiz_slot_n = expansions.wizard_item_slots(wb)
    if "item_slots" not in wiz or not isinstance(wiz.get("item_slots"), list):
        wiz["item_slots"] = normalize_item_slots(wiz.get("items"), wiz_slot_n)
    ap = wb.get("apprentice")
    if ap and ("item_slots" not in ap or not isinstance(ap.get("item_slots"), list)):
        ap["item_slots"] = normalize_item_slots(ap.get("items"), expansions.apprentice_item_slots(wb))


def _migrate_vault_string_to_list(wb: dict) -> None:
    """vault (freeform textarea string) -> vault_items (structured list)."""
    if isinstance(wb.get("vault"), str) and wb["vault"] and not wb.get("vault_items"):
        wb["vault_items"] = [
            {"name": line, "notes": "migrated", "source": "vault"}
            for line in wb["vault"].splitlines()
            if line.strip()
        ]


def _migrate_captain_stat_caps(wb: dict) -> None:
    """Old flat per-stat cap fields (fight/shoot only) + XP multiplier -> captain_stat_caps."""
    hr = wb.get("homerules") or {}
    if "captain_fight_levelup_cap" in hr or "captain_shoot_levelup_cap" in hr:
        caps = deepcopy(CAPTAIN_STAT_CAPS)
        if "captain_fight_levelup_cap" in hr:
            caps["fight"] = {"limit": int(hr["captain_fight_levelup_cap"]), "unlimited": False}
        if "captain_shoot_levelup_cap" in hr:
            caps["shoot"] = {"limit": int(hr["captain_shoot_levelup_cap"]), "unlimited": False}
        hr["captain_stat_caps"] = caps
    for old_key in ("captain_fight_levelup_cap", "captain_shoot_levelup_cap", "captain_xp_multiplier"):
        hr.pop(old_key, None)


def _migrate_captain_mode_flags(wb: dict) -> None:
    """Old independent captains_enabled/promote_captain_enabled booleans -> single captain_mode select."""
    hr = wb.get("homerules") or {}
    if "captain_mode" not in hr:
        old_hire = bool(hr.get("captains_enabled", False))
        old_promote = bool(hr.get("promote_captain_enabled", False))
        if old_hire and old_promote:
            hr["captain_mode"] = "both"
        elif old_hire:
            hr["captain_mode"] = "hire"
        elif old_promote:
            hr["captain_mode"] = "promote"
        else:
            hr["captain_mode"] = "off"
    hr.pop("captains_enabled", None)
    hr.pop("promote_captain_enabled", None)


def _migrate_captain_levelup_counts(wb: dict) -> None:
    """fight_levelup_count/shoot_levelup_count (captain-only) -> levelup_counts."""
    cap = wb.get("captain")
    if not cap:
        return
    counts = cap.setdefault("levelup_counts", {s: 0 for s in LEVELUP_STATS})
    for s in LEVELUP_STATS:
        counts.setdefault(s, 0)
    if "fight_levelup_count" in cap:
        counts["fight"] = int(cap.pop("fight_levelup_count"))
    if "shoot_levelup_count" in cap:
        counts["shoot"] = int(cap.pop("shoot_levelup_count"))


def _migrate_soldier_items_string_to_list(wb: dict) -> None:
    """Soldier items as a freeform newline-separated string -> structured list."""
    for s in wb.get("soldiers") or []:
        if isinstance(s.get("items"), str):
            text = s["items"].strip()
            s["items"] = (
                [{"name": line, "notes": ""} for line in text.splitlines() if line.strip()]
                if text
                else []
            )


MIGRATIONS: list[tuple[int, Callable[[dict], None]]] = [
    (1, _migrate_wizard_health_2e),
    (1, _migrate_item_slots),
    (1, _migrate_vault_string_to_list),
    (1, _migrate_captain_stat_caps),
    (1, _migrate_captain_mode_flags),
    (1, _migrate_captain_levelup_counts),
    (1, _migrate_soldier_items_string_to_list),
]


def _run_migrations(wb: dict) -> None:
    version = int(wb.get("schema_version", 0))
    ran = [target for target, _ in MIGRATIONS if version < target]
    for target_version, migration in MIGRATIONS:
        if version < target_version:
            migration(wb)
    if ran:
        logger.info(
            "Migrated warband %s from schema %d to %d (ran: %s)",
            wb.get("id", "?"), version, SCHEMA_VERSION, ran,
        )
    wb["schema_version"] = SCHEMA_VERSION


def _normalize_warband(wb: dict) -> dict:
    """Backfill defaults and run migrations on a freshly-parsed warband dict —
    shared by load_warband() and import_warband_json() (B3) so an imported
    file is in current shape immediately rather than waiting for the next
    load to pick up the migration chain.

    Backfill defensively, per-key, everywhere below — not version-gated,
    since new optional fields get added over time and every load should
    still see sane defaults for them regardless of a file's schema_version.
    """
    wiz = wb.setdefault("wizard", empty_wizard())
    wiz.setdefault("stats", deepcopy(WIZARD_BASE))
    wiz["stats"].setdefault("health", 14)
    wiz.pop("health_current", None)
    wiz.setdefault("has_dagger", True)
    wiz.setdefault("mutations", [])
    wiz.setdefault("permanent_injuries", [])
    wiz.setdefault("portrait_source_name", None)
    # Wizard state (Lich / Beastcrafter / pact). Backfilled per-key so a warband
    # saved before this existed loads as an ordinary wizard.
    state = wiz.setdefault("state", expansions.default_wizard_state())
    if not isinstance(state, dict):
        state = wiz["state"] = expansions.default_wizard_state()
    for key, value in expansions.default_wizard_state().items():
        state.setdefault(key, value)
    if state.get("kind") not in expansions.WIZARD_STATES:
        state["kind"] = expansions.STATE_NONE
    if isinstance(wiz.get("spells"), str):
        wiz["spells"] = []
    wb.setdefault("vault_items", [])
    if not isinstance(wb.get("base"), dict):
        wb["base"] = empty_base()
    else:
        wb["base"].setdefault("location", "none")
        wb["base"].setdefault("resources", [])
        wb["base"].setdefault("notes", "")
        if wb["base"]["location"] not in BASE_LOCATIONS:
            wb["base"]["location"] = "none"
        wb["base"]["resources"] = [
            r for r in wb["base"]["resources"] if r in BASE_RESOURCES
        ]
    if wb.get("apprentice"):
        ap = wb["apprentice"]
        ap.setdefault("has_dagger", True)
        ap.setdefault("mutations", [])
        ap.setdefault("permanent_injuries", [])
        ap.setdefault("portrait_source_name", None)
        ap.pop("health_current", None)
    hr = wb.setdefault("homerules", default_homerules())
    for k, v in default_homerules().items():
        hr.setdefault(k, v)
    es = hr.setdefault("enabled_sources", {})
    for book in SOURCE_BOOKS:
        es.setdefault(book, False)
    wb.setdefault("captain", None)
    if wb.get("captain"):
        cap = wb["captain"]
        cap.pop("bonus_choice", None)  # removed: fixed +3F/+2S hire bonus no longer exists
        cap.setdefault("bonus_extra_stat", None)
        cap.setdefault("xp", 0)
        cap.setdefault("level_history", [])
        cap.setdefault("has_dagger", True)
        cap.setdefault("notes", "")
        cap.setdefault("portrait", None)
        cap.setdefault("origin", "hired")
        cap.setdefault("known_tricks", [])
        cap.setdefault("mutations", [])
        cap.setdefault("permanent_injuries", [])
        cap.setdefault("portrait_source_name", None)
        cap.setdefault("level", 0)
        n = int(hr.get("captain_item_slots", CAPTAIN_ITEM_SLOTS))
        if cap.get("origin") == "promoted":
            n = int(hr.get("promote_captain_item_slots", PROMOTE_CAPTAIN_ITEM_SLOTS))
        cap["item_slots"] = normalize_item_slots(cap.get("item_slots"), n)
    for s in wb.get("soldiers") or []:
        s.setdefault("portrait", None)
        s.setdefault("portrait_source_name", None)
        s.setdefault("items", [])
        s.setdefault("mutations", [])
        s.setdefault("modifications", [])
        s.setdefault("permanent_injuries", [])
        s.pop("health_current", None)
        if any(s.get(k) is None for k in ("fight", "shoot", "will", "health")):
            info = get_soldier(s.get("type_key", "")) or {}
            for k in ("fight", "shoot", "will", "health"):
                s.setdefault(k, info.get(k))
        s.setdefault("xp", 0)
        s.setdefault("level", 0)
        counts = s.setdefault("levelup_counts", {stat: 0 for stat in LEVELUP_STATS})
        for stat in LEVELUP_STATS:
            counts.setdefault(stat, 0)
        s.setdefault("level_history", [])

    _run_migrations(wb)

    # item_slots normalization must run after migrations (which may populate
    # item_slots from legacy "items" for the first time) so an already-list
    # item_slots also gets re-padded/trimmed to the current slot count even
    # when no migration fired.
    wiz["item_slots"] = normalize_item_slots(wiz.get("item_slots"), expansions.wizard_item_slots(wb))
    if wb.get("apprentice"):
        ap = wb["apprentice"]
        ap["item_slots"] = normalize_item_slots(ap.get("item_slots"), expansions.apprentice_item_slots(wb))
        sync_apprentice(wb)

    return wb


def load_warband(warband_id: str) -> Warband | None:
    path = warband_path(warband_id)
    if not path.is_file():
        return None
    try:
        wb = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        logger.warning("Warband file %s could not be read: %s", path, exc)
        return None
    return _normalize_warband(wb)


def save_warband(wb: Warband) -> None:
    if wb.get("apprentice"):
        sync_apprentice(wb)
    wb.setdefault("schema_version", SCHEMA_VERSION)
    wb["updated"] = _now()
    path = warband_path(wb["id"])
    data = json.dumps(wb, indent=2, ensure_ascii=False) + "\n"
    tmp = path.with_suffix(".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(data)
        f.flush()
        os.fsync(f.fileno())
    if path.is_file():
        bak = path.with_suffix(".bak")
        try:
            shutil.copy2(path, bak)
        except OSError as exc:
            logger.warning("Could not write backup %s for warband %s: %s", bak, wb.get("id", "?"), exc)
    os.replace(tmp, path)


def delete_warband(warband_id: str) -> bool:
    path = warband_path(warband_id)
    ok = False
    if path.is_file():
        path.unlink()
        ok = True
    pdir = portrait_dir(warband_id)
    if pdir.is_dir():
        for f in pdir.iterdir():
            try:
                f.unlink()
            except OSError:
                pass
        try:
            pdir.rmdir()
        except OSError:
            pass
    return ok


def _copy_portrait_file(rel: str | None, old_id: str, new_id: str) -> str | None:
    """Copy a portrait file into the new warband folder; return new relative path."""
    if not rel:
        return None
    src = portrait_filesystem_path(rel)
    if not src:
        # try as old_id/filename
        name = Path(rel).name
        src = portraits_root_dir() / old_id / name
        if not src.is_file():
            return None
    dest_dir = portrait_dir(new_id)
    dest = dest_dir / src.name
    try:
        shutil.copy2(src, dest)
    except OSError:
        return None
    return f"{new_id}/{dest.name}"


def duplicate_warband(source_id: str, new_name: str | None = None) -> tuple[Warband | None, str]:
    """Deep-copy a warband (data + portraits) under a new id and name."""
    src = load_warband(source_id)
    if not src:
        return None, "Warband not found."

    wb = deepcopy(src)
    old_id = src.get("id") or source_id
    base_name = (new_name or "").strip() or f"{src.get('name', 'Warband')} (copy)"
    new_id = new_warband_id(base_name)

    wb["id"] = new_id
    wb["name"] = base_name
    wb["created"] = _now()
    wb["updated"] = _now()

    # Portraits: wizard
    wiz = wb.setdefault("wizard", {})
    wiz["portrait"] = _copy_portrait_file(wiz.get("portrait"), old_id, new_id)

    # Apprentice
    if wb.get("apprentice"):
        ap = wb["apprentice"]
        ap["portrait"] = _copy_portrait_file(ap.get("portrait"), old_id, new_id)

    # Soldiers: new ids + portraits
    for s in wb.get("soldiers") or []:
        old_sid = s.get("id")
        s["id"] = uuid.uuid4().hex[:10]
        old_por = s.get("portrait")
        # portrait may be named soldier_<old_sid>.ext
        new_por = _copy_portrait_file(old_por, old_id, new_id)
        if new_por and old_sid:
            # rename file to match new soldier id if possible
            src_path = portrait_filesystem_path(new_por)
            if src_path and src_path.is_file():
                ext = src_path.suffix
                dest = portrait_dir(new_id) / f"soldier_{s['id']}{ext}"
                try:
                    if dest != src_path:
                        shutil.move(str(src_path), str(dest))
                        new_por = f"{new_id}/{dest.name}"
                except OSError:
                    pass
        s["portrait"] = new_por

    # Vault item ids unique
    for it in wb.get("vault_items") or []:
        it["id"] = uuid.uuid4().hex[:8]

    hist = wb.setdefault("history", [])
    hist.append(
        {
            "when": _now(),
            "text": f"Duplicated from “{src.get('name', old_id)}” as “{base_name}”.",
        }
    )

    save_warband(wb)
    return wb, f"Duplicated as “{base_name}”."


def export_warband_json(wb: Warband) -> str:
    return json.dumps(wb, indent=2, ensure_ascii=False)


def import_warband_json(raw: str) -> Warband:
    data = json.loads(raw)
    if not isinstance(data, dict) or "wizard" not in data:
        raise ValueError("Invalid warband file")
    old_id = data.get("id") or new_warband_id(data.get("name", "imported"))
    if warband_path(old_id).is_file():
        data["id"] = new_warband_id(data.get("name", "imported"))
    else:
        data["id"] = old_id
    data.setdefault("soldiers", [])
    data.setdefault("history", [])
    data.setdefault("gold", STARTING_GOLD)
    data.setdefault("notes", "")
    data.setdefault("vault_items", [])
    data.setdefault("apprentice", None)
    data.setdefault("created", _now())
    return _normalize_warband(data)


def restore_portraits_by_name(wb: dict, files: "Iterable[FileStorage]") -> int:
    """Matches uploaded files (from the Import page's optional 'pictures'
    field) against each character's remembered portrait_source_name and
    reapplies any matches — portrait bytes are never included in an export,
    only this filename pointer, so re-selecting the same picture files on
    import brings them back without a per-character manual re-upload.
    Returns how many were restored."""
    by_name = {}
    for f in files:
        if f and f.filename:
            by_name.setdefault(f.filename.strip().lower(), f)
    if not by_name:
        return 0
    targets = [(wb.get("wizard"), "wizard")]
    if wb.get("apprentice"):
        targets.append((wb["apprentice"], "apprentice"))
    if wb.get("captain"):
        targets.append((wb["captain"], "captain"))
    for s in wb.get("soldiers") or []:
        targets.append((s, f"soldier_{s.get('id')}"))
    count = 0
    for entity, role in targets:
        if not entity:
            continue
        wanted = (entity.get("portrait_source_name") or "").strip().lower()
        if wanted and wanted in by_name:
            apply_portrait(entity, wb["id"], role, by_name[wanted])
            count += 1
    return count


def save_portrait(warband_id: str, role: str, file_storage: "FileStorage | None") -> str | None:
    """Save uploaded image. role = wizard | apprentice | soldier_<id>. Returns relative path."""
    if not file_storage or not file_storage.filename:
        return None
    ext = Path(file_storage.filename).suffix.lower()
    if ext not in ALLOWED_IMAGE_EXT:
        raise ValueError("Image must be jpg, png, gif, or webp.")
    safe_role = _sanitize_filename(role)
    dest = portrait_dir(warband_id) / f"{safe_role}{ext}"
    # Remove old portraits for same role
    for old in portrait_dir(warband_id).glob(f"{safe_role}.*"):
        if old != dest:
            try:
                old.unlink()
            except OSError:
                pass
    file_storage.save(dest)
    return f"{warband_id}/{dest.name}"


def apply_portrait(entity: dict, warband_id: str, role: str, file_storage: "FileStorage | None") -> None:
    """Saves an uploaded portrait onto a character dict and remembers the
    browser-supplied original filename (portrait_source_name) so a later
    Import can re-match and reapply it — see restore_portraits_by_name()."""
    if not (file_storage and file_storage.filename):
        return
    entity["portrait"] = save_portrait(warband_id, role, file_storage)
    entity["portrait_source_name"] = file_storage.filename


def remove_portrait(entity: dict, warband_id: str, role: str) -> None:
    """Deletes any saved portrait file for this role so the character
    reverts to showing default artwork again."""
    safe_role = _sanitize_filename(role)
    for old in portrait_dir(warband_id).glob(f"{safe_role}.*"):
        try:
            old.unlink()
        except OSError:
            pass
    entity["portrait"] = None
    entity.pop("portrait_source_name", None)


def portrait_filesystem_path(rel: str | None) -> Path | None:
    if not rel:
        return None
    parts = Path(rel)
    # prevent traversal
    if ".." in parts.parts:
        return None
    path = portraits_root_dir() / parts
    return path if path.is_file() else None


def resolve_portrait_path(
    rel: str | None, kind: str, type_key: str | None = None
) -> Path | None:
    """The picture to actually show: the uploaded one if there is one, else the
    default that ships with the app. Used by the PDF export; the web templates go
    through the portrait_src() Jinja global for the same decision."""
    path = portrait_filesystem_path(rel)
    if path:
        return path
    name = default_portrait_name(kind, type_key)
    return (DEFAULT_PORTRAIT_DIR / name) if name else None


def _soldier_is_specialist(s: dict) -> bool:
    """A soldier's catalog category, or "specialist" if a Construct
    Modification (Projectile Weapon) forced it — see add_construct_modification."""
    if s.get("forced_specialist"):
        return True
    info = SOLDIERS.get(s.get("type_key", ""), {})
    return info.get("category") == "specialist"


def count_specialists(wb: dict) -> int:
    n = 0
    for s in wb.get("soldiers") or []:
        if s.get("status") == "dead":
            continue
        if _soldier_is_specialist(s):
            n += 1
    return n


def active_soldiers(wb: dict) -> list[dict]:
    return [s for s in (wb.get("soldiers") or []) if s.get("status") != "dead"]


def active_permanent_soldiers(wb: dict) -> list[dict]:
    """Active soldiers excluding temporary members (Raise Zombie, Summon
    Demon) — those don't occupy a permanent roster slot."""
    return [
        s for s in active_soldiers(wb)
        if not SOLDIERS.get(s.get("type_key", ""), {}).get("temporary")
    ]


def soldier_count(wb: dict) -> int:
    """Permanent active soldiers plus the Captain (if any) — a Captain occupies
    a soldier slot just like any other roster member, on top of their own
    specialist slot (see specialist_count). Temporary members (Raise Zombie,
    Summon Demon) don't count towards this."""
    return len(active_permanent_soldiers(wb)) + (1 if wb.get("captain") else 0)


def specialist_count(wb: dict) -> int:
    """Specialist soldiers plus the Captain (if any) — a Captain always counts
    as a specialist, regardless of what type they were hired/promoted as."""
    return count_specialists(wb) + (1 if wb.get("captain") else 0)


def warband_limits(wb: dict) -> dict:
    soldiers = active_soldiers(wb)
    n_soldiers = soldier_count(wb)
    specs = specialist_count(wb)
    spent = 0
    # Approximate gold spent on current roster from costs (not perfect for refunds)
    if wb.get("apprentice"):
        spent += APPRENTICE_COST
    if wb.get("captain"):
        spent += int((wb.get("homerules") or {}).get("captain_hiring_cost", CAPTAIN_HIRING_COST))
    for s in soldiers:
        type_key = s.get("type_key", "")
        info = SOLDIERS.get(type_key, {})
        spent += expansions.soldier_cost(wb, info, type_key)
    wiz = wb.get("wizard") or {}
    xp = int(wiz.get("xp", 0))
    level = int(wiz.get("level", 0))
    per_level = expansions.xp_per_level(wb)
    cap = expansions.max_soldiers(wb)
    spec_cap = expansions.max_specialists(wb)
    return {
        "soldiers": n_soldiers,
        "max_soldiers": cap,
        "specialists": specs,
        "max_specialists": spec_cap,
        "soldiers_ok": n_soldiers <= cap,
        "specialists_ok": specs <= spec_cap,
        "has_apprentice": wb.get("apprentice") is not None,
        "apprentice_cost": APPRENTICE_COST,
        "starting_gold": STARTING_GOLD,
        "gold": int(wb.get("gold", 0)),
        "roster_cost_estimate": spent,
        "xp": xp,
        "level": level,
        "xp_per_level": per_level,
        "xp_to_next": xp_to_next_level(xp, level, per_level),
        "pending_levels": max(0, level_from_xp(xp, per_level, expansions.max_wizard_level(wb)) - level),
    }


def enrich_soldier(wb: dict, s: dict) -> dict:
    type_key = s.get("type_key", "")
    cat = get_soldier(type_key) or {}
    out = {**cat, **s}
    out["type_name"] = cat.get("name", type_key or "?")
    out["category"] = "specialist" if _soldier_is_specialist(s) else cat.get("category", "standard")
    # Live cost, not what was paid at hire time — same rule as everywhere else
    # cost is computed (hireable list, warband_limits): homerule adjustments
    # (Edition 2 toggle, Beastcrafter surcharge, base discount) always apply
    # to the current settings, not a value frozen at hire time.
    out["cost"] = expansions.soldier_cost(wb, cat, type_key) if cat else s.get("cost", 0)
    out["knightly_order_info"] = KNIGHTLY_ORDER_BY_ID.get(s.get("knightly_order") or "")
    return out


def _next_type_name(wb: dict, type_key: str, type_name: str) -> str:
    """Default name for a newly hired soldier: 'Archer 1', 'Archer 2', ..."""
    existing = [s for s in wb.get("soldiers") or [] if s.get("type_key") == type_key]
    return f"{type_name} {len(existing) + 1}"


def _new_soldier_leveling_fields(info: dict) -> dict:
    """Levelable-stat snapshot + XP/level bookkeeping for a newly hired soldier.

    Fight/Shoot/Will/Health are copied onto the soldier dict itself so they can
    diverge from the catalog via Soldier Leveling; enrich_soldier()'s
    {**catalog, **soldier} merge lets these override the catalog once present.
    Move/Armour/cost/name/etc. are never stored per-soldier — always catalog.
    """
    return {
        "fight": info.get("fight"),
        "shoot": info.get("shoot"),
        "will": info.get("will"),
        "health": info.get("health"),
        "xp": 0,
        "level": 0,
        "levelup_counts": {s: 0 for s in LEVELUP_STATS},
        "level_history": [],
    }


def add_soldier(
    wb: dict, type_key: str, name: str = "", order: str = "", illusion_source: str = ""
) -> tuple[bool, str]:
    info = get_soldier(type_key)
    if not info:
        return False, "Unknown soldier type."
    src = info.get("source", "Core Rules")
    if src not in enabled_sources(wb):
        return False, f"{info['name']} is from {src}; enable that source under Additional Rules and Homerules first."
    if not soldier_from_book_enabled(wb, src):
        return False, f"{info['name']}'s soldiers are switched off for {src} under Additional Rules and Homerules (its spells/items/bestiary can stay on)."
    illusion_source = (illusion_source or "").strip()
    illusion_info = None
    if type_key == "illusionary_soldier":
        choices = {c["id"] for c in illusion_source_choices()}
        if illusion_source not in choices:
            return False, "Pick which core soldier type the Illusionary Soldier copies."
        illusion_info = get_soldier(illusion_source)
    order = (order or "").strip()
    if order:
        hr = wb.get("homerules") or {}
        if type_key not in KNIGHTLY_ORDER_ELIGIBLE:
            return False, "Knightly Orders can only be chosen for a Knight or Templar."
        if "Spellcaster Magazine" not in enabled_sources(wb) or not hr.get("knightly_orders_enabled"):
            return False, "Knightly Orders need Spellcaster Magazine and its own toggle switched on under Additional Rules and Homerules."
        if order not in KNIGHTLY_ORDER_IDS:
            return False, "Unknown Knightly Order."
    blocked = expansions.soldier_state_block(wb, type_key)
    if blocked:
        return False, blocked
    req_spell = info.get("requires_spell")
    # Temporary members (Raise Zombie, Summon Demon) are bookkeeping for what's
    # already happened at the table — the player cast the spell for real, dice
    # and all, so the app doesn't re-gate the add on the wizard's known-spell
    # list the way it does for the permanent summons below.
    if req_spell and not info.get("temporary"):
        if req_spell not in known_spell_names(wb):
            return False, f"{info['name']} can only be summoned with the {req_spell} spell — your wizard doesn't know it."
        if req_spell == "Animal Companion" and has_animal_companion(wb):
            limit = animal_companion_limit(wb)
            if limit == 1:
                return False, (
                    "You may only have one Animal Companion at a time — hire an "
                    "apprentice to field a second (one per spellcaster)."
                )
            return False, f"You may only have {limit} Animal Companions at a time (one per spellcaster)."
    if info.get("temporary"):
        temp_count = sum(
            1 for s in active_soldiers(wb)
            if SOLDIERS.get(s.get("type_key", ""), {}).get("temporary")
        )
        if temp_count >= TEMPORARY_MEMBER_LIMIT:
            return False, f"You may only have {TEMPORARY_MEMBER_LIMIT} temporary members (raised zombies/summoned demons combined) on the table at once."
    if not info.get("temporary"):
        cap = expansions.max_soldiers(wb)
        if soldier_count(wb) >= cap:
            return False, f"Soldier limit reached ({cap})."
        spec_cap = expansions.max_specialists(wb)
        if info["category"] == "specialist" and specialist_count(wb) >= spec_cap:
            return False, f"Specialist limit reached ({spec_cap})."
    cost = expansions.soldier_cost(wb, info, type_key)
    if wb.get("gold", 0) < cost:
        return False, f"Not enough gold (need {cost} gc, have {wb.get('gold', 0)} gc)."

    leveling_fields = _new_soldier_leveling_fields(info)
    order_suffix = ""
    if order:
        order_info = KNIGHTLY_ORDER_BY_ID[order]
        stat = order_info["stat"]
        leveling_fields[stat] = leveling_fields[stat] + order_info["delta"]
        order_suffix = f", {order_info['name']}"

    soldier = {
        "id": uuid.uuid4().hex[:10],
        "type_key": type_key,
        "name": (name or _next_type_name(wb, type_key, info["name"])).strip(),
        "status": "active",
        "items": [],
        "mutations": [],
        "modifications": [],
        "permanent_injuries": [],
        "notes": "",
        "portrait": None,
        "knightly_order": order or None,
        **leveling_fields,
    }
    illusion_suffix = ""
    if illusion_info:
        soldier["fight"] = illusion_info.get("fight")
        soldier["shoot"] = illusion_info.get("shoot")
        soldier["will"] = illusion_info.get("will")
        soldier["health"] = 1
        soldier["move"] = illusion_info.get("move")
        soldier["armour"] = illusion_info.get("armour")
        soldier["illusion_source"] = illusion_source
        illusion_suffix = f", as a {illusion_info['name']}"
    wb["gold"] = int(wb.get("gold", 0)) - cost
    wb.setdefault("soldiers", []).append(soldier)
    wb.setdefault("history", []).append(
        {"when": _now(), "text": f"Hired {soldier['name']} ({info['name']}{order_suffix}{illusion_suffix}) for {cost} gc."}
    )
    return True, f"Hired {soldier['name']} ({info['name']}) for {cost} gc. Treasury: {wb['gold']} gc."


def remove_soldier(wb: dict, soldier_id: str, refund: bool = False) -> tuple[bool, str]:
    soldiers = wb.get("soldiers") or []
    for i, s in enumerate(soldiers):
        if s.get("id") == soldier_id:
            type_key = s.get("type_key", "")
            info = get_soldier(type_key) or {}
            cost = expansions.soldier_cost(wb, info, type_key)
            name = s.get("name", "Soldier")
            if refund and cost:
                wb["gold"] = int(wb.get("gold", 0)) + cost
                text = f"Dismissed {name} and refunded {cost} gc."
            else:
                text = f"Removed {name} from the roster."
            soldiers.pop(i)
            wb["soldiers"] = soldiers
            wb.setdefault("history", []).append({"when": _now(), "text": text})
            return True, text
    return False, "Soldier not found."


def dismiss_all_temporary_members(wb: dict) -> tuple[bool, str]:
    """Remove every Raise Zombie / Summon Demon member at once — the "the game
    ended, clear the table" button, rather than removing them one at a time."""
    soldiers = wb.get("soldiers") or []
    temp = [s for s in soldiers if SOLDIERS.get(s.get("type_key", ""), {}).get("temporary")]
    if not temp:
        return False, "No temporary members to dismiss."
    wb["soldiers"] = [s for s in soldiers if not SOLDIERS.get(s.get("type_key", ""), {}).get("temporary")]
    names = ", ".join(s.get("name", "?") for s in temp)
    text = f"Dismissed {len(temp)} temporary member(s): {names}."
    wb.setdefault("history", []).append({"when": _now(), "text": text})
    return True, text


def set_soldier_status(wb: dict, soldier_id: str, status: str) -> tuple[bool, str]:
    if status not in ("active", "injured", "dead"):
        return False, "Invalid status."
    for s in wb.get("soldiers") or []:
        if s.get("id") == soldier_id:
            s["status"] = status
            text = f"{s.get('name', 'Soldier')} marked {status}."
            wb.setdefault("history", []).append({"when": _now(), "text": text})
            return True, text
    return False, "Soldier not found."


def raise_revenant(wb: dict, soldier_id: str) -> tuple[bool, str]:
    """Reanimate a soldier with the Revenant spell (Thaw of the Lich Lord).

    The soldier keeps their own stats — which is why this is an action on an
    existing roster entry rather than a soldier type you hire. Only Will
    changes, dropping to +0. There is no limit on how many revenants a
    warband may field, and a revenant that dies again can be raised once more.

    Doesn't require the soldier to be flagged "dead" first — that status is
    purely optional bookkeeping, and most players just remove a dead soldier
    from the roster instead of flagging it, so gating on it would make the
    spell nearly impossible to use in practice.
    """
    if expansions.REVENANT_SPELL not in known_spell_names(wb):
        return False, "Your wizard doesn't know the Revenant spell."
    for s in wb.get("soldiers") or []:
        if s.get("id") != soldier_id:
            continue
        if s.get("revenant"):
            return False, "Already a revenant."
        cap = expansions.max_soldiers(wb)
        if soldier_count(wb) >= cap:
            return False, f"Soldier limit reached ({cap}); the revenant has nowhere to stand."
        cat = get_soldier(s.get("type_key", "")) or {}
        # Remembered so remove_revenant() can restore it exactly, rather than
        # falling back to the type's catalog Will (which would silently lose
        # any Soldier Leveling bonus this soldier had before being raised).
        s["_pre_revenant_will"] = s.get("will", cat.get("will", 0))
        s["status"] = "active"
        s["revenant"] = True
        s["will"] = expansions.REVENANT_WILL
        text = f"{s.get('name', 'Soldier')} was raised as a revenant (Will +0)."
        add_history(wb, text)
        return True, text
    return False, "Soldier not found."


def remove_revenant(wb: dict, soldier_id: str) -> tuple[bool, str]:
    """Undoes raise_revenant(): clears the revenant tag and restores whatever
    Will value the soldier had immediately beforehand. Leaves the soldier's
    status and everything else untouched."""
    for s in wb.get("soldiers") or []:
        if s.get("id") != soldier_id:
            continue
        if not s.get("revenant"):
            return False, "Not a revenant."
        cat = get_soldier(s.get("type_key", "")) or {}
        s["will"] = s.pop("_pre_revenant_will", cat.get("will", 0))
        s["revenant"] = False
        text = f"{s.get('name', 'Soldier')} is no longer a revenant."
        add_history(wb, text)
        return True, text
    return False, "Soldier not found."


def _mutation_gate(wb: dict) -> str | None:
    if "Grave Mutations" not in enabled_sources(wb):
        return "Grave Mutations is switched off; enable it under Additional Rules and Homerules first."
    return None


def _pick_mutation(number: int | None) -> tuple[dict | None, str | None]:
    """number=None rolls a random 1-1000 result; otherwise resolves that
    specific table entry. Returns (row, None) or (None, error_message)."""
    table = grave_mutations_by_number()
    if number is None:
        number = random.randint(1, 1000)
    row = table.get(number)
    if not row:
        return None, f"Invalid mutation number ({number}). Must be 1-1000."
    return row, None


def _apply_mutation_stat_delta(get_stat, set_stat, delta: dict | None) -> tuple[str, dict]:
    """Applies a mutation's stat_delta in place; returns a human-readable
    summary suffix like " (Armour +2, Health 14 -> 7)" (or "" if there's no
    delta) alongside a {stat: pre-mutation value} backup. The backup is
    recorded on the mutation itself (see _record_mutation) so a later
    remove_*_mutation can restore the exact prior value directly, instead of
    trying to invert a "multiply"/"round" op (e.g. "Health halved"), which
    isn't reliably reversible from the after-value alone. Values are floored
    at 0; homerule stat caps don't apply here — a mutation is a direct table
    event, not a spent level-up."""
    if not delta:
        return "", {}
    parts = []
    backup = {}
    for stat, op in delta.items():
        before = int(get_stat(stat))
        backup[stat] = before
        if "add" in op:
            after = before + op["add"]
        elif "multiply" in op:
            raw = before * op["multiply"]
            if op.get("round") == "up":
                after = math.ceil(raw)
            elif op.get("round") == "down":
                after = math.floor(raw)
            else:
                after = round(raw)
        elif "min" in op:
            # "raised to N if lower" (e.g. Projectile Weapon's Shoot) — never
            # lowers an already-higher stat, unlike "set".
            after = max(before, op["min"])
        else:
            after = op["set"]
        after = max(0, int(after))
        set_stat(stat, after)
        if "add" in op:
            sign = "+" if op["add"] >= 0 else ""
            parts.append(f"{stat.capitalize()} {sign}{op['add']}")
        else:
            parts.append(f"{stat.capitalize()} {before} -> {after}")
    return " (" + ", ".join(parts) + ")", backup


def _record_mutation(target: dict, row: dict, stat_suffix: str, who: str, stat_backup: dict | None = None) -> str:
    target.setdefault("mutations", []).append({
        "number": row["number"],
        "name": row["name"],
        "text": row["text"],
        "short": row["short"],
        "when": _now(),
        "stat_backup": stat_backup or {},
    })
    return f"{who} gained a grave mutation: {row['number']}. {row['name']}{stat_suffix}."


def _remove_mutation(mutations: list, index: int, set_stat) -> tuple[bool, dict | None]:
    """Pops mutations[index] and restores any stats it backed up via
    set_stat(stat, value). Returns (True, removed_dict) on success."""
    if not (0 <= index < len(mutations)):
        return False, None
    m = mutations.pop(index)
    for stat, value in (m.get("stat_backup") or {}).items():
        set_stat(stat, value)
    return True, m


def _mutation_target(wb: dict, kind: str, soldier_id: str | None = None):
    """Resolves 'wizard' | 'apprentice' | 'captain' | 'soldier' (+ soldier_id)
    to (entity, get_stat, set_stat, label) for the mutation add/remove
    helpers below (B2), or (None, None, None, error_message) if the target
    doesn't exist. Soldiers keep their stats flat on the entity dict itself
    (falling back to the catalog for anything a mutation hasn't touched yet),
    while wizard/apprentice/captain nest theirs under a "stats" dict seeded
    from that role's base stat block — a real structural difference, so this
    returns accessor closures rather than a single dict path for all four."""
    if kind == "wizard":
        wiz = wb.setdefault("wizard", {})
        stats = wiz.setdefault("stats", deepcopy(WIZARD_BASE))
        return wiz, (lambda k: int(stats.get(k, 0))), (lambda k, v: stats.__setitem__(k, v)), (wiz.get("name") or "your wizard")
    if kind == "apprentice":
        ap = wb.get("apprentice")
        if not ap:
            return None, None, None, "No apprentice hired."
        stats = ap.setdefault("stats", deepcopy(APPRENTICE_BASE))
        return ap, (lambda k: int(stats.get(k, 0))), (lambda k, v: stats.__setitem__(k, v)), (ap.get("name") or "your apprentice")
    if kind == "captain":
        cap = wb.get("captain")
        if not cap:
            return None, None, None, "No captain hired."
        stats = cap.setdefault("stats", deepcopy(CAPTAIN_BASE))
        return cap, (lambda k: int(stats.get(k, 0))), (lambda k, v: stats.__setitem__(k, v)), (cap.get("name") or "your captain")
    if kind == "soldier":
        for s in wb.get("soldiers") or []:
            if s.get("id") == soldier_id:
                cat = get_soldier(s.get("type_key", "")) or {}
                return s, (lambda k: s.get(k, cat.get(k, 0))), (lambda k, v: s.__setitem__(k, v)), s.get("name", "Soldier")
        return None, None, None, "Soldier not found."
    raise ValueError(f"Unknown mutation target kind: {kind!r}")


def add_mutation(
    wb: dict, kind: str, number: int | None = None, soldier_id: str | None = None
) -> tuple[bool, str]:
    err = _mutation_gate(wb)
    if err:
        return False, err
    entity, get_stat, set_stat, label = _mutation_target(wb, kind, soldier_id)
    if entity is None:
        return False, label  # label holds the not-found message in this branch
    row, err = _pick_mutation(number)
    if err:
        return False, err
    stat_suffix, backup = _apply_mutation_stat_delta(get_stat, set_stat, row["stat_delta"])
    # Sentence-initial here ("Your wizard gained..."), unlike remove_mutation's
    # "Removed your wizard's..." — capitalize only the fallback label ("your
    # wizard" -> "Your wizard"); a real character name is already cased right.
    text = _record_mutation(entity, row, stat_suffix, label[:1].upper() + label[1:], backup)
    if kind == "apprentice" and backup:
        # sync_apprentice() re-derives ap["stats"] from the wizard on every save,
        # which would otherwise wipe this mutation's effect (G1). Record it as a
        # {stat: delta} offset from the pre-mutation value so sync_apprentice can
        # re-apply it after deriving the base stats, instead of trying to replay
        # a possibly-non-idempotent multiply/round op.
        entity["mutations"][-1]["stat_offsets"] = {
            stat: get_stat(stat) - before for stat, before in backup.items()
        }
    add_history(wb, text)
    return True, text


def remove_mutation(
    wb: dict, kind: str, index: int, soldier_id: str | None = None
) -> tuple[bool, str]:
    entity, _get_stat, set_stat, label = _mutation_target(wb, kind, soldier_id)
    if entity is None:
        return False, label
    ok, m = _remove_mutation(entity.get("mutations") or [], index, set_stat)
    if not ok:
        return False, "Mutation not found."
    text = f"Removed {label}'s mutation: {m.get('name', '?')}."
    add_history(wb, text)
    return True, text


def add_soldier_mutation(wb: dict, soldier_id: str, number: int | None = None) -> tuple[bool, str]:
    return add_mutation(wb, "soldier", number, soldier_id)


def remove_soldier_mutation(wb: dict, soldier_id: str, index: int) -> tuple[bool, str]:
    return remove_mutation(wb, "soldier", index, soldier_id)


def add_wizard_mutation(wb: dict, number: int | None = None) -> tuple[bool, str]:
    return add_mutation(wb, "wizard", number)


def remove_wizard_mutation(wb: dict, index: int) -> tuple[bool, str]:
    return remove_mutation(wb, "wizard", index)


def add_apprentice_mutation(wb: dict, number: int | None = None) -> tuple[bool, str]:
    return add_mutation(wb, "apprentice", number)


def remove_apprentice_mutation(wb: dict, index: int) -> tuple[bool, str]:
    return remove_mutation(wb, "apprentice", index)


def add_captain_mutation(wb: dict, number: int | None = None) -> tuple[bool, str]:
    return add_mutation(wb, "captain", number)


def remove_captain_mutation(wb: dict, index: int) -> tuple[bool, str]:
    return remove_mutation(wb, "captain", index)


# Floors for the mandatory -1 modification penalty. Fight/Shoot/Will are
# deliberately absent: Frostgrave prints those negative and the catalog already
# carries some (thug, war hound, construct hound all have negative Will), and
# every standard construct has Will 0 — flooring at 0 would have made "take the
# penalty on Will" a free pass out of a mandatory cost. Move/Armour/Health floor
# at 1, where 0 or less is meaningless; with one modification per construct
# that's a safety rail, not a value a real stat line reaches.
MODIFICATION_PENALTY_FLOORS = {"move": 1, "armour": 1, "health": 1}


def _construct_modification_gate(wb: dict, soldier: dict | None) -> str | None:
    if "Fireheart" not in enabled_sources(wb):
        return "Fireheart is switched off; enable it under Additional Rules and Homerules first."
    if soldier is None:
        return "Soldier not found."
    if soldier.get("type_key") not in STANDARD_CONSTRUCT_TYPE_KEYS:
        return "Only standard small/medium/large constructs can take a Construct Modification."
    return None


def add_construct_modification(
    wb: dict, soldier_id: str, name: str, stat: str | None = None
) -> tuple[bool, str]:
    """Applies one Fireheart Construct Modification to a standard small/medium/
    large construct. The rulebook caps a construct at exactly one modification,
    so a second attempt is rejected rather than silently replacing the first.

    A handful of entries (Armour Plating, Construct Oil, ...) have a clean,
    unconditional numeric effect — that stat_delta (construct_modification_meta.json)
    is applied automatically here, the same way a grave mutation's is. The rest
    are situational (e.g. "+1 Fight vs. constructs") and stay text-only, same as
    every other soldier trait in this app.

    Every modification but the handful marked "No modification penalty" also
    costs a permanent -1 to one stat of the player's choice. Both the auto
    effect and the penalty are backed up into one {stat: prior value} dict on
    the record itself (same idiom as grave mutations' stat_delta backup), so
    remove_construct_modification can restore the soldier exactly."""
    soldier = next((s for s in wb.get("soldiers") or [] if s.get("id") == soldier_id), None)
    err = _construct_modification_gate(wb, soldier)
    if err:
        return False, err
    if soldier.get("modifications"):
        return False, f"{soldier.get('name', 'This construct')} already has a modification; a construct may only take one."
    row = next((m for m in construct_modifications() if m["name"] == name), None)
    if row is None:
        return False, f"Unknown modification ({name!r})."
    if soldier.get("type_key") in row["disallow_types"]:
        return False, f"{row['name']} cannot be taken by this size of construct."

    cat = get_soldier(soldier.get("type_key", "")) or {}
    get_stat = lambda k: int(soldier.get(k, cat.get(k, 0)))  # noqa: E731
    set_stat = lambda k, v: soldier.__setitem__(k, v)  # noqa: E731

    # _apply_mutation_stat_delta's own suffix is dropped — for the handful of
    # entries with an auto stat_delta, the rulebook text (row["text"]) already
    # says the same thing ("+1 Armour."), so echoing it again would be redundant.
    _effect_suffix, backup = _apply_mutation_stat_delta(get_stat, set_stat, row["stat_delta"])

    penalty_suffix = ""
    if not row["no_penalty"]:
        if stat not in ("move", "fight", "shoot", "armour", "will", "health"):
            # Undo the auto effect applied above before bailing out — this
            # function must be all-or-nothing from the caller's perspective.
            for s, v in backup.items():
                set_stat(s, v)
            return False, "Pick a stat to take the modification's -1 penalty."
        before = get_stat(stat)
        after = before - 1
        floor = MODIFICATION_PENALTY_FLOORS.get(stat)
        if floor is not None:
            after = max(floor, after)
        backup.setdefault(stat, before)
        set_stat(stat, after)
        penalty_suffix = f" ({stat.capitalize()} -1: {before} -> {after})"

    # Projectile Weapon: "small/medium constructs become specialist soldiers".
    # Large is already a specialist in the catalog, so only note/flag it when
    # this modification actually changes that construct's status — the flag
    # is read by count_specialists()/enrich_soldier() (see _soldier_is_specialist),
    # not enforced against the specialist cap here; a warband can end up over
    # cap and it's left to the player to resolve (see warband_limits/PDF banner).
    specialist_suffix = ""
    if row["forces_specialist"] and cat.get("category") != "specialist":
        soldier["forced_specialist"] = True
        specialist_suffix = " Now counts as a specialist soldier."

    short = f"{row['text']}{penalty_suffix}{specialist_suffix}"
    soldier.setdefault("modifications", []).append({
        "name": row["name"],
        "text": row["text"],
        "short": short,
        "when": _now(),
        "stat_backup": backup,
    })
    text = f"{soldier.get('name', 'Construct')} gained a Construct Modification: {row['name']}{penalty_suffix}{specialist_suffix}"
    add_history(wb, text)
    return True, text


def remove_construct_modification(wb: dict, soldier_id: str, index: int) -> tuple[bool, str]:
    soldier = next((s for s in wb.get("soldiers") or [] if s.get("id") == soldier_id), None)
    if soldier is None:
        return False, "Soldier not found."
    mods = soldier.get("modifications") or []
    if not (0 <= index < len(mods)):
        return False, "Modification not found."
    m = mods.pop(index)
    for stat, value in (m.get("stat_backup") or {}).items():
        soldier[stat] = value
    soldier.pop("forced_specialist", None)
    text = f"Removed {soldier.get('name', 'Construct')}'s Construct Modification: {m.get('name', '?')}."
    add_history(wb, text)
    return True, text


def _giant_blooded_gate(wb: dict, soldier: dict | None) -> str | None:
    hr = wb.get("homerules") or {}
    if "Blood Legacy" not in enabled_sources(wb) or not hr.get("giant_blooded_enabled"):
        return (
            "Giant-Blooded needs Blood Legacy and its own homerule switched on "
            "under Additional Rules and Homerules first."
        )
    if soldier is None:
        return "Soldier not found."
    if soldier.get("type_key") not in giant_blooded_eligible_type_keys():
        return (
            "Only an ordinary Core Rules standard/specialist soldier can be Giant-Blooded "
            "(not animals, demons, constructs or undead)."
        )
    return None


def set_soldier_giant_blooded(wb: dict, soldier_id: str, fitted: bool) -> tuple[bool, str]:
    """Blood Legacy's Giant-Blooded modification (Chapter Three): +50gc,
    -1 Move, -2 Will, +2 Health, and the Giant-Blooded trait, declared for one
    soldier in the warband. The book allows only one Giant-Blooded soldier per
    warband, so this is exposed as a single global picker (choose which
    hired soldier gets it) gated behind one homerule toggle, rather than a
    "make Giant-Blooded" button repeated on every soldier's row.

    Reverses the stat changes exactly on removal via a backup dict on the
    soldier record itself — same idiom as add_construct_modification's
    stat_backup. The 50gc fee isn't refunded on removal (declared/paid once,
    same as the apprentice-hiring fee unless a refund is explicitly asked for)."""
    soldiers = wb.get("soldiers") or []
    soldier = next((s for s in soldiers if s.get("id") == soldier_id), None)
    err = _giant_blooded_gate(wb, soldier)
    if err:
        return False, err
    already = bool(soldier.get("giant_blooded"))
    if fitted == already:
        return False, "Already in that state."
    if fitted:
        other = next(
            (s for s in soldiers if s.get("giant_blooded") and s.get("id") != soldier_id), None
        )
        if other:
            return False, f"{other.get('name', 'Another soldier')} is already Giant-Blooded; only one per warband."
        if int(wb.get("gold", 0)) < GIANT_BLOODED_COST:
            return False, f"Need {GIANT_BLOODED_COST} gc for Giant-Blooded."
        cat = get_soldier(soldier.get("type_key", "")) or {}
        get_stat = lambda k: int(soldier.get(k, cat.get(k, 0)))  # noqa: E731
        set_stat = lambda k, v: soldier.__setitem__(k, v)  # noqa: E731
        backup = {}
        parts = []
        for stat, delta in GIANT_BLOODED_STAT_DELTA.items():
            before = get_stat(stat)
            after = before + delta
            backup[stat] = before
            set_stat(stat, after)
            parts.append(f"{stat.capitalize()} {before} -> {after}")
        wb["gold"] = int(wb.get("gold", 0)) - GIANT_BLOODED_COST
        soldier["giant_blooded"] = True
        soldier["giant_blooded_backup"] = backup
        text = (
            f"{soldier.get('name', 'Soldier')} became Giant-Blooded for {GIANT_BLOODED_COST}gc "
            f"({', '.join(parts)})."
        )
    else:
        backup = soldier.pop("giant_blooded_backup", {}) or {}
        for stat, value in backup.items():
            soldier[stat] = value
        soldier["giant_blooded"] = False
        text = f"{soldier.get('name', 'Soldier')} is no longer Giant-Blooded."
    add_history(wb, text)
    return True, text


def add_permanent_injury(
    wb: dict, kind: str, injury_id: str, soldier_id: str | None = None
) -> tuple[bool, str]:
    """Records a Core Rules Permanent Injury (Chapter Three, page 77) on the
    wizard/apprentice/captain/soldier — the outcome of a "Permanent Injury"
    result on the Spellcaster Survival Table, applied here by the player after
    making that roll at the table (this app doesn't roll it for you).

    Reuses _mutation_target's (entity, get_stat, set_stat, label) resolution —
    the same four roles can suffer one. A clean, unconditional stat penalty
    (Lost Toes, Crushed Arm, ...) is applied automatically via stat_delta, the
    same idiom as Grave Mutations/Construct Modifications; Niggling Injury/
    Smashed Jaw/Lost Eye stay text-only, since their effects are per-game
    upkeep or situational, not a permanent stat-line change. Each injury may
    be suffered up to its max_stacks times (2, per the rulebook) before the
    book says "any further result must be re-rolled"."""
    entity, get_stat, set_stat, label = _mutation_target(wb, kind, soldier_id)
    if entity is None:
        return False, label
    row = PERMANENT_INJURY_BY_ID.get(injury_id)
    if row is None:
        return False, f"Unknown permanent injury ({injury_id!r})."
    existing = [r for r in entity.get("permanent_injuries") or [] if r.get("id") == injury_id]
    if (
        "Fireheart" in enabled_sources(wb)
        and kind in PROSTHETIC_ELIGIBLE_KINDS
        and row.get("prosthetic_eligible")
        and any(r.get("prosthetic") for r in existing)
    ):
        text = (
            f"{label[:1].upper() + label[1:]} already has an Animated Prosthetic fitted for {row['name']} — "
            "per Fireheart, suffering it again becomes Badly Wounded instead of a second copy of the injury "
            "(no additional stat penalty applied; record the Badly Wounded result as normal)."
        )
        add_history(wb, text)
        return True, text
    max_stacks = row.get("max_stacks", 1)
    if len(existing) >= max_stacks:
        return False, (
            f"{label} has already suffered {row['name']} {max_stacks} time(s) — "
            "the rulebook says any further result must be re-rolled."
        )
    stat_suffix, backup = _apply_mutation_stat_delta(get_stat, set_stat, row.get("stat_delta"))
    entity.setdefault("permanent_injuries", []).append({
        "id": row["id"],
        "name": row["name"],
        "text": row["text"],
        "short": row["text"],
        "when": _now(),
        "stat_backup": backup,
    })
    text = f"{label[:1].upper() + label[1:]} suffered a permanent injury: {row['name']}{stat_suffix}."
    add_history(wb, text)
    return True, text


def remove_permanent_injury(
    wb: dict, kind: str, index: int, soldier_id: str | None = None
) -> tuple[bool, str]:
    """Removes one recorded permanent injury (e.g. healed by Miraculous
    Cure), restoring any stat it had backed up."""
    entity, _get_stat, set_stat, label = _mutation_target(wb, kind, soldier_id)
    if entity is None:
        return False, label
    injuries = entity.get("permanent_injuries") or []
    if not (0 <= index < len(injuries)):
        return False, "Permanent injury not found."
    inj = injuries.pop(index)
    for stat, value in (inj.get("stat_backup") or {}).items():
        set_stat(stat, value)
    text = f"Removed {label}'s permanent injury: {inj.get('name', '?')}."
    add_history(wb, text)
    return True, text


PROSTHETIC_ELIGIBLE_KINDS = {"wizard", "apprentice", "captain"}


def set_permanent_injury_prosthetic(
    wb: dict, kind: str, index: int, fitted: bool, soldier_id: str | None = None
) -> tuple[bool, str]:
    """Fireheart's Animated Prosthetics: a spellcaster/apprentice/captain (not
    an ordinary soldier) with Lost Toes, Smashed Leg, Crushed Arm or Lost
    Fingers may cast Animate Construct to graft a replacement limb, removing
    the stat penalty while the injury itself stays on record (10gc upkeep
    after every game to keep it fitted, or a fresh casting — this app doesn't
    track per-game upkeep for anything, same as Niggling Injury above, so
    that cost is left to the player). Reverses the toggle by re-applying the
    exact delta it removed, not by snapshotting an absolute stat value — so it
    composes correctly regardless of how many other injuries/mutations are
    stacked on the same stat."""
    if "Fireheart" not in enabled_sources(wb):
        return False, "Fireheart is switched off; enable it under Additional Rules and Homerules first."
    if kind not in PROSTHETIC_ELIGIBLE_KINDS:
        return False, "Only a wizard, apprentice or captain can be fitted with an Animated Prosthetic."
    entity, get_stat, set_stat, label = _mutation_target(wb, kind, soldier_id)
    if entity is None:
        return False, label
    injuries = entity.get("permanent_injuries") or []
    if not (0 <= index < len(injuries)):
        return False, "Permanent injury not found."
    inj = injuries[index]
    row = PERMANENT_INJURY_BY_ID.get(inj.get("id"))
    if not row or not row.get("prosthetic_eligible"):
        return False, f"{row['name'] if row else 'This injury'} has no stat penalty an Animated Prosthetic can replace."
    already = bool(inj.get("prosthetic"))
    if fitted == already:
        return False, "Already in that state."
    delta = row.get("stat_delta") or {}
    parts = []
    if fitted:
        # Undo the original penalty: add back the same magnitude it removed.
        for stat, op in delta.items():
            amount = -int(op.get("add", 0))
            set_stat(stat, get_stat(stat) + amount)
            parts.append(f"{stat.capitalize()} +{amount}" if amount >= 0 else f"{stat.capitalize()} {amount}")
        inj["prosthetic"] = True
        verb = "fitted with an Animated Prosthetic for"
    else:
        # Re-apply the original penalty (prosthetic removed/failed upkeep).
        for stat, op in delta.items():
            amount = int(op.get("add", 0))
            set_stat(stat, get_stat(stat) + amount)
            parts.append(f"{stat.capitalize()} {amount}" if amount < 0 else f"{stat.capitalize()} +{amount}")
        inj["prosthetic"] = False
        verb = "no longer has a prosthetic for"
    suffix = " (" + ", ".join(parts) + ")" if parts else ""
    text = f"{label[:1].upper() + label[1:]} is {verb} {row['name']}{suffix}."
    add_history(wb, text)
    return True, text


def add_soldier_permanent_injury(wb: dict, soldier_id: str, injury_id: str) -> tuple[bool, str]:
    hr = wb.setdefault("homerules", default_homerules())
    if not hr.get("soldier_permanent_injuries_enabled"):
        return False, (
            "Ordinary soldiers can't take permanent injuries by default — the Permanent "
            "Injury Table is written for the wizard/apprentice/captain's Survival Roll. "
            "Enable this under Homerules (Soldier Leveling) if your group plays it "
            "differently."
        )
    return add_permanent_injury(wb, "soldier", injury_id, soldier_id)


def remove_soldier_permanent_injury(wb: dict, soldier_id: str, index: int) -> tuple[bool, str]:
    return remove_permanent_injury(wb, "soldier", index, soldier_id)


def add_wizard_permanent_injury(wb: dict, injury_id: str) -> tuple[bool, str]:
    return add_permanent_injury(wb, "wizard", injury_id)


def remove_wizard_permanent_injury(wb: dict, index: int) -> tuple[bool, str]:
    return remove_permanent_injury(wb, "wizard", index)


def add_apprentice_permanent_injury(wb: dict, injury_id: str) -> tuple[bool, str]:
    return add_permanent_injury(wb, "apprentice", injury_id)


def remove_apprentice_permanent_injury(wb: dict, index: int) -> tuple[bool, str]:
    return remove_permanent_injury(wb, "apprentice", index)


def add_captain_permanent_injury(wb: dict, injury_id: str) -> tuple[bool, str]:
    return add_permanent_injury(wb, "captain", injury_id)


def remove_captain_permanent_injury(wb: dict, index: int) -> tuple[bool, str]:
    return remove_permanent_injury(wb, "captain", index)


def hire_apprentice(wb: dict, name: str = "") -> tuple[bool, str]:
    if wb.get("apprentice"):
        return False, "Warband already has an apprentice."
    wschool = (wb.get("wizard") or {}).get("school")
    if wschool == "Fire Giant":
        return False, "A Fire Giant Wizard has no apprentice (Blood Legacy)."
    if wschool == "Vampire":
        return False, "A Vampire Wizard has no apprentice (Blood Legacy)."
    if int(wb.get("gold", 0)) < APPRENTICE_COST:
        return False, f"Need {APPRENTICE_COST} gc for an apprentice."
    wb["gold"] = int(wb["gold"]) - APPRENTICE_COST
    wizard_name = (wb.get("wizard") or {}).get("name", "Wizard")
    wb["apprentice"] = empty_apprentice(name or f"{wizard_name}'s Apprentice")
    sync_apprentice(wb)
    text = f"Hired apprentice for {APPRENTICE_COST} gc."
    wb.setdefault("history", []).append({"when": _now(), "text": text})
    return True, text


def dismiss_apprentice(wb: dict, refund: bool = False) -> tuple[bool, str]:
    if not wb.get("apprentice"):
        return False, "No apprentice to dismiss."
    if refund:
        wb["gold"] = int(wb.get("gold", 0)) + APPRENTICE_COST
        text = f"Dismissed apprentice and refunded {APPRENTICE_COST} gc."
    else:
        text = "Dismissed apprentice (no refund)."
    wb["apprentice"] = None
    wb.setdefault("history", []).append({"when": _now(), "text": text})
    return True, text


def _parse_stat_caps(form: "ImmutableMultiDict", prefix: str, current: dict) -> dict:
    """Parse the 4-stat {limit, unlimited} grid submitted as
    {prefix}_cap_{stat}_limit / {prefix}_cap_{stat}_unlimited."""
    caps = {}
    for stat in LEVELUP_STATS:
        cur = current.get(stat) or {"limit": 0, "unlimited": False}
        limit = int(form.get(f"{prefix}_cap_{stat}_limit") or cur.get("limit", 0))
        unlimited = form.get(f"{prefix}_cap_{stat}_unlimited") == "on"
        caps[stat] = {"limit": max(0, limit), "unlimited": unlimited}
    return caps


def _validate_tricks(tricks: list[str] | None, required: int) -> tuple[bool, str]:
    """Shared validation for the starting-trick picker used by hire_captain and
    promote_soldier_to_captain: no duplicates, all ids known, exact count."""
    tricks = tricks or []
    if len(set(tricks)) != len(tricks) or any(t not in CAPTAIN_TRICK_IDS for t in tricks):
        return False, "Invalid trick selection."
    if len(tricks) != required:
        return False, f"Pick exactly {required} tricks (got {len(tricks)})."
    return True, ""


def update_homerules(wb: dict, form: "ImmutableMultiDict") -> tuple[bool, str]:
    """Parse and apply the per-warband homerule settings form."""
    hr = wb.setdefault("homerules", default_homerules())
    try:
        new_hr = {
            "max_soldiers": max(1, int(form.get("max_soldiers") or hr.get("max_soldiers", MAX_SOLDIERS))),
            "max_specialists": max(
                0, int(form.get("max_specialists") or hr.get("max_specialists", MAX_SPECIALISTS))
            ),
            "captain_mode": (
                form.get("captain_mode")
                if form.get("captain_mode") in CAPTAIN_MODE_OPTIONS
                else hr["captain_mode"]
            ),
            "captain_hiring_cost": int(form.get("captain_hiring_cost") or hr["captain_hiring_cost"]),
            "captain_item_slots": int(form.get("captain_item_slots") or hr["captain_item_slots"]),
            "captain_base_stats": {
                "move": int(form.get("captain_base_move") or hr["captain_base_stats"]["move"]),
                "fight": int(form.get("captain_base_fight") or hr["captain_base_stats"]["fight"]),
                "shoot": int(form.get("captain_base_shoot") or hr["captain_base_stats"]["shoot"]),
                "armour": int(form.get("captain_base_armour") or hr["captain_base_stats"]["armour"]),
                "will": int(form.get("captain_base_will") or hr["captain_base_stats"]["will"]),
                "health": int(form.get("captain_base_health") or hr["captain_base_stats"]["health"]),
            },
            "captain_bonus_choice_enabled": form.get("captain_bonus_choice_enabled") == "on",
            "captain_stat_caps": _parse_stat_caps(form, "captain", hr["captain_stat_caps"]),
            "captain_stat_absolute_limits": {
                stat: int(
                    form.get(f"captain_absolute_limit_{stat}")
                    or hr.get("captain_stat_absolute_limits", CAPTAIN_STAT_ABSOLUTE_LIMITS)[stat]
                )
                for stat in ("move", "fight", "shoot", "will", "health")
            },
            "captain_max_level": int(form.get("captain_max_level") or hr["captain_max_level"]),
            "captain_mind_control": (
                form.get("captain_mind_control")
                if form.get("captain_mind_control") in CAPTAIN_MIND_CONTROL_OPTIONS
                else hr["captain_mind_control"]
            ),
            "captain_starting_tricks": int(
                form.get("captain_starting_tricks") or hr["captain_starting_tricks"]
            ),
            "soldier_leveling_enabled": form.get("soldier_leveling_enabled") == "on",
            "soldier_leveling_animal_companions": form.get("soldier_leveling_animal_companions") == "on",
            "soldier_leveling_constructs": form.get("soldier_leveling_constructs") == "on",
            "soldier_permanent_injuries_enabled": form.get("soldier_permanent_injuries_enabled") == "on",
            "soldier_max_levels": int(form.get("soldier_max_levels") or hr["soldier_max_levels"]),
            "soldier_stat_caps": _parse_stat_caps(form, "soldier", hr["soldier_stat_caps"]),
            "promote_captain_cost": int(
                form.get("promote_captain_cost") or hr["promote_captain_cost"]
            ),
            "promote_captain_bonus": {
                stat: int(form.get(f"promote_bonus_{stat}") or hr["promote_captain_bonus"][stat])
                for stat in LEVELUP_STATS
            },
            "promote_captain_bonus_choice_enabled": (
                form.get("promote_captain_bonus_choice_enabled") == "on"
            ),
            "promote_captain_item_slots": int(
                form.get("promote_captain_item_slots") or hr["promote_captain_item_slots"]
            ),
            "promote_captain_tricks": int(
                form.get("promote_captain_tricks")
                or hr.get("promote_captain_tricks", PROMOTE_CAPTAIN_TRICKS)
            ),
            "promote_captain_specialist_only": form.get("promote_captain_specialist_only") == "on",
            "enabled_sources": {
                book: form.get(f"source_enabled_{slug}") == "on"
                for slug, book in SOURCE_BOOK_BY_SLUG.items()
            },
            "pentangle_schools_playable": form.get("pentangle_schools_playable") == "on",
            "fire_giant_wizard_playable": form.get("fire_giant_wizard_playable") == "on",
            "vampire_wizard_playable": form.get("vampire_wizard_playable") == "on",
            "giant_blooded_enabled": form.get("giant_blooded_enabled") == "on",
            "edition2_soldier_costs": form.get("edition2_soldier_costs") == "on",
            "spellcaster_magazine_soldiers": form.get("spellcaster_magazine_soldiers") == "on",
            "knightly_orders_enabled": form.get("knightly_orders_enabled") == "on",
            "hlw_specialist_allowance": form.get("hlw_specialist_allowance") == "on",
            "hlw_item_slots": form.get("hlw_item_slots") == "on",
            "hlw_max_health": form.get("hlw_max_health") == "on",
            "hlw_casting_min": form.get("hlw_casting_min") == "on",
            "hlw_alt_xp": form.get("hlw_alt_xp") == "on",
            "wizard_level_cap": {
                "limit": max(
                    0,
                    int(
                        form.get("wizard_level_cap_limit")
                        or hr.get("wizard_level_cap", {}).get("limit", MAX_WIZARD_LEVEL)
                    ),
                ),
                "unlimited": form.get("wizard_level_cap_unlimited") == "on",
            },
            "wizard_stat_limits": {
                stat: max(
                    1,
                    int(
                        form.get(f"wizard_max_{stat}")
                        or hr.get("wizard_stat_limits", WIZARD_STAT_LIMITS_DEFAULT)[stat]
                    ),
                )
                for stat in ("fight", "shoot", "will", "health")
            },
            "wizard_min_casting_number": max(
                1,
                int(
                    form.get("wizard_min_casting_number")
                    or hr.get("wizard_min_casting_number", WIZARD_MIN_CASTING_NUMBER_DEFAULT)
                ),
            ),
        }
    except (TypeError, ValueError):
        return False, "Invalid homerule value."
    if new_hr["captain_item_slots"] < 1:
        return False, "Captain item slots must be at least 1."
    if new_hr["promote_captain_item_slots"] < 1:
        return False, "Promoted captain item slots must be at least 1."
    if new_hr["soldier_max_levels"] < 0:
        return False, "Soldier max levels cannot be negative."
    if new_hr["captain_max_level"] < 0:
        return False, "Captain max level cannot be negative."
    if new_hr["captain_starting_tricks"] < 0:
        return False, "Captain starting tricks cannot be negative."
    if new_hr["captain_starting_tricks"] > len(CAPTAIN_TRICKS):
        return False, f"Captain starting tricks cannot exceed {len(CAPTAIN_TRICKS)} (the number of known tricks)."
    if new_hr["promote_captain_tricks"] < 0:
        return False, "Tricks on promotion cannot be negative."
    if new_hr["promote_captain_tricks"] > len(CAPTAIN_TRICKS):
        return False, f"Tricks on promotion cannot exceed {len(CAPTAIN_TRICKS)} (the number of known tricks)."
    # Merge onto defaults + existing values so any homerule key not (yet) handled
    # by the literal above — e.g. one added after this warband was created —
    # survives the save instead of being silently dropped.
    wb["homerules"] = {**default_homerules(), **hr, **new_hr}
    if wb.get("captain"):
        cap = wb["captain"]
        n = (
            new_hr["promote_captain_item_slots"]
            if cap.get("origin") == "promoted"
            else new_hr["captain_item_slots"]
        )
        cap["item_slots"] = normalize_item_slots(cap.get("item_slots"), n)
    add_history(wb, "Updated homerule settings.")
    return True, "Homerules saved."


def hire_captain(
    wb: dict,
    name: str = "",
    extra_stat: str | None = None,
    tricks: list[str] | None = None,
) -> tuple[bool, str]:
    hr = wb.setdefault("homerules", default_homerules())
    if hr.get("captain_mode") not in ("hire", "both"):
        return False, "Hiring a captain is not enabled for this warband (see Homerules)."
    if "The Frostgrave Folio" not in enabled_sources(wb):
        return False, "The Captain is from The Frostgrave Folio; enable that source under Additional Rules and Homerules first."
    if wb.get("captain"):
        return False, "Warband already has a captain."
    n_tricks = int(hr.get("captain_starting_tricks", CAPTAIN_STARTING_TRICKS))
    ok, msg = _validate_tricks(tricks, n_tricks)
    if not ok:
        return False, msg
    # A Captain occupies both a soldier slot and a specialist slot, same as any
    # specialist soldier would — check both caps before adding one (wb has no
    # captain yet at this point, so these counts are the pre-hire baseline).
    soldier_cap = expansions.max_soldiers(wb)
    if soldier_count(wb) >= soldier_cap:
        return False, f"Soldier limit reached ({soldier_cap})."
    spec_cap = expansions.max_specialists(wb)
    if specialist_count(wb) >= spec_cap:
        return False, f"Specialist limit reached ({spec_cap})."
    cost = int(hr.get("captain_hiring_cost", CAPTAIN_HIRING_COST))
    if int(wb.get("gold", 0)) < cost:
        return False, f"Need {cost} gc for a captain."
    wb["gold"] = int(wb["gold"]) - cost
    cap = empty_captain(name or "Captain", hr)
    cap["known_tricks"] = list(tricks or [])
    if hr.get("captain_bonus_choice_enabled") and extra_stat in LEVELUP_STATS:
        limits = hr.get("captain_stat_absolute_limits") or CAPTAIN_STAT_ABSOLUTE_LIMITS
        current = int(cap["stats"].get(extra_stat, 0))
        limit = limits.get(extra_stat)
        if limit is None or current < limit:
            cap["stats"][extra_stat] = _apply_stat_absolute_limit(current, bonus_choice_amount(extra_stat), limit)
            cap["bonus_extra_stat"] = extra_stat
    wb["captain"] = cap
    text = f"Hired captain for {cost} gc (starting equipment free)."
    add_history(wb, text)
    return True, text


def dismiss_captain(wb: dict, refund: bool = False) -> tuple[bool, str]:
    cap = wb.get("captain")
    if not cap:
        return False, "No captain to dismiss."
    hr = wb.setdefault("homerules", default_homerules())
    if cap.get("origin") == "promoted":
        cost = int(hr.get("promote_captain_cost", PROMOTE_CAPTAIN_COST))
    else:
        cost = int(hr.get("captain_hiring_cost", CAPTAIN_HIRING_COST))
    if refund:
        wb["gold"] = int(wb.get("gold", 0)) + cost
        text = f"Dismissed captain and refunded {cost} gc."
    else:
        text = "Dismissed captain (no refund)."
    wb["captain"] = None
    add_history(wb, text)
    return True, text


def _apply_xp_delta(
    entity: dict,
    amount: int,
    reverse_one_level,
    overall_max: int | None,
    label: str,
    per_level: int = XP_PER_LEVEL,
    xp_level_cap: int = MAX_WIZARD_LEVEL,
) -> tuple[bool, str]:
    """Shared XP add/remove logic for Wizard, Captain, and Soldier. A negative amount
    removes XP (clamped so the total never drops below 0). If that leaves the recorded
    level higher than what the new XP total actually earns, auto-reverses the most
    recent level-up(s) — via `reverse_one_level` (each call also logs its own history
    entry) — until the level catches back up.

    `per_level` is the XP a level costs; only the wizard ever varies it (a Lich
    levels at 150 instead of 100). Captains and soldiers keep the default.
    `xp_level_cap` is the level ceiling XP alone can earn — separate from
    `overall_max`, which additionally clamps for Captain/Soldier's own max-level
    homerule. Only the wizard ever raises this (Blood Legacy's High-Level
    Wizards rules reference levels past the normal ceiling)."""
    if amount == 0:
        return False, "Enter a non-zero XP amount."
    old_xp = int(entity.get("xp", 0))
    new_xp = max(0, old_xp + amount)
    entity["xp"] = new_xp
    actual = new_xp - old_xp
    sign = "+" if actual >= 0 else ""
    msg = f"{label} {sign}{actual} XP (total {new_xp})."

    earned = level_from_xp(new_xp, per_level, xp_level_cap)
    if overall_max is not None:
        earned = min(earned, overall_max)
    lost = 0
    while int(entity.get("level", 0)) > earned:
        ok, _ = reverse_one_level()
        if not ok:
            break
        lost += 1
    if lost:
        msg += f" Lost {lost} level-up{'s' if lost != 1 else ''} (now level {entity.get('level', 0)})."
    return True, msg


def _pending_level_check(
    entity: dict,
    overall_max: int | None,
    label: str,
    per_level: int = XP_PER_LEVEL,
    xp_level_cap: int = MAX_WIZARD_LEVEL,
) -> tuple[bool, str]:
    """Shared earned-XP / max-level guard for any level-up spend (stat or trick).

    `xp_level_cap` mirrors the same parameter on `_apply_xp_delta` — the level
    ceiling XP alone can earn — and must be passed through by any caller that
    doesn't also rely on `overall_max` to mask it (see G7)."""
    xp = int(entity.get("xp", 0))
    level = int(entity.get("level", 0))
    earned = level_from_xp(xp, per_level, xp_level_cap)
    if level >= earned:
        return False, f"No pending level-ups (level {level}, XP {xp}). Earn more XP first."
    if overall_max is not None and level >= overall_max:
        return False, f"{label} has reached the max level ({overall_max})."
    return True, ""


def _apply_stat_absolute_limit(current: int, bonus: int, limit: int | None) -> int:
    """Add `bonus` to `current`, clamped so the result never exceeds `limit`. If
    `current` is already at or over the limit, the bonus contributes nothing —
    an existing higher value (e.g. from a promoted soldier's own prior leveling,
    or the class base stats) is never reduced, only further increases blocked."""
    if limit is None:
        return current + bonus
    if current >= limit:
        return current
    return min(current + bonus, limit)


def _spend_stat_level_up(
    entity: dict,
    choice: str,
    stat_caps: dict,
    overall_max: int | None,
    get_stat,
    set_stat,
    label: str,
) -> tuple[bool, str]:
    """Shared flat-XP level-up spend logic for Captain and Soldier (identical mechanics;
    the Wizard keeps its own bespoke apply_level_up because of spell choices)."""
    ok, msg = _pending_level_check(entity, overall_max, label)
    if not ok:
        return False, msg
    level = int(entity.get("level", 0))
    if choice not in LEVELUP_STATS:
        return False, "Invalid level-up choice."
    cap = stat_caps.get(choice) or {"limit": 0, "unlimited": False}
    counts = entity.setdefault("levelup_counts", {s: 0 for s in LEVELUP_STATS})
    counts.setdefault(choice, 0)
    if not cap.get("unlimited") and counts[choice] >= int(cap.get("limit", 0)):
        return False, f"{label} has reached the level-up limit for {choice.capitalize()}."
    set_stat(choice, get_stat(choice) + 1)
    counts[choice] += 1
    entity["level"] = level + 1
    entity.setdefault("level_history", []).append(
        {"level": level + 1, "choice": choice, "detail": f"+1 {choice.capitalize()}", "when": _now()}
    )
    return True, f"{label} +1 {choice.capitalize()} (level {level + 1})."


def _reverse_last_stat_level_up(entity: dict, get_stat, set_stat, label: str) -> tuple[bool, str]:
    history = entity.setdefault("level_history", [])
    if not history:
        return False, f"No {label} level-ups to reverse."
    entry = history.pop()
    choice = entry.get("choice")
    if choice not in LEVELUP_STATS:
        history.append(entry)
        return False, f"Cannot reverse unknown {label} level-up."
    set_stat(choice, get_stat(choice) - 1)
    counts = entity.setdefault("levelup_counts", {s: 0 for s in LEVELUP_STATS})
    counts[choice] = max(0, int(counts.get(choice, 0)) - 1)
    entity["level"] = max(0, int(entity.get("level", 1)) - 1)
    return True, f"Reversed {label} level-up: {entry.get('detail', choice)}."


def apply_captain_level_up(wb: dict, choice: str) -> tuple[bool, str]:
    """Spend one pending captain level-up (flat 100 XP/level, same as the wizard);
    per-stat caps are homerule-editable (limit + unlimited toggle)."""
    cap = wb.get("captain")
    if not cap:
        return False, "No captain hired."
    hr = wb.setdefault("homerules", default_homerules())
    ok, msg = _spend_stat_level_up(
        cap,
        choice,
        hr.get("captain_stat_caps") or CAPTAIN_STAT_CAPS,
        int(hr.get("captain_max_level", CAPTAIN_MAX_LEVEL)),
        get_stat=lambda s: int(cap["stats"].get(s, 0)),
        set_stat=lambda s, v: cap["stats"].__setitem__(s, v),
        label="Captain",
    )
    if ok:
        add_history(wb, msg)
    return ok, msg


def apply_captain_trick(wb: dict, trick_id: str) -> tuple[bool, str]:
    """Spend one pending captain level-up on learning a new trick instead of a stat
    point (FG1E Sellswords p.21: "he may select a new trick... he does not already
    have"). Purely descriptive — not mechanically simulated, same as Mind Control."""
    cap = wb.get("captain")
    if not cap:
        return False, "No captain hired."
    if trick_id not in CAPTAIN_TRICK_IDS:
        return False, "Invalid trick."
    hr = wb.setdefault("homerules", default_homerules())
    ok, msg = _pending_level_check(cap, int(hr.get("captain_max_level", CAPTAIN_MAX_LEVEL)), "Captain")
    if not ok:
        return False, msg
    known = cap.setdefault("known_tricks", [])
    if trick_id in known:
        return False, "Captain already knows this trick."
    level = int(cap.get("level", 0))
    known.append(trick_id)
    cap["level"] = level + 1
    name = CAPTAIN_TRICK_BY_ID[trick_id]["name"]
    cap.setdefault("level_history", []).append(
        {"level": level + 1, "choice": "trick", "trick_id": trick_id, "detail": f"New trick: {name}", "when": _now()}
    )
    text = f"Captain learned a new trick: {name} (level {level + 1})."
    add_history(wb, text)
    return True, text


def reverse_last_captain_level_up(wb: dict) -> tuple[bool, str]:
    cap = wb.get("captain")
    if not cap:
        return False, "No captain hired."
    history = cap.get("level_history") or []
    if history and history[-1].get("choice") == "trick":
        entry = history.pop()
        trick_id = entry.get("trick_id")
        known = cap.setdefault("known_tricks", [])
        if trick_id in known:
            known.remove(trick_id)
        cap["level"] = max(0, int(cap.get("level", 1)) - 1)
        msg = f"Reversed captain level-up: {entry.get('detail', trick_id)}."
        add_history(wb, msg)
        return True, msg
    ok, msg = _reverse_last_stat_level_up(
        cap,
        get_stat=lambda s: int(cap["stats"].get(s, 0)),
        set_stat=lambda s, v: cap["stats"].__setitem__(s, v),
        label="captain",
    )
    if ok:
        add_history(wb, msg)
    return ok, msg


def add_captain_xp(wb: dict, amount: int) -> tuple[bool, str]:
    cap = wb.get("captain")
    if not cap:
        return False, "No captain hired."
    hr = wb.setdefault("homerules", default_homerules())
    overall_max = int(hr.get("captain_max_level", CAPTAIN_MAX_LEVEL))
    ok, msg = _apply_xp_delta(cap, amount, lambda: reverse_last_captain_level_up(wb), overall_max, "Captain")
    if ok:
        add_history(wb, msg)
    return ok, msg


def _promotion_blocked_reason(type_key: str) -> str | None:
    """None if this soldier type may be promoted to Captain, else the reason
    it can't be — temporary members, Animal Companions, and any other
    spell-summoned/magical creature (constructs, Demonic Servant, ...) are
    never eligible, regardless of stats or specialist status."""
    info = SOLDIERS.get(type_key, {}) or {}
    if info.get("temporary"):
        return "Temporary members (raised/summoned for one game) can't be promoted to Captain."
    if type_key in animal_companion_type_keys():
        return "Animal Companions can't be promoted to Captain."
    # construct_hound is bought outright rather than summoned, but it's the
    # same creature as construct_hound_summoned — gating by acquisition path
    # would let one instance of "Construct Hound" promote and not the other.
    if type_key in construct_type_keys() or type_key in ("construct_hound", "war_hound"):
        return "Constructs and war hounds can't be promoted to Captain."
    if info.get("requires_spell"):
        return "Summoned creatures can't be promoted to Captain."
    return None


def promote_soldier_to_captain(
    wb: dict,
    soldier_id: str,
    extra_stat: str | None = None,
    tricks: list[str] | None = None,
) -> tuple[bool, str]:
    """Convert an active soldier into the warband's Captain (mutually exclusive with
    hiring — only one captain slot exists at a time)."""
    hr = wb.setdefault("homerules", default_homerules())
    if hr.get("captain_mode") not in ("promote", "both"):
        return False, "Promoting a captain is not enabled for this warband (see Homerules)."
    if "The Frostgrave Folio" not in enabled_sources(wb):
        return False, "The Captain is from The Frostgrave Folio; enable that source under Additional Rules and Homerules first."
    if wb.get("captain"):
        return False, "Warband already has a captain."
    # Promotion has its own trick allowance, separate from hiring's.
    n_tricks = int(hr.get("promote_captain_tricks", PROMOTE_CAPTAIN_TRICKS))
    ok, msg = _validate_tricks(tricks, n_tricks)
    if not ok:
        return False, msg
    soldiers = wb.get("soldiers") or []
    soldier = None
    idx = None
    for i, s in enumerate(soldiers):
        if s.get("id") == soldier_id:
            soldier, idx = s, i
            break
    if soldier is None:
        return False, "Soldier not found."
    if soldier.get("status") != "active":
        return False, "Only an active soldier can be promoted."
    blocked = _promotion_blocked_reason(soldier.get("type_key", ""))
    if blocked:
        return False, blocked
    if hr.get("promote_captain_specialist_only") and not _soldier_is_specialist(soldier):
        return False, "Only specialists may be promoted to Captain (see Homerules)."
    cost = int(hr.get("promote_captain_cost", PROMOTE_CAPTAIN_COST))
    if int(wb.get("gold", 0)) < cost:
        return False, f"Need {cost} gc to promote a captain."

    info = get_soldier(soldier.get("type_key", "")) or {}
    # The promoted soldier leaves the roster (a wash on the soldier-count cap —
    # one member out, the Captain in), but a Captain always counts as a
    # specialist regardless of what they were promoted from, so promoting a
    # non-specialist can still push the specialist count over the cap.
    spec_cap = expansions.max_specialists(wb)
    if not _soldier_is_specialist(soldier) and specialist_count(wb) >= spec_cap:
        return False, f"Specialist limit reached ({spec_cap})."
    # Soldiers don't normally persist move/armour at all (they're read from the
    # catalog at display time) until a mutation writes them — so all six stats
    # must fall back to the catalog the same way, or mutation-driven move/armour
    # changes are silently discarded on promotion while fight/shoot/will/health
    # changes are kept (G2).
    stats = {
        "move": int(soldier.get("move", info.get("move", 0)) or 0),
        "fight": int(soldier.get("fight", info.get("fight", 0)) or 0),
        "shoot": int(soldier.get("shoot", info.get("shoot", 0)) or 0),
        "armour": int(soldier.get("armour", info.get("armour", 0)) or 0),
        "will": int(soldier.get("will", info.get("will", 0)) or 0),
        "health": int(soldier.get("health", info.get("health", 0)) or 0),
    }
    # The promotion bonus package is always applied in full — it's defined by
    # the homerule, not a per-promotion player choice. Only the optional extra
    # +1 (gated by promote_captain_bonus_choice_enabled) is player-selectable.
    # Both are capped by the absolute stat limits, fixed bonus first, then the
    # chosen +1 — a stat already at/over its limit (e.g. from the soldier's own
    # prior leveling) keeps its higher value rather than being reduced.
    limits = hr.get("captain_stat_absolute_limits") or CAPTAIN_STAT_ABSOLUTE_LIMITS
    bonus = hr.get("promote_captain_bonus") or PROMOTE_CAPTAIN_BONUS
    for stat in LEVELUP_STATS:
        stats[stat] = _apply_stat_absolute_limit(stats.get(stat, 0), int(bonus.get(stat, 0)), limits.get(stat))
    applied_extra_stat = None
    if hr.get("promote_captain_bonus_choice_enabled") and extra_stat in LEVELUP_STATS:
        current = stats.get(extra_stat, 0)
        limit = limits.get(extra_stat)
        if limit is None or current < limit:
            stats[extra_stat] = _apply_stat_absolute_limit(current, bonus_choice_amount(extra_stat), limit)
            applied_extra_stat = extra_stat

    wb["gold"] = int(wb.get("gold", 0)) - cost
    n = int(hr.get("promote_captain_item_slots", PROMOTE_CAPTAIN_ITEM_SLOTS))
    name = soldier.get("name", "Captain")
    cap = {
        "name": name,
        "stats": stats,
        "bonus_extra_stat": applied_extra_stat,
        # Same default starting gear a hired captain gets (empty_captain()) —
        # a promoted soldier's own equipment doesn't carry over; the roster
        # slot it vacated is what gets refunded/removed, not its gear.
        "item_slots": _default_item_slots(CAPTAIN_DEFAULT_GEAR, n),
        "has_dagger": True,
        "notes": soldier.get("notes", ""),
        "portrait": soldier.get("portrait"),
        "portrait_source_name": soldier.get("portrait_source_name"),
        # Kept so a promoted captain who never uploaded a picture keeps showing
        # the default artwork of the soldier type they were promoted from.
        "type_key": soldier.get("type_key"),
        "xp": 0,
        "level": 0,
        "levelup_counts": {s: 0 for s in LEVELUP_STATS},
        "level_history": [],
        "origin": "promoted",
        "known_tricks": list(tricks or []),
        # Carried over rather than reset (G2) — a mutated soldier's grave
        # mutations, and the audit trail (stat_backup) needed to remove them
        # later, shouldn't vanish just because they were promoted. Permanent
        # injuries are real ongoing character history for the same reason.
        "mutations": deepcopy(soldier.get("mutations") or []),
        "permanent_injuries": deepcopy(soldier.get("permanent_injuries") or []),
    }
    wb["captain"] = cap
    soldiers.pop(idx)
    wb["soldiers"] = soldiers
    text = (
        f"Promoted {name} to Captain for {cost} gc "
        "(prior soldier XP/levels are folded into the new base stats, not carried as banked XP)."
    )
    add_history(wb, text)
    return True, text


def _soldier_leveling_blocked(hr: dict, type_key: str) -> str | None:
    """Reason a summoned creature can't level, or None if it's allowed to."""
    if type_key in animal_companion_type_keys() and not hr.get("soldier_leveling_animal_companions"):
        return "Animal companions can't level up for this warband (see Homerules)."
    if type_key in construct_type_keys() and not hr.get("soldier_leveling_constructs"):
        return "Constructs can't level up for this warband (see Homerules)."
    return None


def apply_soldier_level_up(wb: dict, soldier_id: str, choice: str) -> tuple[bool, str]:
    """Spend one pending soldier level-up. Requires the Soldier Leveling homerule."""
    hr = wb.setdefault("homerules", default_homerules())
    if not hr.get("soldier_leveling_enabled"):
        return False, "Soldier Leveling is not enabled for this warband (see Homerules)."
    for s in wb.get("soldiers") or []:
        if s.get("id") == soldier_id:
            blocked = _soldier_leveling_blocked(hr, s.get("type_key", ""))
            if blocked:
                return False, blocked
            ok, msg = _spend_stat_level_up(
                s,
                choice,
                hr.get("soldier_stat_caps") or SOLDIER_STAT_CAPS,
                int(hr.get("soldier_max_levels", SOLDIER_MAX_LEVELS)),
                get_stat=lambda st: int(s.get(st, 0) or 0),
                set_stat=lambda st, v: s.__setitem__(st, v),
                label=s.get("name", "Soldier"),
            )
            if ok:
                add_history(wb, msg)
            return ok, msg
    return False, "Soldier not found."


def reverse_last_soldier_level_up(wb: dict, soldier_id: str) -> tuple[bool, str]:
    for s in wb.get("soldiers") or []:
        if s.get("id") == soldier_id:
            ok, msg = _reverse_last_stat_level_up(
                s,
                get_stat=lambda st: int(s.get(st, 0) or 0),
                set_stat=lambda st, v: s.__setitem__(st, v),
                label=s.get("name", "Soldier"),
            )
            if ok:
                add_history(wb, msg)
            return ok, msg
    return False, "Soldier not found."


def apply_animal_companion_crit_bonus(wb: dict, soldier_id: str) -> tuple[bool, str]:
    """One-time +1 Health for an Animal Companion whose casting roll was a
    critical success (Spellcaster Magazine's Casting Roll Criticals) but whose
    player picked the normal +1 Health option rather than the White Gorilla."""
    for s in wb.get("soldiers") or []:
        if s.get("id") == soldier_id:
            if s.get("type_key") not in animal_companion_type_keys():
                return False, "Only an Animal Companion can take this bonus."
            if s.get("crit_health_bonus"):
                return False, f"{s.get('name', 'This companion')} already took its critical-success Health bonus."
            info = get_soldier(s.get("type_key", "")) or {}
            s["health"] = int(s.get("health", info.get("health", 0)) or 0) + 1
            s["crit_health_bonus"] = True
            text = f"{s.get('name', 'Companion')} summoned with a critical success: +1 Health."
            add_history(wb, text)
            return True, text
    return False, "Soldier not found."


def add_soldier_xp(wb: dict, soldier_id: str, amount: int) -> tuple[bool, str]:
    hr = wb.setdefault("homerules", default_homerules())
    overall_max = int(hr.get("soldier_max_levels", SOLDIER_MAX_LEVELS))
    for s in wb.get("soldiers") or []:
        if s.get("id") == soldier_id:
            ok, msg = _apply_xp_delta(
                s,
                amount,
                lambda: reverse_last_soldier_level_up(wb, soldier_id),
                overall_max,
                s.get("name", "Soldier"),
            )
            if ok:
                add_history(wb, msg)
            return ok, msg
    return False, "Soldier not found."


def adjust_gold(wb: dict, delta: int, reason: str = "") -> None:
    wb["gold"] = int(wb.get("gold", 0)) + int(delta)
    sign = "+" if delta >= 0 else ""
    text = f"Gold {sign}{delta} gc (now {wb['gold']})"
    if reason:
        text += f" — {reason}"
    wb.setdefault("history", []).append({"when": _now(), "text": text})


def add_history(wb: dict, text: str) -> None:
    wb.setdefault("history", []).append({"when": _now(), "text": text.strip()})


def add_vault_item(wb: dict, name: str, notes: str = "", source: str = "loot") -> None:
    name = name.strip()
    if not name:
        return
    wb.setdefault("vault_items", []).append(
        {"id": uuid.uuid4().hex[:8], "name": name, "notes": notes.strip(), "source": source}
    )


def remove_vault_item(wb: dict, item_id: str) -> bool:
    items = wb.get("vault_items") or []
    for i, it in enumerate(items):
        if it.get("id") == item_id:
            items.pop(i)
            wb["vault_items"] = items
            return True
    return False


def record_game_loot(
    wb: dict,
    gold: int,
    items: list[str],
    xp: int = 0,
    notes: str = "",
    captain_xp: int = 0,
) -> str:
    parts = []
    if gold:
        adjust_gold(wb, gold, "after-game loot")
        parts.append(f"{gold:+d} gc")
    for item_name in items:
        item_name = item_name.strip()
        if item_name:
            add_vault_item(wb, item_name, notes="Found in game", source="game")
            parts.append(item_name)
    if xp:
        # Routed through _apply_xp_delta (G3) rather than a bare assignment, so a
        # negative after-game XP entry clamps at 0 and auto-reverses any level-ups
        # the reduced total no longer earns, instead of leaving them held for free.
        wiz = wb.setdefault("wizard", {})
        ok, msg = _apply_xp_delta(
            wiz,
            int(xp),
            lambda: reverse_last_level_up(wb),
            None,
            "Wizard",
            expansions.xp_per_level(wb),
            expansions.max_wizard_level(wb),
        )
        if ok:
            parts.append(msg)
    if captain_xp and wb.get("captain"):
        hr = wb.setdefault("homerules", default_homerules())
        overall_max = int(hr.get("captain_max_level", CAPTAIN_MAX_LEVEL))
        ok, msg = _apply_xp_delta(
            wb["captain"], int(captain_xp), lambda: reverse_last_captain_level_up(wb), overall_max, "Captain"
        )
        if ok:
            parts.append(msg)
    if notes.strip():
        add_history(wb, f"Game notes: {notes.strip()}")
    summary = "After-game: " + (", ".join(parts) if parts else "no loot")
    if not notes.strip():
        add_history(wb, summary)
    return summary


def apply_level_up(
    wb: dict,
    choice: str,
    spell_key: str | None = None,
    improve_spell_id: str | None = None,
) -> tuple[bool, str]:
    """Spend one pending level-up on the wizard; apprentice auto-syncs."""
    wiz = wb.setdefault("wizard", {})
    xp = int(wiz.get("xp", 0))
    level = int(wiz.get("level", 0))
    earned = level_from_xp(xp, expansions.xp_per_level(wb), expansions.max_wizard_level(wb))
    if level >= earned:
        return False, f"No pending level-ups (level {level}, XP {xp}). Earn more XP first."

    stats = wiz.setdefault("stats", deepcopy(WIZARD_BASE))
    detail = ""
    meta: dict = {"choice": choice}
    allowed = {o["id"] for o in expansions.level_up_options(wb)}
    if choice not in allowed:
        # The only way to get here is a hand-crafted POST or a stale page: a Lich
        # may never raise Fight or Shoot.
        return False, f"A {expansions.STATE_LABELS[expansions.state_kind(wb)]} cannot choose that."

    if choice in ("fight", "shoot", "will", "health"):
        caps = expansions.wizard_stat_caps(wb)
        cap = caps.get(choice)
        current = int(stats.get(choice, 0))
        if cap is not None and current >= cap:
            label = expansions.STATE_LABELS[expansions.state_kind(wb)]
            article = "an" if label[0] in "AEIOU" else "a"
            return False, (
                f"{choice.capitalize()} is capped at {cap} for {article} {label} (currently {current})."
            )
        stats[choice] = current + 1
        detail = f"+1 {choice.capitalize()}"
        meta["stat"] = choice
    elif choice == "learn_spell":
        if not spell_key:
            return False, "Pick a spell to learn."
        sp = find_spell(spell_key)
        if not sp:
            return False, "Unknown spell."
        if sp["source"] not in enabled_sources(wb):
            return False, (
                f"{sp['name']} is from {sp['source']}; enable that source under "
                "Additional Rules and Homerules first."
            )
        blocked = expansions.spell_state_block(wb, sp)
        if blocked:
            return False, blocked
        known_ids = {s.get("id") for s in wiz.get("spells") or []}
        if sp["id"] in known_ids:
            return False, "Spell already known."
        wschool = wiz.get("school") or "Elementalist"
        pen = cn_penalty(wschool, sp["school"])
        eff = int(sp["cn"]) + pen
        wiz.setdefault("spells", []).append(
            {
                "id": sp["id"],
                "name": sp["name"],
                "school": sp["school"],
                "base_cn": int(sp["cn"]),
                "cn_penalty": pen,
                "cn_improve": 0,
                "cn": eff,
                "type": sp["type"],
                "relation": school_relation(wschool, sp["school"]),
            }
        )
        detail = f"Learned {sp['name']} (effective CN {eff})"
        meta["spell_id"] = sp["id"]
        meta["spell_name"] = sp["name"]
    elif choice == "improve_spell":
        if not improve_spell_id:
            return False, "Pick a spell to improve."
        found = False
        for s in wiz.get("spells") or []:
            if s.get("id") == improve_spell_id:
                s["cn_improve"] = int(s.get("cn_improve", 0)) + 1
                base = int(s.get("base_cn", s.get("cn", 10)))
                pen = int(s.get("cn_penalty", 0))
                s["cn"] = max(expansions.casting_number_minimum(wb), base + pen - int(s["cn_improve"]))
                detail = f"Improved {s['name']} to CN {s['cn']}"
                meta["spell_id"] = s["id"]
                meta["spell_name"] = s["name"]
                found = True
                break
        if not found:
            return False, "Spell not found on wizard."
    else:
        return False, "Invalid level-up choice."

    wiz["level"] = level + 1
    wiz.setdefault("level_history", []).append(
        {
            "level": wiz["level"],
            "choice": choice,
            "detail": detail,
            "when": _now(),
            **meta,
        }
    )
    recompute_spell_cns(wb)
    sync_apprentice(wb)
    ap_note = ""
    if wb.get("apprentice"):
        ap = wb["apprentice"]
        ap_note = f" Apprentice auto-updated to level {ap.get('level', 0)}."
    msg = f"Wizard reached level {wiz['level']}: {detail}.{ap_note}"
    add_history(wb, msg)
    return True, msg


def reverse_last_level_up(wb: dict) -> tuple[bool, str]:
    """Undo the most recent level-up (LIFO). XP is unchanged; level and benefits reverse."""
    wiz = wb.setdefault("wizard", {})
    history = wiz.setdefault("level_history", [])
    if not history:
        return False, "No level-ups to reverse."
    if int(wiz.get("level", 0)) <= 0:
        return False, "Wizard is already level 0."

    entry = history[-1]
    choice = entry.get("choice") or ""
    detail = entry.get("detail") or choice
    stats = wiz.setdefault("stats", deepcopy(WIZARD_BASE))

    if choice in ("fight", "shoot", "will", "health") or entry.get("stat") in (
        "fight",
        "shoot",
        "will",
        "health",
    ):
        stat = entry.get("stat") or choice
        if stat not in ("fight", "shoot", "will", "health"):
            return False, f"Cannot reverse unknown stat choice: {choice}"
        # Undo exactly what this level-up recorded, floored at 0 (1 for Health)
        # rather than at WIZARD_BASE (G4) — a mutation or wizard state can lower
        # a stat below its starting value independently of level-ups, and the
        # level_history entry (not the base stat) is the source of truth for
        # what a reversal should subtract.
        floor = 1 if stat == "health" else 0
        new_val = max(floor, int(stats.get(stat, 0)) - 1)
        stats[stat] = new_val
    elif choice == "learn_spell":
        spell_id = entry.get("spell_id")
        spell_name = entry.get("spell_name")
        spells = wiz.get("spells") or []
        removed = False
        if spell_id:
            for i, s in enumerate(spells):
                if s.get("id") == spell_id:
                    # only remove if no improvements were made after learning via later undos...
                    # If improved later, those should have been undone first (LIFO).
                    spells.pop(i)
                    removed = True
                    break
        if not removed and spell_name:
            for i, s in enumerate(spells):
                if s.get("name") == spell_name and int(s.get("cn_improve", 0)) == 0:
                    spells.pop(i)
                    removed = True
                    break
        if not removed:
            # parse "Learned Name (...)"
            import re

            m = re.match(r"Learned\s+(.+?)\s*\(", detail)
            if m:
                name = m.group(1).strip()
                for i, s in enumerate(spells):
                    if s.get("name") == name:
                        spells.pop(i)
                        removed = True
                        break
        if not removed:
            return False, f"Could not find learned spell to remove ({detail})."
        wiz["spells"] = spells
    elif choice == "improve_spell":
        spell_id = entry.get("spell_id")
        spells = wiz.get("spells") or []
        target = None
        if spell_id:
            for s in spells:
                if s.get("id") == spell_id:
                    target = s
                    break
        if target is None:
            import re

            m = re.match(r"Improved\s+(.+?)\s+to", detail)
            if m:
                name = m.group(1).strip()
                for s in spells:
                    if s.get("name") == name:
                        target = s
                        break
        if target is None:
            return False, f"Could not find improved spell to reverse ({detail})."
        imp = int(target.get("cn_improve", 0))
        if imp <= 0:
            return False, f"{target.get('name')} has no improvements left to reverse."
        target["cn_improve"] = imp - 1
        base = int(target.get("base_cn", target.get("cn", 10)))
        pen = int(target.get("cn_penalty", 0))
        target["cn"] = max(expansions.casting_number_minimum(wb), base + pen - int(target["cn_improve"]))
    else:
        return False, f"Cannot reverse level-up type “{choice}” (missing undo data)."

    history.pop()
    wiz["level"] = max(0, int(wiz.get("level", 1)) - 1)
    recompute_spell_cns(wb)
    sync_apprentice(wb)
    msg = f"Reversed level-up: {detail}. Wizard is now level {wiz['level']}."
    if wb.get("apprentice"):
        msg += f" Apprentice re-synced to level {wb['apprentice'].get('level', 0)}."
    add_history(wb, msg)
    return True, msg


def add_wizard_xp(wb: dict, amount: int) -> tuple[bool, str]:
    wiz = wb.setdefault("wizard", {})
    ok, msg = _apply_xp_delta(
        wiz,
        amount,
        lambda: reverse_last_level_up(wb),
        None,
        "Wizard",
        expansions.xp_per_level(wb),
        expansions.max_wizard_level(wb),
    )
    if ok:
        add_history(wb, msg)
    return ok, msg


# Blood Legacy's Alternate Experience Point Expenditure (Chapter Three): ways
# to spend banked XP other than a wizard level. Two of these (casting_boost,
# black_market) don't correspond to a stat this app tracks — Out-of-Game
# Casting Rolls and Black Market rolls are dice the player makes at the table,
# not something the app simulates — so they're logged to the campaign history
# for the player's own bookkeeping rather than applied anywhere automatically.
ALT_XP_CONVERSIONS = {
    "gold": {
        "label": "Gold crowns (100 XP → 100gc)",
        "xp_per_unit": 100,
        "value_per_unit": 100,
        "kind": "gold",
    },
    "casting_boost": {
        "label": "Out-of-Game Casting Roll boost (20 XP → +1, max +5 per casting)",
        "xp_per_unit": 20,
        "value_per_unit": 1,
        "kind": "note",
        "note": "+{amount} to one Out-of-Game Casting Roll",
        "max_xp_per_use": 100,
    },
    "potion_ingredients": {
        "label": "Potion ingredients (1 XP → 2gc)",
        "xp_per_unit": 1,
        "value_per_unit": 2,
        "kind": "gold",
        "note": "toward potion ingredients",
    },
    "apprentice": {
        "label": "New apprentice (1 XP → 3gc)",
        "xp_per_unit": 1,
        "value_per_unit": 3,
        "kind": "gold",
        "note": "toward a new apprentice",
    },
    "black_market": {
        "label": "Extra Black Market roll (25 XP → 1 roll, max 100 XP/scenario)",
        "xp_per_unit": 25,
        "value_per_unit": 1,
        "kind": "note",
        "note": "+{amount} extra Black Market roll(s), usable on any potion/weapon/armour/magic-item/grimoire table from any book",
        "max_xp_per_use": 100,
    },
}


def spend_alt_xp(wb: dict, conversion: str, xp_amount: int) -> tuple[bool, str]:
    """Trade banked XP for gold or a logged one-off bonus instead of a wizard
    level — has no effect on the wizard's level. See ALT_XP_CONVERSIONS."""
    if not expansions.alt_xp_enabled(wb):
        return False, "Alternate Experience Point Expenditure needs Blood Legacy and its own homerule switched on."
    conv = ALT_XP_CONVERSIONS.get(conversion)
    if not conv:
        return False, "Unknown conversion."
    try:
        xp_amount = int(xp_amount)
    except (TypeError, ValueError):
        return False, "Enter a whole number of XP to spend."
    if xp_amount <= 0:
        return False, "Enter a positive amount of XP to spend."
    if xp_amount % conv["xp_per_unit"] != 0:
        return False, f"Amount must be a multiple of {conv['xp_per_unit']} XP."
    max_use = conv.get("max_xp_per_use")
    if max_use and xp_amount > max_use:
        return False, f"Max {max_use} XP per use for this option."
    wiz = wb.setdefault("wizard", {})
    xp = int(wiz.get("xp", 0))
    if xp < xp_amount:
        return False, f"Not enough XP (have {xp}, need {xp_amount})."
    units = xp_amount // conv["xp_per_unit"]
    amount = units * conv["value_per_unit"]
    wiz["xp"] = xp - xp_amount
    if conv["kind"] == "gold":
        wb["gold"] = int(wb.get("gold", 0)) + amount
        suffix = f" {conv['note']}" if conv.get("note") else ""
        text = f"Spent {xp_amount} XP for {amount}gc{suffix}."
    else:
        text = f"Spent {xp_amount} XP: {conv['note'].format(amount=amount)}."
    wb.setdefault("history", []).append({"when": _now(), "text": text})
    return True, text


def known_spell_ids(wb: dict) -> set[str]:
    return {s.get("id") for s in (wb.get("wizard") or {}).get("spells") or []}


def known_spell_names(wb: dict) -> set[str]:
    """Spell names the wizard knows — used to gate spell-summoned hires."""
    return {s.get("name") for s in (wb.get("wizard") or {}).get("spells") or [] if s.get("name")}


def count_animal_companions(wb: dict) -> int:
    """How many Animal Companions the warband currently fields (dead ones don't count)."""
    companion_keys = animal_companion_type_keys()
    return sum(
        1
        for s in wb.get("soldiers") or []
        if s.get("type_key") in companion_keys and s.get("status") != "dead"
    )


def animal_companion_limit(wb: dict) -> int:
    """Animal Companions allowed at once — normally one per spellcaster (the wizard,
    plus the apprentice if the warband has one), since each can cast the spell.
    A Beastcrafter II wizard raises the per-caster allowance to two."""
    casters = 2 if wb.get("apprentice") else 1
    return casters * expansions.companions_per_caster(wb)


def has_animal_companion(wb: dict) -> bool:
    """True if the warband is at its Animal Companion limit already."""
    return count_animal_companions(wb) >= animal_companion_limit(wb)


# --- Wizard states (Lich / Beastcrafter / Demonic Pact) ---------------------
#
# expansions.py holds the rules and the validation; these apply the result and
# write the campaign log.


def set_wizard_state(wb: dict, kind: str) -> tuple[bool, str]:
    """Put the wizard into a state, replacing whatever they were in before.

    The three states are mutually exclusive by the rules, so this is a plain
    assignment rather than an accumulation — taking one clears the others, which
    is exactly what Forgotten Pacts describes happening to an existing pact.
    """
    ok, msg = expansions.can_enter_state(wb, kind, enabled_sources(wb))
    if not ok:
        return False, msg
    wiz = wb.setdefault("wizard", {})
    was = expansions.state_kind(wb)
    if was == kind:
        return False, f"Your wizard is already {expansions.STATE_LABELS[kind].lower()}."
    state = expansions.default_wizard_state()
    state["kind"] = kind
    if kind == expansions.STATE_BEASTCRAFTER:
        state["tier"] = 1
    wiz["state"] = state

    label = expansions.STATE_LABELS[kind]
    if kind == expansions.STATE_NONE:
        text = f"{wiz.get('name', 'The wizard')} is no longer {expansions.STATE_LABELS[was].lower()}."
    elif was == expansions.STATE_NONE:
        text = f"{wiz.get('name', 'The wizard')} became {label}."
    else:
        text = (
            f"{wiz.get('name', 'The wizard')} became {label}, "
            f"ending their time as {expansions.STATE_LABELS[was].lower()}."
        )
    add_history(wb, text)
    return True, text


def break_wizard_pact(wb: dict) -> tuple[bool, str]:
    """End a demonic pact, paying the 1 level + 1 Health per Sacrifice held.

    The level cost is charged as XP (G5) — burned via _apply_xp_delta, the
    same machinery add_wizard_xp uses — rather than only popping level_history,
    so the penalty actually sticks instead of leaving `earned` XP the player
    can immediately re-spend for free. The reported Health loss is computed
    from before/after values rather than the raw penalty, since a reversed
    level-up that happened to be a Health level also reduces Health.
    """
    if expansions.state_kind(wb) != expansions.STATE_PACT:
        return False, "Your wizard holds no pact."
    penalty = expansions.pact_break_penalty(wb)
    wiz = wb.setdefault("wizard", {})
    stats = wiz.setdefault("stats", deepcopy(WIZARD_BASE))
    level_before = int(wiz.get("level", 0))
    health_before = int(stats.get("health", 14))

    per_level = expansions.xp_per_level(wb)
    xp_cost = penalty["levels"] * per_level
    if xp_cost:
        _apply_xp_delta(
            wiz, -xp_cost, lambda: reverse_last_level_up(wb), None, "Wizard",
            per_level, expansions.max_wizard_level(wb),
        )
    if penalty["health"]:
        stats["health"] = max(1, int(stats.get("health", 14)) - penalty["health"])

    lost = level_before - int(wiz.get("level", 0))
    health_lost = health_before - int(stats.get("health", 14))
    wiz["state"] = expansions.default_wizard_state()
    text = (
        f"{wiz.get('name', 'The wizard')} broke their pact: "
        f"−{lost} level{'s' if lost != 1 else ''}, −{health_lost} Health."
    )
    add_history(wb, text)
    return True, text


def advance_beastcrafter(wb: dict) -> tuple[bool, str]:
    """Take the next Beastcrafter tier."""
    ok, msg = expansions.can_advance_beastcrafter(wb)
    if not ok:
        return False, msg
    wiz = wb.setdefault("wizard", {})
    state = wiz.setdefault("state", expansions.default_wizard_state())
    state["tier"] = int(state.get("tier") or 0) + 1
    name = expansions.BEASTCRAFTER_TIER_BY_N[state["tier"]]["name"]
    text = f"{wiz.get('name', 'The wizard')} advanced to {name}."
    add_history(wb, text)
    return True, text


def set_animal_feature(wb: dict, feature_id: str) -> tuple[bool, str]:
    """Pick the permanent Animal Feature a Beastcrafter III gains."""
    if expansions.beastcrafter_tier(wb) < 3:
        return False, "Only a Beastcrafter III may pick an Animal Feature."
    if feature_id not in expansions.ANIMAL_FEATURE_IDS:
        return False, "Unknown Animal Feature."
    wiz = wb.setdefault("wizard", {})
    state = wiz.setdefault("state", expansions.default_wizard_state())
    if state.get("feature") == feature_id:
        return False, "That feature is already chosen."
    state["feature"] = feature_id
    name = expansions.ANIMAL_FEATURE_BY_ID[feature_id]["name"]
    text = f"{wiz.get('name', 'The wizard')} gained the {name} Animal Feature."
    add_history(wb, text)
    return True, text


def add_pact_tier(wb: dict, sacrifice: str, boon: str, demon: str = "") -> tuple[bool, str]:
    """Forge another pact tier: one Sacrifice paired with one Boon."""
    ok, msg = expansions.can_add_pact_tier(wb)
    if not ok:
        return False, msg
    if sacrifice not in expansions.PACT_SACRIFICE_IDS:
        return False, "Unknown Sacrifice."
    if boon not in expansions.PACT_BOON_IDS:
        return False, "Unknown Boon."
    wiz = wb.setdefault("wizard", {})
    state = wiz.setdefault("state", expansions.default_wizard_state())
    held = state.setdefault("pacts", [])
    if any(p.get("sacrifice") == sacrifice for p in held):
        return False, "That Sacrifice is already being paid."
    if any(p.get("boon") == boon for p in held):
        return False, "That Boon is already held."
    held.append({"sacrifice": sacrifice, "boon": boon})
    state["tier"] = len(held)
    if demon.strip():
        state["demon"] = demon.strip()
    s_name = expansions.PACT_SACRIFICE_BY_ID[sacrifice]["name"]
    b_name = expansions.PACT_BOON_BY_ID[boon]["name"]
    text = f"{wiz.get('name', 'The wizard')} forged a pact: {s_name} for {b_name}."
    add_history(wb, text)
    return True, text


def set_base_location(wb: dict, location_key: str) -> tuple[bool, str]:
    if location_key not in BASE_LOCATIONS:
        return False, "Unknown base location."
    old = (wb.get("base") or {}).get("location", "none")
    base = wb.setdefault("base", empty_base())
    if old == location_key:
        return True, "Base location unchanged."
    # Changing base loses upgrades (2e p.106)
    lost = list(base.get("resources") or [])
    base["location"] = location_key
    if location_key == "none":
        base["resources"] = []
        text = "Base cleared (no location)."
    else:
        if lost and old != "none":
            base["resources"] = []
            text = (
                f"Base moved to {BASE_LOCATIONS[location_key]['name']}. "
                f"Previous upgrades lost ({len(lost)})."
            )
        else:
            text = f"Base established: {BASE_LOCATIONS[location_key]['name']}."
    add_history(wb, text)
    return True, text


def buy_base_resource(wb: dict, resource_key: str) -> tuple[bool, str]:
    info = BASE_RESOURCES.get(resource_key)
    if not info:
        return False, "Unknown base resource."
    src = info.get("source", "Core Rules")
    if src not in enabled_sources(wb):
        return False, (
            f"{info['name']} is from {src}; enable that source under "
            "Additional Rules and Homerules first."
        )
    base = wb.setdefault("base", empty_base())
    if base.get("location", "none") == "none":
        return False, "Establish a base location first (free)."
    owned = base.setdefault("resources", [])
    if resource_key in owned:
        return False, f"Already own {info['name']} (each type once)."
    cost = int(info["cost"])
    if int(wb.get("gold", 0)) < cost:
        return False, f"Need {cost} gc for {info['name']}."
    wb["gold"] = int(wb["gold"]) - cost
    owned.append(resource_key)
    text = f"Purchased base resource {info['name']} for {cost} gc."
    add_history(wb, text)
    return True, text


def sell_or_remove_base_resource(wb: dict, resource_key: str, refund: bool = False) -> tuple[bool, str]:
    base = wb.setdefault("base", empty_base())
    owned = base.setdefault("resources", [])
    if resource_key not in owned:
        return False, "Resource not owned."
    info = BASE_RESOURCES.get(resource_key, {"name": resource_key, "cost": 0})
    owned.remove(resource_key)
    if refund:
        half = int(info.get("cost", 0)) // 2
        wb["gold"] = int(wb.get("gold", 0)) + half
        text = f"Removed {info['name']} (refunded {half} gc)."
    else:
        text = f"Removed base resource {info['name']}."
    add_history(wb, text)
    return True, text


def base_summary(wb: dict) -> dict:
    base = wb.get("base") or empty_base()
    loc_key = base.get("location", "none")
    loc = BASE_LOCATIONS.get(loc_key, BASE_LOCATIONS["none"])
    resources = []
    for key in base.get("resources") or []:
        info = BASE_RESOURCES.get(key)
        if info:
            resources.append({"key": key, **info})
    return {
        "location_key": loc_key,
        "location_name": loc["name"],
        "location_effects": loc["effects"],
        "resources": resources,
        "notes": base.get("notes", ""),
    }


def recruit_preview(wb: dict, type_key: str) -> dict:
    """Info for hire UI: cost, whether affordable, limit warnings."""
    info = get_soldier(type_key) or {}
    cost = expansions.soldier_cost(wb, info, type_key)
    active = soldier_count(wb)
    specs = specialist_count(wb)
    is_spec = info.get("category") == "specialist"
    gold = int(wb.get("gold", 0))
    return {
        "cost": cost,
        "affordable": gold >= cost,
        "gold_after": gold - cost,
        "soldiers_after": active + 1,
        "specialists_after": specs + (1 if is_spec else 0),
        "hits_soldier_limit": active >= expansions.max_soldiers(wb),
        "hits_specialist_limit": is_spec and specs >= expansions.max_specialists(wb),
        "category": info.get("category", "standard"),
        "name": info.get("name", type_key),
    }
