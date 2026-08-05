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
