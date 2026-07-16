"""
Frostgrave Second Edition reference data.

Source: Frostgrave - 2e - Core Rules.pdf (local rulebooks under
E:\\RPG\\Tabletop\\Frostgrave). Always defer to your printed book for disputes.
"""

from __future__ import annotations

from copy import deepcopy

# --- Campaign limits (2e core) ---------------------------------------------

STARTING_GOLD = 400  # Assembling a Warband, p.26
APPRENTICE_COST = 100  # The Apprentice, p.27
MAX_SOLDIERS = 8
MAX_SPECIALISTS = 4
STARTING_SPELL_COUNT = 8
OWN_SCHOOL_SPELLS = 3  # Choosing Spells, p.24
ALIGNED_SCHOOL_SPELLS = 1  # one from each of the three aligned schools
NEUTRAL_SPELLS = 2  # two neutrals, each from a different school
XP_PER_LEVEL = 100
MAX_WIZARD_LEVEL = 40
# Item slots (2e p.26): dagger does not use a slot
WIZARD_ITEM_SLOTS = 5
APPRENTICE_ITEM_SLOTS = 4
SOLDIER_ITEM_SLOTS = 1

# --- Captains (homerule, not core 2e) --------------------------------------
# Not part of Frostgrave 2e core. Adapted from the FG1E Sellswords supplement;
# the exact numbers are unsettled even in the source house-rules doc (e.g.
# "Hiring Cost: Increase to 250 GC (300?, 500?)"), so every value below is only
# a default — the app exposes them as editable per-warband homerule settings.
CAPTAIN_HIRING_COST = 250
CAPTAIN_ITEM_SLOTS = 6
CAPTAIN_BASE = {
    "move": 6,
    "fight": 4,
    "shoot": 0,
    "armour": 12,
    "will": 1,
    "health": 14,
}
CAPTAIN_MAX_LEVEL = 10

# The 4 stats that can ever be raised via a flat-XP level-up (Wizard, Captain,
# Soldier all share this set — matches the stat subset in LEVEL_UP_OPTIONS).
LEVELUP_STATS = ["fight", "shoot", "will", "health"]

# Per-stat level-up cap shape used by both Captain and Soldier Leveling:
# {"limit": int, "unlimited": bool} — limit is ignored when unlimited is True;
# limit 0 (and not unlimited) means that stat can never be leveled.
CAPTAIN_STAT_CAPS = {
    "fight": {"limit": 1, "unlimited": False},
    "shoot": {"limit": 1, "unlimited": False},
    "will": {"limit": 0, "unlimited": True},
    "health": {"limit": 0, "unlimited": True},
}

# Mind Control resistance flavor note (not simulated), per-warband selectable.
CAPTAIN_MIND_CONTROL_OPTIONS = ["immune", "resistant", "none"]
CAPTAIN_MIND_CONTROL_LABELS = {
    "immune": "Immune to Mind Control",
    "resistant": "Resistant to Mind Control",
    "none": "None",
}
CAPTAIN_MIND_CONTROL_DEFAULT = "immune"

# --- Soldier Leveling (homerule, not core 2e) -------------------------------
SOLDIER_LEVELING_ENABLED = False
SOLDIER_MAX_LEVELS = 3
SOLDIER_STAT_CAPS = {
    "fight": {"limit": 0, "unlimited": False},
    "shoot": {"limit": 0, "unlimited": False},
    "will": {"limit": 0, "unlimited": False},
    "health": {"limit": 3, "unlimited": False},
}

# --- Promote Captain (homerule, not core 2e) --------------------------------
# Independent of the Captains (hiring) homerule — a warband can allow only
# promotion, only hiring, both, or neither.
PROMOTE_CAPTAIN_ENABLED = False
PROMOTE_CAPTAIN_COST = 150
PROMOTE_CAPTAIN_BONUS = {"fight": 1, "shoot": 1, "will": 1, "health": 2}
PROMOTE_CAPTAIN_ITEM_SLOTS = 6

