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
MAX_WIZARD_LEVEL = 40  # fallback figure when the level-cap homerule's Unlimited box is unticked

# Wizard level-up hard caps (2e core "Leveling Up" rules) and the Casting
# Number floor a spell can be improved down to — long assumed by the app but
# never actually enforced for an ordinary wizard until the Wizard stat limits
# homerule section exposed them as editable settings. See
# expansions.wizard_stat_caps() / casting_number_minimum().
WIZARD_STAT_LIMITS_DEFAULT = {"fight": 5, "shoot": 5, "will": 8, "health": 20}
WIZARD_MIN_CASTING_NUMBER_DEFAULT = 5
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

# Absolute ceiling on a captain's actual stat value, applied once at hire/
# promotion time — distinct from CAPTAIN_STAT_CAPS above, which limits how many
# +1s can be *spent* over subsequent level-ups. A stat already above its limit
# (e.g. carried over from a promoted soldier's own prior leveling) is never
# reduced — only further increases (the fixed promotion bonus, then the chosen
# +1) are blocked once at or over the limit.
CAPTAIN_STAT_ABSOLUTE_LIMITS = {
    "move": 7,
    "fight": 5,
    "shoot": 4,
    "will": 6,
    "health": 20,
}

# Mind Control resistance flavor note (not simulated), per-warband selectable.
CAPTAIN_MIND_CONTROL_OPTIONS = ["immune", "resistant", "none"]
CAPTAIN_MIND_CONTROL_LABELS = {
    "immune": "Immune to Mind Control",
    "resistant": "No tricks while mind controlled",
    "none": "No bonus",
}
CAPTAIN_MIND_CONTROL_DEFAULT = "none"

# How a warband can get a Captain at all: hiring, promoting an existing soldier,
# both, or neither (off).
CAPTAIN_MODE_OPTIONS = ["off", "hire", "promote", "both"]
CAPTAIN_MODE_LABELS = {
    "off": "Off (no captain homerule)",
    "hire": "Hire only",
    "promote": "Promote only",
    "both": "Hire or promote",
}
CAPTAIN_MODE_DEFAULT = "hire"

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

# Core Rules' Permanent Injury Table (Chapter Three, page 77) — the outcome of
# a "Permanent Injury" result on the Spellcaster Survival Table. Fixed core
# content (not a supplement), so defined here directly rather than as JSON.
# Each may be suffered at most max_stacks times before the book says any
# further result "must be re-rolled"; stat_delta uses the same {stat: {"add":
# n}} shape as Grave Mutations/Construct Modifications, applied per occurrence
# so a second Lost Toes, say, actually doubles to -2 Move. The book's printed
# "6-10" range for Crushed Arm overlaps Smashed Leg's "3-6" by one — shown
# here as 7-10 so the d20 table sums to 20 with no gap (see the Lexicon's Core
# Rules > Post-Game: Injury & Death card for the full table with die ranges).
PERMANENT_INJURIES = [
    {
        "id": "lost_toes",
        "name": "Lost Toes",
        "text": "-1 to all Move Rolls.",
        "stat_delta": {"move": {"add": -1}},
        "max_stacks": 2,
        "prosthetic_eligible": True,
        "roll": [1, 2],
    },
    {
        "id": "smashed_leg",
        "name": "Smashed Leg",
        "text": "-2 Move.",
        "stat_delta": {"move": {"add": -2}},
        "max_stacks": 2,
        "prosthetic_eligible": True,
        "roll": [3, 6],
    },
    {
        "id": "crushed_arm",
        "name": "Crushed Arm",
        "text": "-1 Fight.",
        "stat_delta": {"fight": {"add": -1}},
        "max_stacks": 2,
        "prosthetic_eligible": True,
        "roll": [7, 10],
    },
    {
        "id": "lost_fingers",
        "name": "Lost Fingers",
        "text": "-1 Shoot.",
        "stat_delta": {"shoot": {"add": -1}},
        "max_stacks": 2,
        "prosthetic_eligible": True,
        "roll": [11, 12],
    },
    {
        "id": "never_quite_as_strong",
        "name": "Never Quite as Strong",
        "text": "-1 Health.",
        "stat_delta": {"health": {"add": -1}},
        "max_stacks": 2,
        "roll": [13, 14],
    },
    {
        "id": "psychological_scars",
        "name": "Psychological Scars",
        "text": "-1 Will.",
        "stat_delta": {"will": {"add": -1}},
        "max_stacks": 2,
        "roll": [15, 16],
    },
    {
        "id": "niggling_injury",
        "name": "Niggling Injury",
        "text": (
            "30gc upkeep before each game, or start that game at -3 Health instead "
            "(10gc discount per apothecary in the warband). No stat_delta — the "
            "upkeep/per-game penalty isn't a permanent stat change, so it's shown "
            "as text only, same as every other situational effect in this app."
        ),
        "stat_delta": None,
        "max_stacks": 2,
        "roll": [17, 18],
    },
    {
        "id": "smashed_jaw",
        "name": "Smashed Jaw",
        "text": "May only activate 2 soldiers per phase instead of the normal 3.",
        "stat_delta": None,
        "max_stacks": 2,
        "roll": [19, 19],
    },
    {
        "id": "lost_eye",
        "name": "Lost Eye",
        "text": (
            "-1 Combat Roll when targeted by a shooting attack. A second Lost Eye "
            "leaves the figure effectively blind."
        ),
        "stat_delta": None,
        "max_stacks": 2,
        "roll": [20, 20],
    },
]
PERMANENT_INJURY_BY_ID = {i["id"]: i for i in PERMANENT_INJURIES}


def permanent_injury_by_roll(n: int) -> dict | None:
    """d20 lookup against each entry's "roll" range — used by the Random
    Recruit Status Table (The Red King), which sends a fresh recruit to a
    roll here rather than the mutation-style single-number table."""
    for row in PERMANENT_INJURIES:
        lo, hi = row["roll"]
        if lo <= n <= hi:
            return row
    return None


# Fireheart's Prosthetic Upgrade table: purchasable add-ons for an already
# Animated-Prosthetic-fitted injury (see set_permanent_injury_prosthetic in
# warband_store.py). "requires" is either "any" prosthetic-eligible injury, or
# the specific injury id(s) the upgrade needs. Most take an item slot (max one
# of each upgrade across the whole entity); Potion Reservoir and Toe Ring are
# the book's two named exceptions ("itself free of item-slot cost").
PROSTHETIC_UPGRADES = [
    {
        "id": "climbing_claws",
        "name": "Climbing Claws",
        "requires": {"lost_toes", "lost_fingers"},
        "cost": 350,
        "text": "Expert Climber.",
        "takes_slot": True,
    },
    {
        "id": "fighting_claws",
        "name": "Fighting Claws",
        "requires": {"lost_fingers"},
        "cost": 450,
        "text": "+1 melee damage, never unarmed.",
        "takes_slot": True,
    },
    {
        "id": "gem_of_power",
        "name": "Gem of Power",
        "requires": "any",
        "cost": 500,
        "text": "One power point for empowering.",
        "takes_slot": True,
    },
    {
        "id": "hidden_projectile",
        "name": "Hidden Projectile",
        "requires": {"lost_fingers", "crushed_arm"},
        "cost": 400,
        "text": "Once/game, 12\" shooting attack at normal Shoot.",
        "takes_slot": True,
    },
    {
        "id": "potion_reservoir_prosthetic",
        "name": "Potion Reservoir",
        "requires": {"smashed_leg", "crushed_arm"},
        "cost": 400,
        "text": "Carries 2 potions with no item slot.",
        "takes_slot": False,
    },
    {
        "id": "shock_absorbers",
        "name": "Shock Absorbers",
        "requires": {"smashed_leg"},
        "cost": 500,
        "text": "Immune to fall damage.",
        "takes_slot": True,
    },
    {
        "id": "toe_ring",
        "name": "Toe Ring",
        "requires": {"lost_toes"},
        "cost": 200,
        "text": "May wear 2 rings, itself free of item-slot cost.",
        "takes_slot": False,
    },
]
PROSTHETIC_UPGRADE_BY_ID = {u["id"]: u for u in PROSTHETIC_UPGRADES}


# --- Ragged Warbands & Random Recruits (The Red King, Chapter Two) ---------
# Each row is (lo, hi, value); a d20 roll against Table I picks which of
# Table II/III to roll on next, and a second d20 roll against that table
# picks the actual recruit (as a SOLDIERS type_key). "Captain" (Table III,
# roll 3) has no type_key — the app models a Captain as a separate entity
# with its own hire flow, so a hit there is a plain reroll (see
# warband_store.roll_random_recruits), same treatment as any result from a
# supplement the warband doesn't have switched on.
RANDOM_RECRUIT_TABLE_I = [(1, 14, "II"), (15, 20, "III")]
RANDOM_RECRUIT_TABLE_II = [
    (1, 2, "thug"),
    (3, 4, "thief"),
    (5, 6, "war_hound"),
    (7, 8, "infantryman"),
    (9, 10, "man_at_arms"),
    (11, 11, "archer"),
    (12, 12, "crossbowman"),
    (13, 13, "treasure_hunter"),
    (14, 14, "apothecary"),
    (15, 15, "knight"),
    (16, 16, "templar"),
    (17, 17, "ranger"),
    (18, 18, "tracker"),
    (19, 19, "barbarian"),
    (20, 20, "marksman"),
]
RANDOM_RECRUIT_TABLE_III = [
    (1, 1, "assassin"),
    (2, 2, "bard"),
    (3, 3, None),  # Captain — reroll
    (4, 4, "collegium_porter"),
    (5, 5, "crow_master"),
    (6, 6, "demon_hunter"),
    (7, 7, "demonic_servant"),
    (8, 8, "javelineer"),
    (9, 9, "monk"),
    (10, 10, "mystic_warrior"),
    (11, 11, "pack_mule"),
    (12, 12, "rangifer"),
    (13, 13, "trap_expert"),
    (14, 14, "tunnel_fighter"),
    (15, 15, "werewolf"),
    (16, 16, "large_construct"),
    (17, 17, "minor_demon"),
    (18, 18, "snow_troll"),
    (19, 19, "foulhorn"),
    (20, 20, "vampire"),
]

