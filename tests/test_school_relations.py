"""H1: school_relation() must be symmetric for every ordered pair, including
the supplement schools (Vampire, Fire Giant, Rangifer, Pentangle) that only
declare relations from their own side."""

from frostgrave_data import PENTANGLE_SCHOOLS, SCHOOLS, school_relation


def test_school_relation_is_symmetric():
    all_schools = SCHOOLS + ["Vampire", "Fire Giant", "Rangifer"] + PENTANGLE_SCHOOLS
    for a in all_schools:
        for b in all_schools:
            assert school_relation(a, b) == school_relation(b, a), (a, b)


def test_starting_spell_aligned_counts_unaffected(fresh_warband):
    # The symmetry fix must not change how many aligned-school spells a core
    # wizard has to pick at creation (fresh_warband's Elementalist wizard is
    # only valid if Elementalist still requires exactly 3: Chronomancer,
    # Enchanter, Summoner — not the reciprocal Fire Giant/Astromancer links).
    from frostgrave_data import SCHOOL_RELATIONS

    assert SCHOOL_RELATIONS["Elementalist"]["aligned"] == [
        "Chronomancer", "Enchanter", "Summoner",
    ]


def test_symmetry_toggle_off_drops_the_reverse_lookup():
    # Astromancer names Elementalist aligned; Elementalist's core row never
    # names Astromancer back, so with symmetry off it reads neutral.
    assert school_relation("Astromancer", "Elementalist") == "aligned"
    assert school_relation("Elementalist", "Astromancer", False) == "neutral"
    assert school_relation("Astromancer", "Elementalist", False) == "aligned"
    # The core ten are symmetric in the table itself — unaffected either way.
    assert school_relation("Elementalist", "Illusionist", False) == "opposed"


def test_homerule_flip_recomputes_casting_numbers(fresh_warband):
    from werkzeug.datastructures import ImmutableMultiDict

    import warband_store as ws

    wb = fresh_warband
    wb["wizard"]["school"] = "Elementalist"
    wb["wizard"]["spells"] = ws.spells_from_keys(
        [ws.spell_id("Astromancer", "Alignment")], "Elementalist"
    )
    spell = wb["wizard"]["spells"][0]
    assert spell["relation"] == "aligned"
    aligned_cn = spell["cn"]

    form = ImmutableMultiDict({})  # nothing ticked = symmetry off
    ok, _ = ws.update_homerules(wb, form)
    assert ok
    assert wb["homerules"]["school_relations_symmetric"] is False
    spell = wb["wizard"]["spells"][0]
    assert spell["relation"] == "neutral"
    assert spell["cn"] > aligned_cn