# Establishing a Base (2e core p.106–107)
BASE_LOCATIONS: dict[str, dict] = {
    "none": {
        "name": "No base yet",
        "effects": "Establish a free base location after one or more games.",
    },
    "inn": {
        "name": "Inn",
        "effects": (
            "May keep one extra soldier (can be specialist) who stays at base "
            "and cannot be used in a game. Still max 8 soldiers / 4 specialists in play."
        ),
    },
    "temple": {
        "name": "Temple",
        "effects": (
            "+3 to Miraculous Cure. After each game, roll d20: on 16+ gain a free potion of healing."
        ),
    },
    "crypt": {
        "name": "Crypt",
        "effects": "+2 to Raise Zombie and Animate Skull (in game or Out of Game).",
    },
    "tower": {
        "name": "Tower",
        "effects": "+2 Casting Rolls for Reveal Secret and Awareness.",
    },
    "treasury": {
        "name": "Treasury",
        "effects": (
            "After each game open a vault: d20 — 2–16 add that many gc; "
            "17–18 add 100+that; 19–20 find a treasure (roll as secured treasure)."
        ),
    },
    "brewery": {
        "name": "Brewery",
        "effects": "All soldiers start each game with +1 Will. +20gc after each game from sales.",
    },
    "library": {
        "name": "Library",
        "effects": "After each game roll d20: 15–18 random scroll; 19–20 random grimoire.",
    },
    "laboratory": {
        "name": "Laboratory",
        "effects": "Wizard gains +20 XP after each game (does not count against the 300 XP game cap).",
    },
}

BASE_RESOURCES: dict[str, dict] = {
    "kennel": {
        "name": "Kennel",
        "cost": 400,
        "effects": "May bring one war hound or wolf (Animal Companion) above normal soldier limit.",
    },
    "giant_cauldron": {
        "name": "Giant Cauldron",
        "cost": 250,
        "effects": "+1 Casting Rolls for Brew Potion.",
    },
    "enchanters_workshop": {
        "name": "Enchanter's Workshop",
        "cost": 400,
        "effects": "+1 Casting Rolls for Animate Construct and Embed Enchantment.",
    },
    "crystal_ball": {
        "name": "Crystal Ball",
        "cost": 250,
        "effects": "+1 Casting Rolls for Reveal Secret.",
    },
    "scriptorium": {
        "name": "Scriptorium",
        "cost": 200,
        "effects": "+1 Casting Rolls for Write Scroll.",
    },
    "celestial_telescope": {
        "name": "Celestial Telescope",
        "cost": 250,
        "effects": "Once per game, before rolling, add +5 to an Initiative Roll.",
    },
    "summoning_circle": {
        "name": "Summoning Circle",
        "cost": 300,
        "effects": (
            "Out of Game: attempt Summon Demon then Control Demon; "
            "success adds a temporary demon not counting toward max warband size."
        ),
    },
    "carrier_pigeons": {
        "name": "Carrier Pigeons",
        "cost": 50,
        "effects": "Soldiers hired cost 10gc less.",
    },
    "arcane_candle": {
        "name": "Arcane Candle",
        "cost": 100,
        "effects": "+1 Casting Rolls for Control Demon cast Out of Game.",
    },
    "summoning_candle": {
        "name": "Summoning Candle",
        "cost": 100,
        "effects": "+1 Casting Rolls for Summon Demon cast Out of Game.",
    },
    "sarcophagus_of_healing": {
        "name": "Sarcophagus of Healing",
        "cost": 300,
        "effects": (
            "Wizard does not miss a game or pay a fee when Badly Wounded; "
            "pays 10gc less for Niggling Injuries."
        ),
    },
}

# Casting number penalties by school relationship (p.18–24 tables)
CN_OWN = 0
CN_ALIGNED = 2
CN_NEUTRAL = 4
CN_OPPOSED = 6

WIZARD_BASE = {
    "move": 6,
    "fight": 2,
    "shoot": 0,
    "armour": 10,
    "will": 4,
    "health": 14,  # Starting Wizard, p.25
}

# Apprentice = wizard M, F-2, S, A10, W-2, H-2 (p.27–28)
APPRENTICE_BASE = {
    "move": 6,
    "fight": 0,
    "shoot": 0,
    "armour": 10,
    "will": 2,
    "health": 12,
}

APPRENTICE_STAT_OFFSET = {
    "move": 0,
    "fight": -2,
    "shoot": 0,
    "armour": 0,  # always 10 for apprentice per rules
    "will": -2,
    "health": -2,
}

SCHOOLS = [
    "Chronomancer",
    "Elementalist",
    "Enchanter",
    "Illusionist",
    "Necromancer",
    "Sigilist",
    "Soothsayer",
    "Summoner",
    "Thaumaturge",
    "Witch",
]