# Random Recruit Status Table (d20, optional follow-up roll after a recruit
# joins). "cannot be logically applied" (e.g. an item result on a 0-item-slot
# recruit) is handled by the roller returning no result, per the book's own
# instruction.
RANDOM_RECRUIT_STATUS_TABLE = [
    (1, 4, "injury"),
    (5, 6, "fight_minus_1"),
    (7, 8, "health_minus_2"),
    (9, 10, "potion"),
    (11, 14, "weapon_fight_plus_1"),
    (15, 16, "magic_item"),
    (17, 18, "will_plus_1"),
    (19, 20, "health_plus_1"),
]


def range_table_lookup(table: list[tuple], n: int):
    for lo, hi, value in table:
        if lo <= n <= hi:
            return value
    return None
CAPTAIN_STARTING_TRICKS = 2

# Knightly Orders (Spellcaster Magazine, Issue 1) — an optional pick made once,
# at hire time, for a Knight or Templar only. Each order trades one point off
# the type's base Fight or Health for a special ability; the ability text is
# purely descriptive (not mechanically simulated), same as CAPTAIN_TRICKS
# above, while the stat trade-off is applied for real via the delta below.
# The book's own "Custom orders" entry (decrease Fight by 1 for a major
# ability of the group's own devising, or Health by 1 for a minor one) is a
# DIY template rather than a concrete pick, so it stays reference-only text
# in expansion_rules.json instead of becoming a selectable option here.
KNIGHTLY_ORDERS = [
    {"id": "sun", "name": "Order of the Sun", "stat": "fight", "delta": -1, "ability": "+2 Fight when fighting undead or demons"},
    {"id": "snake", "name": "Order of the Snake", "stat": "fight", "delta": -1, "ability": "All attacks count as poisonous"},
    {"id": "hammer", "name": "Order of the Hammer", "stat": "fight", "delta": -1, "ability": "+2 Fight and +2 Damage when fighting constructs"},
    {"id": "diamond", "name": "Order of the Diamond", "stat": "health", "delta": -1, "ability": "Never suffers the effects of being wounded"},
    {"id": "fire", "name": "Order of Fire", "stat": "health", "delta": -1, "ability": "+4 Armour against damage from Elemental magic"},
    {"id": "lance", "name": "Order of the Lance", "stat": "fight", "delta": -1, "ability": "Two item slots; only one may hold an Armour-boosting item"},
    {"id": "mirror", "name": "Order of the Mirror", "stat": "fight", "delta": -1, "ability": "Immune to Beauty, Monstrous Form, and Invisibility"},
    {"id": "river", "name": "Order of the River", "stat": "health", "delta": -1, "ability": "Once per game, may spend an action to heal 3 damage"},
    {"id": "gauntlet", "name": "Order of the Gauntlet", "stat": "health", "delta": -1, "ability": "If activated in the soldier phase, may declare a group activation with one other soldier within 3\""},
    {"id": "tower", "name": "Order of the Tower", "stat": "health", "delta": -1, "ability": "+1 Fight and +1 damage when fighting a creature with the Large trait"},
    {"id": "gallows", "name": "Order of the Gallows", "stat": "health", "delta": -1, "ability": "May reroll its survival roll after the game, but must keep the reroll even if it's worse"},
]
KNIGHTLY_ORDER_IDS = {o["id"] for o in KNIGHTLY_ORDERS}
KNIGHTLY_ORDER_BY_ID = {o["id"]: o for o in KNIGHTLY_ORDERS}
KNIGHTLY_ORDER_ELIGIBLE = {"knight", "templar"}

# --- Soldier Leveling (homerule, not core 2e) -------------------------------
SOLDIER_MAX_LEVELS = 3
SOLDIER_STAT_CAPS = {
    "fight": {"limit": 0, "unlimited": False},
    "shoot": {"limit": 0, "unlimited": False},
    "will": {"limit": 1, "unlimited": False},
    "health": {"limit": 2, "unlimited": False},
}

# --- Promote Captain (homerule, not core 2e) --------------------------------
# Whether promotion (vs. hiring) is available is governed by CAPTAIN_MODE_* above.
PROMOTE_CAPTAIN_COST = 125
# No automatic across-the-board bonus by default — a promoted captain's gain is
# the player-chosen +1 instead (promote_captain_bonus_choice_enabled, on by
# default). Still editable per warband for groups who want a flat package.
PROMOTE_CAPTAIN_BONUS = {"fight": 0, "shoot": 0, "will": 0, "health": 0}
PROMOTE_CAPTAIN_ITEM_SLOTS = 6
# Tricks a soldier learns on being promoted. Separate from CAPTAIN_STARTING_TRICKS
# so a group can make promotion more or less rewarding than hiring.
PROMOTE_CAPTAIN_TRICKS = 2

# --- Giant-Blooded (Blood Legacy, Chapter Three) ----------------------------
# Generic soldier modification, one per warband, declared at hire: +50gc,
# -1 Move, -2 Will, +2 Health, plus the Giant-Blooded trait (+1 melee damage,
# +4 to TN-based Fight rolls, includes Large — display text only, this app
# doesn't resolve combat). See giant_blooded_eligible_type_keys() above for
# which soldier types may take it.
GIANT_BLOODED_COST = 50
GIANT_BLOODED_STAT_DELTA = {"move": -1, "will": -2, "health": 2}

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
    # --- The Frostgrave Folio (Arcane Locations) ---
    "alchemical_cupboard": {
        "name": "Alchemical Cupboard",
        "cost": 150,
        "source": "The Frostgrave Folio",
        "effects": "-20gc off potion component costs.",
    },
    "enchanted_clock": {
        "name": "Enchanted Clock",
        "cost": 200,
        "source": "The Frostgrave Folio",
        "effects": "+10 XP once per game if a Chronomancer spell is successfully cast.",
    },
    "homunculus_jar": {
        "name": "Homunculus Jar",
        "cost": 50,
        "source": "The Frostgrave Folio",
        "effects": "+1 Casting Rolls for all Homunculus spells.",
    },
    "lectern": {
        "name": "Lectern",
        "cost": 100,
        "source": "The Frostgrave Folio",
        "effects": "+1 Casting Rolls for all Absorb Knowledge spells.",
    },
    "protected_bookcase": {
        "name": "Protected Bookcase",
        "cost": 100,
        "source": "The Frostgrave Folio",
        "effects": "Grimoires sell for +10gc.",
    },
    "protected_scrollcase": {
        "name": "Protected Scrollcase",
        "cost": 100,
        "source": "The Frostgrave Folio",
        "effects": "Scrolls sell for +10gc.",
    },
    "recovery_room": {
        "name": "Recovery Room",
        "cost": 200,
        "source": "The Frostgrave Folio",
        "effects": (
            "Requires an Apothecary. Lets one injured figure be temporarily replaced on "
            "the roster (still paying full hire cost) until it recovers."
        ),
    },
    "sacrificial_altar": {
        "name": "Sacrificial Altar",
        "cost": 200,
        "source": "The Frostgrave Folio",
        "effects": "+1 Casting Rolls for all Revenant spells.",
    },
    "shrine": {
        "name": "Shrine",
        "cost": 200,
        "source": "The Frostgrave Folio",
        "effects": "+1 Casting Rolls for all Miraculous Cure and Restore Life spells.",
    },
    "weapons_rack": {
        "name": "Weapons Rack",
        "cost": 50,
        "source": "The Frostgrave Folio",
        "effects": "Non-magic weapons are bought or replaced for free.",
    },
    # --- Fireheart ---
    "mirror_of_preening": {
        "name": "Mirror of Preening",
        "cost": 150,
        "source": "Fireheart",
        "effects": (
            "Cast Beauty Out of Game (A); success grants a 10% discount on one post-game "
            "potion/item/weapon/armour purchase."
        ),
    },
    "construct_repair_tools": {
        "name": "Construct Repair Tools",
        "cost": 300,
        "source": "Fireheart",
        "effects": "+2 to Animate Construct rolls repairing or reviving a construct.",
    },
    "construct_forge": {
        "name": "Construct Forge",
        "cost": 400,
        "source": "Fireheart",
        "effects": "One Construct Modification Table pick per game at 50% off (non-stacking).",
    },
    "talking_head": {
        "name": "Talking Head",
        "cost": 800,
        "source": "Fireheart",
        "effects": "+10 XP per game from consulting it (subject to the normal XP cap).",
    },
    "haven_box": {
        "name": "Haven Box",
        "cost": 600,
        "source": "Fireheart",
        "effects": "Protects one chosen item from being lost on a Dead/Close Call Survival roll.",
    },
    # --- Spellcaster Magazine ---
    "stable": {
        "name": "Stable",
        "cost": 300,
        "source": "Spellcaster Magazine",
        "effects": (
            "Lets the warband keep one horse (200gc, one per warband); doesn't affect the "
            "warband size limit. The mounted-combat rules themselves are a deferred mechanic."
        ),
    },
    "breeding_cages": {
        "name": "Breeding Cages",
        "cost": 300,
        "source": "Spellcaster Magazine",
        "effects": "+1 to all Animal Manipulation spells.",
    },
    "alchemical_workshop": {
        "name": "Alchemical Workshop",
        "cost": 400,
        "source": "Spellcaster Magazine",
        "effects": (
            "Once per post-game, mix 2 potions (both consumed): both odd rolls wastes them; "
            "both even takes the lower result on the Greater Potion Table and adds it to the "
            "vault; equal rolls under 20 destroys the workshop and costs -2 Health next game; "
            "one odd and one even returns both potions with no result."
        ),
    },
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

