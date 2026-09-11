"""Regression tests for hostile / corrupt .warbands input.

`.warbands` files are the app's exchange format, so an imported file is
semi-untrusted: it round-trips every field verbatim, including ones that flow
into arithmetic (homerule caps) and filesystem paths (portraits). Each test
here pins a case that previously either read a file outside the portraits
folder or produced a warband that saved fine and then 500'd on every view.
"""

from __future__ import annotations

import json

import pytest

import warband_store as ws


def _round_trip(fresh_warband: dict, **overrides) -> dict:
    """Export the fixture, splice in hostile values, import it back."""
    raw = json.loads(ws.export_warband_json(fresh_warband))
    raw.update(overrides)
    raw["id"] = "hostile-import"
    return ws.import_warband_json(json.dumps(raw))


# --- Portrait path containment ----------------------------------------------


def test_absolute_portrait_path_is_rejected(tmp_path):
    """pathlib's `/` discards the left operand when the right is absolute, so an
    absolute portrait ref used to resolve straight through the portraits root
    and get embedded in the exported PDF."""
    outside = tmp_path / "outside.png"
    outside.write_bytes(b"\x89PNG\r\n\x1a\n")
    assert ws.portrait_filesystem_path(str(outside)) is None
    assert ws.resolve_portrait_path(str(outside), "wizard") != outside


def test_traversal_portrait_path_is_rejected():
    assert ws.portrait_filesystem_path("../../secret.png") is None


def test_portrait_without_image_extension_is_rejected():
    assert ws.portrait_filesystem_path("wb/notes.txt") is None


def test_legitimate_portrait_path_still_resolves(fresh_warband):
    rel = f"{fresh_warband['id']}/wizard.png"
    dest = ws.portrait_dir(fresh_warband["id"]) / "wizard.png"
    dest.write_bytes(b"\x89PNG\r\n\x1a\n")
    assert ws.portrait_filesystem_path(rel) == dest.resolve()


def test_import_strips_unsafe_portrait_reference(fresh_warband, tmp_path):
    outside = tmp_path / "outside.png"
    outside.write_bytes(b"\x89PNG\r\n\x1a\n")
    raw = json.loads(ws.export_warband_json(fresh_warband))
    raw["wizard"]["portrait"] = str(outside)
    raw["id"] = "hostile-portrait"
    imported = ws.import_warband_json(json.dumps(raw))
    assert imported["wizard"]["portrait"] is None


# --- Type coercion ----------------------------------------------------------


def test_non_numeric_homerule_does_not_break_the_warband(fresh_warband):
    """`max_soldiers: "lots"` used to import cleanly, then raise ValueError in
    warband_limits() — which warband_view calls unguarded, so the warband was
    permanently unviewable and could not be deleted from the UI."""
    hostile = json.loads(ws.export_warband_json(fresh_warband))
    hostile["homerules"]["max_soldiers"] = "lots"
    hostile["id"] = "bad-homerule"
    imported = ws.import_warband_json(json.dumps(hostile))
    assert imported["homerules"]["max_soldiers"] == ws.MAX_SOLDIERS
    ws.warband_limits(imported)  # must not raise


def test_nested_numeric_homerules_are_coerced(fresh_warband):
    hostile = json.loads(ws.export_warband_json(fresh_warband))
    hostile["homerules"]["captain_base_stats"]["fight"] = "strong"
    hostile["homerules"]["wizard_stat_limits"] = "nope"
    hostile["id"] = "bad-nested"
    imported = ws.import_warband_json(json.dumps(hostile))
    assert isinstance(imported["homerules"]["captain_base_stats"]["fight"], int)
    assert isinstance(imported["homerules"]["wizard_stat_limits"], dict)


def test_boolean_homerules_are_not_coerced_to_int(fresh_warband):
    """bool is an int subclass; coercion must skip it or every toggle would
    silently become 0/1 and stop round-tripping as a checkbox."""
    imported = _round_trip(fresh_warband)
    assert imported["homerules"]["soldier_leveling_enabled"] is False
    assert imported["homerules"]["edition2_soldier_costs"] is True


@pytest.mark.parametrize("bad_gold", ["heaps", None, [1]])
def test_non_numeric_gold_falls_back(fresh_warband, bad_gold):
    imported = _round_trip(fresh_warband, gold=bad_gold)
    assert imported["gold"] == ws.STARTING_GOLD


