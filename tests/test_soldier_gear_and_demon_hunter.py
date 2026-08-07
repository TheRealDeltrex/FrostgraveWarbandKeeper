"""Blood Legacy/Wildwoods gear-text corrections, the Guide/Expert Guide split,
Forgotten Pacts' variable Demon Hunter cost, and the Free Dagger homerule."""

import expansions
import warband_store
from frostgrave_data import get_soldier

# --- Blood Legacy / Wildwoods gear text --------------------------------------


def test_blood_legacy_soldier_gear_matches_the_book():
    assert get_soldier("blood_merchant")["gear"] == "Hand weapon, Vial of Blood"
    assert get_soldier("swordmaster")["gear"] == "Hand weapon, dagger, light armour"
    assert get_soldier("vampire_hunter")["gear"] == "Hand weapon, crossbow, quiver, light armour"


def test_guide_split_into_guide_and_expert_guide():
    guide = get_soldier("guide")
    assert guide["cost"] == 75
    assert guide["category"] == "standard"
    assert guide["gear"] == "Staff, dagger, light armour"
    assert guide["shoot"] == 0

    expert = get_soldier("expert_guide")
    assert expert["cost"] == 125
    assert expert["category"] == "specialist"
    assert expert["gear"] == "Staff, bow, quiver, dagger, light armour"
    assert expert["shoot"] == 2
    assert "Expert Guide" not in guide["notes"]
    assert "Expert Guide" not in guide["description"]


def test_trophy_hunter_gear_matches_the_book():
    assert get_soldier("trophy_hunter")["gear"] == "Hand weapon, bow, quiver, dagger, light armour"


def test_expert_guide_is_wildwoods_supply_exempt():
    assert "expert_guide" in warband_store.WILDWOODS_SUPPLY_EXEMPT_TYPE_KEYS


# --- Forgotten Pacts: variable Demon Hunter cost -----------------------------


def _demon_hunter_info():
    return get_soldier("demon_hunter")


def test_demon_hunter_base_cost_with_edition2_off(fresh_warband):
    wb = fresh_warband
    wb["homerules"]["edition2_soldier_costs"] = False
    assert expansions.soldier_cost(wb, _demon_hunter_info(), "demon_hunter") == 100


def test_demon_hunter_base_cost_with_edition2_on(fresh_warband):
    wb = fresh_warband
    wb["homerules"]["edition2_soldier_costs"] = True
    assert expansions.soldier_cost(wb, _demon_hunter_info(), "demon_hunter") == 125


def test_demon_hunter_surcharge_for_known_spell(fresh_warband):
    wb = fresh_warband
    wb["homerules"]["edition2_soldier_costs"] = False
    wb["wizard"]["spells"] = [{"name": "Possess", "school": "Summoner"}]
    assert expansions.soldier_cost(wb, _demon_hunter_info(), "demon_hunter") == 125


def test_demon_hunter_surcharge_for_summoner_school(fresh_warband):
    wb = fresh_warband
    wb["homerules"]["edition2_soldier_costs"] = False
    wb["wizard"]["school"] = "Summoner"
    assert expansions.soldier_cost(wb, _demon_hunter_info(), "demon_hunter") == 125


def test_demon_hunter_surcharge_for_summoning_circle(fresh_warband):
    wb = fresh_warband
    wb["homerules"]["edition2_soldier_costs"] = False
    wb["base"]["resources"] = ["summoning_circle"]
    assert expansions.soldier_cost(wb, _demon_hunter_info(), "demon_hunter") == 150


def test_demon_hunter_surcharges_stack_on_top_of_edition2_base(fresh_warband):
    wb = fresh_warband
    wb["homerules"]["edition2_soldier_costs"] = True
    wb["wizard"]["school"] = "Summoner"
    wb["wizard"]["spells"] = [{"name": "Summon Demon", "school": "Summoner"}]
    wb["base"]["resources"] = ["summoning_circle"]
    # 125 (edition2 base) + 25 (spell) + 25 (Summoner) + 50 (circle)
    assert expansions.soldier_cost(wb, _demon_hunter_info(), "demon_hunter") == 225


def test_other_soldier_costs_unaffected_by_demon_hunter_logic(fresh_warband):
    wb = fresh_warband
    wb["wizard"]["school"] = "Summoner"
    wb["wizard"]["spells"] = [{"name": "Summon Demon", "school": "Summoner"}]
    assert expansions.soldier_cost(wb, get_soldier("thug"), "thug") == 0
    assert expansions.soldier_cost(wb, get_soldier("archer"), "archer") == 75


# --- Free Dagger homerule -----------------------------------------------------


def test_free_dagger_disabled_leaves_gear_untouched(fresh_warband):
    wb = fresh_warband
    wb["homerules"]["free_dagger_enabled"] = False
    assert expansions.free_dagger_gear(wb, "thug", "Hand weapon") == "Hand weapon"


def test_free_dagger_adds_dagger_to_a_lone_hand_weapon(fresh_warband):
    wb = fresh_warband
    wb["homerules"]["free_dagger_enabled"] = True
    assert expansions.free_dagger_gear(wb, "thug", "Hand weapon") == "Hand weapon, dagger"


def test_free_dagger_upgrades_a_lone_dagger_to_two(fresh_warband):
    wb = fresh_warband
    wb["homerules"]["free_dagger_enabled"] = True
    assert expansions.free_dagger_gear(wb, "thief", "Dagger") == "2 daggers"


def test_free_dagger_skips_hand_weapon_and_dagger(fresh_warband):
    wb = fresh_warband
    wb["homerules"]["free_dagger_enabled"] = True
    gear = "Hand weapon, dagger, shield, heavy armour"
    assert expansions.free_dagger_gear(wb, "knight", gear) == gear


def test_free_dagger_skips_two_daggers(fresh_warband):
    wb = fresh_warband
    wb["homerules"]["free_dagger_enabled"] = True
    assert expansions.free_dagger_gear(wb, "trap_expert", "Two daggers, light armour") == (
        "Two daggers, light armour"
    )


def test_free_dagger_adds_to_two_hand_weapons(fresh_warband):
    # Two hand weapons isn't a dagger substitute, unlike a hand weapon + dagger
    # or two daggers — this soldier still gets the backup dagger added.
    wb = fresh_warband
    wb["homerules"]["free_dagger_enabled"] = True
    assert expansions.free_dagger_gear(wb, "tunnel_fighter", "Two hand weapons, leather armour") == (
        "Two hand weapons, leather armour, dagger"
    )


def test_free_dagger_skips_animals_constructs_and_demons(fresh_warband):
    wb = fresh_warband
    wb["homerules"]["free_dagger_enabled"] = True
    assert expansions.free_dagger_gear(wb, "war_hound", "—") == "—"
    assert expansions.free_dagger_gear(wb, "companion_wolf", "Unarmed") == "Unarmed"
    assert expansions.free_dagger_gear(wb, "small_construct", "Unarmed") == "Unarmed"


def test_free_dagger_applies_through_enrich_soldier(fresh_warband):
    wb = fresh_warband
    wb["homerules"]["free_dagger_enabled"] = True
    ok, msg = warband_store.add_soldier(wb, "thug", "Grim")
    assert ok, msg
    soldier = wb["soldiers"][0]
    enriched = warband_store.enrich_soldier(wb, soldier)
    assert enriched["gear"] == "Hand weapon, dagger"
    # Purely descriptive — never touches the real item_slots list.
    assert enriched["item_slots"] == [""]