# Blood Legacy's Fire Giant Wizard (Chapter Three) — a giant-scale wizard
# build the book itself frames as being for "very hard/large encounters, not
# balanced campaign play". M6 F+4 S+0 A14 W+4 H22 relative to the ordinary
# Starting Wizard line above, i.e. Fight 6 / Armour 14 (natural, no
# armour/shield item slots) / Will 8 / Health 22. See
# expansions.is_fire_giant()/warband_store.playable_schools() for how a
# warband actually opts into this as the wizard's own school.
FIRE_GIANT_WIZARD_BASE = {
    "move": 6,
    "fight": 6,
    "shoot": 0,
    "armour": 14,
    "will": 8,
    "health": 22,
}
FIRE_GIANT_XP_PER_LEVEL = 200
FIRE_GIANT_HEALTH_CAP = 30

# Blood Legacy's Vampire Wizard (Chapter Three) — "same starting stats as a
# wizard" (WIZARD_BASE above; no separate base-stat constant needed), no
# apprentice, a 9th soldier slot (4 specialist, unchanged), Will capped
# lower than an ordinary wizard, Health capped lower too, and slower
# leveling. Traits (display text only; this app doesn't resolve combat):
# Undead, Immune to Control Undead, Magic Attacks, Mind Lock, Thaumaturgic
# Vulnerability, True Sight, Partial Immunity to Normal Damage. See
# expansions.is_vampire()/warband_store.playable_schools().
VAMPIRE_XP_PER_LEVEL = 120
VAMPIRE_HEALTH_CAP = 22
VAMPIRE_WILL_CAP = 5
VAMPIRE_MIN_MAX_SOLDIERS = 9

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
        "opposed": ["Enchanter"],
    },
    "Elementalist": {
        "aligned": ["Chronomancer", "Enchanter", "Summoner"],
        "neutral": ["Necromancer", "Sigilist", "Soothsayer", "Thaumaturge", "Witch"],
        "opposed": ["Illusionist"],
    },
    "Enchanter": {
        "aligned": ["Elementalist", "Sigilist", "Witch"],
        "neutral": ["Illusionist", "Necromancer", "Soothsayer", "Summoner", "Thaumaturge"],
        "opposed": ["Chronomancer"],
    },
    "Illusionist": {
        "aligned": ["Sigilist", "Soothsayer", "Thaumaturge"],
        "neutral": ["Chronomancer", "Enchanter", "Necromancer", "Summoner", "Witch"],
        "opposed": ["Elementalist"],
    },
    "Necromancer": {
        "aligned": ["Chronomancer", "Summoner", "Witch"],
        "neutral": ["Elementalist", "Enchanter", "Illusionist", "Sigilist", "Soothsayer"],
        "opposed": ["Thaumaturge"],
    },
    "Sigilist": {
        "aligned": ["Enchanter", "Illusionist", "Thaumaturge"],
        "neutral": ["Chronomancer", "Elementalist", "Necromancer", "Soothsayer", "Witch"],
        "opposed": ["Summoner"],
    },
    "Soothsayer": {
        "aligned": ["Chronomancer", "Illusionist", "Thaumaturge"],
        "neutral": ["Elementalist", "Enchanter", "Necromancer", "Sigilist", "Summoner"],
        "opposed": ["Witch"],
    },
    "Summoner": {
        "aligned": ["Elementalist", "Necromancer", "Witch"],
        "neutral": ["Chronomancer", "Enchanter", "Illusionist", "Soothsayer", "Thaumaturge"],
        "opposed": ["Sigilist"],
    },
    "Thaumaturge": {
        "aligned": ["Illusionist", "Sigilist", "Soothsayer"],
        "neutral": ["Chronomancer", "Elementalist", "Enchanter", "Summoner", "Witch"],
        "opposed": ["Necromancer"],
    },
    "Witch": {
        "aligned": ["Enchanter", "Necromancer", "Summoner"],
        "neutral": ["Chronomancer", "Elementalist", "Illusionist", "Sigilist", "Thaumaturge"],
        "opposed": ["Soothsayer"],
    },
}

# Convenience maps (derived)
SCHOOL_ALIGNED = {k: v["aligned"] for k, v in SCHOOL_RELATIONS.items()}
SCHOOL_NEUTRAL = {k: v["neutral"] for k, v in SCHOOL_RELATIONS.items()}
SCHOOL_OPPOSED = {k: v["opposed"] for k, v in SCHOOL_RELATIONS.items()}


def school_relation(wizard_school: str, spell_school: str) -> str:
    """own/aligned/neutral/opposed of spell_school as wizard_school sees it.

    Symmetric (H1): Vampire, Fire Giant, Rangifer, and the five Pentangle
    schools only declare relations FROM their own perspective (toward the ten
    core schools) — the core schools' own rows were never updated to name them
    back. Frostgrave's alignment wheel is symmetric and no supplement
    documents an intentional asymmetry, so if wizard_school's own table
    doesn't mention spell_school, this checks spell_school's table for a
    relation back to wizard_school instead of defaulting straight to neutral.
    This mirroring happens here, dynamically, rather than by writing the
    reverse entries into SCHOOL_RELATIONS itself — validate_starting_spells()
    counts exactly one pick per name in a school's own "aligned" list, and
    mutating that list would silently change how many starting spells a
    wizard has to pick.
    """
    if wizard_school == spell_school:
        return "own"
    rel = SCHOOL_RELATIONS.get(wizard_school)
    if rel:
        if spell_school in rel["aligned"]:
            return "aligned"
        if spell_school in rel["opposed"]:
            return "opposed"
        if spell_school in rel["neutral"]:
            return "neutral"
    rev = SCHOOL_RELATIONS.get(spell_school)
    if rev:
        if wizard_school in rev["aligned"]:
            return "aligned"
        if wizard_school in rev["opposed"]:
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
        "opposed": [],
    }
del _school, _spells

# --- Vampire & Fire Giant schools (Blood Legacy) ----------------------------
#
# Both the Vampire Wizard and Fire Giant Wizard progressions are implemented
# as playable schools (see VAMPIRE_XP_PER_LEVEL/FIRE_GIANT_WIZARD_BASE above
# and expansions.is_vampire()/is_fire_giant()): a warband can play either
# once Blood Legacy and that school's own "playable" homerule are both
# switched on (warband_store.playable_schools()). Genuinely per-game/
# situational nuances that have no existing tracking infrastructure anywhere
# in this app — the Vampire's Unnatural Health economy and Sun Damage, the
# separate "NPC Vampire-led warband" GM tool (henchmen thralls/ghouls, no
# XP, different activation phases) — stay reference-only text, same
# treatment as e.g. the niggling injury's per-game upkeep. Both schools'
# spell lists/alignments also stay usable by an ordinary wizard as off-
# school picks either way (gated on Blood Legacy being enabled, like any
# other supplement spell) — that's what the rest of this section sets up.
BLOOD_LEGACY_SPELLS: dict[str, list[dict]] = {
    "Vampire": [
        {"name": "Animal Form", "cn": 10, "type": "Self Only"},
        {"name": "Call Blood-Drinker Bat", "cn": 10, "type": "Area Effect"},
        {"name": "Ghoul Call", "cn": 12, "type": "Area Effect"},
        {"name": "Hypnotic Gaze", "cn": 14, "type": "Line of Sight"},
        {"name": "Lifedrain", "cn": 10, "type": "Self Only"},
        {"name": "Mist Form", "cn": 10, "type": "Self Only"},
        {"name": "Psychic Leech", "cn": 10, "type": "Line of Sight"},
        {"name": "Thralldom", "cn": 8, "type": "Out of Game (A)"},
    ],
    "Fire Giant": [
        {"name": "Comet", "cn": 14, "type": "Line of Sight"},
        {"name": "Earthquake", "cn": 12, "type": "Area Effect"},
        {"name": "Enflame", "cn": 8, "type": "Line of Sight"},
        {"name": "Mist Shroud", "cn": 8, "type": "Area Effect"},
        {"name": "Magnify", "cn": 14, "type": "Out of Game (A)"},
        {"name": "Pyre", "cn": 12, "type": "Line of Sight"},
        {"name": "Raze", "cn": 14, "type": "Line of Sight"},
        {"name": "Runic Stone", "cn": 16, "type": "Out of Game (B)"},
    ],
}

BLOOD_LEGACY_SCHOOL_RELATIONS = {
    "Vampire": {
        "aligned": ["Chronomancer", "Necromancer", "Soothsayer"],
        "neutral": ["Elementalist", "Enchanter", "Illusionist", "Sigilist", "Summoner", "Witch"],
        "opposed": ["Thaumaturge"],
    },
    "Fire Giant": {
        "aligned": ["Enchanter", "Elementalist", "Soothsayer"],
        "neutral": ["Illusionist", "Necromancer", "Sigilist", "Summoner", "Thaumaturge", "Witch"],
        "opposed": ["Chronomancer"],
    },
}

