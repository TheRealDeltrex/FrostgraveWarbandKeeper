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
CAPTAIN_HIRING_COST = 125
CAPTAIN_ITEM_SLOTS = 6
CAPTAIN_BASE = {
    "move": 6,
    "fight": 2,
    "shoot": 1,
    "armour": 10,
    "will": 3,
    "health": 12,
}
CAPTAIN_MAX_LEVEL = 10

# The single "+1 to a stat of your choice" a captain gets at hire or promotion.
# Health moves in larger steps than the other stats everywhere else in the game,
# so spending the pick on Health is worth +2. Applies to hired and promoted
# captains alike.
BONUS_CHOICE_AMOUNTS = {"health": 2}


def bonus_choice_amount(stat: str) -> int:
    """How much the captain's chosen +1 bonus is actually worth for `stat`."""
    return BONUS_CHOICE_AMOUNTS.get(stat, 1)

# The 4 stats that can ever be raised via a flat-XP level-up (Wizard, Captain,
# Soldier all share this set — matches the stat subset in LEVEL_UP_OPTIONS).
LEVELUP_STATS = ["fight", "shoot", "will", "health"]

# Per-stat level-up cap shape used by both Captain and Soldier Leveling:
# {"limit": int, "unlimited": bool} — limit is ignored when unlimited is True;
# limit 0 (and not unlimited) means that stat can never be leveled.
CAPTAIN_STAT_CAPS = {
    "fight": {"limit": 1, "unlimited": False},
    "shoot": {"limit": 1, "unlimited": False},
    "will": {"limit": 1, "unlimited": False},
    "health": {"limit": 2, "unlimited": False},
}

# Mind Control resistance flavor note (not simulated), per-warband selectable.
CAPTAIN_MIND_CONTROL_OPTIONS = ["immune", "resistant", "none"]
CAPTAIN_MIND_CONTROL_LABELS = {
    "immune": "Immune to Mind Control",
    "resistant": "Resistant to Mind Control",
    "none": "None",
}
CAPTAIN_MIND_CONTROL_DEFAULT = "immune"

# How a warband can get a Captain at all: hiring, promoting an existing soldier,
# both, or neither (off — the default, like every other homerule here).
CAPTAIN_MODE_OPTIONS = ["off", "hire", "promote", "both"]
CAPTAIN_MODE_LABELS = {
    "off": "Off (no captain homerule)",
    "hire": "Hire only",
    "promote": "Promote only",
    "both": "Hire or promote",
}
CAPTAIN_MODE_DEFAULT = "off"

# "Tricks of the Trade" (FG1E Sellswords supplement, p.20) — purely descriptive,
# not mechanically simulated (the player applies these at the table, same as
# Mind Control above). A starting captain knows CAPTAIN_STARTING_TRICKS of
# these (per-warband editable); every level-up may be spent learning one more
# instead of a stat point.
CAPTAIN_TRICKS = [
    {"id": "furious_attack", "name": "Furious Attack", "effect": "+3 Fight for one attack", "declare": "Before the rolls are made"},
    {"id": "riposte", "name": "Riposte", "effect": "+1 Fight for one attack", "declare": "After the rolls are made"},
    {"id": "coup_de_grace", "name": "Coup de Grâce", "effect": "+2 Damage to any hand-to-hand attack that has dealt at least 1 point of damage", "declare": "After damage is calculated"},
    {"id": "steady_hand", "name": "Steady Hand", "effect": "+3 Shoot for one attack", "declare": "Before the rolls are made"},
    {"id": "dead_eye", "name": "Dead Eye", "effect": "+1 Shoot for one attack", "declare": "After the rolls are made"},
    {"id": "brace", "name": "Brace", "effect": "+3 Armour for one attack", "declare": "Before the rolls are made"},
    {"id": "dodge", "name": "Dodge", "effect": "+1 Armour to one attack", "declare": "After the rolls are made"},
    {"id": "nerves_of_steel", "name": "Nerves of Steel", "effect": "+4 Will for one Will roll", "declare": "Before the roll is made"},
    {"id": "iron_heart", "name": "Iron Heart", "effect": "+2 Will for one Will roll", "declare": "After the roll is made"},
    {"id": "sprint", "name": "Sprint", "effect": "+2 Move for the rest of the turn", "declare": "Upon activation"},
    {"id": "leadership", "name": "Leadership", "effect": "If using a Group Activation, the captain may activate up to three soldiers within 3\" who have not already been activated in the turn", "declare": "Upon activation"},
]
CAPTAIN_TRICK_IDS = {t["id"] for t in CAPTAIN_TRICKS}
CAPTAIN_TRICK_BY_ID = {t["id"]: t for t in CAPTAIN_TRICKS}
CAPTAIN_STARTING_TRICKS = 2

# --- Soldier Leveling (homerule, not core 2e) -------------------------------
SOLDIER_LEVELING_ENABLED = False
SOLDIER_MAX_LEVELS = 3
SOLDIER_STAT_CAPS = {
    "fight": {"limit": 0, "unlimited": False},
    "shoot": {"limit": 0, "unlimited": False},
    "will": {"limit": 1, "unlimited": False},
    "health": {"limit": 2, "unlimited": False},
}