# Official 2e school relationship tables (aligned +2 / neutral +4 / opposed +6)
SCHOOL_RELATIONS: dict[str, dict] = {
    "Chronomancer": {
        "aligned": ["Elementalist", "Necromancer", "Soothsayer"],
        "neutral": ["Illusionist", "Sigilist", "Summoner", "Thaumaturge", "Witch"],
        "opposed": "Enchanter",
    },
    "Elementalist": {
        "aligned": ["Chronomancer", "Enchanter", "Summoner"],
        "neutral": ["Necromancer", "Sigilist", "Soothsayer", "Thaumaturge", "Witch"],
        "opposed": "Illusionist",
    },
    "Enchanter": {
        "aligned": ["Elementalist", "Sigilist", "Witch"],
        "neutral": ["Illusionist", "Necromancer", "Soothsayer", "Summoner", "Thaumaturge"],
        "opposed": "Chronomancer",
    },
    "Illusionist": {
        "aligned": ["Sigilist", "Soothsayer", "Thaumaturge"],
        "neutral": ["Chronomancer", "Enchanter", "Necromancer", "Summoner", "Witch"],
        "opposed": "Elementalist",
    },
    "Necromancer": {
        "aligned": ["Chronomancer", "Summoner", "Witch"],
        "neutral": ["Elementalist", "Enchanter", "Illusionist", "Sigilist", "Soothsayer"],
        "opposed": "Thaumaturge",
    },
    "Sigilist": {
        "aligned": ["Enchanter", "Illusionist", "Thaumaturge"],
        "neutral": ["Chronomancer", "Elementalist", "Necromancer", "Soothsayer", "Witch"],
        "opposed": "Summoner",
    },
    "Soothsayer": {
        "aligned": ["Chronomancer", "Illusionist", "Thaumaturge"],
        "neutral": ["Elementalist", "Enchanter", "Necromancer", "Sigilist", "Summoner"],
        "opposed": "Witch",
    },
    "Summoner": {
        "aligned": ["Elementalist", "Necromancer", "Witch"],
        "neutral": ["Chronomancer", "Enchanter", "Illusionist", "Soothsayer", "Thaumaturge"],
        "opposed": "Sigilist",
    },
    "Thaumaturge": {
        "aligned": ["Illusionist", "Sigilist", "Soothsayer"],
        "neutral": ["Chronomancer", "Elementalist", "Enchanter", "Summoner", "Witch"],
        "opposed": "Necromancer",
    },
    "Witch": {
        "aligned": ["Enchanter", "Necromancer", "Summoner"],
        "neutral": ["Chronomancer", "Elementalist", "Illusionist", "Sigilist", "Thaumaturge"],
        "opposed": "Soothsayer",
    },
}

# Convenience maps (derived)
SCHOOL_ALIGNED = {k: v["aligned"] for k, v in SCHOOL_RELATIONS.items()}
SCHOOL_NEUTRAL = {k: v["neutral"] for k, v in SCHOOL_RELATIONS.items()}
SCHOOL_OPPOSED = {k: v["opposed"] for k, v in SCHOOL_RELATIONS.items()}


def school_relation(wizard_school: str, spell_school: str) -> str:
    if wizard_school == spell_school:
        return "own"
    rel = SCHOOL_RELATIONS.get(wizard_school)
    if not rel:
        return "neutral"
    if spell_school in rel["aligned"]:
        return "aligned"
    if spell_school == rel["opposed"]:
        return "opposed"
    return "neutral"


def cn_penalty(wizard_school: str, spell_school: str) -> int:
    rel = school_relation(wizard_school, spell_school)
    return {
        "own": CN_OWN,
        "aligned": CN_ALIGNED,
        "neutral": CN_NEUTRAL,
        "opposed": CN_OPPOSED,
    }[rel]


def effective_cn(base_cn: int, wizard_school: str, spell_school: str) -> int:
    return int(base_cn) + cn_penalty(wizard_school, spell_school)


