"""Legendary Soldier category/captain rules (Spellcaster Magazine, Issue 4),
the split Spellcaster Magazine soldier toggles + Firearms Rules toggle, and
the core rules' apprentice-takes-over-on-wizard-death (p.103, New Wizards)."""

from copy import deepcopy

import expansions
import warband_store
from frostgrave_data import LEGENDARY_SOLDIER_TYPE_KEYS, get_soldier

# --- Legendary Soldiers are labeled "legendary", not "specialist" -----------


def test_legendary_soldiers_have_their_own_category():
    for key in LEGENDARY_SOLDIER_TYPE_KEYS:
        assert get_soldier(key)["category"] == "legendary"


def test_legendary_soldiers_no_longer_count_as_specialists(fresh_warband):
    wb = fresh_warband
    _enable_legendary(wb)
    ok, msg = warband_store.add_soldier(wb, "dire_hound", "Fang")
    assert ok, msg
    assert warband_store.specialist_count(wb) == 0
    assert warband_store.legendary_soldier_count(wb) == 1


# --- Split Spellcaster Magazine soldier toggles ------------------------------


def _enable_legendary(wb: dict) -> None:
    # All three Spellcaster Magazine soldier toggles default True (a group
    # opts out, not in) — tests exercise a specific combination, so set
    # every flag explicitly rather than relying on the current default.
    wb["homerules"]["enabled_sources"]["Spellcaster Magazine"] = True
    wb["homerules"]["spellcaster_magazine_legendary_soldiers"] = True
    wb["homerules"]["spellcaster_magazine_soldiers"] = False
    wb["homerules"]["firearms_rules_enabled"] = False


def _enable_ordinary(wb: dict) -> None:
    wb["homerules"]["enabled_sources"]["Spellcaster Magazine"] = True
    wb["homerules"]["spellcaster_magazine_soldiers"] = True
    wb["homerules"]["spellcaster_magazine_legendary_soldiers"] = False
    wb["homerules"]["firearms_rules_enabled"] = False


def test_legendary_toggle_is_independent_of_the_ordinary_toggle(fresh_warband):
    wb = fresh_warband
    _enable_ordinary(wb)  # ordinary on, legendary off
    ok, msg = warband_store.add_soldier(wb, "dire_hound", "Fang")
    assert not ok
    assert "switched off" in msg.lower()


def test_ordinary_toggle_off_still_blocks_non_legendary_soldiers(fresh_warband):
    wb = fresh_warband
    _enable_legendary(wb)  # legendary on, ordinary off
    warband_store.add_vault_item(wb, "Book of the Rangifer")
    ok, msg = warband_store.add_soldier(wb, "rangifer_herdsman", "Scout")
    assert not ok
    assert "switched off" in msg.lower()


def test_both_toggles_on_allow_both_kinds(fresh_warband):
    wb = fresh_warband
    _enable_legendary(wb)
    wb["homerules"]["spellcaster_magazine_soldiers"] = True
    warband_store.add_vault_item(wb, "Book of the Rangifer")
    ok, msg = warband_store.add_soldier(wb, "rangifer_herdsman", "Scout")
    assert ok, msg
    ok, msg = warband_store.add_soldier(wb, "dire_hound", "Fang")
    assert ok, msg


# --- Firearms Rules toggle: needs BOTH itself and the ordinary toggle -------


def test_firearm_soldier_blocked_with_neither_toggle(fresh_warband):
    wb = fresh_warband
    wb["homerules"]["enabled_sources"]["Spellcaster Magazine"] = True
    wb["homerules"]["spellcaster_magazine_soldiers"] = False
    wb["homerules"]["firearms_rules_enabled"] = False
    ok, msg = warband_store.add_soldier(wb, "musketeer", "Shooter")
    assert not ok


def test_firearm_soldier_blocked_with_only_ordinary_toggle(fresh_warband):
    wb = fresh_warband
    _enable_ordinary(wb)
    ok, msg = warband_store.add_soldier(wb, "musketeer", "Shooter")
    assert not ok


def test_firearm_soldier_blocked_with_only_firearms_toggle(fresh_warband):
    wb = fresh_warband
    wb["homerules"]["enabled_sources"]["Spellcaster Magazine"] = True
    wb["homerules"]["spellcaster_magazine_soldiers"] = False
    wb["homerules"]["firearms_rules_enabled"] = True
    ok, msg = warband_store.add_soldier(wb, "musketeer", "Shooter")
    assert not ok


def test_firearm_soldier_hireable_with_both_toggles(fresh_warband):
    wb = fresh_warband
    _enable_ordinary(wb)
    wb["homerules"]["firearms_rules_enabled"] = True
    ok, msg = warband_store.add_soldier(wb, "musketeer", "Shooter")
    assert ok, msg


# --- Legendary Captain + specialist cap reduction ----------------------------