# --- Promote Captain (homerule, not core 2e) --------------------------------
# Whether promotion (vs. hiring) is available is governed by CAPTAIN_MODE_* above.
PROMOTE_CAPTAIN_COST = 150
# No automatic across-the-board bonus by default — a promoted captain's gain is
# the player-chosen +1 instead (promote_captain_bonus_choice_enabled, on by
# default). Still editable per warband for groups who want a flat package.
PROMOTE_CAPTAIN_BONUS = {"fight": 0, "shoot": 0, "will": 0, "health": 0}
PROMOTE_CAPTAIN_ITEM_SLOTS = 6
# Tricks a soldier learns on being promoted. Separate from CAPTAIN_STARTING_TRICKS
# so a group can make promotion more or less rewarding than hiring.
PROMOTE_CAPTAIN_TRICKS = 2

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
    # --- Supplement resources (gated by the per-warband source-book toggles) ---
    # A missing "source" means Core Rules, so everything above is unaffected.
    "crow_roost": {
        "name": "Crow Roost",
        "cost": 100,
        "source": "Thaw of the Lich Lord",
        "effects": "Required to hire a Crow Master. One roost per Crow Master.",
    },
    "gondola_repair_shop": {
        "name": "Gondola Repair Shop",
        "cost": 500,
        "source": "The Maze of Malcor",
        "effects": "Repairs 5 damage to an owned sky gondola after each game.",
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
    # Beastcrafter is not a school any wizard may pick — its two spells are
    # unlocked by the Beastcrafter state (see expansions.BEASTCRAFTER_SPELLS).
    "Beastcrafter": [
        {
            "name": "Animal Manipulation",
            "cn": 10,
            "type": "Line of Sight",
            "source": "Into the Breeding Pits",
        },
        {
            "name": "Animal Mutation",
            "cn": 14,
            "type": "Out of Game",
            "source": "Into the Breeding Pits",
        },
    ],
}

# Supplement spells, folded into SPELLS above by school. Kept as a separate table
# so the additions stay visible and reviewable against the source books, rather
# than being scattered through 80 core entries.
SUPPLEMENT_SPELLS: dict[str, list[dict]] = {
    # --- Thaw of the Lich Lord ---
    "Witch": [
        {
            "name": "Homunculus",
            "cn": 14,
            "type": "Out of Game",
            "source": "Thaw of the Lich Lord",
        },
    ],
    "Necromancer": [
        {"name": "Lichdom", "cn": 20, "type": "Out of Game", "source": "Thaw of the Lich Lord"},
        {"name": "Revenant", "cn": 14, "type": "Out of Game", "source": "Thaw of the Lich Lord"},
    ],
    # --- Into the Breeding Pits (Reaction spells are a new category) ---
    "Sigilist": [
        {
            "name": "Capture Incantation",
            "cn": 12,
            "type": "Reaction",
            "source": "Into the Breeding Pits",
        },
        {"name": "Mystic Brand", "cn": 12, "type": "Out of Game", "source": "Forgotten Pacts"},
    ],
    "Soothsayer": [
        {"name": "Deflect", "cn": 12, "type": "Reaction", "source": "Into the Breeding Pits"},
    ],
    "Elementalist": [
        {"name": "Elemental Lash", "cn": 12, "type": "Reaction", "source": "Into the Breeding Pits"},
    ],
    "Illusionist": [
        {"name": "Flash", "cn": 8, "type": "Reaction", "source": "Into the Breeding Pits"},
    ],
    "Chronomancer": [
        {
            "name": "Slowfall",
            "cn": 8,
            "type": "Reaction / Line of Sight",
            "source": "Into the Breeding Pits",
        },
    ],
    # --- Forgotten Pacts ---
    "Summoner": [
        {
            "name": "Demonic Servant",
            "cn": 10,
            "type": "Out of Game",
            "source": "Forgotten Pacts",
        },
    ],
}

for _school, _extra in SUPPLEMENT_SPELLS.items():
    SPELLS.setdefault(_school, []).extend(_extra)
    SPELLS[_school].sort(key=lambda sp: sp["name"])
del _school, _extra

# --- The Pentangle (The Maze of Malcor) ------------------------------------
#
# Five schools taught at the Collegium and lost with it. The book is explicit
# that they "can never be learned, and a wizard will never find a grimoire
# containing them" — they exist only on scrolls. It then includes rules for
# running them as full schools if a group agrees, which the
# "pentangle_schools_playable" homerule switches on.
#
# Casting numbers and ranges are extracted from the Lost Spells chapter of the
# book itself (scripts/extract_pentangle_spells.py), not guessed.
PENTANGLE_SCHOOLS = ["Astromancer", "Distortionist", "Fatecaster", "Sonancer", "Spiritualist"]

