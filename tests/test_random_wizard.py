"""The "Random wizard" button on the creation page (core rules only):
warband_store.random_core_wizard() must always produce a legal, Core-Rules
starting spell set and honour exclude_school."""

import random

import warband_store
from frostgrave_data import SCHOOLS


def test_random_core_wizard_is_always_legal():
    random.seed(1)
    for _ in range(200):
        school, keys, names = warband_store.random_core_wizard()
        assert school in SCHOOLS
        assert len(keys) == 8
        ok, err = warband_store.validate_starting_spells(school, keys, {"Core Rules"})
        assert ok, err
        assert names["warband_name"] and names["wizard_name"] and names["apprentice_name"]


def test_random_core_wizard_never_repeats_the_excluded_school():
    random.seed(2)
    for school in SCHOOLS:
        for _ in range(20):
            got, keys, _names = warband_store.random_core_wizard(exclude_school=school)
            assert got != school
            ok, err = warband_store.validate_starting_spells(got, keys, {"Core Rules"})
            assert ok, err


def test_random_core_wizard_output_is_accepted_by_create_warband():
    random.seed(3)
    school, keys, names = warband_store.random_core_wizard()
    wb, msg = warband_store.create_warband(
        warband_name=names["warband_name"],
        wizard_name=names["wizard_name"],
        school=school,
        spell_keys=keys,
        with_apprentice=True,
        apprentice_name=names["apprentice_name"],
    )
    assert wb, msg
    assert wb["wizard"]["school"] == school
    assert wb["apprentice"]["name"] == names["apprentice_name"]