def test_captain_is_ordinary_specialist_when_legendary_disabled(fresh_warband):
    wb = fresh_warband
    wb["homerules"]["captain_mode"] = "hire"
    wb["homerules"]["enabled_sources"]["The Frostgrave Folio"] = True
    wb["homerules"]["spellcaster_magazine_legendary_soldiers"] = False
    wb["gold"] = 1000
    ok, msg = warband_store.hire_captain(wb, "Cap", tricks=["furious_attack", "riposte"])
    assert ok, msg
    assert warband_store.specialist_count(wb) == 1
    assert warband_store.legendary_soldier_count(wb) == 0


def test_captain_becomes_legendary_when_legendary_enabled(fresh_warband):
    wb = fresh_warband
    wb["homerules"]["captain_mode"] = "hire"
    wb["homerules"]["enabled_sources"]["The Frostgrave Folio"] = True
    _enable_legendary(wb)
    wb["gold"] = 1000
    ok, msg = warband_store.hire_captain(wb, "Cap", tricks=["furious_attack", "riposte"])
    assert ok, msg
    assert warband_store.specialist_count(wb) == 0
    assert warband_store.legendary_soldier_count(wb) == 1


def test_legendary_captain_blocked_by_legendary_cap_not_specialist_cap(fresh_warband):
    wb = fresh_warband
    wb["homerules"]["captain_mode"] = "hire"
    wb["homerules"]["enabled_sources"]["The Frostgrave Folio"] = True
    _enable_legendary(wb)
    wb["gold"] = 1000
    # Level 0 wizard: legendary cap is 1, already used up by a Dire Hound.
    ok, msg = warband_store.add_soldier(wb, "dire_hound", "Fang")
    assert ok, msg
    ok, msg = warband_store.hire_captain(wb, "Cap", tricks=["furious_attack", "riposte"])
    assert not ok
    assert "legendary soldier" in msg.lower()


def test_fielding_a_legendary_soldier_caps_specialists_at_three(fresh_warband):
    wb = fresh_warband
    _enable_legendary(wb)
    assert expansions.max_specialists(wb) == 4  # book default, no legendary yet
    ok, msg = warband_store.add_soldier(wb, "dire_hound", "Fang")
    assert ok, msg
    assert expansions.max_specialists(wb) == 3


def test_legendary_specialist_cap_reduction_overrides_a_higher_homerule_base(fresh_warband):
    wb = fresh_warband
    wb["homerules"]["max_specialists"] = 8
    _enable_legendary(wb)
    ok, msg = warband_store.add_soldier(wb, "dire_hound", "Fang")
    assert ok, msg
    assert expansions.max_specialists(wb) == 3


# --- Apprentice takes over on wizard death (core rules p.103) ---------------


def test_no_apprentice_refuses(fresh_warband):
    wb = fresh_warband
    ok, msg = warband_store.apprentice_takes_over(wb)
    assert not ok
    assert "no apprentice" in msg.lower()


def test_wizard_level_5_or_below_refuses(fresh_warband):
    wb = fresh_warband
    warband_store.hire_apprentice(wb, "Appy")
    wb["wizard"]["level"] = 5
    ok, msg = warband_store.apprentice_takes_over(wb)
    assert not ok
    assert "discard" in msg.lower()


def test_apprentice_becomes_wizard_at_level_minus_six(fresh_warband):
    wb = fresh_warband
    warband_store.hire_apprentice(wb, "Appy")
    warband_store.sync_apprentice(wb)
    wb["wizard"]["level"] = 15
    ap_stats_before = deepcopy(wb["apprentice"]["stats"])
    ok, msg = warband_store.apprentice_takes_over(wb)
    assert ok, msg
    assert wb["wizard"]["name"] == "Appy"
    assert wb["wizard"]["level"] == 9
    assert wb["wizard"]["stats"] == ap_stats_before
    assert wb["wizard"]["spells"] == []
    assert wb["apprentice"] is None


def test_apprentice_takes_over_keeps_gear_but_drops_old_wizard_spells(fresh_warband):
    wb = fresh_warband
    warband_store.hire_apprentice(wb, "Appy")
    wb["wizard"]["level"] = 6
    wb["wizard"]["spells"] = [{"id": "x", "name": "Wall", "school": "Elementalist", "cn": 10}]
    wb["apprentice"]["item_slots"][0] = "Staff"
    ok, msg = warband_store.apprentice_takes_over(wb)
    assert ok, msg
    assert "Staff" in wb["wizard"]["item_slots"]
    assert wb["wizard"]["spells"] == []
    assert wb["wizard"]["level"] == 0


def test_apprentice_takes_over_resets_wizard_state(fresh_warband):
    wb = fresh_warband
    warband_store.hire_apprentice(wb, "Appy")
    wb["wizard"]["level"] = 6
    wb["wizard"]["state"]["kind"] = "lich"
    ok, msg = warband_store.apprentice_takes_over(wb)
    assert ok, msg
    assert wb["wizard"]["state"]["kind"] == "none"