# Each combines two existing schools and is aligned with both. The book gives no
# opposed school for them.
PENTANGLE_RELATIONS = {
    "Astromancer": {"combines": ["Sigilist", "Elementalist"], "aligned": ["Elementalist", "Sigilist"]},
    "Distortionist": {"combines": ["Illusionist", "Summoner"], "aligned": ["Illusionist", "Summoner"]},
    "Fatecaster": {"combines": ["Soothsayer", "Witch"], "aligned": ["Soothsayer", "Witch"]},
    "Sonancer": {"combines": ["Chronomancer", "Enchanter"], "aligned": ["Chronomancer", "Enchanter"]},
    "Spiritualist": {"combines": ["Necromancer", "Thaumaturge"], "aligned": ["Necromancer", "Thaumaturge"]},
}

LOST_SPELLS: dict[str, list[dict]] = {
    "Astromancer": [
        {"name": "Alignment", "cn": 12, "type": "Self Only"},
        {"name": "Meteor Strike", "cn": 14, "type": "Line of Sight"},
        {"name": "Misalignment", "cn": 10, "type": "Area Effect"},
        {"name": "Shape Starfire Elemental", "cn": 12, "type": "Line of Sight"},
        {"name": "Starfall", "cn": 12, "type": "Area Effect"},
        {"name": "Starfire Bolt", "cn": 14, "type": "Line of Sight"},
    ],
    "Distortionist": [
        {"name": "Break Armour", "cn": 10, "type": "Line of Sight"},
        {"name": "Collapse", "cn": 8, "type": "Line of Sight"},
        {"name": "Fracture", "cn": 12, "type": "Self Only"},
        {"name": "Implode / Explode", "cn": 12, "type": "Line of Sight"},
        {"name": "Misstep", "cn": 10, "type": "Out of Game"},
        {"name": "Whiplash", "cn": 12, "type": "Self Only"},
    ],
    "Fatecaster": [
        {"name": "Blood Wager", "cn": 10, "type": "Self Only"},
        {"name": "Fickle Finger", "cn": 12, "type": "Line of Sight"},
        {"name": "Mischance", "cn": 8, "type": "Line of Sight"},
        {"name": "Scatter", "cn": 8, "type": "Line of Sight"},
        {"name": "Serendipity", "cn": 8, "type": "Line of Sight"},
        {"name": "True Gold", "cn": 10, "type": "Out of Game"},
    ],
    "Sonancer": [
        {"name": "Charm", "cn": 8, "type": "Area Effect"},
        {"name": "Humming Blade", "cn": 8, "type": "Line of Sight"},
        {"name": "Imbue Instrument", "cn": 10, "type": "Self Only & Out of Game"},
        {"name": "Sound Cloud", "cn": 10, "type": "Self Only"},
        {"name": "Sound Wave", "cn": 12, "type": "Line of Sight"},
        {"name": "Steal Voice", "cn": 12, "type": "Line of Sight"},
    ],
    "Spiritualist": [
        {"name": "Call Wraith", "cn": 12, "type": "Line of Sight"},
        {"name": "Command Ethereal", "cn": 12, "type": "Line of Sight"},
        {"name": "Ethereal Form", "cn": 10, "type": "Self Only"},
        {"name": "Inhabit", "cn": 8, "type": "Line of Sight"},
        {"name": "Nightmare", "cn": 12, "type": "Out of Game"},
        {"name": "Speak with the Dead", "cn": 12, "type": "Out of Game"},
    ],
}

for _school, _spells in LOST_SPELLS.items():
    SPELLS[_school] = [{**sp, "source": "The Maze of Malcor"} for sp in _spells]
    SCHOOL_RELATIONS[_school] = {
        "aligned": PENTANGLE_RELATIONS[_school]["aligned"],
        "neutral": [s for s in SCHOOLS if s not in PENTANGLE_RELATIONS[_school]["aligned"]],
        "opposed": "",
    }
del _school, _spells