# Spells: base CN from 2e spell cards / core book
SPELLS: dict[str, list[dict]] = {
    "Chronomancer": [
        {"name": "Crumble", "cn": 10, "type": "Line of Sight"},
        {"name": "Decay", "cn": 12, "type": "Line of Sight"},
        {"name": "Fast Act", "cn": 8, "type": "Line of Sight"},
        {"name": "Fleet Feet", "cn": 10, "type": "Line of Sight"},
        {"name": "Petrify", "cn": 10, "type": "Line of Sight"},
        {"name": "Slow", "cn": 10, "type": "Line of Sight"},
        {"name": "Time Store", "cn": 14, "type": "Self Only"},
        {"name": "Time Walk", "cn": 14, "type": "Self Only"},
    ],
    "Elementalist": [
        {"name": "Call Storm", "cn": 12, "type": "Area Effect"},
        {"name": "Destructive Sphere", "cn": 12, "type": "Area Effect"},
        {"name": "Elemental Ball", "cn": 12, "type": "Line of Sight"},
        {"name": "Elemental Bolt", "cn": 12, "type": "Line of Sight"},
        {"name": "Elemental Hammer", "cn": 10, "type": "Line of Sight"},
        {"name": "Elemental Shield", "cn": 10, "type": "Self Only"},
        {"name": "Scatter Shot", "cn": 12, "type": "Area Effect"},
        {"name": "Wall", "cn": 10, "type": "Line of Sight"},
    ],
    "Enchanter": [
        {"name": "Animate Construct", "cn": 10, "type": "Out of Game (B)"},
        {"name": "Control Construct", "cn": 12, "type": "Line of Sight"},
        {"name": "Embed Enchantment", "cn": 14, "type": "Out of Game (A)"},
        {"name": "Enchant Armour", "cn": 8, "type": "Line of Sight"},
        {"name": "Enchant Weapon", "cn": 8, "type": "Line of Sight"},
        {"name": "Grenade", "cn": 10, "type": "Line of Sight"},
        {"name": "Strength", "cn": 10, "type": "Line of Sight"},
        {"name": "Telekinesis", "cn": 10, "type": "Line of Sight"},
    ],
    "Illusionist": [
        {"name": "Beauty", "cn": 10, "type": "Self Only"},
        {"name": "Blink", "cn": 12, "type": "Line of Sight"},
        {"name": "Fool's Gold", "cn": 10, "type": "Line of Sight"},
        {"name": "Glow", "cn": 10, "type": "Line of Sight"},
        {"name": "Illusionary Soldier", "cn": 12, "type": "Out of Game (B) / Touch"},
        {"name": "Invisibility", "cn": 12, "type": "Touch"},
        {"name": "Teleport", "cn": 10, "type": "Self Only"},
        {"name": "Transpose", "cn": 12, "type": "Line of Sight"},
    ],
    "Necromancer": [
        {"name": "Animate Skull", "cn": 8, "type": "Line of Sight"},
        {"name": "Bone Dart", "cn": 10, "type": "Line of Sight"},
        {"name": "Bones of the Earth", "cn": 10, "type": "Line of Sight"},
        {"name": "Control Undead", "cn": 12, "type": "Line of Sight"},
        {"name": "Raise Zombie", "cn": 10, "type": "Out of Game (B) / Touch"},
        {"name": "Spell Eater", "cn": 12, "type": "Line of Sight"},
        {"name": "Steal Health", "cn": 10, "type": "Line of Sight"},
        {"name": "Strike Dead", "cn": 18, "type": "Line of Sight"},
    ],
    "Sigilist": [
        {"name": "Absorb Knowledge", "cn": 12, "type": "Out of Game (A)"},
        {"name": "Bridge", "cn": 10, "type": "Line of Sight"},
        {"name": "Draining Word", "cn": 14, "type": "Area Effect"},
        {"name": "Explosive Rune", "cn": 10, "type": "Line of Sight"},
        {"name": "Furious Quill", "cn": 10, "type": "Line of Sight"},
        {"name": "Power Word", "cn": 14, "type": "Area Effect"},
        {"name": "Push", "cn": 8, "type": "Line of Sight"},
        {"name": "Write Scroll", "cn": 12, "type": "Out of Game (A)"},
    ],
    "Soothsayer": [
        {"name": "Awareness", "cn": 12, "type": "Out of Game (B)"},
        {"name": "Combat Awareness", "cn": 12, "type": "Touch"},
        {"name": "Mind Control", "cn": 12, "type": "Line of Sight"},
        {"name": "Mind Lock", "cn": 12, "type": "Line of Sight"},
        {"name": "Reveal Secret", "cn": 12, "type": "Out of Game (B)"},
        {"name": "Suggestion", "cn": 12, "type": "Line of Sight"},
        {"name": "True Sight", "cn": 10, "type": "Self Only"},
        {"name": "Wizard Eye", "cn": 8, "type": "Line of Sight"},
    ],
    "Summoner": [
        {"name": "Control Demon", "cn": 10, "type": "Line of Sight"},
        {"name": "Imp", "cn": 10, "type": "Line of Sight"},
        {"name": "Leap", "cn": 8, "type": "Line of Sight"},
        {"name": "Plague of Insects", "cn": 10, "type": "Line of Sight"},
        {"name": "Planar Tear", "cn": 12, "type": "Line of Sight"},
        {"name": "Plane Walk", "cn": 10, "type": "Self Only"},
        {"name": "Possess", "cn": 12, "type": "Line of Sight"},
        {"name": "Summon Demon", "cn": 12, "type": "Touch"},
    ],
    "Thaumaturge": [
        {"name": "Banish", "cn": 10, "type": "Line of Sight"},
        {"name": "Blinding Light", "cn": 8, "type": "Line of Sight"},
        {"name": "Circle of Protection", "cn": 12, "type": "Touch"},
        {"name": "Destroy Undead", "cn": 10, "type": "Line of Sight"},
        {"name": "Dispel", "cn": 12, "type": "Line of Sight"},
        {"name": "Heal", "cn": 8, "type": "Line of Sight"},
        {"name": "Miraculous Cure", "cn": 16, "type": "Out of Game (A)"},
        {"name": "Shield", "cn": 10, "type": "Line of Sight"},
    ],
    "Witch": [
        {"name": "Animal Companion", "cn": 10, "type": "Out of Game (B)"},
        {"name": "Brew Potion", "cn": 12, "type": "Out of Game (B)"},
        {"name": "Control Animal", "cn": 12, "type": "Line of Sight"},
        {"name": "Curse", "cn": 8, "type": "Line of Sight"},
        {"name": "Familiar", "cn": 10, "type": "Out of Game (B)"},
        {"name": "Fog", "cn": 8, "type": "Line of Sight"},
        {"name": "Mud", "cn": 10, "type": "Line of Sight"},
        {"name": "Poison Dart", "cn": 10, "type": "Line of Sight"},
    ],
}

