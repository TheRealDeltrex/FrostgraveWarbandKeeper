"""Legendary Soldiers (Spellcaster Magazine, Issue 4): a rare troop category
limited by wizard level rather than freely hired. A warband may field 1, plus
one more per 10 full wizard levels, capped at 8 total, never more than one of
each type."""

import expansions
import warband_store


def _enable(wb: dict) -> None:
    wb["homerules"]["enabled_sources"]["Spellcaster Magazine"] = True
    wb["homerules"]["spellcaster_magazine_soldiers"] = True


def test_max_legendary_soldiers_scales_with_wizard_level_and_caps_at_8(fresh_warband):
    wb = fresh_warband
    assert expansions.max_legendary_soldiers(wb) == 1
    wb["wizard"]["level"] = 9
    assert expansions.max_legendary_soldiers(wb) == 1
    wb["wizard"]["level"] = 10
    assert expansions.max_legendary_soldiers(wb) == 2
    wb["wizard"]["level"] = 35
    assert expansions.max_legendary_soldiers(wb) == 4
    wb["wizard"]["level"] = 1000
    assert expansions.max_legendary_soldiers(wb) == 8


def test_a_level_0_wizard_may_field_only_one_legendary_soldier(fresh_warband):
    wb = fresh_warband
    _enable(wb)
    ok, msg = warband_store.add_soldier(wb, "dire_hound", "Fang")
    assert ok, msg
    ok, msg = warband_store.add_soldier(wb, "bookhound", "Tome")
    assert not ok
    assert "legendary soldier limit reached" in msg.lower()


def test_leveling_up_raises_the_legendary_cap(fresh_warband):
    wb = fresh_warband
    _enable(wb)
    wb["wizard"]["level"] = 10
    wb["gold"] = 1000
    ok, msg = warband_store.add_soldier(wb, "dire_hound", "Fang")
    assert ok, msg
    ok, msg = warband_store.add_soldier(wb, "bookhound", "Tome")
    assert ok, msg


def test_only_one_of_each_legendary_type_regardless_of_cap(fresh_warband):
    wb = fresh_warband
    _enable(wb)
    wb["wizard"]["level"] = 1000
    ok, msg = warband_store.add_soldier(wb, "dire_hound", "Fang")
    assert ok, msg
    ok, msg = warband_store.add_soldier(wb, "dire_hound", "Fang II")
    assert not ok
    assert "only one" in msg.lower()


def test_dropping_wizard_level_keeps_existing_legendary_soldiers(fresh_warband):
    wb = fresh_warband
    _enable(wb)
    wb["wizard"]["level"] = 10
    wb["gold"] = 1000
    ok, msg = warband_store.add_soldier(wb, "dire_hound", "Fang")
    assert ok, msg
    ok, msg = warband_store.add_soldier(wb, "bookhound", "Tome")
    assert ok, msg
    wb["wizard"]["level"] = 0
    assert warband_store.legendary_soldier_count(wb) == 2
    ok, msg = warband_store.add_soldier(wb, "whip_master", "Lash")
    assert not ok
    assert "legendary soldier limit reached" in msg.lower()
