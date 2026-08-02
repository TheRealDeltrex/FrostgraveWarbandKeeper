"""Blood Legacy (Chapter Three): Giant-Blooded soldier modification, the Fire
Giant and Vampire Wizard playable builds, plus The Grimoire of Fin Dalka
magic item."""

import warband_store
from frostgrave_data import (
    FIRE_GIANT_HEALTH_CAP,
    FIRE_GIANT_WIZARD_BASE,
    FIRE_GIANT_XP_PER_LEVEL,
    GIANT_BLOODED_COST,
    VAMPIRE_HEALTH_CAP,
    VAMPIRE_MIN_MAX_SOLDIERS,
    VAMPIRE_WILL_CAP,
    VAMPIRE_XP_PER_LEVEL,
    WIZARD_BASE,
    giant_blooded_eligible_type_keys,
    spell_id,
)
from game_content import load_magic_items, magic_items_for_sources
import expansions


# --- Giant-Blooded -----------------------------------------------------------


def test_giant_blooded_eligibility_excludes_animals_constructs_demons_undead():
    eligible = giant_blooded_eligible_type_keys()
    assert "thug" in eligible
    assert "archer" in eligible
    assert "war_hound" not in eligible  # Core Rules animal
    assert "small_construct" not in eligible  # Animate Construct
    assert "companion_wolf" not in eligible  # Animal Companion
    assert "raised_zombie" not in eligible  # temporary/undead
    assert "summoned_minor_demon" not in eligible  # temporary/demon


def test_giant_blooded_requires_homerule_enabled(fresh_warband):
    wb = fresh_warband
    ok, msg = warband_store.add_soldier(wb, "thug", "Grunt")
    assert ok, msg
    soldier = wb["soldiers"][0]

    ok, msg = warband_store.set_soldier_giant_blooded(wb, soldier["id"], True)
    assert not ok
    assert "homerule" in msg.lower()


def test_giant_blooded_apply_and_remove(fresh_warband):
    wb = fresh_warband
    wb["homerules"]["giant_blooded_enabled"] = True
    ok, msg = warband_store.add_soldier(wb, "thug", "Grunt")
    assert ok, msg
    soldier = wb["soldiers"][0]
    before_gold = wb["gold"]

    ok, msg = warband_store.set_soldier_giant_blooded(wb, soldier["id"], True)
    assert ok, msg
    assert soldier["giant_blooded"] is True
    assert soldier["move"] == 6 - 1
    assert soldier["will"] == -1 - 2
    assert soldier["health"] == 10 + 2
    assert wb["gold"] == before_gold - GIANT_BLOODED_COST

    ok, msg = warband_store.set_soldier_giant_blooded(wb, soldier["id"], False)
    assert ok, msg
    assert soldier["giant_blooded"] is False
    assert soldier["move"] == 6
    assert soldier["will"] == -1
    assert soldier["health"] == 10
    # The 50gc fee isn't refunded on removal.
    assert wb["gold"] == before_gold - GIANT_BLOODED_COST


def test_giant_blooded_only_one_per_warband(fresh_warband):
    wb = fresh_warband
    wb["homerules"]["giant_blooded_enabled"] = True
    warband_store.add_soldier(wb, "thug", "Grunt")
    warband_store.add_soldier(wb, "thief", "Sneak")
    s1, s2 = wb["soldiers"]

    ok, msg = warband_store.set_soldier_giant_blooded(wb, s1["id"], True)
    assert ok, msg
    ok, msg = warband_store.set_soldier_giant_blooded(wb, s2["id"], True)
    assert not ok
    assert "only one" in msg.lower()


def test_giant_blooded_rejects_ineligible_soldier(fresh_warband):
    wb = fresh_warband
    wb["homerules"]["giant_blooded_enabled"] = True
    ok, msg = warband_store.add_soldier(wb, "war_hound", "Fang")
    assert ok, msg
    soldier = wb["soldiers"][0]

    ok, msg = warband_store.set_soldier_giant_blooded(wb, soldier["id"], True)
    assert not ok


# --- Fire Giant Wizard --------------------------------------------------------


def _fire_giant_spell_keys() -> list[str]:
    # 3 own (Fire Giant) + 1 each aligned (Enchanter/Elementalist/Soothsayer)
    # + 2 neutral from different schools (Illusionist/Necromancer here).
    school = "Fire Giant"
    return [
        spell_id(school, "Comet"),
        spell_id(school, "Earthquake"),
        spell_id(school, "Enflame"),
        spell_id("Enchanter", "Enchant Weapon"),
        spell_id("Elementalist", "Wall"),
        spell_id("Soothsayer", "Awareness"),
        spell_id("Illusionist", "Blink"),
        spell_id("Necromancer", "Bone Dart"),
    ]


def test_fire_giant_school_rejected_without_homerule():
    wb, msg = warband_store.create_warband(
        warband_name="Giants", wizard_name="Grond", school="Fire Giant",
        spell_keys=[], fire_giant_playable=False,
    )
    assert wb is None
    assert "fire giant" in msg.lower()


def test_fire_giant_wizard_stats_no_apprentice_and_health_cap():
    wb, msg = warband_store.create_warband(
        warband_name="Giants", wizard_name="Grond", school="Fire Giant",
        spell_keys=_fire_giant_spell_keys(), fire_giant_playable=True,
        with_apprentice=False,
    )
    assert wb, msg
    wiz = wb["wizard"]
    assert wiz["stats"] == FIRE_GIANT_WIZARD_BASE
    assert expansions.is_fire_giant(wb) is True
    assert expansions.xp_per_level(wb) == FIRE_GIANT_XP_PER_LEVEL
    assert expansions.wizard_stat_caps(wb)["health"] == FIRE_GIANT_HEALTH_CAP

    ok, msg = warband_store.hire_apprentice(wb)
    assert not ok
    assert "apprentice" in msg.lower()