for _school, _spells in BLOOD_LEGACY_SPELLS.items():
    SPELLS[_school] = [{**sp, "source": "Blood Legacy"} for sp in _spells]
    SCHOOL_RELATIONS[_school] = dict(BLOOD_LEGACY_SCHOOL_RELATIONS[_school])
del _school, _spells

# --- Rangifer school (Spellcaster Magazine, Issue 3) ------------------------
#
# Cast only by the Rangifer Shaman hireling in the book — a distinct spellcaster
# type the app doesn't model (no "hireling with its own spell list" concept
# exists yet; a deferred mechanic, see the implementation plan). The spells
# themselves are still added here so they're learnable by an ordinary wizard
# once Spellcaster Magazine is enabled, same deferral as Vampire/Fire Giant.
RANGIFER_SPELLS = [
    {"name": "Antler Shard", "cn": 10, "type": "Line of Sight"},
    {"name": "Briar", "cn": 8, "type": "Line of Sight"},
    {"name": "Command Soul", "cn": 12, "type": "Line of Sight"},
    {"name": "Darkness", "cn": 12, "type": "Area Effect"},
    {"name": "Fire Spice", "cn": 10, "type": "Out of Game"},
    {"name": "Mend", "cn": 10, "type": "Line of Sight"},
    {"name": "Nature's Cloak", "cn": 10, "type": "Touch"},
    {"name": "Pyre", "cn": 12, "type": "Area Effect"},
    {"name": "Shattering Blow", "cn": 10, "type": "Line of Sight"},
    {"name": "Sunder", "cn": 8, "type": "Line of Sight"},
]
SPELLS["Rangifer"] = [{**sp, "source": "Spellcaster Magazine"} for sp in RANGIFER_SPELLS]
SCHOOL_RELATIONS["Rangifer"] = {"aligned": [], "neutral": list(SCHOOLS), "opposed": []}
del RANGIFER_SPELLS

