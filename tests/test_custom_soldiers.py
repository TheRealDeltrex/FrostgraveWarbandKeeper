"""User-defined mercenaries: stored in the data dir, hired like any type."""

import json

import warband_store
from app import app
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
    warband_store.save_warband(wb)
    assert warband_store.update_custom_soldier(key, {**FORM, "armour": "13"})[0]
    wb = warband_store.load_warband(wb["id"])
    assert warband_store.enrich_soldier(wb, wb["soldiers"][-1])["armour"] == 13


def test_survives_restart(fresh_warband):
    key = _create()
    wb = fresh_warband
    assert warband_store.add_soldier(wb, key, "Bob")[0]
    warband_store.save_warband(wb)
    assert key not in SOLDIERS
    loaded = warband_store.load_warband(wb["id"])
    assert warband_store.enrich_soldier(loaded, loaded["soldiers"][-1])["type_name"] == "Sellsword"
    assert key in {c["key"] for c in warband_store.custom_soldier_list()}


def test_import_elsewhere_restores_type_for_its_roster(fresh_warband, monkeypatch, tmp_path):
    key = _create()
    wb = fresh_warband
    assert warband_store.add_soldier(wb, key, "Bob")[0]
    warband_store.save_warband(wb)
    raw = warband_store.export_warband_json(wb)
    # Another install: this type isn't in its library.
    monkeypatch.setenv("FWK_DATA_DIR", str(tmp_path))
    imported = warband_store.import_warband_json(raw)
    view = warband_store.enrich_soldier(imported, imported["soldiers"][-1])
    assert (view["type_name"], view["armour"]) == ("Sellsword", 11)
    assert key not in {c["key"] for c in warband_store.custom_soldier_list()}
    assert not warband_store.add_soldier(imported, key, "Ann")[0]


def test_export_uses_the_current_type_without_resaving_the_warband(fresh_warband):
    key = _create()
    wb = fresh_warband
    assert warband_store.add_soldier(wb, key, "Bob")[0]
    warband_store.save_warband(wb)
    assert warband_store.update_custom_soldier(key, {**FORM, "armour": "13"})[0]

    response = app.test_client().get(f"/warband/{wb['id']}/export")
    assert response.status_code == 200
    assert response.get_json()["custom_soldier_types"][key]["armour"] == 13


def test_imported_custom_types_stay_with_their_own_warband(fresh_warband, monkeypatch, tmp_path):
    key = _create()
    wb = fresh_warband
    assert warband_store.add_soldier(wb, key, "Bob")[0]
    first = warband_store.export_warband_json(wb)
    assert warband_store.update_custom_soldier(key, {**FORM, "armour": "13", "category": "specialist"})[0]
    second = warband_store.export_warband_json(wb)

    monkeypatch.setenv("FWK_DATA_DIR", str(tmp_path))
    original = warband_store.import_warband_json(first)
    warband_store.save_warband(original)
    revised = warband_store.import_warband_json(second)
    assert revised["id"] != original["id"]
    assert warband_store.enrich_soldier(revised, revised["soldiers"][-1])["armour"] == 13
    assert warband_store.count_specialists(revised) == 1
    assert warband_store.enrich_soldier(original, original["soldiers"][-1])["armour"] == 11
    assert warband_store.count_specialists(original) == 0
    warband_store.save_warband(original)
    exported = json.loads(warband_store.export_warband_json(original))
    assert exported["custom_soldier_types"][key]["armour"] == 11
    assert key not in SOLDIERS


def test_cannot_remove_an_occupied_slot_from_another_warband(fresh_warband):
    key = _create(item_slots="2")
    wb = fresh_warband
    assert warband_store.add_soldier(wb, key, "Bob")[0]
    soldier = wb["soldiers"][-1]
    soldier["item_slots"] = ["Dagger", "Shield"]
    warband_store.save_warband(wb)
    ok, msg = warband_store.update_custom_soldier(key, FORM)
    assert not ok and "Unequip items" in msg
    assert warband_store.load_warband(wb["id"])["soldiers"][-1]["item_slots"] == ["Dagger", "Shield"]

    soldier["item_slots"][1] = ""
    warband_store.save_warband(wb)
    assert warband_store.update_custom_soldier(key, FORM)[0]
    assert warband_store.load_warband(wb["id"])["soldiers"][-1]["item_slots"] == ["Dagger"]


def test_import_preserves_occupied_slots_above_the_local_limit(fresh_warband):
    key = _create()
    wb = fresh_warband
    assert warband_store.add_soldier(wb, key, "Bob")[0]
    wb["soldiers"][-1]["item_slots"] = ["Dagger", "Shield"]
    imported = warband_store.import_warband_json(warband_store.export_warband_json(wb))
    warband_store.save_warband(imported)
    loaded = warband_store.load_warband(imported["id"])
    assert loaded["soldiers"][-1]["item_slots"] == ["Dagger", "Shield"]


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
