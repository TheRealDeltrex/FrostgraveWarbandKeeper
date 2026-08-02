"""B3: old-format warband fixtures must load into the current shape, and a
second load must be a no-op (migrations gated by schema_version)."""

import json

import warband_store as ws


def _write_old_warband(warband_id: str, data: dict) -> None:
    path = ws.warband_path(warband_id)
    path.write_text(json.dumps(data), encoding="utf-8")


def test_pre2e_health_and_item_slots_migrate():
    _write_old_warband("old-1", {
        "id": "old-1",
        "name": "Old Warband",
        "gold": 50,
        "wizard": {
            "name": "Old Wiz", "school": "Elementalist", "level": 0, "xp": 0,
            "stats": {"move": 6, "fight": 2, "shoot": 0, "armour": 10, "will": 4, "health": 10},
            "items": ["Staff", "Dagger"],
            "spells": [],
        },
        "vault": "Potion of Healing\nScroll of Wall",
        "soldiers": [
            {"id": "s1", "type_key": "thug", "name": "Grim", "status": "active",
             "items": "Hand weapon\nShield"},
        ],
    })
    wb = ws.load_warband("old-1")
    assert wb["schema_version"] == ws.SCHEMA_VERSION
    assert wb["wizard"]["stats"]["health"] == 14
    assert "Staff" in wb["wizard"]["item_slots"]
    assert [v["name"] for v in wb["vault_items"]] == ["Potion of Healing", "Scroll of Wall"]
    # Soldier gear used to live in a dead "items" field (never rendered
    # anywhere); it now migrates straight into item_slots (a thug gets the
    # standard 1 slot, so only the first entry survives) and "items" is gone.
    assert wb["soldiers"][0]["item_slots"] == ["Hand weapon"]
    assert "items" not in wb["soldiers"][0]


def test_soldier_items_dict_form_migrates_to_item_slots():
    _write_old_warband("old-4", {
        "id": "old-4",
        "name": "Old Warband 4",
        "gold": 0,
        "wizard": {"name": "W", "school": "Elementalist", "level": 0, "xp": 0,
                   "stats": {"move": 6, "fight": 2, "shoot": 0, "armour": 10, "will": 4, "health": 10},
                   "spells": []},
        "soldiers": [
            {"id": "s1", "type_key": "pack_mule", "name": "Mule", "status": "active",
             "items": [{"name": "Potion of Healing", "notes": ""}, {"name": "Rope", "notes": ""}]},
            {"id": "s2", "type_key": "companion_wolf", "name": "Wolf", "status": "active", "items": []},
        ],
    })
    wb = ws.load_warband("old-4")
    # pack_mule has 3 explicit item_slots (frostgrave_data.py), so both entries
    # survive, padded to length 3.
    assert wb["soldiers"][0]["item_slots"] == ["Potion of Healing", "Rope", ""]
    # An Animal Companion has 0 item slots regardless of what "items" held.
    assert wb["soldiers"][1]["item_slots"] == []
    assert "items" not in wb["soldiers"][0]
    assert "items" not in wb["soldiers"][1]


def test_captain_homerule_and_levelup_count_migrate():
    _write_old_warband("old-2", {
        "id": "old-2",
        "name": "Old Warband 2",
        "gold": 0,
        "wizard": {"name": "W", "school": "Elementalist", "level": 0, "xp": 0,
                   "stats": {"move": 6, "fight": 2, "shoot": 0, "armour": 10, "will": 4, "health": 14},
                   "spells": []},
        "homerules": {
            "captain_fight_levelup_cap": 3,
            "captain_shoot_levelup_cap": 2,
            "captains_enabled": True,
            "promote_captain_enabled": False,
        },
        "captain": {
            "name": "Old Cap",
            "stats": {"move": 6, "fight": 2, "shoot": 0, "armour": 10, "will": 0, "health": 10},
            "fight_levelup_count": 2,
            "shoot_levelup_count": 1,
        },
    })
    wb = ws.load_warband("old-2")
    hr = wb["homerules"]
    assert hr["captain_stat_caps"]["fight"] == {"limit": 3, "unlimited": False}
    assert hr["captain_stat_caps"]["shoot"] == {"limit": 2, "unlimited": False}
    assert "captain_fight_levelup_cap" not in hr
    assert hr["captain_mode"] == "hire"
    assert "captains_enabled" not in hr
    cap = wb["captain"]
    assert cap["levelup_counts"]["fight"] == 2
    assert cap["levelup_counts"]["shoot"] == 1
    assert "fight_levelup_count" not in cap


def test_second_load_is_stable_noop():
    _write_old_warband("old-3", {
        "id": "old-3",
        "name": "Old Warband 3",
        "gold": 0,
        "wizard": {"name": "W", "school": "Elementalist", "level": 0, "xp": 0,
                   "stats": {"move": 6, "fight": 2, "shoot": 0, "armour": 10, "will": 4, "health": 10},
                   "spells": []},
    })
    first = ws.load_warband("old-3")
    ws.save_warband(first)
    second = ws.load_warband("old-3")
    assert second == first
