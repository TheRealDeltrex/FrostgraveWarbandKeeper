"""Core Rules Permanent Injury Table (Chapter Three, page 77): applying and
removing a permanent injury on the wizard/apprentice/captain/soldier."""

import warband_store
from frostgrave_data import PERMANENT_INJURIES, PERMANENT_INJURY_BY_ID


def test_every_injury_has_a_max_stacks_of_two():
    """The rulebook caps every entry at twice before a further result must be
    re-rolled — a widened cap would silently let a stat spiral unbounded."""
    for inj in PERMANENT_INJURIES:
        assert inj["max_stacks"] == 2


def test_add_and_remove_stat_affecting_injury(fresh_warband):
    wb = fresh_warband
    before = wb["wizard"]["stats"]["fight"]

    ok, msg = warband_store.add_wizard_permanent_injury(wb, "crushed_arm")
    assert ok, msg
    assert wb["wizard"]["stats"]["fight"] == before - 1
    assert wb["wizard"]["permanent_injuries"][0]["name"] == "Crushed Arm"

    ok, msg = warband_store.remove_wizard_permanent_injury(wb, 0)
    assert ok, msg
    assert wb["wizard"]["stats"]["fight"] == before
    assert wb["wizard"]["permanent_injuries"] == []


def test_second_occurrence_stacks_the_penalty(fresh_warband):
    wb = fresh_warband
    before = wb["wizard"]["stats"]["move"]

    ok, msg = warband_store.add_wizard_permanent_injury(wb, "lost_toes")
    assert ok, msg
    ok, msg = warband_store.add_wizard_permanent_injury(wb, "lost_toes")
    assert ok, msg
    assert wb["wizard"]["stats"]["move"] == before - 2
    assert len(wb["wizard"]["permanent_injuries"]) == 2


def test_third_occurrence_is_rejected(fresh_warband):
    wb = fresh_warband
    warband_store.add_wizard_permanent_injury(wb, "lost_toes")
    warband_store.add_wizard_permanent_injury(wb, "lost_toes")
    ok, msg = warband_store.add_wizard_permanent_injury(wb, "lost_toes")
    assert not ok
    assert "re-rolled" in msg.lower()
    assert len(wb["wizard"]["permanent_injuries"]) == 2


def test_text_only_injury_touches_no_stat(fresh_warband):
    wb = fresh_warband
    wiz_stats_before = dict(wb["wizard"]["stats"])

    ok, msg = warband_store.add_wizard_permanent_injury(wb, "niggling_injury")
    assert ok, msg
    assert wb["wizard"]["stats"] == wiz_stats_before


def test_apprentice_permanent_injury(fresh_warband):
    wb = fresh_warband
    ok, msg = warband_store.hire_apprentice(wb)
    assert ok, msg
    before = wb["apprentice"]["stats"]["will"]  # apprentice Will starts at 2 (has headroom to drop)

    ok, msg = warband_store.add_apprentice_permanent_injury(wb, "psychological_scars")
    assert ok, msg
    assert wb["apprentice"]["stats"]["will"] == before - 1

    ok, msg = warband_store.remove_apprentice_permanent_injury(wb, 0)
    assert ok, msg
    assert wb["apprentice"]["stats"]["will"] == before


def test_captain_permanent_injury(fresh_warband):
    wb = fresh_warband
    wb["homerules"]["captain_mode"] = "hire"
    ok, msg = warband_store.hire_captain(wb, "Cap", tricks=["furious_attack", "riposte"])
    assert ok, msg
    before = wb["captain"]["stats"]["will"]

    ok, msg = warband_store.add_captain_permanent_injury(wb, "psychological_scars")
    assert ok, msg
    assert wb["captain"]["stats"]["will"] == before - 1


def test_soldier_permanent_injury_blocked_by_default(fresh_warband):
    """Ordinary soldiers use a different Survival Roll (die/dismiss) than the
    wizard/apprentice/captain's — off by default; a group must opt in."""
    wb = fresh_warband
    ok, msg = warband_store.add_soldier(wb, "thug", "Grunt")
    assert ok, msg
    soldier = wb["soldiers"][0]

    ok, msg = warband_store.add_soldier_permanent_injury(wb, soldier["id"], "never_quite_as_strong")
    assert not ok
    assert soldier["permanent_injuries"] == []


def test_soldier_permanent_injury_when_homerule_enabled(fresh_warband):
    wb = fresh_warband
    wb["homerules"]["soldier_permanent_injuries_enabled"] = True
    ok, msg = warband_store.add_soldier(wb, "thug", "Grunt")
    assert ok, msg
    soldier = wb["soldiers"][0]
    before = soldier["health"]

    ok, msg = warband_store.add_soldier_permanent_injury(wb, soldier["id"], "never_quite_as_strong")
    assert ok, msg
    assert soldier["health"] == before - 1

    ok, msg = warband_store.remove_soldier_permanent_injury(wb, soldier["id"], 0)
    assert ok, msg
    assert soldier["health"] == before


def test_unknown_injury_id_rejected(fresh_warband):
    wb = fresh_warband
    ok, msg = warband_store.add_wizard_permanent_injury(wb, "not_a_real_injury")
    assert not ok


def test_all_catalog_ids_resolve():
    for inj in PERMANENT_INJURIES:
        assert PERMANENT_INJURY_BY_ID[inj["id"]] is inj
