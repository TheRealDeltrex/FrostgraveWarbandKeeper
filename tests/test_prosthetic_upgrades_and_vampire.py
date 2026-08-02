"""Fireheart's Prosthetic Upgrade table (add-ons for an Animated-Prosthetic-
fitted injury) and Blood Legacy's "Becoming a Vampire" (an existing wizard
transformed mid-campaign, distinct from choosing Vampire at creation)."""

import warband_store
from frostgrave_data import PROSTHETIC_UPGRADE_BY_ID


# --- Fireheart: Prosthetic Upgrades ------------------------------------------


def test_add_upgrade_requires_a_fitted_prosthetic(fresh_warband):
    wb = fresh_warband
    warband_store.add_wizard_permanent_injury(wb, "crushed_arm")

    ok, msg = warband_store.add_wizard_prosthetic_upgrade(wb, 0, "fighting_claws")
    assert not ok
    assert "prosthetic" in msg.lower()


def test_add_upgrade_checks_required_injury(fresh_warband):
    wb = fresh_warband
    warband_store.add_wizard_permanent_injury(wb, "crushed_arm")
    warband_store.set_permanent_injury_prosthetic(wb, "wizard", 0, True)

    # Fighting Claws needs Lost Fingers, not Crushed Arm.
    ok, msg = warband_store.add_wizard_prosthetic_upgrade(wb, 0, "fighting_claws")
    assert not ok
    assert "lost fingers" in msg.lower()


def test_add_upgrade_takes_an_item_slot_and_records_it(fresh_warband):
    wb = fresh_warband
    warband_store.add_wizard_permanent_injury(wb, "lost_fingers")
    warband_store.set_permanent_injury_prosthetic(wb, "wizard", 0, True)
    free_slots_before = wb["wizard"]["item_slots"].count("")

    ok, msg = warband_store.add_wizard_prosthetic_upgrade(wb, 0, "fighting_claws")
    assert ok, msg
    assert wb["wizard"]["item_slots"].count("") == free_slots_before - 1
    assert "Fighting Claws" in "".join(wb["wizard"]["item_slots"])
    assert wb["wizard"]["permanent_injuries"][0]["upgrades"][0]["id"] == "fighting_claws"


def test_toe_ring_and_potion_reservoir_do_not_take_a_slot(fresh_warband):
    wb = fresh_warband
    warband_store.add_wizard_permanent_injury(wb, "lost_toes")
    warband_store.set_permanent_injury_prosthetic(wb, "wizard", 0, True)
    free_slots_before = wb["wizard"]["item_slots"].count("")

    ok, msg = warband_store.add_wizard_prosthetic_upgrade(wb, 0, "toe_ring")
    assert ok, msg
    assert wb["wizard"]["item_slots"].count("") == free_slots_before
    assert wb["wizard"]["permanent_injuries"][0]["upgrades"][0]["slot_index"] is None


def test_cannot_add_the_same_upgrade_twice(fresh_warband):
    # Two distinct injuries, both prosthetic-fitted, both eligible for the
    # "any" Gem of Power upgrade — but only one Gem of Power per entity.
    wb = fresh_warband
    warband_store.add_wizard_permanent_injury(wb, "lost_toes")
    warband_store.set_permanent_injury_prosthetic(wb, "wizard", 0, True)
    warband_store.add_wizard_permanent_injury(wb, "crushed_arm")
    warband_store.set_permanent_injury_prosthetic(wb, "wizard", 1, True)

    ok, msg = warband_store.add_wizard_prosthetic_upgrade(wb, 0, "gem_of_power")
    assert ok, msg
    ok, msg = warband_store.add_wizard_prosthetic_upgrade(wb, 1, "gem_of_power")
    assert not ok
    assert "already has" in msg.lower()


