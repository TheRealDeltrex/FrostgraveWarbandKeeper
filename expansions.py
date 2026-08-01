"""Supplement rules: the three wizard states and the numbers they change.

Frostgrave's supplements each add a long-term state a wizard can enter — Lichdom
(Thaw of the Lich Lord), the Beastcrafter track (Into the Breeding Pits) and a
Demonic Pact (Forgotten Pacts). They are mutually exclusive by the rules: a wizard
cannot pact while a Lich or Beastcrafter, and gaining either of those breaks an
existing pact.

Each state changes numbers the rest of the app reads straight from module
constants (XP per level, soldier cost, the soldier cap, level-up options). Those
call sites go through the hooks here instead, so a warband with no state set —
which is every warband that existed before this module — behaves exactly as it
did before.

This module deliberately knows nothing about persistence: it reads warband dicts
and returns values. warband_store owns the mutations and the campaign log.
"""

from __future__ import annotations

from frostgrave_data import (
    APPRENTICE_ITEM_SLOTS,
    LEVEL_UP_OPTIONS,
    MAX_SOLDIERS,
    MAX_SPECIALISTS,
    MAX_WIZARD_LEVEL,
    WIZARD_ITEM_SLOTS,
    WIZARD_MIN_CASTING_NUMBER_DEFAULT,
    WIZARD_STAT_LIMITS_DEFAULT,
    XP_PER_LEVEL,
)

# Internal sentinel for an "unlimited" wizard level cap — plain int rather than
# float('inf') so it stays a normal int everywhere it flows (level_from_xp(),
# comparisons, JSON round-tripping via save/load).
WIZARD_LEVEL_UNCAPPED = 100_000

# --- The states -------------------------------------------------------------

STATE_NONE = "none"
STATE_LICH = "lich"
STATE_BEASTCRAFTER = "beastcrafter"
STATE_PACT = "pact"

WIZARD_STATES = [STATE_NONE, STATE_LICH, STATE_BEASTCRAFTER, STATE_PACT]

STATE_LABELS = {
    STATE_NONE: "Ordinary wizard",
    STATE_LICH: "Lich",
    STATE_BEASTCRAFTER: "Beastcrafter",
    STATE_PACT: "Pact-holder",
}

# Which source book has to be switched on for a state to be available at all.
STATE_SOURCE = {
    STATE_LICH: "Thaw of the Lich Lord",
    STATE_BEASTCRAFTER: "Into the Breeding Pits",
    STATE_PACT: "Forgotten Pacts",
}


def default_wizard_state() -> dict:
    return {
        "kind": STATE_NONE,
        "tier": 0,  # Beastcrafter I–III; number of pact tiers held
        "feature": None,  # Beastcrafter III animal feature id
        "demon": "",  # pact: the demon whose True Name was found
        "pacts": [],  # pact: [{"sacrifice": id, "boon": id}, ...], one per tier
    }


def wizard_state(wb: dict) -> dict:
    return (wb.get("wizard") or {}).get("state") or default_wizard_state()


def state_kind(wb: dict) -> str:
    kind = wizard_state(wb).get("kind") or STATE_NONE
    return kind if kind in WIZARD_STATES else STATE_NONE


def is_lich(wb: dict) -> bool:
    return state_kind(wb) == STATE_LICH


def beastcrafter_tier(wb: dict) -> int:
    """0 if the wizard isn't a Beastcrafter, else the tier (1–3) reached."""
    if state_kind(wb) != STATE_BEASTCRAFTER:
        return 0
    return max(0, min(len(BEASTCRAFTER_TIERS), int(wizard_state(wb).get("tier") or 0)))


def pact_tiers(wb: dict) -> list[dict]:
    """The {sacrifice, boon} pairs held, one per pact tier."""
    if state_kind(wb) != STATE_PACT:
        return []
    return [p for p in wizard_state(wb).get("pacts") or [] if isinstance(p, dict)]


# --- Lichdom (Thaw of the Lich Lord) ----------------------------------------

