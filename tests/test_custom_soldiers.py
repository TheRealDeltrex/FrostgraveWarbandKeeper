"""User-defined mercenaries: stored in the data dir, hired like any type."""

import json

import warband_store
from frostgrave_data import SOLDIERS, soldier_list_for_ui

FORM = {
    "name": "Sellsword",
    "cost": "40",
    "category": "standard",
    "move": "6",
    "fight": "3",
    "shoot": "0",
    "armour": "11",
    "will": "0",
    "health": "11",
    "item_slots": "1",
    "gear": "Hand weapon, light armour",
    "description": "House-ruled hireling.",
}


def _create(**overrides):
    ok, msg, key = warband_store.create_custom_soldier({**FORM, **overrides})
    assert ok, msg
    return key


def test_create_stores_in_data_dir_and_stays_off_official_list():
    key = _create()
    data = json.loads(warband_store.custom_soldiers_path().read_text(encoding="utf-8"))
    assert data["types"][key]["name"] == "Sellsword"
    assert data["types"][key]["fight"] == 3
    assert key in {c["key"] for c in warband_store.custom_soldier_list()}
    assert key not in {c["key"] for c in soldier_list_for_ui()}


def test_create_rejects_blank_name():
    ok, _, key = warband_store.create_custom_soldier({**FORM, "name": "  "})
    assert not ok and key is None


def test_hire_charges_gold_and_uses_custom_stats(fresh_warband):
    key = _create()
    wb = fresh_warband
    gold = wb["gold"]
    ok, msg = warband_store.add_soldier(wb, key, "Bob")
    assert ok, msg
    assert wb["gold"] == gold - 40
    view = warband_store.enrich_soldier(wb, wb["soldiers"][-1])
    assert (view["type_name"], view["move"], view["fight"], view["armour"]) == ("Sellsword", 6, 3, 11)


def test_delete_unused_type_removes_it_completely():
    key = _create()
    assert warband_store.delete_custom_soldier(key)[0]
    data = json.loads(warband_store.custom_soldiers_path().read_text(encoding="utf-8"))
    assert key not in data["types"]
    assert key not in SOLDIERS


def test_delete_used_type_only_retires_it(fresh_warband):
    key = _create()
    wb = fresh_warband
    assert warband_store.add_soldier(wb, key, "Bob")[0]
    warband_store.save_warband(wb)
    assert warband_store.delete_custom_soldier(key)[0]
    assert key not in {c["key"] for c in warband_store.custom_soldier_list()}
    assert not warband_store.add_soldier(wb, key, "Ann")[0]
    assert warband_store.enrich_soldier(wb, wb["soldiers"][-1])["type_name"] == "Sellsword"


def test_edit_reaches_hired_soldier(fresh_warband):
    key = _create()
    wb = fresh_warband
    assert warband_store.add_soldier(wb, key, "Bob")[0]
    assert warband_store.update_custom_soldier(key, {**FORM, "armour": "13"})[0]
    assert warband_store.enrich_soldier(wb, wb["soldiers"][-1])["armour"] == 13


def test_survives_restart(fresh_warband):
    key = _create()
    wb = fresh_warband
    assert warband_store.add_soldier(wb, key, "Bob")[0]
    warband_store.save_warband(wb)
    SOLDIERS.pop(key)  # simulate a fresh process
    loaded = warband_store.load_warband(wb["id"])
    assert warband_store.enrich_soldier(loaded, loaded["soldiers"][-1])["type_name"] == "Sellsword"
    assert key in {c["key"] for c in warband_store.custom_soldier_list()}


def test_import_elsewhere_restores_type_as_retired(fresh_warband):
    key = _create()
    wb = fresh_warband
    assert warband_store.add_soldier(wb, key, "Bob")[0]
    warband_store.save_warband(wb)
    raw = warband_store.export_warband_json(wb)
    # Another install: this type isn't in its library.
    warband_store.custom_soldiers_path().unlink()
    SOLDIERS.pop(key)
    imported = warband_store.import_warband_json(raw)
    view = warband_store.enrich_soldier(imported, imported["soldiers"][-1])
    assert (view["type_name"], view["armour"]) == ("Sellsword", 11)
    assert key not in {c["key"] for c in warband_store.custom_soldier_list()}


def test_hostile_embedded_types_are_dropped(fresh_warband):
    wb = fresh_warband
    warband_store.save_warband(wb)
    data = json.loads(warband_store.export_warband_json(wb))
    data["custom_soldier_types"] = {
        "custom_bad": {"name": ["x"], "armour": None},
        "thug": {"name": "Evil"},
        5: 1,
    }
    imported = warband_store.import_warband_json(json.dumps(data))
    assert SOLDIERS["thug"]["name"] == "Thug"
    assert imported["custom_soldier_types"] == {}
    assert "custom_bad" not in SOLDIERS