def test_remove_upgrade_frees_its_item_slot(fresh_warband):
    wb = fresh_warband
    warband_store.add_wizard_permanent_injury(wb, "lost_fingers")
    warband_store.set_permanent_injury_prosthetic(wb, "wizard", 0, True)
    warband_store.add_wizard_prosthetic_upgrade(wb, 0, "fighting_claws")
    free_slots_before = wb["wizard"]["item_slots"].count("")

    ok, msg = warband_store.remove_wizard_prosthetic_upgrade(wb, 0, 0)
    assert ok, msg
    assert wb["wizard"]["item_slots"].count("") == free_slots_before + 1
    assert wb["wizard"]["permanent_injuries"][0]["upgrades"] == []


def test_recurring_injury_destroys_its_upgrades(fresh_warband):
    wb = fresh_warband
    warband_store.add_wizard_permanent_injury(wb, "lost_fingers")
    warband_store.set_permanent_injury_prosthetic(wb, "wizard", 0, True)
    warband_store.add_wizard_prosthetic_upgrade(wb, 0, "fighting_claws")
    free_slots_before = wb["wizard"]["item_slots"].count("")

    ok, msg = warband_store.add_wizard_permanent_injury(wb, "lost_fingers")
    assert ok, msg
    assert "badly wounded" in msg.lower()
    assert "destroyed" in msg.lower()
    assert wb["wizard"]["permanent_injuries"][0]["upgrades"] == []
    assert wb["wizard"]["item_slots"].count("") == free_slots_before + 1


def test_add_upgrade_requires_fireheart(fresh_warband):
    wb = fresh_warband
    warband_store.add_wizard_permanent_injury(wb, "lost_toes")
    warband_store.set_permanent_injury_prosthetic(wb, "wizard", 0, True)
    wb["homerules"]["enabled_sources"]["Fireheart"] = False

    ok, msg = warband_store.add_wizard_prosthetic_upgrade(wb, 0, "toe_ring")
    assert not ok


def test_every_upgrade_requires_a_real_or_any_injury():
    from frostgrave_data import PERMANENT_INJURY_BY_ID

    for up in PROSTHETIC_UPGRADE_BY_ID.values():
        if up["requires"] == "any":
            continue
        for inj_id in up["requires"]:
            assert inj_id in PERMANENT_INJURY_BY_ID


# --- Blood Legacy: Becoming a Vampire ----------------------------------------


def test_become_vampire_requires_blood_legacy(fresh_warband):
    wb = fresh_warband
    wb["homerules"]["enabled_sources"]["Blood Legacy"] = False

    ok, msg = warband_store.become_vampire(wb)
    assert not ok
    assert "blood legacy" in msg.lower()


def test_become_vampire_switches_school_and_drops_thaumaturge_spells(fresh_warband):
    wb = fresh_warband
    assert any(s["school"] == "Thaumaturge" for s in wb["wizard"]["spells"])

    ok, msg = warband_store.become_vampire(wb)
    assert ok, msg
    assert wb["wizard"]["school"] == "Vampire"
    assert not any(s["school"] == "Thaumaturge" for s in wb["wizard"]["spells"])


def test_become_vampire_clamps_will_and_health_to_vampire_caps(fresh_warband):
    wb = fresh_warband
    wb["wizard"]["stats"]["will"] = 8
    wb["wizard"]["stats"]["health"] = 24

    ok, msg = warband_store.become_vampire(wb)
    assert ok, msg
    assert wb["wizard"]["stats"]["will"] == 5
    assert wb["wizard"]["stats"]["health"] == 22


def test_become_vampire_drops_apprentice_for_a_ninth_soldier_slot(fresh_warband):
    wb = fresh_warband
    warband_store.hire_apprentice(wb)
    assert wb["apprentice"]

    ok, msg = warband_store.become_vampire(wb)
    assert ok, msg
    assert wb["apprentice"] is None
    assert wb["homerules"]["max_soldiers"] >= 9


def test_become_vampire_twice_is_a_no_op(fresh_warband):
    wb = fresh_warband
    warband_store.become_vampire(wb)

    ok, msg = warband_store.become_vampire(wb)
    assert not ok
    assert "already" in msg.lower()


def test_fire_giant_cannot_become_vampire(fresh_warband):
    wb = fresh_warband
    wb["wizard"]["school"] = "Fire Giant"

    ok, msg = warband_store.become_vampire(wb)
    assert not ok