LICH_XP_PER_LEVEL = 150
# A Lich's Will caps at +10 and Health at 25. Nothing else about the wizard is
# capped in core, so these are the only two entries.
LICH_STAT_CAPS = {"will": 10, "health": 25}
# "May never raise Fight or Shoot on level-up."
LICH_FORBIDDEN_LEVELUP = {"fight", "shoot"}
# Transcendence is a Perilous Dark spell the app doesn't carry yet; listed so the
# restriction holds automatically if it is ever added.
LICH_FORBIDDEN_SPELLS = {"Familiar", "Transcendence"}
# The rangifer "will leave if any undead join the warband", and a Lich is undead.
LICH_BLOCKED_SOLDIERS = {"rangifer"}

# Casting Lichdom (CN 20, Out of Game) and missing. The app records the outcome
# rather than rolling it; the player applies the penalty through the existing
# XP / level-reversal controls.
LICH_FAILURE_TABLE = [
    {"missed_by": "1–5", "penalty": "−1 level, −1 Health stat."},
    {"missed_by": "6–10", "penalty": "−3 levels, −2 Health, −1 Will, 1 random permanent injury."},
    {"missed_by": "11–15", "penalty": "−5 levels, −3 Health, −2 Will, 2 random permanent injuries."},
    {"missed_by": "16–20", "penalty": "−8 levels, −6 Health, −2 Will, 3 random permanent injuries."},
    {"missed_by": "21+", "penalty": "The wizard's soul is lost — unrecoverable by any means."},
]

LICH_NOTES = [
    "Subject to all undead rules, but immune to Control Undead, Poison Dart, Restore Life "
    "and the Elixir of Life.",
    "Heal, Miraculous Cure and Restore Life only affect undead.",
    "Animal Companion yields undead animals.",
    "May still have an apprentice (fully human and unaffected) and recruits soldiers as normal.",
]


# --- Beastcrafter (Into the Breeding Pits) ----------------------------------

# Drinking the Elixir of the Beastcrafter converts a level-up into one of these
# stacking tiers instead of a normal advancement.
BEASTCRAFTER_TIERS = [
    {
        "tier": 1,
        "name": "Beastcrafter I",
        "min_level": 5,
        "surcharge": 2,
        "summary": (
            "+1 to cast Control Animal; adds boar and ice spider to the Animal Companion "
            "options; soldiers cost +2gc."
        ),
    },
    {
        "tier": 2,
        "name": "Beastcrafter II",
        "min_level": 10,
        "surcharge": 10,
        "summary": (
            "+1 to cast Animal Companion; up to 2 companions per spellcaster; may learn "
            "Animal Manipulation; soldiers cost +10gc."
        ),
    },
    {
        "tier": 3,
        "name": "Beastcrafter III",
        "min_level": 15,
        "surcharge": 20,
        "summary": (
            "May learn Animal Mutation; picks one permanent Animal Feature; soldiers cost +20gc."
        ),
    },
]

BEASTCRAFTER_TIER_BY_N = {t["tier"]: t for t in BEASTCRAFTER_TIERS}

# One permanent pick at tier III. Fast and Scales are real stat changes; the rest
# are situational and only described.
ANIMAL_FEATURES = [
    {"id": "claws", "name": "Claws", "effect": "Always counts as armed.", "stat": None, "amount": 0},
    {"id": "fast", "name": "Fast", "effect": "+1 Move.", "stat": "move", "amount": 1},
    {
        "id": "night_vision",
        "name": "Night Vision",
        "effect": "+6\" line of sight in darkness.",
        "stat": None,
        "amount": 0,
    },
    {
        "id": "poison_resistance",
        "name": "Poison Resistance",
        "effect": "May self-cure poison with a Will-10 roll.",
        "stat": None,
        "amount": 0,
    },
    {"id": "scales", "name": "Scales", "effect": "+1 Armour.", "stat": "armour", "amount": 1},
    {
        "id": "wings",
        "name": "Wings",
        "effect": "No falling damage; may glide.",
        "stat": None,
        "amount": 0,
    },
]

ANIMAL_FEATURE_IDS = {f["id"] for f in ANIMAL_FEATURES}
ANIMAL_FEATURE_BY_ID = {f["id"]: f for f in ANIMAL_FEATURES}

# Companion types the Beastcrafter track unlocks, and the tier that does it.
BEASTCRAFTER_COMPANIONS = {"companion_boar": 1, "companion_ice_spider": 1}

# Spells gated on a Beastcrafter tier rather than only on their source book.
BEASTCRAFTER_SPELLS = {"Animal Manipulation": 2, "Animal Mutation": 3}

# Tier II: "up to 2 companions per caster".
BEASTCRAFTER_COMPANIONS_PER_CASTER = 2