# Schools that carry spells but that no wizard may choose at creation. They are
# reachable only through a wizard state (Beastcrafter) or, for the Pentangle,
# the "Pentangle schools playable" homerule.
EXTRA_SPELL_SCHOOLS = ["Beastcrafter"] + PENTANGLE_SCHOOLS

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
        "description": 'A common laborer or petty criminal turned muscle-for-hire — no training, just a hand weapon and a willingness to fight. No special rules beyond their listed gear.',
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
        "description": 'Fast and light-fingered, trained to slip in, grab treasure, and slip out again rather than stand and fight. Free to hire, armed only with a dagger. No special rules beyond their listed gear.',
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
        "description": 'A trained hunting dog, useful for harrying an enemy rather than holding a line. Animal: cannot pick up treasure tokens and has no item slot.',
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
        "description": 'A basic melee soldier, competent with a two-handed weapon and equipped with light armour. No special rules beyond their listed gear.',
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
        "description": "A disciplined hand-weapon-and-shield fighter in light armour, sturdier than an infantryman thanks to the shield's extra protection. No special rules beyond their listed gear.",
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
        "description": 'A battlefield healer who starts every game already carrying a potion of healing. May spend an action to hand any potion they carry — not just the free one — to a warband member within 1" who isn\'t in combat; that figure counts as having drunk it immediately, with the effects applied right away.',
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
        "description": 'A trained bowman. A bow loads and fires as a single action, so an archer can move and shoot within the same activation.',
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
        "description": 'A marksman with a heavier, harder-hitting weapon. A crossbow deals +2 damage but must be loaded and fired as two separate actions, so a crossbowman cannot move and shoot in the same activation.',
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
        "description": 'A scrappy adventurer built for grabbing loot and getting out alive, with solid Fight and Will for a mid-cost specialist. No special rules beyond their listed gear.',
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
        "description": 'A woodsman equally comfortable at range or in melee, carrying both a staff and a bow. Like all bows, theirs loads and fires as a single action, so they can move and shoot in the same activation.',
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
        "description": 'A heavily armoured melee specialist with a hand weapon, dagger, and shield. No special rules beyond their listed gear.',
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
        "description": "A heavily armoured warrior who trades the knight's shield for a two-handed weapon, giving up some defense for extra damage. No special rules beyond their listed gear.",
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
        "description": 'A versatile fighter carrying both a bow and a hand weapon, able to switch between ranged and melee as a fight develops. Like all bows, theirs loads and fires as a single action.',
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
        "description": 'A savage two-handed fighter with the highest Health of any specialist, built to wade into combat and keep swinging. No special rules beyond their listed gear.',
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
        "description": 'An elite crossbowman in heavy armour, backing up their hard-hitting shot with a hand weapon for when an enemy closes the distance. Like all crossbows, theirs must be loaded and fired as two separate actions, so a marksman cannot move and shoot in the same activation.',
    },
    # --- Supplement soldiers (gated by the per-warband source-book toggles) ---
    # Categorisation (standard/specialist) follows the Supplemental Soldier
    # Table in the 2e core rulebook (p.199).
    "javelineer": {
        "name": "Javelineer",
        "cost": 25,
        "category": "standard",
        "source": "Thaw of the Lich Lord",
        "move": 6,
        "fight": 0,
        "shoot": 0,
        "armour": 10,
        "will": 0,
        "health": 10,
        "gear": "Javelins",
        "notes": "Javelins are hand weapons in melee and may be thrown up to 10\" as a shooting attack.",
        "description": 'A skirmisher who fights with a bundle of javelins — a hand weapon in melee, or a 10" thrown shooting attack, drawn from a functionally unlimited supply.',
    },
    "pack_mule": {
        "name": "Pack Mule",
        "cost": 20,
        "category": "standard",
        "source": "Thaw of the Lich Lord",
        "move": 6,
        "fight": 0,
        "shoot": 0,
        "armour": 10,
        "will": 0,
        "health": 10,
        "gear": "Dagger",
        "notes": "May carry up to three items and hand them to nearby warband members (3 item slots).",
        "description": 'A hired hand whose whole job is logistics: they carry three items and can hand any of them off to (or take one from) a warband member within 1", freeing up other soldiers\' single item slot for something more useful in a fight.',
    },
    "bard": {
        "name": "Bard",
        "cost": 100,
        "category": "standard",
        "source": "Thaw of the Lich Lord",
        "move": 6,
        "fight": 2,
        "shoot": 0,
        "armour": 11,
        "will": 4,
        "health": 12,
        "gear": "Hand weapon, leather armour",
        "notes": "Soldiers within 6\" and line of sight gain +1 to Will rolls (once per warband).",
        "description": 'A traveling performer whose music steadies nerves in the field. Warband members within 6" and line of sight of a bard get +1 to Will rolls; this bonus doesn\'t stack with a second bard and never applies to the bard themself.',
    },
    "crow_master": {
        "name": "Crow Master",
        "cost": 100,
        "category": "standard",
        "source": "Thaw of the Lich Lord",
        "move": 6,
        "fight": 0,
        "shoot": 0,
        "armour": 11,
        "will": 2,
        "health": 10,
        "gear": "Hand weapon, leather armour",
        "notes": "Requires a Crow Roost base upgrade (100gc). Brings one blood crow; may carry treasure but no items.",
        "description": "A handler bonded to a trained blood crow. Requires a Crow Roost base upgrade (100gc) before one can be hired. Comes with one blood crow that acts independently and is replaced free of charge if it's killed; the crow master may carry treasure but has no item slots of their own.",
    },
    "rangifer": {
        "name": "Rangifer",
        "cost": 100,
        "category": "standard",
        "source": "Thaw of the Lich Lord",
        "move": 7,
        "fight": 2,
        "shoot": 0,
        "armour": 12,
        "will": 3,
        "health": 12,
        "gear": "Hand weapon",
        "notes": "Reindeer-man hybrid. Hate Undead: +1 Fight and magic attacks when fighting undead.",
        "description": 'A reindeer-human hybrid from the far north with a deep-seated hatred of the walking dead. Hate Undead: gains +1 Fight and all its attacks count as magic when fighting undead creatures. Will refuse to join, or leave, a warband that fields any undead member.',
    },
    "collegium_porter": {
        "name": "Collegium Porter",
        "cost": 0,
        "category": "standard",
        "source": "The Maze of Malcor",
        "move": 5,
        "fight": 4,
        "shoot": 0,
        "armour": 13,
        "will": 3,
        "health": 14,
        "gear": "—",
        "notes": (
            "Joins via the Porter Control Rod (treasure), not purchased. Construct; "
            "never attacks spellcasters; gains 3 potion/scroll item slots once recruited."
        ),
        "description": 'Constructs unique to the Collegium that once served as door guards, message carriers, and low-level security — mostly resembling fancy furniture with short legs and long arms, now feral with no staff to command them. Joins only via a Porter Control Rod (treasure, not purchased). Construct: immune to poison, never counts as wounded, may carry treasure but has no item slots. Never forces combat with a spellcaster; gains 3 potion/scroll-only item slots once recruited.',
    },
    "trap_expert": {
        "name": "Trap Expert",
        "cost": 50,
        "category": "standard",
        "source": "Into the Breeding Pits",
        "move": 6,
        "fight": 2,
        "shoot": 0,
        "armour": 11,
        "will": 1,
        "health": 12,
        "gear": "Two daggers, leather armour",
        "notes": "Once per game, may treat the first initiative roll of 2 as a 1 for the purpose of springing a trap.",
        "description": "Someone who has survived the city's traps often enough to read the warning signs. Once per game, treats the first initiative roll of 2 as a 1 for the purpose of springing a trap, giving the party one extra chance to avoid it.",
    },
    "tunnel_fighter": {
        "name": "Tunnel Fighter",
        "cost": 80,
        "category": "standard",
        "source": "Into the Breeding Pits",
        "move": 6,
        "fight": 3,
        "shoot": 0,
        "armour": 11,
        "will": 1,
        "health": 12,
        "gear": "Two hand weapons, leather armour",
        "notes": "With the Secret Passages rules, an initiative roll of 19 lets one tunnel fighter discover a secret passage.",
        "description": "A specialist trained for the city's collapsed passages and hidden shortcuts. Under the Secret Passages rules, an initiative roll of 19 lets a tunnel fighter (and only a tunnel fighter) discover and use a secret passage that game.",
    },
    "assassin": {
        "name": "Assassin",
        "cost": 80,
        "category": "standard",
        "source": "Forgotten Pacts",
        "move": 6,
        "fight": 2,
        "shoot": 0,
        "armour": 10,
        "will": 3,
        "health": 12,
        "gear": "Hand weapon",
        "notes": "Attacks poison (target reduced to one action). +2 Fight when already supported; never counts as a supporting figure.",
        "description": 'A killer for hire who works best from the shadows of a crowd rather than alone. Attacks are poisoned, reducing the target to one action. Gains +2 Fight whenever already supported by another figure, but never counts as a supporting figure themself.',
    },
    "demonic_servant": {
        "name": "Demonic Servant",
        "cost": 0,
        "category": "standard",
        "source": "Forgotten Pacts",
        "move": 6,
        "fight": 1,
        "shoot": 0,
        "armour": 10,
        "will": 4,
        "health": 10,
        "gear": "—",
        "requires_spell": "Demonic Servant",
        "notes": "Joins via the Demonic Servant spell (never purchased). Demon; one minor demonic attribute; aids Summon Demon rolls.",
        "description": "A minor demon bound into service, joining a warband only through the Demonic Servant spell (Forgotten Pacts) rather than being purchased. Demon: immune to poison, all its attacks count as magic, and it may carry treasure tokens but has no item slots. Rolls one Minor Demonic Attribute on arrival and improves the wizard's future Summon Demon rolls.",
    },
    # Joins through a pact boon rather than a spell — gated in expansions.py.
    "chilopendra": {
        "name": "Chilopendra",
        "cost": 0,
        "category": "standard",
        "source": "Forgotten Pacts",
        "move": 6,
        "fight": 4,
        "shoot": 0,
        "armour": 12,
        "will": 4,
        "health": 14,
        "gear": "—",
        "notes": "Requires the Chilopendra Soldier pact boon (Tiszirain). Demon; Horns; Poisonous.",
        "description": 'Demon/human hybrids created when a human sacrifices himself to the demon lord Tiszirain; human from the waist up, with the lower body of a great centipede, fighting just as readily with sharp horns and envenomed legs as with a weapon. Joins only through the Chilopendra Soldier pact boon (Forgotten Pacts, Tiszirain pact only). Demon: immune to poison, all its attacks count as magic, may carry treasure tokens but has no item slots. Horns: +2 Fight when it charges into combat and fights in the same activation. Poisonous: its own attacks deal poison damage.',
    },
    "demon_hunter": {
        "name": "Demon Hunter",
        "cost": 100,
        "category": "specialist",
        "source": "Forgotten Pacts",
        "move": 6,
        "fight": 2,
        "shoot": 2,
        "armour": 11,
        "will": 2,
        "health": 12,
        "gear": "Two-handed weapon, crossbow, leather armour",
        "notes": "+1 Fight and +1 damage vs demons. Variable cost: base 100gc (+25gc if the wizard knows Summon Demon/Imp/Possess, +25gc if a Summoner, +50gc if the base has a summoning circle).",
        "description": 'A specialist trained specifically to fight demons, dealing +1 Fight and +1 damage against them. Cost is variable rather than fixed: base 100gc, +25gc if the wizard knows Summon Demon, Imp, or Possess, a further +25gc if the wizard is a Summoner, and +50gc if the base owns a Summoning Circle — the more demon-adjacent the warband already is, the more this specialist costs to bring in.',
    },
    "monk": {
        "name": "Monk",
        "cost": 100,
        "category": "specialist",
        "source": "Forgotten Pacts",
        "move": 6,
        "fight": 4,
        "shoot": 0,
        "armour": 10,
        "will": 4,
        "health": 12,
        "gear": "Bladed staff",
        "notes": "Bladed staff: +1 Fight and -1 to the enemy's hand-to-hand attacks.",
        "description": "A disciplined martial artist who fights with a bladed staff — a quarterstaff with a blade lashed to one end. It grants +1 Fight and reduces the enemy's hand-to-hand damage against the monk by 1.",
    },
    "mystic_warrior": {
        "name": "Mystic Warrior",
        "cost": 100,
        "category": "specialist",
        "source": "Forgotten Pacts",
        "move": 6,
        "fight": 4,
        "shoot": 0,
        "armour": 10,
        "will": 4,
        "health": 12,
        "gear": "Unarmed (gauntlets / vambraces)",
        "notes": "Never suffers unarmed penalties; all hand-to-hand attacks count as magic attacks.",
        "description": 'A warrior who has trained the body itself into a weapon. Fights unarmed with no penalty, and every hand-to-hand attack they make counts as a magic attack — able to hurt creatures that are otherwise immune to normal weapons.',
    },
    # --- Spell-summoned members: only hireable (free) when the wizard knows the
    # listed spell. Gated by "requires_spell", not a source book. ---
    "small_construct": {
        "name": "Small Construct",
        "cost": 0,
        "category": "standard",
        "requires_spell": "Animate Construct",
        "move": 6,
        "fight": 1,
        "shoot": 0,
        "armour": 11,
        "will": 0,
        "health": 10,
        "gear": "Unarmed",
        "notes": "Construct: immune to poison, never counts as wounded; carries treasure but has no item slots. Animated by the Animate Construct spell (small, -0 to cast).",
        "description": 'A crude animated figure summoned by the Animate Construct spell at its easiest casting tier. Construct: immune to poison, never counts as wounded, and may carry treasure tokens but has no item slots (though some items may be permanently grafted to it instead of carried).',
    },
    "medium_construct": {
        "name": "Medium Construct",
        "cost": 0,
        "category": "standard",
        "requires_spell": "Animate Construct",
        "move": 5,
        "fight": 3,
        "shoot": 0,
        "armour": 12,
        "will": 0,
        "health": 12,
        "gear": "Unarmed",
        "notes": "Construct: immune to poison, never wounded; carries treasure but has no item slots. Animated by the Animate Construct spell (medium, -3 to cast).",
        "description": 'A sturdier animated figure summoned by the Animate Construct spell at its middle casting tier. Construct: immune to poison, never counts as wounded, and may carry treasure tokens but has no item slots (though some items may be permanently grafted to it instead of carried).',
    },
    "large_construct": {
        "name": "Large Construct",
        "cost": 0,
        "category": "specialist",
        "requires_spell": "Animate Construct",
        "move": 4,
        "fight": 4,
        "shoot": 0,
        "armour": 13,
        "will": 0,
        "health": 14,
        "gear": "Unarmed",
        "notes": "Construct; Large (-2 Large Target vs shooting); Strong (+2 damage). Counts as a specialist. Animated by the Animate Construct spell (large, -6 to cast).",
        "description": 'A hulking animated figure summoned by the Animate Construct spell at its hardest casting tier. Large: suffers the -2 Large Target penalty against shooting attacks. Strong: deals +2 damage. Also has the standard Construct traits: immune to poison, never counts as wounded, and may carry treasure tokens but has no item slots. Counts as a specialist.',
    },
    "companion_bear": {
        "name": "Bear",
        "cost": 0,
        "category": "standard",
        "requires_spell": "Animal Companion",
        "move": 6,
        "fight": 4,
        "shoot": 0,
        "armour": 12,
        "will": 3,
        "health": 14,
        "gear": "Unarmed",
        "notes": "Animal Companion; Animal; Large; Strong (+2 damage). Will includes the +3 Animal Companion bonus.",
        "description": 'A wilderness companion bonded via the Animal Companion spell. Large: suffers the -2 Large Target penalty against shooting attacks. Strong: deals +2 damage. Animal: cannot pick up treasure tokens and has no item slot. Will shown already includes the +3 Animal Companion bonus.',
    },
    "companion_ice_toad": {
        "name": "Ice Toad",
        "cost": 0,
        "category": "standard",
        "requires_spell": "Animal Companion",
        "move": 4,
        "fight": 2,
        "shoot": 0,
        "armour": 10,
        "will": 3,
        "health": 5,
        "gear": "Unarmed",
        "notes": "Animal Companion; Animal; Amphibious; Powerful (double damage). Will includes the +3 Animal Companion bonus.",
        "description": 'A wilderness companion bonded via the Animal Companion spell. Amphibious: automatically passes Swimming Rolls, treats water as normal ground instead of rough terrain, and suffers no Fight penalty while in water. Powerful: damage it deals is doubled. Animal: cannot pick up treasure tokens and has no item slot. Will shown already includes the +3 Animal Companion bonus.',
    },
    "companion_snow_leopard": {
        "name": "Snow Leopard",
        "cost": 0,
        "category": "standard",
        "requires_spell": "Animal Companion",
        "move": 8,
        "fight": 3,
        "shoot": 0,
        "armour": 10,
        "will": 5,
        "health": 10,
        "gear": "Unarmed",
        "notes": "Animal Companion; Animal; Expert Climber. Will includes the +3 Animal Companion bonus.",
        "description": 'A wilderness companion bonded via the Animal Companion spell. Expert Climber: suffers no movement penalty for climbing. Animal: cannot pick up treasure tokens and has no item slot. Will shown already includes the +3 Animal Companion bonus.',
    },
    "companion_wolf": {
        "name": "Wolf",
        "cost": 0,
        "category": "standard",
        "requires_spell": "Animal Companion",
        "move": 8,
        "fight": 1,
        "shoot": 0,
        "armour": 10,
        "will": 3,
        "health": 6,
        "gear": "Unarmed",
        "notes": "Animal Companion; Animal; Pack Hunter. Will includes the +3 Animal Companion bonus.",
        "description": 'A wilderness companion bonded via the Animal Companion spell. Pack Hunter: if more than one wolf is fielded, they act together — all activate and move as one whenever any of them is activated, following whichever is rolled as pack leader. Animal: cannot pick up treasure tokens and has no item slot. Will shown already includes the +3 Animal Companion bonus.',
    },
    # Beastcrafter I adds these two to the Animal Companion options. Base stats
    # are the core-rules creatures; Will includes the +3 companion bonus, same
    # convention as the four above.
    "companion_boar": {
        "name": "Boar",
        "cost": 0,
        "category": "standard",
        "source": "Into the Breeding Pits",
        "requires_spell": "Animal Companion",
        "move": 6,
        "fight": 2,
        "shoot": 0,
        "armour": 12,
        "will": 5,
        "health": 8,
        "gear": "Unarmed",
        "notes": (
            "Animal Companion; Animal. Requires a Beastcrafter I wizard. "
            "Will includes the +3 Animal Companion bonus."
        ),
        "description": 'A wilderness companion available only to a Beastcrafter I wizard (Into the Breeding Pits), bonded via the Animal Companion spell like the core companions. Animal: cannot pick up treasure tokens and has no item slot. Will shown already includes the +3 Animal Companion bonus.',
    },
    "companion_ice_spider": {
        "name": "Ice Spider",
        "cost": 0,
        "category": "standard",
        "source": "Into the Breeding Pits",
        "requires_spell": "Animal Companion",
        "move": 6,
        "fight": 1,
        "shoot": 0,
        "armour": 8,
        "will": 3,
        "health": 4,
        "gear": "Unarmed",
        "notes": (
            "Animal Companion; Animal; Poison. Requires a Beastcrafter I wizard. "
            "Will includes the +3 Animal Companion bonus."
        ),
        "description": 'A wilderness companion available only to a Beastcrafter I wizard (Into the Breeding Pits), bonded via the Animal Companion spell. Poison: its attacks deal poison damage. Animal: cannot pick up treasure tokens and has no item slot. Will shown already includes the +3 Animal Companion bonus.',
    },
}

