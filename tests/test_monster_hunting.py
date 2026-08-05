"""Spellcaster Magazine Issue 5's Monster Hunting: For Fun and Profit — a
per-game kill log (record_monster_kill/claim_monster_prize) that settles
into XP/gold via apply_monster_hunting_results, plus a spell/potion
component inventory on the wizard/apprentice (expansions.component_capacity)."""

import expansions
import warband_store
from frostgrave_data import (
    MONSTER_HUNTER_COMPONENTS_PER_KILL,
    MONSTER_HUNTER_PRIZE_BONUS,
    SPELL_COMPONENT_BAG_COST,
    SPELL_COMPONENT_BAG_LIMIT,
)


def _enable(wb: dict) -> None:
    wb["homerules"]["enabled_sources"]["Spellcaster Magazine"] = True
    wb["homerules"]["monster_hunting_enabled"] = True


def test_gate_requires_book_and_homerule(fresh_warband):
    wb = fresh_warband
    # Neither on.
    wb["homerules"]["enabled_sources"]["Spellcaster Magazine"] = False
    wb["homerules"]["monster_hunting_enabled"] = False
    ok, msg = warband_store.record_monster_kill(wb, "Boar")
    assert not ok
    assert "spellcaster magazine" in msg.lower()

    # Book on, homerule still off.
    wb["homerules"]["enabled_sources"]["Spellcaster Magazine"] = True
    ok, msg = warband_store.record_monster_kill(wb, "Boar")
    assert not ok
    assert "homerule" in msg.lower()

    # Both on.
    wb["homerules"]["monster_hunting_enabled"] = True
    ok, msg = warband_store.record_monster_kill(wb, "Boar")
    assert ok, msg


def test_record_kill_rejects_unknown_monster(fresh_warband):
    wb = fresh_warband
    _enable(wb)
    ok, msg = warband_store.record_monster_kill(wb, "Not A Real Monster")
    assert not ok
    assert "unknown monster" in msg.lower()


def test_settle_up_banks_total_xp_and_gold_and_clears_log(fresh_warband):
    wb = fresh_warband
    _enable(wb)
    before_gold, before_xp = wb["gold"], wb["wizard"]["xp"]

    ok, msg = warband_store.record_monster_kill(wb, "Boar")  # 3 XP, Boar tusk -> 10gc
    assert ok, msg
    kill1 = wb["monster_hunting"]["kills"][-1]["id"]
    ok, msg = warband_store.record_monster_kill(wb, "Wraith")  # 8 XP, Wraith dust -> component
    assert ok, msg

    ok, msg = warband_store.claim_monster_prize(wb, kill1, "sell")
    assert ok, msg
    assert wb["monster_hunting"]["prizes"][-1]["gold"] == 10

    ok, msg = warband_store.apply_monster_hunting_results(wb)
    assert ok, msg
    # 3 + 8 = 11 XP, 10gc — the Wraith kill's prize was never claimed, so its
    # XP still banks (XP is per-kill; only the prize needs claiming) but its
    # gold doesn't exist to add.
    assert wb["wizard"]["xp"] == before_xp + 11
    assert wb["gold"] == before_gold + 10
    assert wb["monster_hunting"]["kills"] == []
    assert wb["monster_hunting"]["prizes"] == []


def test_apply_with_nothing_pending_is_a_no_op_error(fresh_warband):
    wb = fresh_warband
    _enable(wb)
    ok, msg = warband_store.apply_monster_hunting_results(wb)
    assert not ok


def test_claim_gold_prize_twice_is_rejected(fresh_warband):
    wb = fresh_warband
    _enable(wb)
    warband_store.record_monster_kill(wb, "Boar")
    kill_id = wb["monster_hunting"]["kills"][-1]["id"]
    ok, msg = warband_store.claim_monster_prize(wb, kill_id, "sell")
    assert ok, msg
    ok, msg = warband_store.claim_monster_prize(wb, kill_id, "sell")
    assert not ok
    assert "already been claimed" in msg.lower()


def test_component_prize_goes_onto_the_chosen_figure(fresh_warband):
    wb = fresh_warband
    _enable(wb)
    warband_store.record_monster_kill(wb, "Wraith")  # Wraith dust -> +1 Control Undead
    kill_id = wb["monster_hunting"]["kills"][-1]["id"]
    ok, msg = warband_store.claim_monster_prize(wb, kill_id, "wizard")
    assert ok, msg
    comps = wb["wizard"]["components"]
    assert len(comps) == 1
    assert comps[0]["name"] == "Wraith dust"
    assert comps[0]["target"] == "Control Undead"
    assert comps[0]["known"] is True