# --- Demonic Pacts (Forgotten Pacts) ----------------------------------------

# A wizard may forge a pact at level 10, a second at 25, a third at 50 (max).
PACT_TIER_LEVELS = [10, 25, 50]
PACT_MAX_TIERS = len(PACT_TIER_LEVELS)

# Forging requires a demon's True Name, which is treasure-only and never bought.
PACT_TRUE_NAME_ITEM = "True Name"

PACT_SACRIFICES = [
    {"id": "blood", "name": "Blood", "cost": "Start each game at −4 Health."},
    {
        "id": "tithing",
        "name": "Tithing",
        "cost": "Discard one treasure token after the game, or pay 10gc if none was found.",
    },
    {
        "id": "worship",
        "name": "Worship",
        "cost": "One warband member must sit out the game performing devotions.",
    },
    {
        "id": "arcane_energy",
        "name": "Arcane Energy",
        "cost": "A randomly chosen known spell may not be cast this game.",
    },
    {
        "id": "prayer",
        "name": "Prayer",
        "cost": "The wizard's first activation is limited to a single movement action.",
    },
]

PACT_BOONS = [
    {
        "id": "demonic_endurance",
        "name": "Demonic Endurance",
        "effect": "Never treated as Wounded below 5 Health.",
    },
    {
        "id": "demonic_power",
        "name": "Demonic Power",
        "effect": "Roll a random Minor Demonic Attribute for the wizard.",
    },
    {"id": "lost_secrets", "name": "Lost Secrets", "effect": "Reroll one treasure-table result per game."},
    {
        "id": "pentaculum",
        "name": "Pentaculum",
        "effect": (
            "Bind Demon can imprison the demon in an amulet, discardable for +3 to an "
            "Out of Game Casting Roll."
        ),
    },
    {
        "id": "twist_of_fate",
        "name": "Twist of Fate",
        "effect": "Once per game, reroll any one die roll made by your warband.",
    },
    {
        "id": "chilopendra_soldier",
        "name": "Chilopendra Soldier",
        "effect": "(Tiszirain pact only) add a willing chilopendra to the warband as a soldier slot.",
    },
]

PACT_SACRIFICE_IDS = {s["id"] for s in PACT_SACRIFICES}
PACT_BOON_IDS = {b["id"] for b in PACT_BOONS}
PACT_SACRIFICE_BY_ID = {s["id"]: s for s in PACT_SACRIFICES}
PACT_BOON_BY_ID = {b["id"]: b for b in PACT_BOONS}

# The one boon with a mechanical effect on warband size.
BOON_EXTRA_SOLDIER = "chilopendra_soldier"
# ...and the soldier it lets you field.
PACT_BOON_SOLDIERS = {"chilopendra": BOON_EXTRA_SOLDIER}


# --- Treasure-gated content -------------------------------------------------

# Soldiers that join only because a particular item is in the vault. Matched the
# same loose way as the True Name, since vault items are typed by hand.
VAULT_ITEM_SOLDIERS = {
    "collegium_porter": "Porter Control Rod",
}

# Reanimating a dead soldier (Thaw of the Lich Lord). Keeps their stats; Will
# becomes +0. Unlimited revenants per warband.
REVENANT_SPELL = "Revenant"
REVENANT_WILL = 0


def has_vault_item(wb: dict, needle: str) -> bool:
    """Whether something matching `needle` is recorded in the vault."""
    for it in wb.get("vault_items") or []:
        name = (it.get("name") if isinstance(it, dict) else str(it)) or ""
        if needle.lower() in name.lower():
            return True
    return False


# --- Effect hooks -----------------------------------------------------------
#
# Each of these replaces a constant the app used to read directly. They all
# return the unchanged core value when no state is set.


def xp_per_level(wb: dict) -> int:
    """XP one wizard level costs. A Lich levels more slowly."""
    return LICH_XP_PER_LEVEL if is_lich(wb) else XP_PER_LEVEL


def soldier_surcharge(wb: dict) -> int:
    """Extra gold every soldier costs because of the wizard's state."""
    tier = beastcrafter_tier(wb)
    return BEASTCRAFTER_TIER_BY_N[tier]["surcharge"] if tier else 0