# Extra source books whose soldiers / creatures / rules can be toggled on per
# warband from the "Additional Rules and Homerules" tab. Core Rules content is
# always available and is not part of this list. Order = release order.
SOURCE_BOOKS = [
    "Thaw of the Lich Lord",
    "Into the Breeding Pits",
    "Forgotten Pacts",
    "The Maze of Malcor",
    "The Perilous Dark",
]


def source_slug(name: str) -> str:
    """Stable form-field key for a source book name, e.g. 'the-maze-of-malcor'."""
    import re

    return re.sub(r"[^a-z0-9]+", "-", (name or "").lower()).strip("-")


# [{"name": ..., "slug": ...}] convenience for templates/forms.
SOURCE_BOOK_OPTIONS = [{"name": b, "slug": source_slug(b)} for b in SOURCE_BOOKS]
SOURCE_BOOK_BY_SLUG = {source_slug(b): b for b in SOURCE_BOOKS}


def soldier_list_for_ui() -> list[dict]:
    rows = [{"key": k, "source": "Core Rules", **v} for k, v in SOLDIERS.items()]
    rows.sort(key=_ui_sort_key)
    return rows


# Heading the spell-summoned members are listed under, instead of their nominal
# "Core Rules" source — they're gated by a spell, not by a source book.
SUMMONED_GROUP_LABEL = "Summoned by spell"


