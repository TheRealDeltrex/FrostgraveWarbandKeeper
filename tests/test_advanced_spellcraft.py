"""Advanced Spellcraft: the spell codex data and how it reaches the Info panels."""

from __future__ import annotations

import json
from pathlib import Path

import warband_store
from game_content import spell_codex_view

DATA = Path(__file__).resolve().parent.parent / "data" / "spell_codex.json"


def test_codex_covers_the_core_spells_without_watermark():
    raw = DATA.read_text(encoding="utf-8")
    assert "belongs to" not in raw and "purchased on" not in raw
    codex = json.loads(raw)
    assert len(codex) == 80
    for name, entry in codex.items():
        for c in entry["criticals"]:
            assert c["success"] and c["failure"], name
            assert set(c["pages"]) == set(c["sources"]), name


def test_view_keeps_only_enabled_books():
    every = spell_codex_view("Telekinesis")
    assert [c["sources"] for c in every["criticals"]] == [["Advanced Spellcraft"], ["Spellcaster Magazine"]]
    assert every["flourishes"]

    magazine_only = spell_codex_view("Telekinesis", {"Core Rules", "Spellcaster Magazine"})
    assert [c["sources"] for c in magazine_only["criticals"]] == [["Spellcaster Magazine"]]
    assert not magazine_only["flourishes"]

    # Wording-only changes are one entry carrying both books.
    shared = spell_codex_view("Fog", {"Core Rules", "Spellcaster Magazine"})
    assert shared["criticals"][0]["sources"] == ["Spellcaster Magazine", "Advanced Spellcraft"]

    assert spell_codex_view("Telekinesis", {"Core Rules"}) is None


def test_warband_view_shows_codex_only_with_the_book_on(fresh_warband):
    import app as app_module

    client = app_module.app.test_client()
    wb = fresh_warband
    wb["homerules"]["enabled_sources"] = {"Advanced Spellcraft": False, "Spellcaster Magazine": False}
    warband_store.save_warband(wb)
    page = client.get(f"/warband/{wb['id']}", headers={"Host": "127.0.0.1"}).get_data(as_text=True)
    assert 'class="spell-codex"' not in page

    wb["homerules"]["enabled_sources"]["Advanced Spellcraft"] = True
    warband_store.save_warband(wb)
    page = client.get(f"/warband/{wb['id']}", headers={"Host": "127.0.0.1"}).get_data(as_text=True)
    assert 'class="spell-codex"' in page and "Casting Roll Criticals" in page


def test_bibliosepulchre_treasure_is_sell_only(fresh_warband):
    from game_content import load_magic_items, load_supplement_item_prices

    items = [it for it in load_magic_items() if it["source"] == "Advanced Spellcraft"]
    prices = [p for p in load_supplement_item_prices() if p["source"] == "Advanced Spellcraft"]
    assert len(items) == len(prices) == 40
    assert {it["name"] for it in items} == {p["name"] for p in prices}
    # p.125: never purchasable; the cost is for comparison only.
    assert all(p["purchase"] is None and p["listed_cost"] and p["sale"] for p in prices)

    # The Maze of Malcor's Porter Control Rod stays beside the reprint.
    rods = {it["source"] for it in load_magic_items() if it["name"] == "Porter Control Rod"}
    assert rods == {"The Maze of Malcor", "Advanced Spellcraft"}

    wb = fresh_warband
    wb["homerules"]["enabled_sources"]["Advanced Spellcraft"] = True
    shelf = [
        row for group in warband_store.shop_catalog(wb)
        for row in group["rows"] if row.get("source") == "Advanced Spellcraft"
    ]
    assert shelf and all(row["purchase"] is None for row in shelf)


def test_bestiary_reprints_are_tagged_or_kept_side_by_side():
    from game_content import load_bestiary

    rows = load_bestiary()
    crow = next(c for c in rows if c["name"] == "Blood Crow")
    assert crow["sources"] == ["Thaw of the Lich Lord", "Advanced Spellcraft"]
    hounds = {c["source"] for c in rows if c["name"] == "Chronohound"}
    assert hounds == {"The Perilous Dark", "Advanced Spellcraft"}
    assert any(c["name"] == "Book Wight" and c["source"] == "Advanced Spellcraft" for c in rows)


def test_lexicon_renders_with_every_source_tag():
    import app as app_module

    page = app_module.app.test_client().get("/reference", headers={"Host": "127.0.0.1"})
    assert page.status_code == 200
    text = page.get_data(as_text=True)
    row = text[text.index("<strong>Blood Crow</strong>"):][:400]
    assert "Thaw of the Lich Lord" in row and "Advanced Spellcraft" in row


def _with_spellcraft(wb: dict) -> dict:
    wb["homerules"]["enabled_sources"]["Advanced Spellcraft"] = True
    return wb


def test_optional_rules_default_on_except_forgetting_spells():
    hr = warband_store.default_homerules()
    assert hr["as_flourishes"] and hr["as_draining_magical_items"]
    assert hr["as_forgetting_spells"] is False


def test_learning_a_flourish_spends_a_level_and_the_grimoire(fresh_warband):
    import expansions

    wb = _with_spellcraft(fresh_warband)
    assert "learn_flourish" not in {o["id"] for o in expansions.level_up_options(fresh_warband | {"homerules": {}})}
    assert "learn_flourish" in {o["id"] for o in expansions.level_up_options(wb)}
    wall = next(s for s in wb["wizard"]["spells"] if s["name"] == "Wall")
    flourish = next(f for f in expansions.learnable_flourishes(wb) if f["spell"] == "Wall")
    warband_store.add_vault_item(wb, "Grimoire: Wall", source="manual")
    wb["wizard"]["xp"] = 100
    ok, msg = warband_store.apply_level_up(wb, "learn_flourish", flourish_key=flourish["key"])
    assert ok, msg
    assert wall["flourishes"] == [flourish["name"]]
    assert not any(i["name"] == "Grimoire: Wall" for i in wb["vault_items"])

    ok, msg = warband_store.reverse_last_level_up(wb)
    assert ok, msg
    assert wall["flourishes"] == []
    assert any(i["name"] == "Grimoire: Wall" for i in wb["vault_items"])


def test_draining_destroys_the_item_and_respects_no_market(fresh_warband):
    wb = _with_spellcraft(fresh_warband)
    warband_store.add_vault_item(wb, "Book of Arcane Desire", source="manual")
    item = wb["vault_items"][-1]
    ok, msg = warband_store.drain_vault_item(wb, item["id"])
    assert ok and "+2" in msg  # sells for 200gc (p.125)
    assert item not in wb["vault_items"]

    warband_store.add_vault_item(wb, "Potion of Healing", source="brew_potion")
    ok, _ = warband_store.drain_vault_item(wb, wb["vault_items"][-1]["id"])
    assert not ok
