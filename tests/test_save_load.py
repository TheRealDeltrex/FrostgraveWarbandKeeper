"""A1: atomic saves. A2: corrupted files are surfaced instead of vanishing."""

import json

import pytest

import warband_store


def test_save_is_atomic_and_bak_rotates(fresh_warband):
    wb = fresh_warband
    warband_store.save_warband(wb)
    path = warband_store.warband_path(wb["id"])
    assert path.is_file()
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["id"] == wb["id"]
    assert not path.with_suffix(".tmp").exists()
    assert not path.with_suffix(".bak").exists()  # no prior file on first save

    warband_store.save_warband(wb)
    assert path.with_suffix(".bak").is_file()
    assert not path.with_suffix(".tmp").exists()


def test_corrupted_file_is_listed_not_silently_dropped(fresh_warband):
    wb = fresh_warband
    warband_store.save_warband(wb)
    bad_path = warband_store.warband_dir() / "broken.warbands"
    bad_path.write_text("{broken", encoding="utf-8")

    good = warband_store.list_warbands()
    assert all(w["id"] != "broken" for w in good)

    unreadable = warband_store.list_unreadable_warbands()
    assert any(u["filename"] == "broken.warbands" for u in unreadable)


def test_export_import_round_trip(fresh_warband):
    wb = fresh_warband
    warband_store.save_warband(wb)
    exported = warband_store.export_warband_json(wb)
    imported = warband_store.import_warband_json(exported)
    assert imported["name"] == wb["name"]
    assert imported["wizard"]["school"] == wb["wizard"]["school"]


def test_import_beside_original_copies_portraits(fresh_warband):
    wb = fresh_warband
    (warband_store.portrait_dir(wb["id"]) / "wizard.png").write_bytes(b"png")
    wb["wizard"]["portrait"] = f"{wb['id']}/wizard.png"
    warband_store.save_warband(wb)
    copy = warband_store.import_warband_json(warband_store.export_warband_json(wb))
    warband_store.delete_warband(wb["id"])
    assert copy["id"] != wb["id"]
    assert copy["wizard"]["portrait"].startswith(f"{copy['id']}/")
    assert warband_store.portrait_filesystem_path(copy["wizard"]["portrait"])


def test_duplicate_copies_captain_portrait(fresh_warband):
    wb = fresh_warband
    wb["captain"] = warband_store.empty_captain("Cap", wb["homerules"])
    (warband_store.portrait_dir(wb["id"]) / "captain.png").write_bytes(b"png")
    wb["captain"]["portrait"] = f"{wb['id']}/captain.png"
    warband_store.save_warband(wb)
    copy, _ = warband_store.duplicate_warband(wb["id"])
    warband_store.delete_warband(wb["id"])
    assert copy["captain"]["portrait"].startswith(f"{copy['id']}/")
    assert warband_store.portrait_filesystem_path(copy["captain"]["portrait"])


@pytest.mark.parametrize(
    "raw",
    ['[1, 2]', '{"wizard": "oops", "soldiers": []}', '{"wizard": {}, "soldiers": ["x"]}'],
)
def test_wrong_shaped_save_is_reported_not_listed(fresh_warband, raw):
    warband_store.save_warband(fresh_warband)
    bad = warband_store.warband_dir() / "bad.warbands"
    bad.write_text(raw, encoding="utf-8")
    try:
        ids = [row["id"] for row in warband_store.list_warbands()]
        assert fresh_warband["id"] in ids and "bad" not in ids
        assert "bad.warbands" in [u["filename"] for u in warband_store.list_unreadable_warbands()]
    finally:
        bad.unlink()