def soldier_group_label(row: dict) -> str:
    return SUMMONED_GROUP_LABEL if row.get("requires_spell") else row["source"]


def group_soldiers_by_source(rows: list[dict]) -> list[dict]:
    """Split an already-sorted soldier list into the headed sections the UI
    shows: Core Rules, the spell-summoned members, then one section per
    supplement book. Returns [{"label": str, "soldiers": [...]}, ...].

    Relies on _ui_sort_key having put each group's rows together, so callers
    may filter rows out beforehand (the hire list drops books that aren't
    switched on) without breaking the grouping.
    """
    groups: list[dict] = []
    for row in rows:
        label = soldier_group_label(row)
        if not groups or groups[-1]["label"] != label:
            groups.append({"label": label, "soldiers": []})
        groups[-1]["soldiers"].append(row)
    return groups


# Order the spell-summoned members appear in: the animal companions as one
# group, then the constructs from small to large. Anything not listed sorts
# after these, by name.
SUMMONED_ORDER = [
    "companion_bear",
    "companion_boar",
    "companion_ice_spider",
    "companion_ice_toad",
    "companion_snow_leopard",
    "companion_wolf",
    "small_construct",
    "medium_construct",
    "large_construct",
    "demonic_servant",
]


def _source_rank(source: str) -> int:
    """Core Rules first, then the supplement books in release order."""
    if source == "Core Rules":
        return 0
    return SOURCE_BOOKS.index(source) + 1 if source in SOURCE_BOOKS else len(SOURCE_BOOKS) + 1