def test_non_numeric_wizard_xp_falls_back(fresh_warband):
    hostile = json.loads(ws.export_warband_json(fresh_warband))
    hostile["wizard"]["xp"] = "loads"
    hostile["wizard"]["level"] = None
    hostile["id"] = "bad-xp"
    imported = ws.import_warband_json(json.dumps(hostile))
    assert imported["wizard"]["xp"] == 0
    assert imported["wizard"]["level"] == 0


# --- Vault items ------------------------------------------------------------


def test_vault_item_without_a_name_is_dropped(fresh_warband):
    """warband_view calls .strip() on every vault name; a null one raised
    AttributeError and 500'd the page."""
    imported = _round_trip(fresh_warband, vault_items=[{"id": "a", "notes": "n"}])
    assert imported["vault_items"] == []


def test_vault_items_are_normalized_to_dicts(fresh_warband):
    imported = _round_trip(
        fresh_warband,
        vault_items=["Ring of Power", {"name": "  Amulet  ", "notes": "found"}],
    )
    names = [it["name"] for it in imported["vault_items"]]
    assert names == ["Ring of Power", "Amulet"]
    assert all(it.get("id") for it in imported["vault_items"])


def test_wrong_typed_containers_are_replaced(fresh_warband):
    imported = _round_trip(
        fresh_warband, soldiers="not a list", vault_items=42, homerules=[1, 2]
    )
    assert imported["soldiers"] == []
    assert imported["vault_items"] == []
    assert imported["homerules"]["max_soldiers"] == ws.MAX_SOLDIERS


def test_non_dict_soldiers_are_discarded(fresh_warband):
    imported = _round_trip(fresh_warband, soldiers=["ghost", None, {"type_key": "thug"}])
    assert len(imported["soldiers"]) == 1
    assert imported["soldiers"][0]["type_key"] == "thug"
    assert imported["soldiers"][0]["id"]


def test_two_level_stat_cap_grids_are_backfilled(fresh_warband):
    """captain_stat_caps/soldier_stat_caps nest {stat: {limit, unlimited}}, one
    level deeper than every other numeric homerule. Coercion used to skip any
    sub-value that wasn't itself an int, so a grid missing a stat imported fine
    and then 500'd warband_view, which reads hr.<grid>[stat].limit."""
    hostile = json.loads(ws.export_warband_json(fresh_warband))
    del hostile["homerules"]["captain_stat_caps"]["health"]
    hostile["homerules"]["soldier_stat_caps"]["fight"] = "unlimited"
    hostile["id"] = "bad-cap-grid"
    imported = ws.import_warband_json(json.dumps(hostile))
    defaults = ws.default_homerules()
    for grid in ("captain_stat_caps", "soldier_stat_caps"):
        for stat in defaults[grid]:
            assert isinstance(imported["homerules"][grid][stat], dict), (grid, stat)
            assert isinstance(imported["homerules"][grid][stat]["limit"], int), (grid, stat)
    # a wrong-typed sub-grid is replaced wholesale with the default, not patched
    assert (
        imported["homerules"]["soldier_stat_caps"]["fight"]
        == defaults["soldier_stat_caps"]["fight"]
    )


def test_soldier_of_an_unknown_type_key_still_gets_numeric_stats(fresh_warband):
    """The stat backfill falls back to get_soldier(type_key), which is empty for
    a type this build doesn't know — a renamed key, or a file written by a build
    carrying more supplements. It used to write that None straight back, and
    enrich_soldier() then called int() on it."""
    imported = _round_trip(
        fresh_warband, soldiers=[{"id": "x1", "type_key": "no_such_soldier", "name": "Ghost"}]
    )
    s = imported["soldiers"][0]
    for stat in ("fight", "shoot", "will", "health"):
        assert isinstance(s[stat], int), stat
    ws.enrich_soldier(imported, s)  # must not raise