def test_gold_prize_ignores_holder_and_always_sells(fresh_warband):
    # A gc-value prize has nowhere else to go, so "wizard"/"apprentice" behave
    # the same as "sell" for a gold-kind prize — see claim_monster_prize's
    # docstring.
    wb = fresh_warband
    _enable(wb)
    warband_store.record_monster_kill(wb, "Boar")
    kill_id = wb["monster_hunting"]["kills"][-1]["id"]
    ok, msg = warband_store.claim_monster_prize(wb, kill_id, "wizard")
    assert ok, msg
    assert wb["monster_hunting"]["prizes"][-1]["gold"] == 10
    assert not wb["wizard"].get("components")


def test_component_prize_cannot_be_sold(fresh_warband):
    wb = fresh_warband
    _enable(wb)
    warband_store.record_monster_kill(wb, "Wraith")
    kill_id = wb["monster_hunting"]["kills"][-1]["id"]
    ok, msg = warband_store.claim_monster_prize(wb, kill_id, "sell")
    assert not ok


def test_pouch_caps_at_three_and_bag_raises_it_to_thirteen(fresh_warband):
    wb = fresh_warband
    _enable(wb)
    assert expansions.component_capacity(wb, wb["wizard"]) == 3
    for _ in range(3):
        warband_store.record_monster_kill(wb, "Wraith")
        kill_id = [k for k in wb["monster_hunting"]["kills"] if not k["claimed"]][-1]["id"]
        ok, msg = warband_store.claim_monster_prize(wb, kill_id, "wizard")
        assert ok, msg
    assert len(wb["wizard"]["components"]) == 3

    warband_store.record_monster_kill(wb, "Wraith")
    kill_id = [k for k in wb["monster_hunting"]["kills"] if not k["claimed"]][-1]["id"]
    ok, msg = warband_store.claim_monster_prize(wb, kill_id, "wizard")
    assert not ok
    assert "can't hold" in msg.lower()

    ok, msg = warband_store.buy_component_bag(wb)
    assert ok, msg
    ok, msg = warband_store.assign_component_bag(wb, "wizard", 1)
    assert ok, msg
    assert expansions.component_capacity(wb, wb["wizard"]) == 13
    ok, msg = warband_store.claim_monster_prize(wb, kill_id, "wizard")
    assert ok, msg
    assert len(wb["wizard"]["components"]) == 4


def test_use_and_discard_component(fresh_warband):
    wb = fresh_warband
    _enable(wb)
    warband_store.record_monster_kill(wb, "Wraith")
    kill_id = wb["monster_hunting"]["kills"][-1]["id"]
    warband_store.claim_monster_prize(wb, kill_id, "wizard")
    comp_id = wb["wizard"]["components"][0]["id"]

    ok, msg = warband_store.use_component(wb, "wizard", comp_id)
    assert ok, msg
    assert wb["wizard"]["components"] == []

    warband_store.record_monster_kill(wb, "Wraith")
    kill_id2 = wb["monster_hunting"]["kills"][-1]["id"]
    warband_store.claim_monster_prize(wb, kill_id2, "wizard")
    comp_id2 = wb["wizard"]["components"][0]["id"]
    ok, msg = warband_store.discard_component(wb, "wizard", comp_id2)
    assert ok, msg
    assert wb["wizard"]["components"] == []


def test_monster_hunter_doubles_components_and_adds_gold_bonus(fresh_warband):
    wb = fresh_warband
    _enable(wb)
    wb["homerules"]["spellcaster_magazine_soldiers"] = True
    ok, msg = warband_store.add_soldier(wb, "monster_hunter", "Hunter")
    assert ok, msg
    assert expansions.monster_hunter_active(wb)

    warband_store.record_monster_kill(wb, "Boar")
    kill_id = wb["monster_hunting"]["kills"][-1]["id"]
    ok, msg = warband_store.claim_monster_prize(wb, kill_id, "sell")
    assert ok, msg
    assert wb["monster_hunting"]["prizes"][-1]["gold"] == 10 + MONSTER_HUNTER_PRIZE_BONUS

    warband_store.record_monster_kill(wb, "Wraith")
    kill_id2 = wb["monster_hunting"]["kills"][-1]["id"]
    ok, msg = warband_store.claim_monster_prize(wb, kill_id2, "wizard")
    assert ok, msg
    assert len(wb["wizard"]["components"]) == MONSTER_HUNTER_COMPONENTS_PER_KILL


