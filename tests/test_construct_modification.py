"""Fireheart's Construct Modification: exactly one modification per standard
small/medium/large construct, most costing a permanent -1 to a chosen stat."""

import warband_store
from game_content import construct_modifications

# The only entries whose effect is an unconditional change to the printed stat
# line. Pinned as a literal so widening the set has to be a deliberate edit —
# a situational bonus that leaks a stat_delta silently inflates a real stat
# (the Projectile Shield trap: its "+2 Armour" only applies vs. projectiles).
AUTO_APPLIED = {
    "Armour Plating": {"armour": {"add": 1}},
    "Construct Oil": {"move": {"add": 1}},
    "Improved Joints": {"fight": {"add": 1}},
    "Improved Resistance": {"will": {"add": 1}},
    "Projectile Weapon": {"shoot": {"min": 2}},
}


def test_only_unconditional_effects_are_auto_applied():
    applied = {m["name"]: m["stat_delta"] for m in construct_modifications() if m["stat_delta"]}
    assert applied == AUTO_APPLIED


def test_situational_effects_never_touch_the_stat_line():
    """Anything qualified by circumstance stays text-only however numeric it
    reads — "vs. <target>", "while ...", or a once-per-game trigger."""
    for m in construct_modifications():
        text = m["text"].lower()
        if any(k in text for k in ("vs.", "while", "once/game", "whenever")):
            assert m["stat_delta"] is None, f"{m['name']} is situational but carries a stat_delta"


def test_every_table_entry_has_authored_metadata():
    """A modification missing from the meta file would silently read as
    "no auto effect" rather than failing loudly."""
    from game_content import load_construct_modification_meta

    meta = load_construct_modification_meta()
    missing = [m["name"] for m in construct_modifications() if m["name"] not in meta]
    assert not missing, f"no metadata authored for: {missing}"


def _hire_small_construct(wb, name="Bolt"):
    wb["wizard"]["spells"].append({"name": "Animate Construct"})
    ok, msg = warband_store.add_soldier(wb, "small_construct", name)
    assert ok, msg
    return wb["soldiers"][0]


def test_add_and_remove_modification_with_penalty(fresh_warband):
    wb = fresh_warband
    soldier = _hire_small_construct(wb)
    before_fight = soldier["fight"]

    # "Armour Plating" has a clean, unconditional +1 Armour effect, so it's
    # auto-applied (construct_modification_meta.json), on top of the universal
    # -1 penalty on a stat of the owner's choice.
    ok, msg = warband_store.add_construct_modification(wb, soldier["id"], "Armour Plating", "fight")
    assert ok, msg
    assert soldier["armour"] == 12  # small_construct catalog Armour (11) + 1
    assert soldier["fight"] == before_fight - 1
    assert soldier["modifications"][0]["name"] == "Armour Plating"
    assert "-1" in soldier["modifications"][0]["short"]

    ok, msg = warband_store.remove_construct_modification(wb, soldier["id"], 0)
    assert ok, msg
    assert soldier["fight"] == before_fight
    assert soldier["armour"] == 11  # restored to the small_construct catalog value
    assert soldier["modifications"] == []


def test_clean_stat_effect_applies_without_a_penalty_stat(fresh_warband):
    wb = fresh_warband
    soldier = _hire_small_construct(wb)

    ok, msg = warband_store.add_construct_modification(wb, soldier["id"], "Armour Plating")
    assert not ok, "should still require a penalty-stat pick"
    assert soldier.get("armour", 11) == 11, "the auto effect must be rolled back when the call is rejected"


def test_no_penalty_modification_needs_no_stat(fresh_warband):
    wb = fresh_warband
    soldier = _hire_small_construct(wb)
    before_fight = soldier["fight"]
    before_will = soldier["will"]
    before_health = soldier["health"]

    ok, msg = warband_store.add_construct_modification(wb, soldier["id"], "Impact Absorbers")
    assert ok, msg
    assert soldier["fight"] == before_fight
    assert soldier["will"] == before_will
    assert soldier["health"] == before_health
    assert "move" not in soldier
    assert "armour" not in soldier


def test_penalty_may_take_will_negative(fresh_warband):
    """Every standard construct has Will 0, and Frostgrave prints Will negative
    (the catalog's thug/war hound/construct hound all do) — so the mandatory -1
    must actually bite here rather than flooring at 0 and costing nothing."""
    wb = fresh_warband
    soldier = _hire_small_construct(wb)
    assert soldier["will"] == 0

    ok, msg = warband_store.add_construct_modification(wb, soldier["id"], "Armour Plating", "will")
    assert ok, msg
    assert soldier["will"] == -1

    ok, msg = warband_store.remove_construct_modification(wb, soldier["id"], 0)
    assert ok, msg
    assert soldier["will"] == 0


def test_penalized_modification_requires_a_stat_choice(fresh_warband):
    wb = fresh_warband
    soldier = _hire_small_construct(wb)
    ok, msg = warband_store.add_construct_modification(wb, soldier["id"], "Armour Plating")
    assert not ok
    assert soldier["modifications"] == []


def test_construct_may_only_take_one_modification(fresh_warband):
    wb = fresh_warband
    soldier = _hire_small_construct(wb)
    ok, msg = warband_store.add_construct_modification(wb, soldier["id"], "Armour Plating", "armour")
    assert ok, msg
    ok, msg = warband_store.add_construct_modification(wb, soldier["id"], "Improved Resistance")
    assert not ok
    assert len(soldier["modifications"]) == 1


