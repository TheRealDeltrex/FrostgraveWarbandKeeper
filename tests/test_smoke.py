"""Mirrors the smoke check scripts/build_preview_pages.py already does: the
main pages load and a warband can be created and viewed."""

import app as app_module
from frostgrave_data import spell_id


def test_pages_and_warband_flow():
    client = app_module.app.test_client()

    for path in ("/", "/reference", "/about"):
        resp = client.get(path)
        assert resp.status_code < 400, f"GET {path} -> {resp.status_code}"

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
    resp = client.post(
        "/warband/new",
        data={
            "warband_name": "Smoke Test Warband",
            "wizard_name": "Smoke Wizard",
            "school": school,
            "spells": spells,
        },
    )
    assert resp.status_code < 400
    warband_id = resp.headers["Location"].rstrip("/").rsplit("/", 1)[-1]

    resp = client.get(f"/warband/{warband_id}")
    assert resp.status_code < 400