def _ui_sort_key(r: dict) -> tuple:
    """Hire-list ordering: soldiers grouped by the book they come from — Core
    Rules, then each supplement in release order — with the spell-gated summons
    as their own group after the core soldiers.

    Ordinary soldiers sort within their book by category (standard before
    specialist), cost, name. The summons instead keep their own fixed grouping —
    sorting them by category would strand the Large Construct at the end for
    being a specialist, away from the two smaller constructs it belongs with.

    Summons ignore their source book entirely and all sort as one block right
    after the core soldiers. They are grouped under "Summoned by spell" rather
    than under a book, so letting a supplement companion (the Beastcrafter's boar
    and ice spider) sort into its own book's position would emit that heading a
    second time further down the list.
    """
    if r.get("requires_spell"):
        rank = SUMMONED_ORDER.index(r["key"]) if r["key"] in SUMMONED_ORDER else len(SUMMONED_ORDER)
        return (0, 1, rank, 0, r["name"])
    return (
        _source_rank(r["source"]),
        0,
        1 if r["category"] != "standard" else 0,
        r["cost"],
        r["name"],
    )


def animal_companion_type_keys() -> set[str]:
    """Soldier type keys summoned by the Animal Companion spell (one allowed at a time)."""
    return {k for k, v in SOLDIERS.items() if v.get("requires_spell") == "Animal Companion"}


