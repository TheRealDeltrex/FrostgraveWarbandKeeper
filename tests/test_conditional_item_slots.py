"""soldier_item_slots() and its supporting eligibility/restriction helpers for
the creature_item_slot_enabled homerule (companions/constructs) and the Crow
Master's Sickle-of-the-Crowmaster exception — see expansions.py and
game_content.MAGIC_ITEM_RESTRICTIONS."""

import expansions
import game_content


def test_companion_has_no_slot_by_default():
    wb = {"homerules": {}}
    assert expansions.soldier_item_slots(wb, "companion_bear", []) == 0


def test_companion_gets_one_slot_under_homerule():
    wb = {"homerules": {"creature_item_slot_enabled": True}}
    assert expansions.soldier_item_slots(wb, "companion_bear", []) == 1


def test_companion_slot_ignores_vault_contents_when_homerule_off():
    wb = {"homerules": {}, "vault_items": [{"name": "Bear Armour"}]}
    assert expansions.soldier_item_slots(wb, "companion_bear", []) == 0


def test_crow_master_has_no_slot_with_empty_vault():
    wb = {"vault_items": []}
    assert expansions.soldier_item_slots(wb, "crow_master", []) == 0


def test_crow_master_gets_slot_once_sickle_is_owned():
    wb = {"vault_items": [{"name": "Sickle of the Crowmaster"}]}
    assert expansions.soldier_item_slots(wb, "crow_master", []) == 1


def test_crow_master_keeps_slot_while_carrying_sickle_even_if_vault_empties():
    wb = {"vault_items": []}
    assert expansions.soldier_item_slots(wb, "crow_master", ["Sickle of the Crowmaster"]) == 1


def test_crow_master_ignores_the_creature_homerule():
    wb = {"homerules": {"creature_item_slot_enabled": True}, "vault_items": []}
    assert expansions.soldier_item_slots(wb, "crow_master", []) == 0


def test_item_eligible_for_role_unrestricted_item_passes_everyone():
    assert expansions.item_eligible_for_role("Hand Weapon", "tracker") is True
    assert expansions.item_eligible_for_role("Hand Weapon", "companion_bear") is True


def test_item_eligible_for_role_respects_restriction():
    assert expansions.item_eligible_for_role("Bear Armour", "companion_bear") is True
    assert expansions.item_eligible_for_role("Bear Armour", "tracker") is False


def test_item_restricted_for_type_key_is_narrower_than_eligible():
    # An unrestricted item is eligible everywhere but "restricted for" nowhere.
    assert expansions.item_eligible_for_role("Hand Weapon", "companion_bear") is True
    assert expansions.item_restricted_for_type_key("Hand Weapon", "companion_bear") is False


def test_equipment_bonuses_applies_magic_item_restriction_bonus():
    bonus = game_content.equipment_bonuses(["Bear Armour"])
    assert bonus["armour"] == 2
    assert bonus["move"] == -1
    assert bonus["fight"] == 0


def test_equipment_bonuses_sums_fight_shoot_will_from_iron_collar():
    bonus = game_content.equipment_bonuses(["Iron Collar"])
    assert bonus["armour"] == 2
    assert bonus["fight"] == 2
    assert bonus["will"] == 1