def test_soldier_move_and_armour_stay_catalog_driven(fresh_warband):
    """Move/Armour are deliberately not stored per soldier, so a later data fix
    to a soldier type reaches existing warbands. Normalization must not start
    writing them onto the instance dict."""
    imported = _round_trip(fresh_warband, soldiers=[{"id": "x1", "type_key": "thug"}])
    assert "move" not in imported["soldiers"][0]
    assert "armour" not in imported["soldiers"][0]
    enriched = ws.enrich_soldier(imported, imported["soldiers"][0])
    assert enriched["move"] == ws.get_soldier("thug")["move"]
    assert enriched["armour"] == ws.get_soldier("thug")["armour"]


@pytest.mark.parametrize("field", ["mutations", "permanent_injuries", "level_history"])
def test_explicitly_null_list_fields_become_lists(fresh_warband, field):
    """setdefault() leaves a present-but-null key alone, and every template that
    renders one takes its |length."""
    hostile = json.loads(ws.export_warband_json(fresh_warband))
    hostile["wizard"][field] = None
    hostile["soldiers"] = [{"id": "x1", "type_key": "thug", field: None}]
    hostile["id"] = "null-lists"
    imported = ws.import_warband_json(json.dumps(hostile))
    assert imported["wizard"][field] == []
    assert imported["soldiers"][0][field] == []


def test_non_dict_spells_are_dropped_and_scalars_coerced(fresh_warband):
    """recompute_spell_cns() calls .get() on every spell and feeds base_cn into
    arithmetic and school into a dict lookup."""
    hostile = json.loads(ws.export_warband_json(fresh_warband))
    hostile["wizard"]["spells"][0]["base_cn"] = "twelve"
    hostile["wizard"]["spells"][1]["school"] = []
    hostile["wizard"]["spells"].append("elementalist::wall")
    hostile["id"] = "bad-spells"
    imported = ws.import_warband_json(json.dumps(hostile))
    assert all(isinstance(sp, dict) for sp in imported["wizard"]["spells"])
    assert all(isinstance(sp["base_cn"], int) for sp in imported["wizard"]["spells"])
    assert all(isinstance(sp["school"], str) for sp in imported["wizard"]["spells"])


def test_unhashable_lookup_keys_are_coerced(fresh_warband):
    """type_key, knightly_order and base.location are all used as dict keys
    downstream (get_soldier, KNIGHTLY_ORDER_BY_ID, BASE_LOCATIONS). A list or
    dict there is an unhashable-type TypeError, not a lookup miss — raised out
    of _normalize_warband itself, which load_warband() does not catch."""
    hostile = json.loads(ws.export_warband_json(fresh_warband))
    hostile["base"]["location"] = []
    hostile["soldiers"] = [{"id": "x1", "type_key": {}, "knightly_order": []}]
    hostile["id"] = "unhashable-keys"
    imported = ws.import_warband_json(json.dumps(hostile))
    assert imported["base"]["location"] == "none"
    assert imported["soldiers"][0]["type_key"] == ""
    assert imported["soldiers"][0]["knightly_order"] is None


def test_malformed_black_market_offers_are_dropped(fresh_warband):
    """black_market_buy_item() indexes offer["id"], entry["id"] and
    entry["name"] directly, so an offer or entry missing one raised out of the
    Buy button. Well-formed ones survive and stay buyable."""
    good_entry = {"id": "e1", "name": "Potion of Healing", "price": "junk"}
    imported = _round_trip(
        fresh_warband,
        black_market={
            "rolls_used": 1,
            "offers": [
                "not an offer",
                {"entries": [good_entry]},
                {"id": 7, "entries": [good_entry]},
                {"id": "o1", "entries": 5},
                {"id": "o2", "entries": [good_entry, {"name": "no id"}, {"id": "e2", "name": None}, "x"]},
            ],
        },
    )
    offers = imported["black_market"]["offers"]
    assert [o["id"] for o in offers] == ["o1", "o2"]
    assert offers[0]["entries"] == []
    assert offers[1]["entries"] == [{"id": "e1", "name": "Potion of Healing", "price": 0}]

    imported["homerules"]["black_market_enabled"] = True
    ok, _ = ws.black_market_buy_item(imported, "o2", "e1")
    assert ok
    assert ws.black_market_buy_item(imported, "o1", "e1")[0] is False


