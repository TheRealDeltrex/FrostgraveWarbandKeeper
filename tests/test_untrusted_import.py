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


# --- Filename sanitisation --------------------------------------------------


@pytest.mark.parametrize("hostile_id", ["..", ".", "", "///"])
def test_dot_ids_cannot_escape_the_portraits_root(hostile_id):
    """portrait_dir('..') used to resolve to the data-dir root, one level above
    portraits/ — delete_warband() would then unlink every loose file there."""
    assert ws.portrait_dir(hostile_id).resolve().parent == ws.portraits_root_dir().resolve()
