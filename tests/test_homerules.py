"""A4: update_homerules() must not silently drop homerule keys it doesn't
explicitly re-parse."""

import warband_store


def test_unknown_key_survives_update(fresh_warband):
    wb = fresh_warband
    wb["homerules"]["a_future_homerule_not_yet_handled"] = "keep-me"

    ok, msg = warband_store.update_homerules(wb, {})
    assert ok, msg
    assert wb["homerules"]["a_future_homerule_not_yet_handled"] == "keep-me"


def test_all_default_keys_present_after_update(fresh_warband):
    wb = fresh_warband
    ok, msg = warband_store.update_homerules(wb, {})
    assert ok, msg
    for key in warband_store.default_homerules():
        assert key in wb["homerules"]


def test_ragged_warbands_forces_soldier_injuries_on(fresh_warband):
    """Ragged Warbands' own campaign rules need soldiers to be able to take
    permanent injuries (the Random Recruit Status Table's "injury" result,
    and the book's Survival Roll extending to soldiers too), so switching it
    on forces soldier_permanent_injuries_enabled on too. Unlike an earlier
    attempt at this, the checkbox itself is rendered `disabled` while Ragged
    Warbands is on (see warband_view.html), so this never fights the player
    over a value they explicitly chose — they simply can't uncheck it until
    Ragged Warbands is off again."""
    wb = fresh_warband
    ok, msg = warband_store.update_homerules(wb, {"ragged_warbands_enabled": "on"})
    assert ok, msg
    assert wb["homerules"]["ragged_warbands_enabled"] is True
    assert wb["homerules"]["soldier_permanent_injuries_enabled"] is True


def test_soldier_injuries_still_settable_on_its_own(fresh_warband):
    wb = fresh_warband
    ok, msg = warband_store.update_homerules(
        wb, {"soldier_permanent_injuries_enabled": "on"}
    )
    assert ok, msg
    assert wb["homerules"]["soldier_permanent_injuries_enabled"] is True


def test_ragged_warbands_off_does_not_force_soldier_injuries_on(fresh_warband):
    wb = fresh_warband
    ok, msg = warband_store.update_homerules(wb, {})
    assert ok, msg
    assert wb["homerules"]["ragged_warbands_enabled"] is False
    assert wb["homerules"]["soldier_permanent_injuries_enabled"] is False
