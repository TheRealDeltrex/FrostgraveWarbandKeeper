"""Captain promotion homerules: promote_captain_specialist_only (off by
default) restricts promote_soldier_to_captain to specialist soldiers."""

import warband_store


def _setup(wb):
    wb["homerules"]["captain_mode"] = "promote"


def test_specialist_only_off_by_default(fresh_warband):
    wb = fresh_warband
    _setup(wb)
    assert wb["homerules"]["promote_captain_specialist_only"] is False


def test_non_specialist_blocked_when_specialist_only_enabled(fresh_warband):
    wb = fresh_warband
    _setup(wb)
    wb["homerules"]["promote_captain_specialist_only"] = True
    ok, msg = warband_store.add_soldier(wb, "thug", "Grunt")
    assert ok, msg
    soldier = wb["soldiers"][0]

    ok, msg = warband_store.promote_soldier_to_captain(wb, soldier["id"], tricks=["furious_attack", "riposte"])
    assert not ok
    assert "specialist" in msg.lower()
    assert wb["captain"] is None


def test_specialist_allowed_when_specialist_only_enabled(fresh_warband):
    wb = fresh_warband
    _setup(wb)
    wb["homerules"]["promote_captain_specialist_only"] = True
    ok, msg = warband_store.add_soldier(wb, "archer", "Sharpshooter")
    assert ok, msg
    soldier = wb["soldiers"][0]

    ok, msg = warband_store.promote_soldier_to_captain(wb, soldier["id"], tricks=["furious_attack", "riposte"])
    assert ok, msg
    assert wb["captain"] is not None


def test_non_specialist_allowed_when_toggle_off(fresh_warband):
    wb = fresh_warband
    _setup(wb)
    ok, msg = warband_store.add_soldier(wb, "thug", "Grunt")
    assert ok, msg
    soldier = wb["soldiers"][0]

    ok, msg = warband_store.promote_soldier_to_captain(wb, soldier["id"], tricks=["furious_attack", "riposte"])
    assert ok, msg
    assert wb["captain"] is not None


def test_construct_never_promotable_even_when_forced_specialist(fresh_warband):
    """Constructs are blocked from promotion outright (see
    _promotion_blocked_reason), regardless of specialist status — a Projectile
    Weapon-modified construct becoming a specialist via forced_specialist must
    not create a loophole around the construct ban."""
    wb = fresh_warband
    _setup(wb)
    wb["wizard"]["spells"].append({"name": "Animate Construct"})
    ok, msg = warband_store.add_soldier(wb, "small_construct", "Bolt")
    assert ok, msg
    soldier = wb["soldiers"][0]

    ok, msg = warband_store.add_construct_modification(wb, soldier["id"], "Projectile Weapon", "will")
    assert ok, msg
    assert soldier.get("forced_specialist")

    ok, msg = warband_store.promote_soldier_to_captain(wb, soldier["id"], tricks=["furious_attack", "riposte"])
    assert not ok
    assert "construct" in msg.lower()


def test_animal_companion_cannot_be_promoted(fresh_warband):
    wb = fresh_warband
    _setup(wb)
    wb["wizard"]["spells"].append({"name": "Animal Companion"})
    ok, msg = warband_store.add_soldier(wb, "companion_wolf", "Fang")
    assert ok, msg
    soldier = wb["soldiers"][0]

    ok, msg = warband_store.promote_soldier_to_captain(wb, soldier["id"], tricks=["furious_attack", "riposte"])
    assert not ok
    assert "animal" in msg.lower()


def test_construct_hound_cannot_be_promoted(fresh_warband):
    """Bought outright (no requires_spell), but the same creature as
    construct_hound_summoned — must still be blocked."""
    wb = fresh_warband
    _setup(wb)
    ok, msg = warband_store.add_soldier(wb, "construct_hound", "Rex")
    assert ok, msg
    soldier = wb["soldiers"][0]

    ok, msg = warband_store.promote_soldier_to_captain(wb, soldier["id"], tricks=["furious_attack", "riposte"])
    assert not ok


def test_war_hound_cannot_be_promoted(fresh_warband):
    wb = fresh_warband
    _setup(wb)
    ok, msg = warband_store.add_soldier(wb, "war_hound", "Fido")
    assert ok, msg
    soldier = wb["soldiers"][0]

    ok, msg = warband_store.promote_soldier_to_captain(wb, soldier["id"], tricks=["furious_attack", "riposte"])
    assert not ok


def test_temporary_member_cannot_be_promoted(fresh_warband):
    wb = fresh_warband
    _setup(wb)
    wb["wizard"]["spells"].append({"name": "Raise Zombie"})
    ok, msg = warband_store.add_soldier(wb, "raised_zombie", "Shambler")
    assert ok, msg
    soldier = wb["soldiers"][0]

    ok, msg = warband_store.promote_soldier_to_captain(wb, soldier["id"], tricks=["furious_attack", "riposte"])
    assert not ok
    assert "temporary" in msg.lower()


def test_promoted_captain_gets_default_hired_equipment(fresh_warband):
    """A promoted captain gets the same default starting gear as a hired one
    (CAPTAIN_DEFAULT_GEAR) — the promoted soldier's own equipment doesn't
    carry over onto the new Captain."""
    wb = fresh_warband
    _setup(wb)
    ok, msg = warband_store.add_soldier(wb, "thug", "Grunt")
    assert ok, msg
    soldier = wb["soldiers"][0]
    soldier["items"] = ["Dagger", "Dagger"]

    ok, msg = warband_store.promote_soldier_to_captain(wb, soldier["id"], tricks=["furious_attack", "riposte"])
    assert ok, msg
    hired_cap = warband_store.empty_captain("X", wb["homerules"])
    assert wb["captain"]["item_slots"] == hired_cap["item_slots"]
