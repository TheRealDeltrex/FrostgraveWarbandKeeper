"""G3: after-game XP is clamped/level-synced like any other XP change.
G4: reversing a level-up must not be blocked by a stat that was independently
lowered below its starting value (e.g. by a mutation).
G5: breaking a pact must actually cost XP and report the true Health delta."""

import expansions
import warband_store


def test_after_game_negative_xp_clamps_and_reverses(fresh_warband):
    wb = fresh_warband
    wiz = wb["wizard"]
    wiz["xp"] = 300
    wiz["level"] = 3
    wiz["stats"]["fight"] = wiz["stats"].get("fight", 0) + 3
    wiz["level_history"] = [
        {"level": i + 1, "choice": "fight", "detail": "+1 Fight", "stat": "fight"} for i in range(3)
    ]

    summary = warband_store.record_game_loot(wb, gold=0, items=[], xp=-500)
    assert wiz["xp"] == 0, "XP must floor at 0, never go negative"
    assert wiz["level"] == 0, "levels no longer earned by XP must auto-reverse"
    assert "+-" not in summary, "sign formatting must not produce a double sign"


def test_reverse_after_stat_lowered_below_base(fresh_warband):
    wb = fresh_warband
    wiz = wb["wizard"]
    stats = wiz["stats"]
    base_fight = stats["fight"]
    stats["fight"] = base_fight - 1  # simulate a mutation/state lowering the stat

    wiz["xp"] = 100
    ok, msg = warband_store.apply_level_up(wb, "fight")
    assert ok, msg
    raised = stats["fight"]
    assert raised == base_fight  # -1 then +1

    ok, msg = warband_store.reverse_last_level_up(wb)
    assert ok, msg
    assert stats["fight"] == raised - 1


def test_break_pact_penalty_costs_xp_and_reports_true_health_delta(fresh_warband):
    wb = fresh_warband
    wiz = wb["wizard"]
    wiz["level"] = 10
    wiz["xp"] = 1000
    wiz["level_history"] = [
        {"level": i + 1, "choice": "health", "detail": "+1 Health", "stat": "health"} for i in range(10)
    ]
    wiz["stats"]["health"] = wiz["stats"].get("health", 14) + 10
    wiz["state"] = {
        "kind": expansions.STATE_PACT,
        "tier": 1,
        "feature": None,
        "demon": "",
        "pacts": [{"sacrifice": "s1", "boon": "b1"}],
    }

    health_before = wiz["stats"]["health"]
    xp_before = wiz["xp"]
    ok, msg = warband_store.break_wizard_pact(wb)
    assert ok, msg
    assert wiz["xp"] < xp_before, "the level penalty must actually cost XP, not be free"
    health_after = wiz["stats"]["health"]
    reported = health_before - health_after
    assert f"−{reported} Health" in msg, "reported Health loss must match the real delta"


def test_grimoire_marking_reads_both_vault_name_shapes(fresh_warband):
    """Core Rules p.84: a new spell needs a grimoire in the vault. The Shop
    stores "Grimoire: Bone Dart (Elementalist)", the loot tables store
    "Grimoire of Bone Dart", and neither a bare "Grimoire" nor the base
    resource's "Grimoire (random)" names a spell at all."""
    wb = fresh_warband
    wb["vault_items"] = [
        {"name": "Grimoire: Bone Dart (Elementalist)"},
        {"name": "Grimoire of Plague of Insects"},
        {"name": "Grimoire (random)"},
        {"name": "Grimoire"},
        {"name": "Scroll of Leap"},
    ]
    assert expansions.vault_grimoire_spells(wb) == {"bone dart", "plague of insects"}
    assert expansions.has_grimoire_for(wb, "Bone Dart")
    assert expansions.has_grimoire_for(wb, "plague of insects")
    assert not expansions.has_grimoire_for(wb, "Leap")


def test_learning_without_a_grimoire_is_warned_not_refused(fresh_warband):
    """The app warns and lets the player confirm; it never blocks the pick."""
    wb = fresh_warband
    wiz = wb["wizard"]
    wiz["xp"] = 1000
    wiz["level"] = 0
    wb["vault_items"] = []
    known = {s["id"] for s in wiz["spells"]}
    target = next(s for s in warband_store.all_spells_flat() if s["id"] not in known)
    ok, msg = warband_store.apply_level_up(wb, "learn_spell", spell_key=target["id"])
    assert ok, msg
    assert any(s["id"] == target["id"] for s in wiz["spells"])


def test_level_up_picker_marks_spells_with_no_grimoire(fresh_warband):
    """The marker and the confirm hook must survive rendering, not just exist
    in the context."""
    import re

    import app as app_module

    wb = fresh_warband
    wiz = wb["wizard"]
    wiz["xp"] = 1000
    known = {s["id"] for s in wiz["spells"]}
    have = next(s for s in warband_store.all_spells_flat() if s["id"] not in known)
    wb["vault_items"] = [{"id": "v1", "name": f"Grimoire: {have['name']} ({have['school']})"}]
    warband_store.save_warband(wb)

    client = app_module.app.test_client()
    html = client.get(f"/warband/{wb['id']}", headers={"Host": "127.0.0.1:5000"}).get_data(as_text=True)
    block = html[html.index('id="learn_spell"') :]
    block = block[: block.index("</select>")]
    options = [o.strip() for o in re.findall(r"<option[^>]*>\s*([^\n<]+)", block)]

    held = [o for o in options if "no grimoire" not in o]
    assert len(held) == 1 and held[0].startswith(have["name"])
    assert len(options) > 1, "every other learnable spell should be marked"
    assert 'onsubmit="return confirmLevelUp();"' in html
