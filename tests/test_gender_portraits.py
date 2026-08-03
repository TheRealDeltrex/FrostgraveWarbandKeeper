"""Wizard/apprentice gender toggle (creation/hire only) and the default
portrait swap when a wizard becomes a Lich or Vampire."""

import expansions
import warband_store


def test_wizard_defaults_to_male_and_portrait_name(fresh_warband):
    wb = fresh_warband
    assert wb["wizard"]["gender"] == "male"
    assert warband_store.default_portrait_name("wizard", gender="male") == "wizard.png"
    assert warband_store.default_portrait_name("wizard", gender="female") == "wizard_female.png"


def test_apprentice_gender_defaults_male_and_hire_can_set_female(fresh_warband):
    wb = fresh_warband
    ok, msg = warband_store.hire_apprentice(wb, "Sable", "female")
    assert ok, msg
    assert wb["apprentice"]["gender"] == "female"
    assert warband_store.default_portrait_name("apprentice", gender="female") == "apprentice_female.png"


def test_wizard_portrait_switches_on_lich_and_vampire_state():
    assert warband_store.default_portrait_name("wizard", gender="male", state=None) == "wizard.png"
    assert (
        warband_store.default_portrait_name("wizard", gender="female", state="lich")
        == "wizard_lich_female.png"
    )
    assert (
        warband_store.default_portrait_name("wizard", gender="male", state="vampire")
        == "wizard_vampire.png"
    )


def test_normalize_backfills_missing_gender_as_male(fresh_warband):
    wb = fresh_warband
    del wb["wizard"]["gender"]
    wb = warband_store._normalize_warband(wb)
    assert wb["wizard"]["gender"] == "male"


def test_list_warbands_reports_wizard_state_for_portrait(tmp_path, monkeypatch, fresh_warband):
    monkeypatch.setattr(warband_store, "warband_dir", lambda: tmp_path)
    wb = fresh_warband
    wb["wizard"]["state"]["kind"] = expansions.STATE_LICH
    warband_store.save_warband(wb)
    items = warband_store.list_warbands()
    assert items[0]["state"] == "lich"
    assert items[0]["gender"] == "male"