def test_non_standard_construct_cannot_be_modified(fresh_warband):
    wb = fresh_warband
    wb["wizard"]["spells"].append({"name": "Animate Construct"})
    ok, msg = warband_store.add_soldier(wb, "construct_hound_summoned", "Rex")
    assert ok, msg
    hound = wb["soldiers"][0]

    ok, msg = warband_store.add_construct_modification(wb, hound["id"], "Improved Resistance")
    assert not ok


def test_size_restricted_modification_is_rejected(fresh_warband):
    wb = fresh_warband
    wb["wizard"]["spells"].append({"name": "Animate Construct"})
    ok, msg = warband_store.add_soldier(wb, "large_construct", "Golem")
    assert ok, msg
    large = wb["soldiers"][0]

    # "Improved Joints" (+1 Fight) is explicitly "not usable on large constructs".
    ok, msg = warband_store.add_construct_modification(wb, large["id"], "Improved Joints", "will")
    assert not ok
    assert large["modifications"] == []


def test_fireheart_disabled_blocks_modification(fresh_warband):
    wb = fresh_warband
    soldier = _hire_small_construct(wb)
    wb["homerules"]["enabled_sources"]["Fireheart"] = False

    ok, msg = warband_store.add_construct_modification(wb, soldier["id"], "Improved Resistance")
    assert not ok


def test_projectile_weapon_raises_shoot_and_makes_small_construct_a_specialist(fresh_warband):
    wb = fresh_warband
    soldier = _hire_small_construct(wb)
    assert soldier["shoot"] == 0
    assert warband_store.enrich_soldier(wb, soldier)["category"] == "standard"

    ok, msg = warband_store.add_construct_modification(wb, soldier["id"], "Projectile Weapon", "will")
    assert ok, msg
    assert soldier["shoot"] == 2  # raised to the modification's floor
    assert warband_store.enrich_soldier(wb, soldier)["category"] == "specialist"
    assert warband_store.specialist_count(wb) == 1
    assert "now counts as a specialist" in soldier["modifications"][0]["short"].lower()

    ok, msg = warband_store.remove_construct_modification(wb, soldier["id"], 0)
    assert ok, msg
    assert soldier["shoot"] == 0
    assert warband_store.enrich_soldier(wb, soldier)["category"] == "standard"
    assert warband_store.specialist_count(wb) == 0


def test_projectile_weapon_never_lowers_a_higher_shoot(fresh_warband):
    """Shoot is "raised to +2 if lower" — never a plain set, which would wrongly
    lower a construct whose Shoot was already boosted above 2 some other way."""
    wb = fresh_warband
    soldier = _hire_small_construct(wb)
    soldier["shoot"] = 4

    ok, msg = warband_store.add_construct_modification(wb, soldier["id"], "Projectile Weapon", "will")
    assert ok, msg
    assert soldier["shoot"] == 4


def test_projectile_weapon_does_not_relabel_an_already_specialist_large_construct(fresh_warband):
    wb = fresh_warband
    wb["wizard"]["spells"].append({"name": "Animate Construct"})
    ok, msg = warband_store.add_soldier(wb, "large_construct", "Golem")
    assert ok, msg
    large = wb["soldiers"][0]

    ok, msg = warband_store.add_construct_modification(wb, large["id"], "Projectile Weapon", "will")
    assert ok, msg
    assert not large.get("forced_specialist")
    # The rulebook text itself mentions "specialist soldiers" (it's talking
    # about small/medium), but the app's own "Now counts as..." note — added
    # only when the modification actually changes a construct's status —
    # must not appear here, since Large already was one.
    assert "now counts as a specialist" not in large["modifications"][0]["short"].lower()


def test_specialist_overflow_from_a_modification_is_flagged_not_blocked(fresh_warband):
    """The app doesn't forcibly resolve an over-cap warband — that's the
    warband_limits()/PDF banner's job, not add_construct_modification's."""
    wb = fresh_warband
    wb["homerules"]["max_specialists"] = 0
    soldier = _hire_small_construct(wb)

    ok, msg = warband_store.add_construct_modification(wb, soldier["id"], "Projectile Weapon", "will")
    assert ok, msg
    limits = warband_store.warband_limits(wb)
    assert limits["specialists"] == 1
    assert limits["max_specialists"] == 0
    assert not limits["specialists_ok"]


def test_max_soldiers_and_specialists_are_house_ruleable_at_creation():
    from frostgrave_data import spell_id

    school = "Elementalist"
    spells = [
        spell_id(school, "Wall"), spell_id(school, "Elemental Bolt"), spell_id(school, "Elemental Shield"),
        spell_id("Chronomancer", "Fast Act"), spell_id("Enchanter", "Enchant Weapon"),
        spell_id("Summoner", "Leap"), spell_id("Necromancer", "Bone Dart"), spell_id("Thaumaturge", "Heal"),
    ]
    wb, msg = warband_store.create_warband(
        "Big Warband", "W", school, spells, max_soldiers=12, max_specialists=6,
    )
    assert wb, msg
    assert wb["homerules"]["max_soldiers"] == 12
    assert wb["homerules"]["max_specialists"] == 6
    import expansions
    assert expansions.max_soldiers(wb) == 12
    assert expansions.max_specialists(wb) == 6


def test_max_soldiers_and_specialists_editable_via_homerules(fresh_warband):
    from werkzeug.datastructures import ImmutableMultiDict

    wb = fresh_warband
    form = ImmutableMultiDict({"max_soldiers": "10", "max_specialists": "5"})
    ok, msg = warband_store.update_homerules(wb, form)
    assert ok, msg
    assert wb["homerules"]["max_soldiers"] == 10
    assert wb["homerules"]["max_specialists"] == 5
