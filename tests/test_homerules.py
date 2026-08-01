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