# Schools that carry spells but that no *ordinary* wizard may choose as their
# own school at creation — they're reachable only through a wizard state
# (Beastcrafter), a homerule (Pentangle's "Pentangle schools playable",
# Vampire's "Vampire Wizard playable", Fire Giant's "Fire Giant Wizard
# playable"), or (Rangifer) not at all yet.
EXTRA_SPELL_SCHOOLS = ["Beastcrafter", "Vampire", "Fire Giant", "Rangifer"] + PENTANGLE_SCHOOLS

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
        "item_slots": 0,
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
        "item_slots": 3,
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
        "item_slots": 0,
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
        "item_slots": 3,
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
        "gear": "Two daggers, light armour",
        "notes": "Once per game, may treat the first initiative roll of 1 as a 2 for the purpose of springing a trap.",
        "description": "Someone who has survived the city's traps often enough to read the warning signs. Once per game, treats the first initiative roll of 1 as a 2 for the purpose of springing a trap, giving the party one extra chance to avoid it.",
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
        "item_slots": 0,
        "requires_spell": "Demonic Servant",
        "notes": "Joins via the Demonic Servant spell (never purchased). Demon; one minor demonic attribute; aids Summon Demon rolls.",
        "description": "A minor demon bound into service, joining a warband only through the Demonic Servant spell (Forgotten Pacts) rather than being purchased. Demon: immune to poison, all its attacks count as magic, and it may carry treasure tokens but has no item slots. Rolls one Minor Demonic Attribute on arrival and improves the wizard's future Summon Demon rolls.",
    },
    # Temporary members: Raise Zombie and Summon Demon (core rules) add a
    # creature to the warband for the rest of the game rather than permanently
    # — unlike demonic_servant above, these are expected to leave (killed,
    # exits the table, or the spell lapses) and can then be re-summoned. They
    # don't count against the soldier/specialist caps and get their own "Hire
    # temporary member" panel instead of living in the main hire catalog.
    "raised_zombie": {
        "name": "Zombie",
        "cost": 0,
        "category": "temporary",
        "temporary": True,
        "temporary_group": "zombie",
        "requires_spell": "Raise Zombie",
        "move": 4,
        "fight": 1,
        "shoot": 0,
        "armour": 12,
        "will": 0,
        "health": 6,
        "gear": "Unarmed",
        "notes": "Joins via Raise Zombie as a temporary member; only one at a time. Undead.",
        "description": "Raised by the Raise Zombie spell as a temporary member of the warband — not a permanent hire, and doesn't count against the soldier or specialist limit. A warband may only have one raised zombie at a time; if it is killed or leaves the table, Raise Zombie can be cast again for another. Undead: immune to poison, never wounded, can carry treasure tokens but has no item slots.",
    },
    "summoned_imp": {
        "name": "Imp",
        "cost": 0,
        "category": "temporary",
        "temporary": True,
        "temporary_group": "demon",
        "requires_spell": "Summon Demon",
        "move": 6,
        "fight": 1,
        "shoot": 0,
        "armour": 10,
        "will": 4,
        "health": 6,
        "gear": "Unarmed",
        "notes": "Joins via Summon Demon (Casting Roll succeeded by 0–5) as a temporary member; only one summoned demon at a time. Demon.",
        "description": "Placed by the Summon Demon spell as a temporary member of the warband — not a permanent hire, and doesn't count against the soldier or specialist limit. Which demon tier arrives depends on how much the Casting Roll succeeded by: 0–5 gives this imp, 6–12 a minor demon, 13+ a major demon. Summon Demon can't be cast again while a summoned demon is already under control. Demon: immune to poison, all attacks count as magic, can carry treasure tokens but has no item slots.",
    },
    "summoned_minor_demon": {
        "name": "Minor Demon",
        "cost": 0,
        "category": "temporary",
        "temporary": True,
        "temporary_group": "demon",
        "requires_spell": "Summon Demon",
        "move": 6,
        "fight": 3,
        "shoot": 0,
        "armour": 11,
        "will": 4,
        "health": 12,
        "gear": "Unarmed",
        "notes": "Joins via Summon Demon (Casting Roll succeeded by 6–12) as a temporary member; only one summoned demon at a time. Demon.",
        "description": "Placed by the Summon Demon spell as a temporary member of the warband — not a permanent hire, and doesn't count against the soldier or specialist limit. Which demon tier arrives depends on how much the Casting Roll succeeded by: 0–5 an imp, 6–12 gives this minor demon, 13+ a major demon. Summon Demon can't be cast again while a summoned demon is already under control. Demon: immune to poison, all attacks count as magic, can carry treasure tokens but has no item slots.",
    },
    "summoned_major_demon": {
        "name": "Major Demon",
        "cost": 0,
        "category": "temporary",
        "temporary": True,
        "temporary_group": "demon",
        "requires_spell": "Summon Demon",
        "move": 6,
        "fight": 5,
        "shoot": 0,
        "armour": 12,
        "will": 6,
        "health": 15,
        "gear": "Unarmed",
        "notes": "Joins via Summon Demon (Casting Roll succeeded by 13+) as a temporary member; only one summoned demon at a time. Demon; Large; Strong (+2 damage); True Sight.",
        "description": "Placed by the Summon Demon spell as a temporary member of the warband — not a permanent hire, and doesn't count against the soldier or specialist limit. Which demon tier arrives depends on how much the Casting Roll succeeded by: 0–5 an imp, 6–12 a minor demon, 13+ gives this major demon. Summon Demon can't be cast again while a summoned demon is already under control. Demon: immune to poison, all attacks count as magic, can carry treasure tokens but has no item slots. Large: suffers the -2 Large Target penalty against shooting attacks. Strong: deals +2 damage. True Sight: ignores Beauty and Invisibility, and destroys any Illusionary Soldier it fights.",
    },
    "illusionary_soldier": {
        "name": "Illusionary Soldier",
        "cost": 0,
        "category": "temporary",
        "temporary": True,
        "temporary_group": "illusion",
        "requires_spell": "Illusionary Soldier",
        # Placeholder stats — overwritten at hire time by the chosen core
        # soldier type's Move/Fight/Shoot/Armour/Will, with Health fixed to 1
        # (see illusion_source in add_soldier).
        "move": 5,
        "fight": 0,
        "shoot": 0,
        "armour": 10,
        "will": 0,
        "health": 1,
        "gear": "—",
        "notes": "Joins via Illusionary Soldier as a temporary member; takes the Move/Fight/Shoot/Armour/Will of a chosen core soldier type (any but the Apothecary) but always has 1 Health.",
        "description": "Conjured by the Illusionary Soldier spell as a temporary member of the warband — not a permanent hire, and doesn't count against the soldier or specialist limit. Chosen at hire to look and fight like any core soldier type except the Apothecary, copying that type's Move, Fight, Shoot, Armour, and Will — but it always has only 1 Health, since it's an illusion rather than a real body. Destroyed automatically if it ever fights a creature with True Sight.",
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
        "item_slots": 0,
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
        "gear": "Two-handed weapon, crossbow, quiver, leather armour",
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
    "companion_white_gorilla": {
        "name": "White Gorilla",
        "cost": 0,
        "cost_label": "Crit spell",
        "category": "standard",
        "requires_spell": "Animal Companion",
        "move": 6,
        "fight": 4,
        "shoot": 0,
        "armour": 12,
        "will": 8,
        "health": 14,
        "gear": "Unarmed",
        "notes": (
            "Animal Companion; Animal; Strong (+2 damage). Only available in place of the "
            "usual Animal Companion pick if the Animal Companion casting roll was a critical "
            "success (Spellcaster Magazine, Casting Roll Criticals)."
        ),
        "description": 'A rare, powerful companion bonded via a critical success on the Animal Companion casting roll (Spellcaster Magazine’s Casting Roll Criticals), taken instead of the normal companion pick. Strong: deals +2 damage. Animal: cannot pick up treasure tokens and has no item slot. Will shown already includes the +3 Animal Companion bonus.',
    },
    # --- The Wildwoods ---
    "guide": {
        "name": "Guide",
        "cost": 75,
        "category": "specialist",
        "source": "The Wildwoods",
        "move": 6,
        "fight": 1,
        "shoot": 0,
        "armour": 11,
        "will": 1,
        "health": 12,
        "gear": "Hand weapon",
        "notes": (
            "Picks a Terrain Expertise (Mountain/Bog/Ice/Forest); never consumes Supply "
            "Points. In a wilderness game matching that terrain, gains Nimble and the "
            "warband gains +2 Initiative and +2sp post-game. An Expert Guide costs 125gc "
            "(+2 Fight/+2 Shoot in matching terrain instead of +0/+0); only one guide's "
            "bonus applies per game even with multiple in the warband."
        ),
        "description": 'A wilderness scout (The Wildwoods) who knows one kind of terrain intimately. Picks a Terrain Expertise (Mountain, Bog, Ice, or Forest) at hire; never consumes Supply Points. In a wilderness game whose dominant terrain matches, gains the Nimble trait (no rough-ground movement penalty) and the whole warband gains +2 to its Initiative Roll and +2 Supply Points after the game. Costs 125gc as an "Expert" (+2 Fight/+2 Shoot instead of +0/+0 in matching terrain). Multiple Guides may be hired, but only one grants its bonus in any given game.',
    },
    "trapper": {
        "name": "Trapper",
        "cost": 50,
        "category": "standard",
        "source": "The Wildwoods",
        "move": 6,
        "fight": 2,
        "shoot": 0,
        "armour": 11,
        "will": 1,
        "health": 12,
        "gear": "Two daggers, light armour",
        "notes": "Wilderness Survival (no Supply Point upkeep unless reduced to 0 Health); Set Traps. House rule: max one per warband.",
        "description": 'A wilderness specialist (The Wildwoods) who lays traps rather than springing them. Wilderness Survival: pays no Supply Point upkeep unless reduced to 0 Health. Set Traps: may place a 1" trap token (max 3 per game); a figure triggering it either takes +1 damage or rolls a Move Roll (TN20) or loses its next activation. Intended as a max-one-per-warband hire.',
    },
    "trophy_hunter": {
        "name": "Trophy Hunter",
        "cost": 125,
        "category": "specialist",
        "source": "The Wildwoods",
        "move": 6,
        "fight": 2,
        "shoot": 2,
        "armour": 11,
        "will": 0,
        "health": 12,
        "gear": "Hand weapon",
        "notes": (
            "Wilderness Survival. Prize Taker: +1 Fight/Shoot vs. Horns/Antlers/Bounty "
            "creatures, +5 XP for personally killing one (once/game). House rule: cannot "
            "share a warband with any Horns/Antlers/Bounty creature (e.g. a hired Rangifer "
            "or Animal Companion with that trait)."
        ),
        "description": 'A big-game hunter (The Wildwoods) who specializes against trophy beasts. Wilderness Survival: pays no Supply Point upkeep unless reduced to 0 Health. Prize Taker: +1 Fight and +1 Shoot against any creature with the Horns, Antlers, or Bounty trait, and +5 XP for personally landing the killing blow on one (once per game). Refuses to serve alongside any Horns/Antlers/Bounty creature already in the warband.',
    },
    # --- Blood Legacy ---
    "blood_merchant": {
        "name": "Blood Merchant",
        "cost": 75,
        "category": "standard",
        "source": "Blood Legacy",
        "move": 6,
        "fight": 0,
        "shoot": 0,
        "armour": 10,
        "will": 0,
        "health": 12,
        "gear": "—",
        "notes": "Starts with a Vial of Blood. Adjacent to a vampire with no enemies within 1\", may hand it off to heal the vampire up to 5 Health.",
        "description": 'A supplier to the undead nobility (Blood Legacy), keeping a vampire fed away from the hunt. Starts with a Vial of Blood; while adjacent to a vampire with no enemies within 1", may give it up as an action to heal that vampire up to 5 Health.',
    },
    "swordmaster": {
        "name": "Swordmaster",
        "cost": 125,
        "category": "specialist",
        "source": "Blood Legacy",
        "move": 6,
        "fight": 4,
        "shoot": 0,
        "armour": 11,
        "will": 1,
        "health": 12,
        "gear": "Hand weapon",
        "notes": "Supporting Figure Maximum (opponents gain at most +2 from supporting figures against it). Opponent Armour Reduction: -1 Armour to a light/heavy-armoured foe it beats in combat.",
        "description": 'A blade specialist (Blood Legacy) who thrives against groups. Supporting Figure Maximum limits any opponent to at most +2 Fight from supporting figures when fighting the Swordmaster. Opponent Armour Reduction: a light- or heavy-armoured foe it beats in combat suffers -1 Armour.',
    },
    "vampire_hunter": {
        "name": "Vampire Hunter",
        "cost": 125,
        "category": "specialist",
        "source": "Blood Legacy",
        "move": 6,
        "fight": 3,
        "shoot": 2,
        "armour": 11,
        "will": 2,
        "health": 12,
        "gear": "Hand weapon",
        "notes": "Magic Attacks vs. Undead. Hunter's Will: +2 Will while a vampire is on the table. Immune to Energy Drain.",
        "description": "A specialist (Blood Legacy) trained specifically to hunt the undead nobility. All attacks count as magic when fighting Undead. Hunter's Will: gains +2 Will for as long as a vampire is on the table. Immune to Energy Drain.",
    },
    # --- Fireheart ---
    "construct_familiar": {
        "name": "Construct Familiar",
        "cost": 0,
        "category": "standard",
        "source": "Fireheart",
        "requires_spell": "Animate Construct",
        "move": 6,
        "fight": 1,
        "shoot": 0,
        "armour": 11,
        "will": 0,
        "health": 2,
        "gear": "—",
        "notes": "Construct, Cannot Carry Treasure, Expert Climber, Construct Eye-Socket. Having one excludes a Familiar-spell familiar.",
        "description": 'A tiny construct animated to serve as a familiar (Fireheart). Construct: immune to poison, never counts as wounded. Cannot Carry Treasure, Expert Climber, Construct Eye-Socket (any wizard may cast Wizard Eye on it). A warband may not have both a Construct Familiar and a Familiar-spell familiar.',
    },
    "construct_hound": {
        "name": "Construct Hound",
        "cost": 25,
        "category": "standard",
        "source": "Fireheart",
        "move": 7,
        "fight": 1,
        "shoot": 0,
        "armour": 10,
        "will": -1,
        "health": 10,
        "gear": "—",
        "item_slots": 0,
        "notes": "Construct, Cannot Carry Treasure. Already modified; cannot be modified further. May fill a kennel's wolf/warhound slot.",
        "description": 'A construct built to resemble and serve as a war hound (Fireheart). Construct: immune to poison, never counts as wounded. Cannot Carry Treasure. Comes pre-modified and cannot take any further Construct Modification. May be taken in place of a wolf or warhound wherever a kennel-type resource allows one.',
    },
    "construct_hound_summoned": {
        "name": "Construct Hound",
        "cost": 0,
        "category": "standard",
        "source": "Fireheart",
        "requires_spell": "Animate Construct",
        "move": 7,
        "fight": 1,
        "shoot": 0,
        "armour": 10,
        "will": -1,
        "health": 10,
        "gear": "—",
        "notes": "Construct, Cannot Carry Treasure. Already modified; cannot be modified further. May fill a kennel's wolf/warhound slot. Animated by the Animate Construct spell instead of purchased.",
        "description": 'A construct built to resemble and serve as a war hound (Fireheart), animated directly with the Animate Construct spell rather than bought outright. Construct: immune to poison, never counts as wounded. Cannot Carry Treasure. Comes pre-modified and cannot take any further Construct Modification. May be taken in place of a wolf or warhound wherever a kennel-type resource allows one.',
    },
    "scrounger": {
        "name": "Scrounger",
        "cost": 60,
        "category": "standard",
        "source": "Fireheart",
        "move": 5,
        "fight": 3,
        "shoot": 0,
        "armour": 11,
        "will": 1,
        "health": 12,
        "gear": "Staff, hand weapon",
        "notes": (
            "Grants the warband one Black Market roll restricted to the Construct Modification "
            "table (or a 20% discount on such a purchase without the Black Market rule). Only "
            "one Scrounger's benefit applies per warband."
        ),
        "description": 'A construct-parts hoarder and tinkerer (Fireheart). Grants the warband one Black Market roll restricted to the Construct Modification table (or a 20% discount on such a purchase if the Black Market rule isn\'t in use); only one Scrounger\'s benefit applies even with multiple in the warband. Scroungers carry both a staff and a hand weapon. They may decide which to use during any given round of combat but must decide before the dice are rolled.',
    },
    "tinkerer": {
        "name": "Tinkerer",
        "cost": 25,
        "category": "standard",
        "source": "Fireheart",
        "move": 6,
        "fight": 2,
        "shoot": 0,
        "armour": 11,
        "will": 1,
        "health": 10,
        "gear": "Dagger",
        "notes": "+1 to one Embed Enchantment or Animate Construct roll (including repair/re-animation) between games. Never counts as unarmed.",
        "description": 'A gifted construct-and-enchantment mechanic (Fireheart). Grants +1 to one Embed Enchantment or Animate Construct roll (including repair or re-animation attempts) made between games. Always counts as carrying a dagger and so never counts as unarmed.',
    },
    # --- Spellcaster Magazine: Issue 1 firearms ---
    "musketeer": {
        "name": "Musketeer",
        "cost": 60,
        "category": "specialist",
        "source": "Spellcaster Magazine",
        "move": 6,
        "fight": 2,
        "shoot": 2,
        "armour": 11,
        "will": 1,
        "health": 10,
        "gear": "Musket, powder horn, leather armour, hand weapon",
        "notes": "Specialist Soldier (2E errata). Firearm rules (range, reload, Misfire table) are a deferred mechanic.",
        "description": 'A black-powder marksman (Spellcaster Magazine, Issue 1). Carries a Musket — a two-handed firearm, only one at a time, no shield; usable in melee as a two-handed weapon but without the usual +2 damage bonus. The full firearm subsystem (Inaccurate/Armour Piercing/Loud traits, reload actions, the Misfire table) is a deferred mechanic — see the Additional Rules reference for the full rules text.',
    },
    "coachman": {
        "name": "Coachman",
        "cost": 60,
        "category": "specialist",
        "source": "Spellcaster Magazine",
        "move": 6,
        "fight": 2,
        "shoot": 2,
        "armour": 11,
        "will": 1,
        "health": 10,
        "gear": "Blunderbuss, powder horn, leather armour, hand weapon",
        "notes": "Specialist Soldier (2E errata). Firearm rules (range, reload, Misfire table) are a deferred mechanic.",
        "description": 'A shotgun-armed guard (Spellcaster Magazine, Issue 1). Carries a Blunderbuss — a two-handed firearm whose shooting attack normally hits the target and every other figure within 1" of it; usable in melee like a pistol, but without the +1 Fight combo bonus. The full firearm subsystem is a deferred mechanic — see the Additional Rules reference for the full rules text.',
    },
    "duellist": {
        "name": "Duellist",
        "cost": 100,
        "category": "specialist",
        "source": "Spellcaster Magazine",
        "move": 6,
        "fight": 3,
        "shoot": 2,
        "armour": 11,
        "will": 2,
        "health": 12,
        "gear": "2 pistols, powder horn, leather armour, hand weapon",
        "notes": "Specialist Soldier (2E errata). Firearm rules (range, reload, Misfire table) are a deferred mechanic.",
        "description": 'A two-pistol gunfighter (Spellcaster Magazine, Issue 1). Carries a pair of Pistols — one-handed firearms that double as daggers (never counts as unarmed) and grant +1 Fight when paired with a hand weapon in Frostgrave. The full firearm subsystem is a deferred mechanic — see the Additional Rules reference for the full rules text.',
    },
    # --- Spellcaster Magazine: Issue 3 rangifer troop types ---
    "rangifer_boar": {
        "name": "Rangifer Boar",
        "cost": 10,
        "category": "standard",
        "source": "Spellcaster Magazine",
        "move": 6,
        "fight": 2,
        "shoot": 0,
        "armour": 12,
        "will": 2,
        "health": 8,
        "gear": "—",
        "notes": "Part of a rangifer \"hide\" (Issue 3). Animal; cannot carry items or treasure.",
        "description": 'A tamed boar from rangifer culture (Spellcaster Magazine, Issue 3), part of a hired "hide" of up to 5 rangifer troops. Animal: cannot carry items or treasure.',
    },
    "rangifer_ambusher": {
        "name": "Rangifer Ambusher",
        "cost": 20,
        "category": "standard",
        "source": "Spellcaster Magazine",
        "move": 7,
        "fight": 2,
        "shoot": 0,
        "armour": 12,
        "will": 3,
        "health": 12,
        "gear": "2 flint daggers",
        "notes": (
            "Part of a rangifer \"hide\" (Issue 3). Hate Undead, Antlers, Flint Weapons "
            "(destroyed on any natural 1 rolled in combat). All Trap Expert abilities "
            "(Into the Breeding Pits)."
        ),
        "description": 'A rangifer scout skilled with traps (Spellcaster Magazine, Issue 3), part of a hired "hide" of up to 5 rangifer troops. Cultural traits shared by all rangifer: Hate Undead (+1 Fight vs. undead, magic attacks, only while armed with antlers/flint/wood), Antlers (never unarmed; -1 Fight if antlers are the only weapon), Flint Weapons (destroyed on any natural 1 rolled in combat). Also has all of a Trap Expert\'s abilities (Into the Breeding Pits).',
    },
    "rangifer_charger": {
        "name": "Rangifer Charger",
        "cost": 30,
        "category": "standard",
        "source": "Spellcaster Magazine",
        "move": 7,
        "fight": 3,
        "shoot": 0,
        "armour": 12,
        "will": 4,
        "health": 12,
        "gear": "—",
        "notes": "Part of a rangifer \"hide\" (Issue 3). Hate Undead, Antlers (no Fight penalty when armed only with antlers), Flint Weapons.",
        "description": 'A rangifer shock-fighter (Spellcaster Magazine, Issue 3), part of a hired "hide" of up to 5 rangifer troops. Hate Undead, Antlers (suffers no Fight penalty when armed only with its antlers, unlike other rangifer), Flint Weapons.',
    },
    "rangifer_herdsman": {
        "name": "Rangifer Herdsman",
        "cost": 20,
        "category": "standard",
        "source": "Spellcaster Magazine",
        "move": 7,
        "fight": 2,
        "shoot": 0,
        "armour": 12,
        "will": 3,
        "health": 12,
        "gear": "Flint hand weapon",
        "notes": "Part of a rangifer \"hide\" (Issue 3). Hate Undead, Antlers, Flint Weapons.",
        "description": 'A rangifer herder-warrior (Spellcaster Magazine, Issue 3), part of a hired "hide" of up to 5 rangifer troops. Hate Undead, Antlers, Flint Weapons.',
    },
    "rangifer_hewer": {
        "name": "Rangifer Hewer",
        "cost": 60,
        "category": "standard",
        "source": "Spellcaster Magazine",
        "move": 7,
        "fight": 4,
        "shoot": 0,
        "armour": 12,
        "will": 4,
        "health": 14,
        "gear": "Flint two-handed weapon",
        "notes": "Part of a rangifer \"hide\" (Issue 3). Hate Undead, Antlers, Flint Weapons.",
        "description": 'A rangifer heavy fighter (Spellcaster Magazine, Issue 3), part of a hired "hide" of up to 5 rangifer troops. Hate Undead, Antlers, Flint Weapons.',
    },
    "rangifer_hurler": {
        "name": "Rangifer Hurler",
        "cost": 30,
        "category": "standard",
        "source": "Spellcaster Magazine",
        "move": 7,
        "fight": 2,
        "shoot": 2,
        "armour": 12,
        "will": 3,
        "health": 12,
        "gear": "Flint throwing spear, flint hand weapon",
        "notes": (
            "Part of a rangifer \"hide\" (Issue 3). Hate Undead, Antlers, Flint Weapons. "
            "Throwing spear: once/game, a 12\" shooting attack with no damage modifier."
        ),
        "description": 'A rangifer skirmisher (Spellcaster Magazine, Issue 3), part of a hired "hide" of up to 5 rangifer troops. Hate Undead, Antlers, Flint Weapons. Once per game may throw its flint spear as a 12" shooting attack with no damage modifier.',
    },
    "rangifer_packdeer": {
        "name": "Rangifer Packdeer",
        "cost": 20,
        "category": "standard",
        "source": "Spellcaster Magazine",
        "move": 7,
        "fight": 1,
        "shoot": 0,
        "armour": 12,
        "will": 3,
        "health": 12,
        "gear": "—",
        "item_slots": 3,
        "notes": "Part of a rangifer \"hide\" (Issue 3). Hate Undead, Antlers, Flint Weapons. 3 item slots; all Pack Mule abilities (Thaw of the Lich Lord).",
        "description": 'A burden-bearing rangifer (Spellcaster Magazine, Issue 3), part of a hired "hide" of up to 5 rangifer troops. Hate Undead, Antlers, Flint Weapons. Carries 3 item slots and has all of a Pack Mule\'s abilities (Thaw of the Lich Lord).',
    },
    "rangifer_war_leader": {
        "name": "Rangifer War-Leader",
        "cost": 100,
        "category": "specialist",
        "source": "Spellcaster Magazine",
        "move": 7,
        "fight": 2,
        "shoot": 0,
        "armour": 12,
        "will": 3,
        "health": 12,
        "gear": "Flint hand weapon",
        "notes": (
            "Part of a rangifer \"hide\" (Issue 3). Hate Undead, Antlers, Flint Weapons. Free "
            "flint hand weapon, no shield/armour, Move never above 7. Uses the Captain rules "
            "(The Frostgrave Folio) in place of the warband's own Captain — the actual "
            "Captain-replacement mechanic is deferred; hires here as a stat-block soldier."
        ),
        "description": 'The chieftain of a rangifer "hide" (Spellcaster Magazine, Issue 3), who leads using the Captain rules (The Frostgrave Folio) in place of a warband\'s own Captain — never carries a shield or armour, and Move never rises above 7 regardless of bonuses. The actual Captain-replacement mechanic (fielding a War-Leader instead of hiring/promoting a Captain) is a deferred feature; for now this hires as an ordinary specialist stat-block.',
    },
    # --- Spellcaster Magazine: Legendary Soldiers (Issues 4-5) ---
    "bookhound": {
        "name": "Bookhound",
        "cost": 300,
        "category": "specialist",
        "source": "Spellcaster Magazine",
        "move": 6,
        "fight": 2,
        "shoot": 0,
        "armour": 10,
        "will": 5,
        "health": 14,
        "gear": "—",
        "item_slots": 3,
        "notes": (
            "Legendary Soldier (Issue 4) — the by-wizard-level hiring cap is a deferred "
            "mechanic; hires here like an ordinary Specialist Soldier. Immune to Critical "
            "Hits; caps damage from one attack at 10; never triggers Explosive Runes; may "
            "reroll grimoire results on the Random Spell Table; sells grimoires for 270gc; "
            "+1 to one Out of Game Casting Roll per game. 3 item slots."
        ),
        "description": 'A rare, expensive scholar-troop ("Legendary Soldier", Spellcaster Magazine Issue 4). Immune to Critical Hits; caps damage taken from any single attack at 10; never triggers Explosive Runes; may reroll grimoire results on the Random Spell Table; sells grimoires for 270gc; grants +1 to one Out of Game Casting Roll each game. The book\'s wizard-level-gated hiring cap for Legendary Soldiers is a deferred mechanic — this hires uncapped for now, like any Specialist Soldier.',
    },
    "dire_hound": {
        "name": "Dire Hound",
        "cost": 200,
        "category": "specialist",
        "source": "Spellcaster Magazine",
        "move": 8,
        "fight": 3,
        "shoot": 0,
        "armour": 12,
        "will": 4,
        "health": 12,
        "gear": "—",
        "item_slots": 0,
        "notes": (
            "Legendary Soldier (Issue 4) — the by-wizard-level hiring cap is a deferred "
            "mechanic. Animal, Leap (up to 6\" of any move as a leap in any direction), "
            "Powerful Jaws (+2 damage). Cannot carry items or treasure."
        ),
        "description": 'A massive hunting hound ("Legendary Soldier", Spellcaster Magazine Issue 4). Animal, Leap (up to 6" of any move may be a leap in any direction), Powerful Jaws (+2 damage); cannot carry items or treasure. The Legendary Soldier hiring cap is a deferred mechanic.',
    },
    "elemental_archer": {
        "name": "Elemental Archer",
        "cost": 300,
        "category": "specialist",
        "source": "Spellcaster Magazine",
        "move": 6,
        "fight": 2,
        "shoot": 3,
        "armour": 11,
        "will": 4,
        "health": 12,
        "gear": "Bow, up to 3 magic arrows (free)",
        "item_slots": 2,
        "notes": (
            "Legendary Soldier (Issue 4) — the by-wizard-level hiring cap is a deferred "
            "mechanic. All shooting attacks count as magic. May \"steady aim\" (an action, "
            "can replace the move) for -1 Fight on the target's defence if it shoots the "
            "same activation. 2 item slots plus up to 3 free magic arrows."
        ),
        "description": 'An archer whose every shot is magical ("Legendary Soldier", Spellcaster Magazine Issue 4). All shooting attacks count as magic. May "steady aim" — an action that can replace its move — to impose -1 Fight on the target\'s defence if it also shoots that activation. The Legendary Soldier hiring cap is a deferred mechanic.',
    },
    "graverobber": {
        "name": "Graverobber",
        "cost": 300,
        "category": "specialist",
        "source": "Spellcaster Magazine",
        "move": 6,
        "fight": 3,
        "shoot": 0,
        "armour": 11,
        "will": 4,
        "health": 14,
        "gear": "—",
        "item_slots": 2,
        "notes": (
            "Legendary Soldier (Issue 4) — the by-wizard-level hiring cap is a deferred "
            "mechanic. +2 Fight vs. undead, magic attacks vs. undead. Immune to Drain Life "
            "Force, Reveal Death, Strike Dead. Raise Zombie may add a ghoul instead. +5 vs. "
            "Trap Numbers. 2 item slots."
        ),
        "description": 'A tomb-raiding specialist ("Legendary Soldier", Spellcaster Magazine Issue 4). +2 Fight against undead, and its attacks count as magic against them. Immune to Drain Life Force, Reveal Death, and Strike Dead. When Raise Zombie targets the warband, a ghoul may be added instead. +5 to resist Trap Numbers. The Legendary Soldier hiring cap is a deferred mechanic.',
    },
    "shadow_walker": {
        "name": "Shadow-Walker",
        "cost": 300,
        "category": "specialist",
        "source": "Spellcaster Magazine",
        "move": 7,
        "fight": 4,
        "shoot": 0,
        "armour": 10,
        "will": 5,
        "health": 12,
        "gear": "Poisoned weapons",
        "notes": (
            "Legendary Soldier (Issue 4) — the by-wizard-level hiring cap is a deferred "
            "mechanic. Out-of-LoS activation may teleport anywhere else out of enemy line "
            "of sight (not while carrying treasure); can't be targeted from beyond 12\". "
            "+2 Fight when shot at. Poisoned weapons; immune to poison."
        ),
        "description": 'An assassin who moves between shadows ("Legendary Soldier", Spellcaster Magazine Issue 4). When activating out of enemy line of sight, may instead teleport anywhere else out of enemy line of sight (not while carrying treasure); can\'t be targeted by shooting beyond 12", and gains +2 Fight when shot at. Poisoned weapons; immune to poison. The Legendary Soldier hiring cap is a deferred mechanic.',
    },
    "telekinetic": {
        "name": "Telekinetic",
        "cost": 300,
        "category": "specialist",
        "source": "Spellcaster Magazine",
        "move": 6,
        "fight": 3,
        "shoot": 0,
        "armour": 11,
        "will": 7,
        "health": 12,
        "gear": "—",
        "item_slots": 2,
        "notes": (
            "Legendary Soldier (Issue 4) — the by-wizard-level hiring cap is a deferred "
            "mechanic. Once per activation: move a visible treasure token 3\", or move "
            "itself 4\" (either may replace the move action). Immune to Mind Control. "
            "2 item slots."
        ),
        "description": 'A mind-over-matter specialist ("Legendary Soldier", Spellcaster Magazine Issue 4). Once per activation may move a visible treasure token 3", or move itself 4" — either can replace its move action. Immune to Mind Control. The Legendary Soldier hiring cap is a deferred mechanic.',
    },
    "whip_master": {
        "name": "Whip-Master",
        "cost": 300,
        "category": "specialist",
        "source": "Spellcaster Magazine",
        "move": 6,
        "fight": 3,
        "shoot": 2,
        "armour": 11,
        "will": 3,
        "health": 14,
        "gear": "Whip",
        "item_slots": 2,
        "notes": (
            "Legendary Soldier (Issue 4) — the by-wizard-level hiring cap is a deferred "
            "mechanic. Whip: 3\" range shooting attack (max +2); on a hit, target drops "
            "treasure and needs a Move Roll (TN18) or is reeled in 2\". Falling more than "
            "3\": a Move Roll (TN16) catches terrain with the whip to soften the landing. "
            "2 item slots."
        ),
        "description": 'A whip-fighting specialist ("Legendary Soldier", Spellcaster Magazine Issue 4). Its whip makes a 3" range shooting attack (max +2); on a hit the target drops any carried treasure and must pass a Move Roll (TN18) or be reeled in 2". When falling more than 3", a Move Roll (TN16) lets it catch terrain with the whip to soften the landing. The Legendary Soldier hiring cap is a deferred mechanic.',
    },
    "monster_hunter": {
        "name": "Monster Hunter",
        "cost": 300,
        "category": "specialist",
        "source": "Spellcaster Magazine",
        "move": 6,
        "fight": 3,
        "shoot": 1,
        "armour": 11,
        "will": 2,
        "health": 14,
        "gear": "—",
        "item_slots": 2,
        "notes": (
            "Legendary Soldier (Issue 5) — the by-wizard-level hiring cap is a deferred "
            "mechanic, as is the Monster Hunting harvest-economy this soldier ties into. "
            "+1 Fight/+1 Shoot vs. uncontrolled creatures; claims two components per kill, "
            "+5gc extra when selling a monster prize. May place a Monster Trap within 8\" "
            "of setup. 2 item slots."
        ),
        "description": 'A hunter specialized against monsters ("Legendary Soldier", Spellcaster Magazine Issue 5). +1 Fight and +1 Shoot against uncontrolled creatures. Ties into the Monster Hunting harvest economy (claims two components per kill, +5gc extra selling a monster prize) — that whole economy is a deferred mechanic, described in the Additional Rules reference. May place a Monster Trap within 8" of table setup (Deadfall, Spring-loaded Spike, or Net).',
    },
    "potion_master": {
        "name": "Potion Master",
        "cost": 300,
        "category": "specialist",
        "source": "Spellcaster Magazine",
        "move": 6,
        "fight": 2,
        "shoot": 0,
        "armour": 11,
        "will": 5,
        "health": 14,
        "gear": "—",
        "item_slots": 4,
        "notes": (
            "Legendary Soldier (Issues 5 & 6, reprinted) — the by-wizard-level hiring cap "
            "is a deferred mechanic. Doubles the wizard's Brew Potion component bonus "
            "(+2 casting, 50gc off). Drinks potions as a free action. 4 item slots (3 "
            "potions only). Applies potions to nearby figures. Wizard may reroll one "
            "potion-table roll per game."
        ),
        "description": 'A potion specialist ("Legendary Soldier", Spellcaster Magazine Issues 5 and 6). Doubles the wizard\'s Brew Potion component bonus (+2 to the Casting Roll, 50gc off ingredient cost). Drinks potions as a free action, and may apply a potion to a nearby figure. Carries 4 item slots, but only for potions (max 3). The wizard may reroll one potion-table roll per game while this soldier is on the roster. The Legendary Soldier hiring cap is a deferred mechanic.',
    },
    # --- Bestiary creatures hireable as soldiers, previously reference-only ---
    # Added for Ragged Warbands & Random Recruits (The Red King, Chapter Two),
    # whose Random Recruit Table III can produce any of these four. Each is
    # sourced to the book that actually grants the hire (only Foulhorn is
    # genuinely a Red King addition), modeled on "rangifer": a plain soldier
    # entry whose hiring prerequisite (a magic item, here) is documented but
    # not enforced by the app.
    "werewolf": {
        "name": "Werewolf",
        "cost": 200,
        "category": "specialist",
        "source": "The Perilous Dark",
        "item_slots": 0,
        "move": 7,
        "fight": 4,
        "shoot": 0,
        "armour": 11,
        "will": 5,
        "health": 12,
        "gear": "—",
        "notes": "Joins via the Book of the Werewolf (200gc; carries no items). Needs 20gc/game upkeep or it leaves. Expert Climber; Bounty 20gc.",
        "description": 'A wolf-human hybrid, hired via the Book of the Werewolf. Expert Climber: suffers no movement penalty for climbing. Bounty (20gc): a reward awaits any warband that kills it. Requires 20gc upkeep before each game or it leaves the warband; carries no item slots.',
    },
    "snow_troll": {
        "name": "Snow Troll",
        "cost": 0,
        "category": "specialist",
        "source": "The Maze of Malcor",
        "move": 4,
        "fight": 4,
        "shoot": 0,
        "armour": 14,
        "will": 2,
        "health": 16,
        "gear": "—",
        "notes": "Captured (not purchased) via Troll Shackles after being dropped to 0 Health. Large; Strong (+2 damage).",
        "description": 'A captured snow troll, joining only via Troll Shackles once dropped to 0 Health in a game. Large: suffers the -2 Large Target penalty against shooting attacks. Strong: deals +2 damage.',
    },
    "foulhorn": {
        "name": "Foulhorn",
        "cost": 200,
        "category": "specialist",
        "source": "The Red King",
        "item_slots": 0,
        "move": 7,
        "fight": 4,
        "shoot": 0,
        "armour": 12,
        "will": 5,
        "health": 12,
        "gear": "—",
        "notes": "Joins via the Book of the Foulhorn (200gc). Can pick up treasure but has no item slots. Horns, Keen Senses. Risk of injuring a random warband member (-3 Health) before each game on a 16+.",
        "description": 'A four-armed mountain predator, hired via the Book of the Foulhorn. Horns: +2 Fight when it charges into combat and fights in the same activation. Keen Senses: treats everything within 6" as being in line of sight for movement purposes. Before each game, roll a die: on a 16+ it has wounded a random warband member (-3 Health) in a brawl.',
    },
    "vampire": {
        "name": "Vampire",
        "cost": 0,
        "category": "specialist",
        "source": "The Red King",
        "item_slots": 0,
        "move": 7,
        "fight": 4,
        "shoot": 0,
        "armour": 12,
        "will": 5,
        "health": 14,
        "gear": "—",
        "notes": "Undead: can carry treasure but has no item slots. Immune to Normal Weapons, Magic Attack, Mind Lock, True Sight.",
        "description": 'A vampire fielded as a soldier rather than a wizard\'s school (see the separate playable Vampire Wizard, Blood Legacy). Undead: immune to poison, never wounded, may carry treasure tokens but has no item slots. Immune to Normal Weapons: can only be harmed by magic. Magic Attack: all its attacks count as magic. Mind Lock: immune to Mind Control and Suggestion. True Sight: ignores Beauty and Invisibility, and destroys any Illusionary Soldier it fights.',
    },
    "minor_demon": {
        "name": "Minor Demon",
        "cost": 0,
        "category": "specialist",
        "source": "The Red King",
        "item_slots": 0,
        "move": 6,
        "fight": 3,
        "shoot": 0,
        "armour": 11,
        "will": 4,
        "health": 12,
        "gear": "—",
        "notes": (
            "A permanent minor demon (distinct from summoned_minor_demon, which is a "
            "temporary Summon Demon result). Demon: can carry treasure but has no item slots."
        ),
        "description": 'A minor demon that has joined the warband as a permanent member, rather than the temporary result of casting Summon Demon (see summoned_minor_demon). Demon: immune to poison, all its attacks count as magic, and it may carry treasure tokens but has no item slots.',
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
    "The Frostgrave Folio",
    "Grave Mutations",
    "The Red King",
    "Blood Legacy",
    "Fireheart",
    "The Wildwoods",
    "Spellcaster Magazine",
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

# Heading for Raise Zombie / Summon Demon's temporary members — grouped apart
# from the permanent summons above since they don't count against the
# soldier/specialist caps and get their own "Hire temporary member" panel
# rather than living in the main hire catalog (see app.py's warband_view).
TEMPORARY_GROUP_LABEL = "Temporary members"

# Total cap across raised zombies + summoned demons combined, no per-type
# sub-limit — a house-rule loosening of the strict "one zombie, one demon"
# reading, on the reasoning that the app is a bookkeeping tool and any real
# limit is enforced at the table, not by the software.
TEMPORARY_MEMBER_LIMIT = 10


def soldier_group_label(row: dict) -> str:
    if row.get("temporary"):
        return TEMPORARY_GROUP_LABEL
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
    "companion_white_gorilla",
    "small_construct",
    "medium_construct",
    "large_construct",
    "construct_familiar",
    "construct_hound_summoned",
    "demonic_servant",
]

# Order the temporary members appear in: the raised zombie, then the three
# summoned-demon tiers from weakest to strongest.
TEMPORARY_ORDER = [
    "raised_zombie",
    "summoned_imp",
    "summoned_minor_demon",
    "summoned_major_demon",
    "illusionary_soldier",
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

    Temporary members (Raise Zombie, Summon Demon) get their own block right
    after the permanent summons, for the same reason.
    """
    if r.get("temporary"):
        rank = TEMPORARY_ORDER.index(r["key"]) if r["key"] in TEMPORARY_ORDER else len(TEMPORARY_ORDER)
        return (0, 2, rank, 0, r["name"])
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


def construct_type_keys() -> set[str]:
    """Soldier type keys animated by the Animate Construct spell."""
    return {k for k, v in SOLDIERS.items() if v.get("requires_spell") == "Animate Construct"}


# Fireheart's Construct Modification rule only applies to the "standard"
# small/medium/large constructs — the Construct Familiar and both Construct
# Hound entries come pre-modified and can never take another modification
# (see their "notes" above), even though the familiar is also animated by
# Animate Construct.
STANDARD_CONSTRUCT_TYPE_KEYS = {"small_construct", "medium_construct", "large_construct"}


# Blood Legacy's Giant-Blooded modification (Chapter Three) is written for
# "any core-rulebook standard/specialist soldier" — which already excludes
# every animal/demon/construct/undead entry, since none of those are plain
# Core Rules hires with no requires_spell/temporary marker (war_hound is the
# one Core Rules animal, so it's excluded explicitly).
GIANT_BLOODED_EXCLUDED_TYPE_KEYS = {"war_hound"}


def giant_blooded_eligible_type_keys() -> set[str]:
    """Soldier type keys Giant-Blooded may be applied to: ordinary Core Rules
    standard/specialist hires only — not animals, demons, constructs or
    undead (see GIANT_BLOODED_EXCLUDED_TYPE_KEYS and the requires_spell/
    temporary checks below, which rule out every summoned/animated entry)."""
    return {
        k
        for k, v in SOLDIERS.items()
        if v.get("source", "Core Rules") == "Core Rules"
        and not v.get("requires_spell")
        and not v.get("temporary")
        and k not in GIANT_BLOODED_EXCLUDED_TYPE_KEYS
    }


# Core soldier types an Illusionary Soldier may copy Move/Fight/Shoot/Armour/
# Will from — every Core Rules standard/specialist soldier except the
# Apothecary (its stat line wouldn't make sense on a combat illusion).
def illusion_source_choices() -> list[dict]:
    rows = [
        {"id": k, "label": v["name"]}
        for k, v in SOLDIERS.items()
        if v.get("source", "Core Rules") == "Core Rules"
        and not v.get("requires_spell")
        and not v.get("temporary")
        and k != "apothecary"
    ]
    rows.sort(key=lambda r: r["label"])
    return rows


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


def level_from_xp(xp: int, per_level: int = XP_PER_LEVEL, max_level: int = MAX_WIZARD_LEVEL) -> int:
    return min(max_level, max(0, int(xp) // int(per_level or XP_PER_LEVEL)))


def xp_to_next_level(xp: int, level: int, per_level: int = XP_PER_LEVEL) -> int:
    return max(0, xp_for_level(level + 1, per_level) - int(xp))