def get_soldier(type_key: str) -> dict | None:
    s = SOLDIERS.get(type_key)
    if not s:
        return None
    out = deepcopy(s)
    out.setdefault("source", "Core Rules")
    return out


def format_stat(value: int) -> str:
    return f"+{value}" if value >= 0 else str(value)


def all_spells_flat() -> list[dict]:
    out = []
    for school, spells in SPELLS.items():
        for sp in spells:
            out.append(
                {
                    **sp,
                    "school": school,
                    "id": spell_id(school, sp["name"]),
                    # Normalised here so every consumer can rely on it being set;
                    # core spells carry no "source" key of their own.
                    "source": sp.get("source", "Core Rules"),
                }
            )
    return out


def spell_id(school: str, name: str) -> str:
    return f"{school}::{name}"


def find_spell(spell_key: str) -> dict | None:
    if "::" not in spell_key:
        return None
    school, name = spell_key.split("::", 1)
    for sp in SPELLS.get(school, []):
        if sp["name"] == name:
            return {
                **sp,
                "school": school,
                "id": spell_key,
                "source": sp.get("source", "Core Rules"),
            }
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


# The XP helpers take the cost of a level rather than a warband, so they stay
# pure and every existing caller keeps working. A Lich levels at 150 XP instead
# of 100 — see expansions.xp_per_level().
def xp_for_level(level: int, per_level: int = XP_PER_LEVEL) -> int:
    return max(0, int(level)) * int(per_level or XP_PER_LEVEL)


def level_from_xp(xp: int, per_level: int = XP_PER_LEVEL) -> int:
    return min(MAX_WIZARD_LEVEL, max(0, int(xp) // int(per_level or XP_PER_LEVEL)))


def xp_to_next_level(xp: int, level: int, per_level: int = XP_PER_LEVEL) -> int:
    return max(0, xp_for_level(level + 1, per_level) - int(xp))
