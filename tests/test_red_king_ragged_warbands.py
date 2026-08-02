"""The Red King (Chapter Two): soldier item slots (prerequisite), the new
bestiary-derived soldiers (Werewolf/Snow Troll/Foulhorn/Vampire/Minor Demon),
and the Ragged Warbands & Random Recruits roller."""

import random

import warband_store
from frostgrave_data import (
    RANDOM_RECRUIT_TABLE_II,
    RANDOM_RECRUIT_TABLE_III,
    SOLDIERS,
    permanent_injury_by_roll,
)
import expansions


# --- Soldier item slots (Phase A/B prerequisite) -----------------------------


def test_soldier_item_slots_derived_for_ordinary_and_zero_slot_types(fresh_warband):
    wb = fresh_warband
    assert expansions.soldier_item_slots(wb, "thug") == 1
    assert expansions.soldier_item_slots(wb, "pack_mule") == 3
    assert expansions.soldier_item_slots(wb, "war_hound") == 0
    assert expansions.soldier_item_slots(wb, "companion_wolf") == 0
    assert expansions.soldier_item_slots(wb, "small_construct") == 0
    assert expansions.soldier_item_slots(wb, "raised_zombie") == 0


def test_add_soldier_gets_correctly_sized_item_slots(fresh_warband):
    wb = fresh_warband
    ok, msg = warband_store.add_soldier(wb, "thug", "Grunt")
    assert ok, msg
    ok, msg = warband_store.add_soldier(wb, "pack_mule", "Mule")
    assert ok, msg
    thug = next(s for s in wb["soldiers"] if s["type_key"] == "thug")
    mule = next(s for s in wb["soldiers"] if s["type_key"] == "pack_mule")
    assert thug["item_slots"] == [""]
    assert mule["item_slots"] == ["", "", ""]
    assert "items" not in thug and "items" not in mule


# --- New Red King / bestiary-derived soldiers --------------------------------


def test_new_soldiers_registered_with_expected_sources():
    assert SOLDIERS["werewolf"]["source"] == "The Perilous Dark"
    assert SOLDIERS["snow_troll"]["source"] == "The Maze of Malcor"
    assert SOLDIERS["foulhorn"]["source"] == "The Red King"
    assert SOLDIERS["vampire"]["source"] == "The Red King"
    assert SOLDIERS["minor_demon"]["source"] == "The Red King"
    # Distinct from the temporary Summon Demon result of the same display name.
    assert SOLDIERS["minor_demon"].get("temporary") is not True
    assert SOLDIERS["summoned_minor_demon"]["temporary"] is True


def test_permanent_injury_by_roll_covers_all_20():
    seen = {permanent_injury_by_roll(n)["id"] for n in range(1, 21)}
    assert len(seen) == 9  # all 9 injuries reachable, none overlap/gap


# --- Ragged Warbands & Random Recruits ---------------------------------------


def test_ragged_warbands_requires_source_and_homerule(fresh_warband):
    wb = fresh_warband
    wb["homerules"]["enabled_sources"]["The Red King"] = False
    ok, msg = warband_store.roll_random_recruits(wb)
    assert not ok
    assert "red king" in msg.lower()

    wb["homerules"]["enabled_sources"]["The Red King"] = True
    ok, msg = warband_store.roll_random_recruits(wb)
    assert not ok
    assert "homerule" in msg.lower()


def test_roll_fills_roster_to_ten_accounting_for_apprentice(fresh_warband):
    random.seed(1)
    wb = fresh_warband
    wb["homerules"]["ragged_warbands_enabled"] = True
    ok, msg = warband_store.hire_apprentice(wb)
    assert ok, msg
    ok, msg = warband_store.roll_random_recruits(wb, with_status=False)
    assert ok, msg
    have = 1 + 1 + warband_store.soldier_count(wb)  # wizard + apprentice + soldiers(+captain)
    assert have == 10

    # A second roll on an already-full roster is a no-op.
    ok, msg = warband_store.roll_random_recruits(wb)
    assert not ok
    assert "10" in msg


def test_roll_bypasses_gold_and_specialist_cap(fresh_warband):
    random.seed(2)
    wb = fresh_warband
    wb["gold"] = 0
    wb["homerules"]["max_specialists"] = 0
    wb["homerules"]["ragged_warbands_enabled"] = True
    ok, msg = warband_store.roll_random_recruits(wb, with_status=False)
    assert ok, msg
    assert wb["gold"] == 0  # no gold was ever charged
    assert len(wb["soldiers"]) == 9


def test_roll_never_produces_a_soldier_from_a_disabled_source(fresh_warband):
    random.seed(3)
    wb = fresh_warband
    for book in wb["homerules"]["enabled_sources"]:
        wb["homerules"]["enabled_sources"][book] = False
    wb["homerules"]["enabled_sources"]["The Red King"] = True
    wb["homerules"]["ragged_warbands_enabled"] = True
    ok, msg = warband_store.roll_random_recruits(wb, with_status=False)
    assert ok, msg
    for s in wb["soldiers"]:
        src = SOLDIERS[s["type_key"]].get("source", "Core Rules")
        assert src in ("Core Rules", "The Red King"), (s["type_key"], src)


def test_zero_slot_soldier_never_gets_an_item_written_by_status_roll(fresh_warband):
    # war_hound has 0 item slots. Run the status roll many times (seeded) so
    # every branch of the d20 table gets exercised at least once, and confirm
    # an item result never has anywhere to go — "cannot be logically
    # applied" — rather than raising or growing item_slots out of nowhere.
    random.seed(4)
    wb = fresh_warband
    info = warband_store.get_soldier("war_hound")
    for _ in range(200):
        soldier, _order, _illusion = warband_store._build_soldier_record(wb, "war_hound", info)
        assert soldier["item_slots"] == []
        warband_store._apply_random_recruit_status(wb, soldier)
        assert soldier["item_slots"] == []


def test_random_recruit_tables_only_reference_real_soldiers_or_reroll():
    for lo, hi, type_key in RANDOM_RECRUIT_TABLE_II + RANDOM_RECRUIT_TABLE_III:
        assert lo <= hi
        if type_key is not None:
            assert type_key in SOLDIERS, type_key
