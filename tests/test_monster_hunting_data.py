"""Data-integrity guard for data/monster_hunting.json (the Master Monster
Table, Spellcaster Magazine Issue 5) — hand-curated from a PDF extraction
(scripts/extract_monster_hunting.py), so this checks the shape and the
cross-references stay consistent rather than the row content itself."""

from frostgrave_data import SOURCE_BOOKS, SPELLS
from game_content import load_bestiary, load_monster_hunting, load_potion_choices


def test_row_count_is_ninety_two():
    assert len(load_monster_hunting()) == 92


def test_every_row_has_the_expected_shape():
    for row in load_monster_hunting():
        assert set(row.keys()) == {"monster", "rules", "source", "xp", "bestiary_name", "prize"}
        assert isinstance(row["monster"], str) and row["monster"]
        assert isinstance(row["xp"], int) and row["xp"] >= 0
        prize = row["prize"]
        assert set(prize.keys()) == {"name", "kind", "target", "gold", "known"}
        assert prize["kind"] in ("spell", "potion", "gold", "none")


def test_every_source_is_a_known_source_book():
    valid = set(SOURCE_BOOKS) | {"Core Rules"}
    for row in load_monster_hunting():
        assert row["source"] in valid, row["monster"]


def test_every_bestiary_name_resolves():
    names = {c["name"] for c in load_bestiary()}
    for row in load_monster_hunting():
        if row["bestiary_name"] is not None:
            assert row["bestiary_name"] in names, row["monster"]


def test_known_spell_and_potion_targets_actually_resolve():
    known_spells = {s["name"] for spells in SPELLS.values() for s in spells}
    known_potions = set(load_potion_choices())
    for row in load_monster_hunting():
        prize = row["prize"]
        if prize["kind"] == "spell" and prize["known"]:
            assert prize["target"] in known_spells, row["monster"]
        if prize["kind"] == "potion" and prize["known"]:
            assert prize["target"] in known_potions, row["monster"]


def test_gold_and_none_prizes_have_no_target():
    for row in load_monster_hunting():
        if row["prize"]["kind"] in ("gold", "none"):
            assert row["prize"]["target"] is None, row["monster"]


def test_chilopendra_carries_the_issue_7_errata_not_monstrous_form():
    row = next(r for r in load_monster_hunting() if r["monster"] == "Chilopendra")
    assert row["prize"]["kind"] == "gold"
    assert row["prize"]["gold"] == 10


def test_rangifer_xp_is_zero_by_design():
    row = next(r for r in load_monster_hunting() if r["monster"] == "Rangifer")
    assert row["xp"] == 0


def test_boar_and_werewolf_bounties_match_the_bestiary():
    # These two are also recorded directly on the bestiary entry's
    # description (Bounty 10gc / 20gc) — a second, independent source that
    # should agree with the magazine table's own gc value.
    by_name = {r["monster"]: r for r in load_monster_hunting()}
    assert by_name["Boar"]["prize"] == {
        "name": "Boar tusk", "kind": "gold", "target": None, "gold": 10, "known": True,
    }
    assert by_name["Werewolf"]["prize"] == {
        "name": "Werewolf head", "kind": "gold", "target": None, "gold": 20, "known": True,
    }


def test_no_duplicate_monster_names():
    names = [r["monster"] for r in load_monster_hunting()]
    assert len(names) == len(set(names))