def test_non_dict_permanent_injuries_are_dropped(fresh_warband):
    """Every consumer calls .get() on each injury, and the text resync uses its
    id as a dict key -- a string entry or a list id raised out of
    _normalize_warband(), so a file already on disk 500'd every view."""
    known = next(iter(ws.PERMANENT_INJURY_BY_ID))
    injuries = ["x", 3, None, {"id": ["unhashable"]}, {"id": known}]
    raw = json.loads(ws.export_warband_json(fresh_warband))
    raw["wizard"]["permanent_injuries"] = injuries
    raw["soldiers"] = [{"id": "s1", "type_key": "thug", "permanent_injuries": injuries}]
    imported = ws.import_warband_json(json.dumps(raw))
    for figure in (imported["wizard"], imported["soldiers"][0]):
        assert [inj["id"] for inj in figure["permanent_injuries"]] == [["unhashable"], known]
        assert figure["permanent_injuries"][1]["name"] == ws.PERMANENT_INJURY_BY_ID[known]["name"]


@pytest.mark.parametrize("bad_name", [["x"], {"a": 1}, 7, None])
def test_non_string_warband_name_still_imports(fresh_warband, bad_name):
    """The name seeds the new warband id; a non-string one raised
    AttributeError out of _slug() and the import was refused with that
    message instead of going through."""
    raw = json.loads(ws.export_warband_json(fresh_warband))
    raw["name"] = bad_name
    raw["id"] = None
    imported = ws.import_warband_json(json.dumps(raw))
    assert imported["id"].startswith("warband-")


@pytest.mark.parametrize("bad_resources", [None, 5, True, "stable"])
def test_non_list_base_resources_becomes_a_list(fresh_warband, bad_resources):
    """The resources filter iterates it directly."""
    hostile = json.loads(ws.export_warband_json(fresh_warband))
    hostile["base"]["resources"] = bad_resources
    hostile["id"] = "bad-resources"
    imported = ws.import_warband_json(json.dumps(hostile))
    assert imported["base"]["resources"] == []


@pytest.mark.parametrize("bad_notes", [42, True, None, []])
def test_non_string_base_notes_becomes_a_string(fresh_warband, bad_notes):
    """pdf_export.build_warband_pdf() calls .strip() on it."""
    imported = _round_trip(fresh_warband, base={"location": "none", "notes": bad_notes})
    assert imported["base"]["notes"] == ""


@pytest.mark.parametrize("bad_version", ["abc", None, [], {}, ""])
def test_non_numeric_schema_version_falls_back(fresh_warband, bad_version):
    """_run_migrations() int()s it before any migration runs, so this fails
    ahead of every other guard in _normalize_warband."""
    imported = _round_trip(fresh_warband, schema_version=bad_version)
    assert imported["schema_version"] == ws.SCHEMA_VERSION


# --- Filename sanitisation --------------------------------------------------


@pytest.mark.parametrize("hostile_id", ["..", ".", "", "///"])
def test_dot_ids_cannot_escape_the_portraits_root(hostile_id):
    """portrait_dir('..') used to resolve to the data-dir root, one level above
    portraits/ — delete_warband() would then unlink every loose file there."""
    assert ws.portrait_dir(hostile_id).resolve().parent == ws.portraits_root_dir().resolve()


# --- Whole-file type fuzz -----------------------------------------------------
#
# Every field of a full warband (apprentice, captain, a spread of soldier
# types), replaced in turn by each wrong-typed value, must either be refused
# at import or produce a warband whose page and PDF still render. The
# 2026-09-08 audit found 14 fields that imported fine and 500'd forever
# (full_audit_2026-09-08.md, F6); this keeps the whole class closed rather
# than one field at a time. ~250 paths × 10 values, each a view + PDF render:
# about five minutes, by far the slowest test in the suite — run it when
# touching _normalize_warband(), import, or the PDF, not as a routine check.

_BAD_VALUES = [None, "str", 123, -7, [], {}, ["x"], {"a": 1}, True, 1.5]


