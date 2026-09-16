"""The apprentice's stats derive from the wizard's *base* line (2e p.27), so a
grave mutation or permanent injury the wizard suffered must not propagate down
to her — while her own mutations and injuries must survive sync_apprentice()'s
wholesale rebuild of ap["stats"]."""
import warband_store


def _ap(fresh_warband):
    warband_store.hire_apprentice(fresh_warband, "Ap")
    warband_store.sync_apprentice(fresh_warband)
    return fresh_warband["apprentice"]


def test_wizard_injury_does_not_reach_apprentice(fresh_warband):
    before = dict(_ap(fresh_warband)["stats"])
    ok, msg = warband_store.add_wizard_permanent_injury(fresh_warband, "smashed_leg")
    assert ok, msg
    assert fresh_warband["wizard"]["stats"]["move"] == 4
    warband_store.sync_apprentice(fresh_warband)
    assert fresh_warband["apprentice"]["stats"] == before


def test_wizard_mutation_does_not_reach_apprentice(fresh_warband):
    fresh_warband["homerules"]["source_books"] = list(
        set(fresh_warband["homerules"].get("source_books") or []) | {"Grave Mutations"}
    )
    before = dict(_ap(fresh_warband)["stats"])
    wiz_will = fresh_warband["wizard"]["stats"]["will"]
    ok, msg = warband_store.add_wizard_mutation(fresh_warband, 1)
    assert ok, msg
    warband_store.sync_apprentice(fresh_warband)
    if fresh_warband["wizard"]["stats"]["will"] != wiz_will:
        assert fresh_warband["apprentice"]["stats"] == before


def test_apprentice_own_injury_survives_resync(fresh_warband):
    ap = _ap(fresh_warband)
    before_move = ap["stats"]["move"]
    ok, msg = warband_store.add_apprentice_permanent_injury(fresh_warband, "smashed_leg")
    assert ok, msg
    warband_store.sync_apprentice(fresh_warband)
    assert fresh_warband["apprentice"]["stats"]["move"] == before_move - 2


def test_wizard_level_up_still_reaches_apprentice(fresh_warband):
    _ap(fresh_warband)
    warband_store.add_wizard_permanent_injury(fresh_warband, "smashed_leg")
    fresh_warband["wizard"]["stats"]["will"] += 1
    warband_store.sync_apprentice(fresh_warband)
    assert (
        fresh_warband["apprentice"]["stats"]["will"]
        == fresh_warband["wizard"]["stats"]["will"] - 2
    )