def test_potion_master_doubles_brew_potion_bonus(fresh_warband):
    wb = fresh_warband
    _enable(wb)
    assert expansions.brew_potion_component_bonus(wb) == (1, 25)
    wb["homerules"]["spellcaster_magazine_soldiers"] = True
    warband_store.add_soldier(wb, "potion_master", "Master")
    assert expansions.potion_master_active(wb)
    assert expansions.brew_potion_component_bonus(wb) == (2, 50)


def test_remove_monster_kill(fresh_warband):
    wb = fresh_warband
    _enable(wb)
    warband_store.record_monster_kill(wb, "Boar")
    kill_id = wb["monster_hunting"]["kills"][-1]["id"]
    ok, msg = warband_store.remove_monster_kill(wb, kill_id)
    assert ok, msg
    assert wb["monster_hunting"]["kills"] == []


def test_no_loot_kill_gives_xp_but_no_prize(fresh_warband):
    wb = fresh_warband
    _enable(wb)
    ok, msg = warband_store.record_monster_kill(wb, "Wraith", mode="no_loot")
    assert ok, msg
    kill = wb["monster_hunting"]["kills"][-1]
    assert kill["xp"] == 8
    assert kill["prize"]["kind"] == "none"
    assert not kill["claimed"]


def test_loot_only_kill_gives_prize_but_no_xp(fresh_warband):
    wb = fresh_warband
    _enable(wb)
    ok, msg = warband_store.record_monster_kill(wb, "Wraith", mode="loot_only")
    assert ok, msg
    kill = wb["monster_hunting"]["kills"][-1]
    assert kill["xp"] == 0
    assert kill["prize"]["kind"] == "spell"
    kill_id = kill["id"]
    ok, msg = warband_store.claim_monster_prize(wb, kill_id, "wizard")
    assert ok, msg
    assert len(wb["wizard"]["components"]) == 1


def test_record_monster_kill_rejects_unknown_mode(fresh_warband):
    wb = fresh_warband
    _enable(wb)
    ok, msg = warband_store.record_monster_kill(wb, "Boar", mode="bogus")
    assert not ok


def test_buy_component_bag_costs_gold_and_caps_at_the_limit(fresh_warband):
    wb = fresh_warband
    _enable(wb)
    before_gold = wb["gold"]
    ok, msg = warband_store.buy_component_bag(wb)
    assert ok, msg
    assert wb["gold"] == before_gold - SPELL_COMPONENT_BAG_COST
    assert wb["monster_hunting"]["bags_bought"] == 1

    for _ in range(SPELL_COMPONENT_BAG_LIMIT - 1):
        ok, msg = warband_store.buy_component_bag(wb)
        assert ok, msg
    assert wb["monster_hunting"]["bags_bought"] == SPELL_COMPONENT_BAG_LIMIT

    ok, msg = warband_store.buy_component_bag(wb)
    assert not ok
    assert "maximum" in msg.lower()


def test_assign_component_bag_shares_the_bought_pool(fresh_warband):
    wb = fresh_warband
    _enable(wb)
    wb["apprentice"] = warband_store.empty_wizard("Ap")
    warband_store.buy_component_bag(wb)

    ok, msg = warband_store.assign_component_bag(wb, "wizard", 1)
    assert ok, msg
    assert wb["wizard"]["component_bags_held"] == 1
    assert expansions.component_capacity(wb, wb["wizard"]) == 13

    # No spare bags left for the apprentice.
    ok, msg = warband_store.assign_component_bag(wb, "apprentice", 1)
    assert not ok
    assert "spare" in msg.lower()

    ok, msg = warband_store.assign_component_bag(wb, "wizard", -1)
    assert ok, msg
    assert wb["wizard"]["component_bags_held"] == 0
    ok, msg = warband_store.assign_component_bag(wb, "apprentice", 1)
    assert ok, msg
    assert wb["apprentice"]["component_bags_held"] == 1


def test_cannot_unassign_a_bag_that_would_overflow_held_components(fresh_warband):
    wb = fresh_warband
    _enable(wb)
    warband_store.buy_component_bag(wb)
    warband_store.assign_component_bag(wb, "wizard", 1)
    for _ in range(5):
        warband_store.record_monster_kill(wb, "Wraith")
        kill_id = [k for k in wb["monster_hunting"]["kills"] if not k["claimed"]][-1]["id"]
        ok, msg = warband_store.claim_monster_prize(wb, kill_id, "wizard")
        assert ok, msg
    assert len(wb["wizard"]["components"]) == 5

    ok, msg = warband_store.assign_component_bag(wb, "wizard", -1)
    assert not ok
    assert "too many components" in msg.lower()