def _full_export() -> dict:
    from frostgrave_data import spell_id

    school = "Elementalist"
    spells = [
        spell_id(school, "Wall"),
        spell_id(school, "Elemental Bolt"),
        spell_id(school, "Elemental Shield"),
        spell_id("Chronomancer", "Fast Act"),
        spell_id("Enchanter", "Enchant Weapon"),
        spell_id("Summoner", "Leap"),
        spell_id("Necromancer", "Bone Dart"),
        spell_id("Thaumaturge", "Heal"),
    ]
    wb, msg = ws.create_warband("fuzz", "W", school, spells, True, "A")
    assert wb is not None, msg
    hr = wb["homerules"]
    for key, value in ws.default_homerules().items():
        if isinstance(value, bool):
            hr[key] = True
    for book in hr["enabled_sources"]:
        hr["enabled_sources"][book] = True
    hr["max_soldiers"] = hr["max_specialists"] = 50
    wb["gold"] = 90000
    ws.hire_captain(wb, "Cap")
    for type_key in ("thug", "war_hound", "man_at_arms", "musketeer", "apprentice_construct"):
        ws.add_soldier(wb, type_key, type_key, "", "")
    # Save and reload so the export carries every key _normalize_warband()
    # backfills (fin_dalka, horse, supply_points, monster_hunting...) — a
    # fresh create_warband() dict lacks them and the walk would never visit them.
    ws.save_warband(wb)
    return json.loads(ws.export_warband_json(ws.load_warband(wb["id"])))


def _field_paths(obj, prefix=(), depth=0):
    if depth > 3:
        return
    if isinstance(obj, dict):
        for key, value in obj.items():
            if prefix == () and key == "id":
                continue
            yield prefix + (key,)
            yield from _field_paths(value, prefix + (key,), depth + 1)
    elif isinstance(obj, list) and obj:
        yield prefix + (0,)
        yield from _field_paths(obj[0], prefix + (0,), depth + 1)


_FUZZ_BASE = None


def _fuzz_base() -> dict:
    global _FUZZ_BASE
    if _FUZZ_BASE is None:
        _FUZZ_BASE = _full_export()
    return _FUZZ_BASE


@pytest.mark.parametrize("bad", _BAD_VALUES, ids=repr)
def test_every_field_with_a_wrong_type_still_renders(bad):
    import copy

    import app as app_module

    app_module.app.config["TESTING"] = True
    client = app_module.app.test_client()
    base = _fuzz_base()
    failures = []
    for path in _field_paths(base):
        data = copy.deepcopy(base)
        target = data
        for key in path[:-1]:
            target = target[key]
        target[path[-1]] = bad
        data["id"] = None
        try:
            wb = ws.import_warband_json(json.dumps(data))
            ws.save_warband(wb)
        except Exception:
            # Refused at import is fine -- but a file already in the warband
            # folder never passes through import, and load_warband() can't
            # refuse it. `"black_market": null` was refused here and still
            # 500'd every view once on disk, so try that route too.
            wb = {"id": "disk-fuzz"}
            ws.warband_path(wb["id"]).write_text(json.dumps(data), encoding="utf-8")
        label = ".".join(map(str, path))
        for suffix in ("", "/pdf"):
            try:
                resp = client.get(f"/warband/{wb['id']}{suffix}")
                if resp.status_code != 200:
                    failures.append(f"{label}{suffix or '/view'} -> HTTP {resp.status_code}")
            except Exception as exc:  # noqa: BLE001 - any raise is the failure
                failures.append(f"{label}{suffix or '/view'} -> {type(exc).__name__}: {exc}")
        ws.delete_warband(wb["id"])
    assert not failures, "imported fine, then crashed:\n  " + "\n  ".join(failures)


@pytest.mark.parametrize("bad_id", [123, None, [], {}, 1.5, True], ids=repr)
def test_hand_edited_non_string_id_is_repaired_from_the_filename(fresh_warband, bad_id):
    """The import path forces a fresh id, but a hand-edited file keeps whatever
    `id` it carries. A non-string one renders fine and then raises
    `TypeError: expected string or bytes-like object` out of `warband_path()`
    on the next `save_warband()` — so every mutation 500s, not just one view."""
    ws.save_warband(fresh_warband)
    file_id = fresh_warband["id"]
    path = ws.warband_path(file_id)
    data = json.loads(path.read_text(encoding="utf-8"))
    data["id"] = bad_id
    path.write_text(json.dumps(data), encoding="utf-8")

    loaded = ws.load_warband(file_id)
    assert loaded is not None
    assert loaded["id"] == file_id
    ws.save_warband(loaded)  # used to raise
    assert ws.warband_path(loaded["id"]) == path
