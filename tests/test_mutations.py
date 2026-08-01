"""G1: apprentice mutations must survive save_warband(). G2: promoting a
mutated soldier must carry both stat deltas and the mutation record."""

import warband_store

# Mutation #1, "Crystalline Body": Armour +2, Health halved (round up) —
# the exact repro used in IMPROVEMENTS.md G1/G2.
CRYSTALLINE_BODY = 1


def test_apprentice_mutation_survives_save(fresh_warband):
    wb = fresh_warband
    ok, msg = warband_store.hire_apprentice(wb)
    assert ok, msg

    before = dict(wb["apprentice"]["stats"])
    ok, msg = warband_store.add_apprentice_mutation(wb, CRYSTALLINE_BODY)
    assert ok, msg
    after_add = dict(wb["apprentice"]["stats"])
    assert after_add["armour"] == before["armour"] + 2
    assert after_add["health"] < before["health"]

    warband_store.save_warband(wb)
    assert wb["apprentice"]["stats"] == after_add, "mutation was reverted by sync_apprentice on save"

    ok, msg = warband_store.remove_apprentice_mutation(wb, 0)
    assert ok, msg
    warband_store.save_warband(wb)
    assert wb["apprentice"]["stats"] == before


def test_promote_carries_mutations(fresh_warband):
    wb = fresh_warband
    wb["homerules"]["captain_mode"] = "promote"
    ok, msg = warband_store.add_soldier(wb, "archer", "Wren")
    assert ok, msg
    soldier = wb["soldiers"][0]

    ok, msg = warband_store.add_soldier_mutation(wb, soldier["id"], CRYSTALLINE_BODY)
    assert ok, msg
    mutated_armour = soldier["armour"]
    mutated_health = soldier["health"]

    ok, msg = warband_store.promote_soldier_to_captain(
        wb, soldier["id"], tricks=["furious_attack", "riposte"]
    )
    assert ok, msg
    cap = wb["captain"]
    # Armour isn't touched by the promotion bonus package (only fight/shoot/will/
    # health are), so it must carry over from the mutation exactly.
    assert cap["stats"]["armour"] == mutated_armour
    # Health additionally gets the promotion bonus package on top, so it can only
    # have gone up from the mutated value, never been reset to the catalog's.
    assert cap["stats"]["health"] >= mutated_health
    assert cap["mutations"], "mutation records were dropped on promotion"