LEVEL_UP_OPTIONS = [
    {"id": "fight", "label": "+1 Fight", "stat": "fight"},
    {"id": "shoot", "label": "+1 Shoot", "stat": "shoot"},
    {"id": "will", "label": "+1 Will", "stat": "will"},
    {"id": "health", "label": "+1 Health", "stat": "health"},
    {"id": "learn_spell", "label": "Learn a new spell", "stat": None},
    {"id": "improve_spell", "label": "Improve a known spell (−1 CN)", "stat": None},
]

# Soldier tables p.30–31
SOLDIERS: dict[str, dict] = {
    "thug": {
        "name": "Thug",
        "cost": 0,
        "category": "standard",
        "move": 6,
        "fight": 2,
        "shoot": 0,
        "armour": 10,
        "will": -1,
        "health": 10,
        "gear": "Hand weapon",
        "notes": "Free standard soldier.",
    },
    "thief": {
        "name": "Thief",
        "cost": 0,
        "category": "standard",
        "move": 7,
        "fight": 1,
        "shoot": 0,
        "armour": 10,
        "will": 0,
        "health": 10,
        "gear": "Dagger",
        "notes": "Free standard soldier.",
    },
    "war_hound": {
        "name": "War Hound",
        "cost": 10,
        "category": "standard",
        "move": 8,
        "fight": 1,
        "shoot": 0,
        "armour": 10,
        "will": -2,
        "health": 8,
        "gear": "—",
        "notes": "Animal; no treasure, no item slots.",
    },
    "infantryman": {
        "name": "Infantryman",
        "cost": 50,
        "category": "standard",
        "move": 6,
        "fight": 3,
        "shoot": 0,
        "armour": 11,
        "will": 0,
        "health": 10,
        "gear": "Two-handed weapon, light armour",
        "notes": "Standard soldier.",
    },
    "man_at_arms": {
        "name": "Man-at-Arms",
        "cost": 75,
        "category": "standard",
        "move": 6,
        "fight": 3,
        "shoot": 0,
        "armour": 12,
        "will": 1,
        "health": 12,
        "gear": "Hand weapon, shield, light armour",
        "notes": "Standard soldier.",
    },
    "apothecary": {
        "name": "Apothecary",
        "cost": 75,
        "category": "standard",
        "move": 6,
        "fight": 1,
        "shoot": 0,
        "armour": 10,
        "will": 3,
        "health": 12,
        "gear": "Staff, healing potion",
        "notes": "Standard. Starts with potion of healing each game.",
    },
    "archer": {
        "name": "Archer",
        "cost": 75,
        "category": "specialist",
        "move": 6,
        "fight": 1,
        "shoot": 2,
        "armour": 11,
        "will": 0,
        "health": 10,
        "gear": "Bow, quiver, dagger, light armour",
        "notes": "Specialist.",
    },
    "crossbowman": {
        "name": "Crossbowman",
        "cost": 75,
        "category": "specialist",
        "move": 6,
        "fight": 1,
        "shoot": 2,
        "armour": 11,
        "will": 0,
        "health": 10,
        "gear": "Crossbow, quiver, dagger, light armour",
        "notes": "Specialist.",
    },
    "treasure_hunter": {
        "name": "Treasure Hunter",
        "cost": 100,
        "category": "specialist",
        "move": 7,
        "fight": 3,
        "shoot": 0,
        "armour": 11,
        "will": 2,
        "health": 12,
        "gear": "Hand weapon, dagger, light armour",
        "notes": "Specialist.",
    },
    "tracker": {
        "name": "Tracker",
        "cost": 100,
        "category": "specialist",
        "move": 7,
        "fight": 1,
        "shoot": 2,
        "armour": 11,
        "will": 1,
        "health": 12,
        "gear": "Staff, bow, quiver, light armour",
        "notes": "Specialist.",
    },
    "knight": {
        "name": "Knight",
        "cost": 125,
        "category": "specialist",
        "move": 5,
        "fight": 4,
        "shoot": 0,
        "armour": 13,
        "will": 1,
        "health": 12,
        "gear": "Hand weapon, dagger, shield, heavy armour",
        "notes": "Specialist.",
    },
    "templar": {
        "name": "Templar",
        "cost": 125,
        "category": "specialist",
        "move": 5,
        "fight": 4,
        "shoot": 0,
        "armour": 12,
        "will": 1,
        "health": 12,
        "gear": "Two-handed weapon, heavy armour",
        "notes": "Specialist.",
    },
    "ranger": {
        "name": "Ranger",
        "cost": 125,
        "category": "specialist",
        "move": 7,
        "fight": 2,
        "shoot": 2,
        "armour": 11,
        "will": 2,
        "health": 12,
        "gear": "Bow, quiver, hand weapon, light armour",
        "notes": "Specialist.",
    },
    "barbarian": {
        "name": "Barbarian",
        "cost": 125,
        "category": "specialist",
        "move": 6,
        "fight": 4,
        "shoot": 0,
        "armour": 10,
        "will": 3,
        "health": 14,
        "gear": "Two-handed weapon, dagger",
        "notes": "Specialist.",
    },
    "marksman": {
        "name": "Marksman",
        "cost": 125,
        "category": "specialist",
        "move": 5,
        "fight": 2,
        "shoot": 2,
        "armour": 12,
        "will": 1,
        "health": 12,
        "gear": "Crossbow, quiver, hand weapon, heavy armour",
        "notes": "Specialist.",
    },
}


