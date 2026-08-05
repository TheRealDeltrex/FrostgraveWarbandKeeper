"""A soldier's Armour/Move should reflect a Shield/Armour item sitting in
their item slot, the same way it already does for the captain
(warband_store.captain_effective_stats) — see enrich_soldier()."""

import warband_store


def test_soldier_with_shield_gets_armour_bonus(fresh_warband):
    wb = fresh_warband
    ok, msg = warband_store.add_soldier(wb, "thug", "Grim")
    assert ok, msg
    soldier = wb["soldiers"][0]
    base_armour = warband_store.enrich_soldier(wb, soldier)["armour"]

    soldier["item_slots"] = ["Shield"]
    enriched = warband_store.enrich_soldier(wb, soldier)
    assert enriched["armour"] == base_armour + 1
    assert enriched["move"] == warband_store.enrich_soldier(wb, {**soldier, "item_slots": [""]})["move"]


def test_soldier_with_heavy_armour_gets_armour_and_move_penalty(fresh_warband):
    wb = fresh_warband
    ok, msg = warband_store.add_soldier(wb, "thug", "Bram")
    assert ok, msg
    soldier = wb["soldiers"][0]
    unequipped = warband_store.enrich_soldier(wb, soldier)

    soldier["item_slots"] = ["Heavy Armour"]
    enriched = warband_store.enrich_soldier(wb, soldier)
    assert enriched["armour"] == unequipped["armour"] + 2
    assert enriched["move"] == unequipped["move"] - 1


def test_soldier_with_no_matching_item_is_unaffected(fresh_warband):
    wb = fresh_warband
    ok, msg = warband_store.add_soldier(wb, "thug", "Fenn")
    assert ok, msg
    soldier = wb["soldiers"][0]
    unequipped = warband_store.enrich_soldier(wb, soldier)

    soldier["item_slots"] = ["Hand Weapon"]
    enriched = warband_store.enrich_soldier(wb, soldier)
    assert enriched["armour"] == unequipped["armour"]
    assert enriched["move"] == unequipped["move"]
