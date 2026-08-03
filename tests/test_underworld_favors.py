"""Spellcaster Magazine Issue 3's Underworld Favours: a debt economy tracked
on the wizard (Markers), previously reference-only in the Lexicon."""

import warband_store
from frostgrave_data import UNDERWORLD_PAYOFF_COST


def test_underworld_favors_requires_spellcaster_magazine(fresh_warband):
    wb = fresh_warband
    wb["homerules"]["enabled_sources"]["Spellcaster Magazine"] = False
    ok, msg = warband_store.take_underworld_loan(wb, 100)
    assert not ok
    assert "spellcaster magazine" in msg.lower()


def test_take_loan_adds_gold_and_markers(fresh_warband):
    wb = fresh_warband
    before_gold = wb["gold"]
    ok, msg = warband_store.take_underworld_loan(wb, 300)
    assert ok, msg
    assert wb["gold"] == before_gold + 300
    assert wb["wizard"]["underworld_favors"]["markers"] == 3


def test_take_loan_rejects_bad_amounts(fresh_warband):
    wb = fresh_warband
    ok, msg = warband_store.take_underworld_loan(wb, 50)
    assert not ok
    ok, msg = warband_store.take_underworld_loan(wb, 1100)
    assert not ok
    ok, msg = warband_store.take_underworld_loan(wb, 150)
    assert not ok


def test_claim_free_favor_capped_by_wizard_level(fresh_warband):
    wb = fresh_warband
    ok, msg = warband_store.claim_free_underworld_favor(wb)
    assert not ok
    assert "level" in msg.lower()
    wb["wizard"]["level"] = 2
    ok, msg = warband_store.claim_free_underworld_favor(wb)
    assert ok, msg
    assert wb["wizard"]["underworld_favors"]["markers"] == 1
    ok, msg = warband_store.claim_free_underworld_favor(wb)
    assert ok, msg
    assert wb["wizard"]["underworld_favors"]["markers"] == 2
    ok, msg = warband_store.claim_free_underworld_favor(wb)
    assert not ok


def test_pay_off_marker_costs_gold(fresh_warband):
    wb = fresh_warband
    warband_store.take_underworld_loan(wb, 200)
    before_gold = wb["gold"]
    ok, msg = warband_store.pay_off_underworld_marker(wb)
    assert ok, msg
    assert wb["gold"] == before_gold - UNDERWORLD_PAYOFF_COST
    assert wb["wizard"]["underworld_favors"]["markers"] == 1


def test_pay_off_marker_requires_markers_and_gold(fresh_warband):
    wb = fresh_warband
    ok, msg = warband_store.pay_off_underworld_marker(wb)
    assert not ok
    assert "no markers" in msg.lower()
    warband_store.take_underworld_loan(wb, 100)
    wb["gold"] = 0
    ok, msg = warband_store.pay_off_underworld_marker(wb)
    assert not ok


def test_debt_call_requires_markers_held(fresh_warband):
    wb = fresh_warband
    ok, msg = warband_store.roll_underworld_debt_call(wb)
    assert not ok
    assert "no markers" in msg.lower()


def test_debt_call_resolves_and_never_raises(fresh_warband, monkeypatch):
    wb = fresh_warband
    warband_store.take_underworld_loan(wb, 1000)
    wb["gold"] = 5000
    for call_roll, outcome_roll, who_roll in [
        (20, 3, 1),
        (1, 9, 1),
        (1, 15, 1),
        (1, 20, 3),
        (1, 20, 15),
    ]:
        rolls = iter([call_roll, outcome_roll, who_roll])
        monkeypatch.setattr(warband_store.random, "randint", lambda a, b: next(rolls))
        warband_store.take_underworld_loan(wb, 100)
        ok, msg = warband_store.roll_underworld_debt_call(wb)
        assert ok, msg
        assert isinstance(msg, str) and msg


def test_debt_call_accepts_physical_dice_results(fresh_warband):
    wb = fresh_warband
    warband_store.take_underworld_loan(wb, 500)
    wb["gold"] = 5000
    before_markers = wb["wizard"]["underworld_favors"]["markers"]

    # No call this time: reported call roll above Markers held.
    ok, msg = warband_store.roll_underworld_debt_call(wb, call_roll=20)
    assert ok, msg
    assert "no call" in msg.lower()
    assert wb["wizard"]["underworld_favors"]["markers"] == before_markers

    # A reported table roll of 20 (19-20 band) with a reported who roll of 3 (wizard).
    ok, msg = warband_store.roll_underworld_debt_call(wb, call_roll=1, outcome_roll=20, who_roll=3)
    assert ok, msg
    assert "wizard" in msg.lower()
    # Markers untouched by the 19-20 branch — it's a reported injury, not bookkeeping.
    assert wb["wizard"]["underworld_favors"]["markers"] == before_markers


def test_debt_call_rejects_out_of_range_dice(fresh_warband):
    wb = fresh_warband
    warband_store.take_underworld_loan(wb, 100)
    ok, msg = warband_store.roll_underworld_debt_call(wb, call_roll=21)
    assert not ok
    assert "1 and 20" in msg
    ok, msg = warband_store.roll_underworld_debt_call(wb, outcome_roll=0)
    assert not ok
