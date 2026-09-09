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


def test_mind_lock_ring_is_excluded_from_undead_and_demons():
    """The Maze of Malcor p.95: the ring "cannot be worn by undead or demons".
    An exclusion, not a whitelist — everyone else keeps it."""
    assert expansions.item_eligible_for_role("Mind Lock Ring", "wizard") is True
    assert expansions.item_eligible_for_role("Mind Lock Ring", "wizard:undead") is False
    assert expansions.item_eligible_for_role("Mind Lock Ring", "infantryman:undead") is False
    assert expansions.item_eligible_for_role("Mind Lock Ring", "minor_demon:demon") is False
    # A trait tag must not disturb anything else the picker filters on.
    assert expansions.item_eligible_for_role("Hand Weapon", "wizard:undead") is True
    assert expansions.item_eligible_for_role("Bear Armour", "companion_bear:undead") is True
    assert expansions.item_eligible_for_role("Bear Armour", "tracker:undead") is False


def test_figure_item_role_tags_the_states_that_carry_the_trait(fresh_warband):
    wb = fresh_warband
    assert expansions.figure_item_role(wb, "wizard") == "wizard"
    wb["wizard"]["state"] = {"kind": expansions.STATE_LICH, "tier": 1}
    assert expansions.figure_item_role(wb, "wizard") == "wizard:undead"
    # A Lich's apprentice is not itself undead.
    assert expansions.figure_item_role(wb, "apprentice", wb.get("apprentice")) == "apprentice"
    # A revenant is an ordinary soldier carrying a flag, not a type of its own.
    soldier = {"type_key": "infantryman", "revenant": True}
    assert expansions.figure_item_role(wb, "infantryman", soldier) == "infantryman:undead"
    assert expansions.figure_item_role(wb, "infantryman", {"type_key": "infantryman"}) == "infantryman"


def test_undead_wizard_is_not_offered_the_ring_but_keeps_one_already_worn(fresh_warband):
    """Acquisition is gated; possession persists — the slot's text input still
    carries an already-equipped ring once the picker stops offering it."""
    import re

    import app as app_module
    import warband_store

    wb = fresh_warband
    wb["vault_items"] = [{"id": "v1", "name": "Mind Lock Ring"}]
    warband_store.save_warband(wb)
    client = app_module.app.test_client()

    def slot_zero() -> str:
        html = client.get(
            f"/warband/{wb['id']}", headers={"Host": "127.0.0.1:5000"}
        ).get_data(as_text=True)
        start = html.index('data-prefix="wizard"')
        return html[start : html.index('name="wizard_slot_1"')]

    offered = re.compile(r'<option\s[^>]*value="Mind Lock Ring"', re.S)
    equipped = re.compile(r'<input\s[^>]*value="Mind Lock Ring"', re.S)

    assert offered.search(slot_zero()), "an ordinary wizard is offered the ring"

    wb["wizard"]["state"] = {"kind": expansions.STATE_LICH, "tier": 1}
    wb["wizard"]["item_slots"] = ["Mind Lock Ring"]
    warband_store.save_warband(wb)
    block = slot_zero()
    assert not offered.search(block), "a Lich must not be offered it"
    assert equipped.search(block), "one already worn must survive the render"