def soldier_discount(wb: dict) -> int:
    """Gold off every soldier from base resources (Carrier Pigeons: −10gc)."""
    owned = ((wb.get("base") or {}).get("resources")) or []
    return 10 if "carrier_pigeons" in owned else 0


# A homerule, on by default: several supplement soldiers (Into the Breeding
# Pits, The Maze of Malcor, Forgotten Pacts) read as costed closer to 1st
# edition than the rest of the 2e soldier tables. This bumps them to the
# house-corrected 2e-consistent prices. Trap Expert also gains a dagger and a
# hand weapon under this toggle. Off, the documented catalog costs/gear apply.
EDITION_2_SOLDIER_COSTS = {
    "assassin": 100,
    "demon_hunter": 125,
    "monk": 125,
    "mystic_warrior": 125,
}


def edition2_enabled(wb: dict) -> bool:
    return bool((wb.get("homerules") or {}).get("edition2_soldier_costs", True))


def soldier_cost(wb: dict, info: dict, type_key: str = "") -> int:
    """What hiring this soldier type actually costs this warband, after any
    Edition 2 cost adjustment, the Beastcrafter surcharge, and any base-
    resource discount. Never negative, and free soldiers (thug, thief,
    summoned members) stay free."""
    base = int(info.get("cost", 0))
    if base <= 0:
        return 0
    if type_key and edition2_enabled(wb) and type_key in EDITION_2_SOLDIER_COSTS:
        base = EDITION_2_SOLDIER_COSTS[type_key]
    return max(0, base + soldier_surcharge(wb) - soldier_discount(wb))


def max_soldiers(wb: dict) -> int:
    """The roster cap: the group's own base (settable at warband creation,
    default MAX_SOLDIERS — see default_homerules()), raised by the Chilopendra
    Soldier boon."""
    hr = wb.get("homerules") or {}
    base_raw = hr.get("max_soldiers")
    base = int(base_raw) if base_raw is not None else MAX_SOLDIERS
    extra = sum(1 for p in pact_tiers(wb) if p.get("boon") == BOON_EXTRA_SOLDIER)
    return base + extra


