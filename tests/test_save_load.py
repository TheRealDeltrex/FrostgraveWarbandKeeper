"""A1: atomic saves. A2: corrupted files are surfaced instead of vanishing."""

import json

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