def soldier_list_for_ui() -> list[dict]:
    rows = [{"key": k, **v} for k, v in SOLDIERS.items()]
    rows.sort(key=lambda r: (r["category"] != "standard", r["cost"], r["name"]))
    return rows


def get_soldier(type_key: str) -> dict | None:
    s = SOLDIERS.get(type_key)
    return deepcopy(s) if s else None


def format_stat(value: int) -> str:
    return f"+{value}" if value >= 0 else str(value)


def all_spells_flat() -> list[dict]:
    out = []
    for school, spells in SPELLS.items():
        for sp in spells:
            out.append({**sp, "school": school, "id": spell_id(school, sp["name"])})
    return out


def spell_id(school: str, name: str) -> str:
    return f"{school}::{name}"


def find_spell(spell_key: str) -> dict | None:
    if "::" not in spell_key:
        return None
    school, name = spell_key.split("::", 1)
    for sp in SPELLS.get(school, []):
        if sp["name"] == name:
            return {**sp, "school": school, "id": spell_key}
    return None


def spells_for_wizard_ui(wizard_school: str) -> list[dict]:
    """All spells with relation + effective CN for a wizard school."""
    out = []
    for sp in all_spells_flat():
        rel = school_relation(wizard_school, sp["school"])
        pen = cn_penalty(wizard_school, sp["school"])
        out.append(
            {
                **sp,
                "relation": rel,
                "cn_penalty": pen,
                "effective_cn": sp["cn"] + pen,
            }
        )
    return out


def xp_for_level(level: int) -> int:
    return max(0, int(level)) * XP_PER_LEVEL


def level_from_xp(xp: int) -> int:
    return min(MAX_WIZARD_LEVEL, max(0, int(xp) // XP_PER_LEVEL))


def xp_to_next_level(xp: int, level: int) -> int:
    return max(0, xp_for_level(level + 1) - int(xp))