def test_fire_giant_cannot_take_apprentice_at_creation():
    wb, msg = warband_store.create_warband(
        warband_name="Giants", wizard_name="Grond", school="Fire Giant",
        spell_keys=_fire_giant_spell_keys(), fire_giant_playable=True,
        with_apprentice=True,
    )
    assert wb is None
    assert "apprentice" in msg.lower()


def test_fire_giant_cannot_learn_chronomancer_or_write_scroll():
    wb, msg = warband_store.create_warband(
        warband_name="Giants", wizard_name="Grond", school="Fire Giant",
        spell_keys=_fire_giant_spell_keys(), fire_giant_playable=True,
    )
    assert wb, msg
    chrono = {"name": "Fast Act", "school": "Chronomancer", "source": "Core Rules"}
    write_scroll = {"name": "Write Scroll", "school": "Enchanter", "source": "Core Rules"}
    ok_spell = {"name": "Enflame", "school": "Fire Giant", "source": "Blood Legacy"}
    assert expansions.spell_state_block(wb, chrono) is not None
    assert expansions.spell_state_block(wb, write_scroll) is not None
    assert expansions.spell_state_block(wb, ok_spell) is None


def test_ordinary_wizard_is_not_fire_giant(fresh_warband):
    assert expansions.is_fire_giant(fresh_warband) is False
    assert expansions.spell_state_block(
        fresh_warband, {"name": "Write Scroll", "school": "Elementalist"}
    ) is None


# --- Vampire Wizard -----------------------------------------------------------


def _vampire_spell_keys() -> list[str]:
    # 3 own (Vampire) + 1 each aligned (Chronomancer/Necromancer/Soothsayer)
    # + 2 neutral from different schools (Elementalist/Enchanter here).
    school = "Vampire"
    return [
        spell_id(school, "Mist Form"),
        spell_id(school, "Lifedrain"),
        spell_id(school, "Thralldom"),
        spell_id("Chronomancer", "Fast Act"),
        spell_id("Necromancer", "Bone Dart"),
        spell_id("Soothsayer", "Awareness"),
        spell_id("Elementalist", "Wall"),
        spell_id("Enchanter", "Enchant Weapon"),
    ]


def test_vampire_school_rejected_without_homerule():
    wb, msg = warband_store.create_warband(
        warband_name="Nightfall", wizard_name="Countess", school="Vampire",
        spell_keys=[], vampire_playable=False,
    )
    assert wb is None
    assert "vampire" in msg.lower()


def test_vampire_wizard_stats_no_apprentice_bigger_roster_and_caps():
    wb, msg = warband_store.create_warband(
        warband_name="Nightfall", wizard_name="Countess", school="Vampire",
        spell_keys=_vampire_spell_keys(), vampire_playable=True,
        with_apprentice=False,
    )
    assert wb, msg
    wiz = wb["wizard"]
    # Same starting stats as an ordinary wizard.
    assert wiz["stats"] == WIZARD_BASE
    assert expansions.is_vampire(wb) is True
    assert expansions.xp_per_level(wb) == VAMPIRE_XP_PER_LEVEL
    caps = expansions.wizard_stat_caps(wb)
    assert caps["health"] == VAMPIRE_HEALTH_CAP
    assert caps["will"] == VAMPIRE_WILL_CAP
    assert wb["homerules"]["max_soldiers"] >= VAMPIRE_MIN_MAX_SOLDIERS

    ok, msg = warband_store.hire_apprentice(wb)
    assert not ok
    assert "apprentice" in msg.lower()


def test_vampire_cannot_take_apprentice_at_creation():
    wb, msg = warband_store.create_warband(
        warband_name="Nightfall", wizard_name="Countess", school="Vampire",
        spell_keys=_vampire_spell_keys(), vampire_playable=True,
        with_apprentice=True,
    )
    assert wb is None
    assert "apprentice" in msg.lower()


def test_vampire_cannot_learn_thaumaturge_spells_or_field_a_rangifer():
    wb, msg = warband_store.create_warband(
        warband_name="Nightfall", wizard_name="Countess", school="Vampire",
        spell_keys=_vampire_spell_keys(), vampire_playable=True,
    )
    assert wb, msg
    thaum_spell = {"name": "Heal", "school": "Thaumaturge", "source": "Core Rules"}
    ok_spell = {"name": "Lifedrain", "school": "Vampire", "source": "Blood Legacy"}
    assert expansions.spell_state_block(wb, thaum_spell) is not None
    assert expansions.spell_state_block(wb, ok_spell) is None
    assert expansions.soldier_state_block(wb, "rangifer") is not None


def test_ordinary_wizard_is_not_vampire(fresh_warband):
    assert expansions.is_vampire(fresh_warband) is False
    assert expansions.spell_state_block(
        fresh_warband, {"name": "Heal", "school": "Thaumaturge"}
    ) is None
    assert expansions.soldier_state_block(fresh_warband, "rangifer") is None


# --- The Grimoire of Fin Dalka ------------------------------------------------


def test_grimoire_of_fin_dalka_listed_as_a_blood_legacy_magic_item():
    names = {it["name"] for it in load_magic_items()}
    assert "The Grimoire of Fin Dalka" in names
    scoped = {it["name"] for it in magic_items_for_sources({"Blood Legacy"})}
    assert "The Grimoire of Fin Dalka" in scoped