def wizard_stat_caps(wb: dict) -> dict:
    """Hard ceilings on the wizard's stats, {stat: max}. For an ordinary
    wizard these come from the Wizard stat limits homerule (2e core defaults:
    Fight/Shoot 5, Will 8, Health 20); a Lich instead uses its own fixed caps
    (Will 10, Health 25). Blood Legacy's Increased Maximum Health stacks its
    level-based bonus on top of whichever health cap applies either way."""
    hr = wb.get("homerules") or {}
    if is_lich(wb):
        caps = dict(LICH_STAT_CAPS)
    else:
        caps = dict(hr.get("wizard_stat_limits") or WIZARD_STAT_LIMITS_DEFAULT)
    if _hlw_active(wb, "hlw_max_health"):
        base = caps.get("health", WIZARD_STAT_LIMITS_DEFAULT["health"])
        caps["health"] = base + min(10, wizard_level(wb) // 10)
    return caps


# --- Blood Legacy: High-Level Wizards ---------------------------------------
#
# A collection of optional rules (2e Blood Legacy, Chapter Three) that mainly
# come into play once a wizard reaches higher levels. The book is explicit
# that "each optional rule should be considered separately" — so each gets its
# own homerule toggle rather than one bundled switch, and all of them also
# need Blood Legacy itself switched on (they're that book's content).


def _hlw_active(wb: dict, key: str) -> bool:
    hr = wb.get("homerules") or {}
    if not (hr.get("enabled_sources") or {}).get("Blood Legacy"):
        return False
    return bool(hr.get(key))


def wizard_level(wb: dict) -> int:
    return int((wb.get("wizard") or {}).get("level", 0))


def max_specialists(wb: dict) -> int:
    """Specialist-soldier cap: the group's own base (settable at warband
    creation, default MAX_SPECIALISTS — see default_homerules()), raised by
    Increased Specialist Soldier Allowance: +1 per full 20 wizard levels,
    capped at +4 (8 total at level 80+ on top of the default base)."""
    hr = wb.get("homerules") or {}
    base_raw = hr.get("max_specialists")
    base = int(base_raw) if base_raw is not None else MAX_SPECIALISTS
    extra = min(4, wizard_level(wb) // 20) if _hlw_active(wb, "hlw_specialist_allowance") else 0
    return base + extra


def _hlw_item_slot_bonus(wb: dict) -> int:
    if not _hlw_active(wb, "hlw_item_slots"):
        return 0
    level = wizard_level(wb)
    return (1 if level >= 30 else 0) + (1 if level >= 70 else 0)


def wizard_item_slots(wb: dict) -> int:
    """Wizard item slots, raised by Increased Item Slots: +1 at level 30, +1
    more at level 70 (max +2)."""
    return WIZARD_ITEM_SLOTS + _hlw_item_slot_bonus(wb)


def apprentice_item_slots(wb: dict) -> int:
    """Same Increased Item Slots bonus, applied to the apprentice too — the
    book raises both together."""
    return APPRENTICE_ITEM_SLOTS + _hlw_item_slot_bonus(wb)


def casting_number_minimum(wb: dict) -> int:
    """Floor a Casting Number can be improved down to via level-ups —
    configurable via the Wizard stat limits homerule (2e core default 5).
    Blood Legacy's Lower Casting Number Minimum drops it 1 further for a
    level 100+ wizard, on top of whatever floor is set here."""
    hr = wb.get("homerules") or {}
    base = int(hr.get("wizard_min_casting_number", WIZARD_MIN_CASTING_NUMBER_DEFAULT))
    if _hlw_active(wb, "hlw_casting_min") and wizard_level(wb) >= 100:
        return max(1, base - 1)
    return base


def max_wizard_level(wb: dict) -> int:
    """Level ceiling the wizard's earned XP can convert into — the Wizard
    stat limits homerule's Level field (unlimited by default; 2e core doesn't
    actually cap wizard level)."""
    hr = wb.get("homerules") or {}
    cap_cfg = hr.get("wizard_level_cap") or {"limit": MAX_WIZARD_LEVEL, "unlimited": True}
    if cap_cfg.get("unlimited"):
        return WIZARD_LEVEL_UNCAPPED
    return max(0, int(cap_cfg.get("limit", MAX_WIZARD_LEVEL)))


def alt_xp_enabled(wb: dict) -> bool:
    """Alternate Experience Point Expenditure — unlike the other High-Level
    Wizards rules this one has no level requirement (it's about spending XP
    that would otherwise sit unused, at any level), but it's still that book's
    content, so it needs the same Blood Legacy + own-toggle gate."""
    return _hlw_active(wb, "hlw_alt_xp")


def level_up_options(wb: dict) -> list[dict]:
    """The level-up choices open to this wizard."""
    if is_lich(wb):
        return [o for o in LEVEL_UP_OPTIONS if o["id"] not in LICH_FORBIDDEN_LEVELUP]
    return list(LEVEL_UP_OPTIONS)


def companions_per_caster(wb: dict) -> int:
    """Animal Companions each spellcaster may field. Beastcrafter II doubles it."""
    return BEASTCRAFTER_COMPANIONS_PER_CASTER if beastcrafter_tier(wb) >= 2 else 1


def wizard_state_stat_bonus(wb: dict) -> dict:
    """Stat changes the state grants outright — currently only the Beastcrafter III
    animal feature. Returned as {stat: amount} to add to the displayed stats."""
    bonus: dict[str, int] = {}
    feature = ANIMAL_FEATURE_BY_ID.get(wizard_state(wb).get("feature") or "")
    if feature and feature["stat"]:
        bonus[feature["stat"]] = bonus.get(feature["stat"], 0) + int(feature["amount"])
    return bonus


# --- Gating -----------------------------------------------------------------


def soldier_state_block(wb: dict, type_key: str) -> str | None:
    """Why this soldier type is unavailable beyond its source book — the wizard's
    state forbids it, or it needs a pact boon or a treasure in the vault.
    None means nothing here blocks it."""
    if type_key in LICH_BLOCKED_SOLDIERS and is_lich(wb):
        return "A Rangifer will not serve an undead wizard — your wizard is a Lich."
    need_tier = BEASTCRAFTER_COMPANIONS.get(type_key)
    if need_tier and beastcrafter_tier(wb) < need_tier:
        name = BEASTCRAFTER_TIER_BY_N[need_tier]["name"]
        return f"Only a {name} wizard may take this Animal Companion."
    need_boon = PACT_BOON_SOLDIERS.get(type_key)
    if need_boon and not any(p.get("boon") == need_boon for p in pact_tiers(wb)):
        boon = PACT_BOON_BY_ID[need_boon]["name"]
        return f"Requires the {boon} pact boon."
    need_item = VAULT_ITEM_SOLDIERS.get(type_key)
    if need_item and not has_vault_item(wb, need_item):
        return f"Requires a {need_item} in the vault."
    return None


def spell_state_block(wb: dict, spell: dict) -> str | None:
    """Why the wizard's state forbids learning this spell, or None."""
    name = spell.get("name", "")
    if name in LICH_FORBIDDEN_SPELLS and is_lich(wb):
        return f"A Lich cannot cast {name}."
    need_tier = BEASTCRAFTER_SPELLS.get(name)
    if need_tier and beastcrafter_tier(wb) < need_tier:
        return f"Requires {BEASTCRAFTER_TIER_BY_N[need_tier]['name']}."
    return None


def spell_available(wb: dict, spell: dict, sources: set[str]) -> bool:
    """Whether this spell may be learned: its source book is on for the warband
    and the wizard's state allows it.

    `sources` is warband_store.enabled_sources(wb), passed in rather than looked
    up so this module stays free of the persistence layer.
    """
    if spell.get("source", "Core Rules") not in sources:
        return False
    return spell_state_block(wb, spell) is None


def has_true_name(wb: dict) -> bool:
    """Whether a demon's True Name is in the vault — the prerequisite for forging
    a pact. Matched loosely, since the item is recorded by hand and often reads
    'True Name (Tiszirain)'."""
    return has_vault_item(wb, PACT_TRUE_NAME_ITEM)


# --- Validation -------------------------------------------------------------
#
# Pure checks; warband_store applies the result and writes the campaign log.


def can_enter_state(wb: dict, kind: str, sources: set[str]) -> tuple[bool, str]:
    """Whether the wizard may take on `kind` right now."""
    if kind == STATE_NONE:
        return True, ""
    if kind not in WIZARD_STATES:
        return False, "Unknown wizard state."
    book = STATE_SOURCE[kind]
    if book not in sources:
        return False, f"{STATE_LABELS[kind]} comes from {book}; switch that book on first."
    level = int((wb.get("wizard") or {}).get("level", 0))
    if kind == STATE_BEASTCRAFTER and level < BEASTCRAFTER_TIERS[0]["min_level"]:
        return False, (
            f"Beastcrafter I needs a level {BEASTCRAFTER_TIERS[0]['min_level']} wizard "
            f"(yours is level {level})."
        )
    if kind == STATE_PACT:
        if level < PACT_TIER_LEVELS[0]:
            return False, (
                f"Forging a pact needs a level {PACT_TIER_LEVELS[0]} wizard (yours is level {level})."
            )
        # No True Name check here: item requirements are optional to track in the
        # app and can be handled at the gaming table instead.
    return True, ""


def can_advance_beastcrafter(wb: dict) -> tuple[bool, str]:
    """Whether the wizard may take the next Beastcrafter tier."""
    tier = beastcrafter_tier(wb)
    if not tier:
        return False, "Your wizard is not a Beastcrafter."
    if tier >= len(BEASTCRAFTER_TIERS):
        return False, "Already at Beastcrafter III."
    nxt = BEASTCRAFTER_TIER_BY_N[tier + 1]
    level = int((wb.get("wizard") or {}).get("level", 0))
    if level < nxt["min_level"]:
        return False, f"{nxt['name']} needs a level {nxt['min_level']} wizard (yours is level {level})."
    return True, ""


def can_add_pact_tier(wb: dict) -> tuple[bool, str]:
    """Whether the wizard may forge another pact tier."""
    if state_kind(wb) != STATE_PACT:
        return False, "Your wizard holds no pact."
    held = len(pact_tiers(wb))
    if held >= PACT_MAX_TIERS:
        return False, f"A wizard may hold at most {PACT_MAX_TIERS} pacts."
    level = int((wb.get("wizard") or {}).get("level", 0))
    need = PACT_TIER_LEVELS[held]
    if level < need:
        return False, f"The next pact needs a level {need} wizard (yours is level {level})."
    return True, ""


def pact_break_penalty(wb: dict) -> dict:
    """Breaking a pact costs 1 level and 1 Health per Sacrifice held."""
    n = sum(1 for p in pact_tiers(wb) if p.get("sacrifice"))
    return {"levels": n, "health": n}
