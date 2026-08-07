"""Black Powder Firearms (Spellcaster Magazine, Issue 1): Pistol/Musket/
Blunderbuss and their four commissioned upgrades as real catalog items with
real gc costs — previously a "deferred mechanic" note on three soldier
catalog entries. Also covers the Spell Component Bag's caster_only exclusion
from the captain/soldier item picker, introduced alongside the firearm work."""

import game_content


def _by_name(items: list[dict], name: str) -> dict:
    row = next((it for it in items if it["name"] == name), None)
    assert row is not None, f"{name!r} not found in {[it['name'] for it in items]}"
    return row


def test_base_firearms_have_real_costs():
    items = game_content.load_standard_items()
    assert _by_name(items, "Pistol")["cost"] == 50
    assert _by_name(items, "Musket")["cost"] == 100
    assert _by_name(items, "Blunderbuss")["cost"] == 100


def test_musket_and_blunderbuss_are_two_handed():
    items = game_content.load_standard_items()
    assert _by_name(items, "Musket")["slot_cost"] == 2
    assert _by_name(items, "Blunderbuss")["slot_cost"] == 2
    assert _by_name(items, "Pistol")["slot_cost"] == 1


def test_axe_gun_is_an_upgrade_not_a_standalone_weapon():
    """Axe-gun is bought for an already-owned Pistol/Blunderbuss, not a
    catalog weapon in its own right — it shouldn't appear as one."""
    items = game_content.load_standard_items()
    names = [it["name"] for it in items]
    assert "Axe-gun" not in names
    row = _by_name(items, "Axe-gun (Firearm Upgrade)")
    assert row["cost"] == 250
    assert row["category"] == "Gear"


def test_all_four_firearm_upgrades_exist_with_book_costs():
    items = game_content.load_standard_items()
    costs = {
        "Double-barrelled (Firearm Upgrade)": 400,
        "Axe-gun (Firearm Upgrade)": 250,
        "Superior Craftsmanship (Firearm Upgrade)": 300,
        "Silver Bullets (Firearm Upgrade)": 250,
    }
    for name, cost in costs.items():
        row = _by_name(items, name)
        assert row["cost"] == cost
        assert row["category"] == "Gear"
        assert row["source"] == "Spellcaster Magazine"


def test_musketeer_coachman_duellist_no_longer_call_firearms_deferred():
    """These three soldiers' catalog notes used to say firearm rules were a
    deferred mechanic — stale now that Pistol/Musket/Blunderbuss are real
    purchasable, costed items."""
    from frostgrave_data import SOLDIERS

    for key in ("musketeer", "coachman", "duellist"):
        text = (SOLDIERS[key]["notes"] + SOLDIERS[key]["description"]).lower()
        assert "deferred" not in text


def test_spell_component_bag_is_caster_only():
    items = game_content.load_standard_items()
    assert _by_name(items, "Spell Component Bag")["caster_only"] is True
    # Everything else defaults to not caster-only.
    assert _by_name(items, "Pistol")["caster_only"] is False


def test_spellcaster_items_still_include_the_component_bag():
    """Wizard/apprentice pickers must keep offering it — only the
    captain/soldier picker excludes it."""
    names = [it["name"] for it in game_content.load_spellcaster_items()]
    assert "Spell Component Bag" in names


def test_soldier_capable_items_excludes_the_component_bag():
    """A captain/soldier has nowhere to put spell components, so it's
    meaningless gear for them — excluded from their item picker."""
    names = [it["name"] for it in game_content.load_soldier_capable_items()]
    assert "Spell Component Bag" not in names


def test_soldier_capable_items_still_includes_armour_and_firearms():
    """The captain/soldier list must stay a superset of everything except
    caster_only gear — armour (wizard/apprentice-excluded the other way,
    via spellcaster_allowed) and firearms both still belong here."""
    names = [it["name"] for it in game_content.load_soldier_capable_items()]
    assert "Shield" in names
    assert "Pistol" in names
    assert "Musket" in names


def test_buy_standard_item_needs_firearms_rules_enabled(fresh_warband):
    """firearms_rules_enabled gates purchases the same as the source-book
    toggle does — switching it off must not leave base firearms buyable."""
    import warband_store

    wb = fresh_warband
    wb["homerules"]["enabled_sources"]["Spellcaster Magazine"] = True
    wb["homerules"]["firearms_rules_enabled"] = False
    wb["gold"] = 1000
    ok, msg = warband_store.buy_standard_item(wb, "Pistol")
    assert not ok
    assert "Firearms Rules" in msg

    wb["homerules"]["firearms_rules_enabled"] = True
    ok, msg = warband_store.buy_standard_item(wb, "Pistol")
    assert ok


def test_upgrade_firearm_needs_firearms_rules_enabled(fresh_warband):
    import warband_store

    wb = fresh_warband
    wb["homerules"]["enabled_sources"]["Spellcaster Magazine"] = True
    wb["gold"] = 1000
    ok, _ = warband_store.buy_standard_item(wb, "Pistol")
    assert ok

    wb["homerules"]["firearms_rules_enabled"] = False
    ok, msg = warband_store.upgrade_firearm(wb, "Pistol", "Double-barrelled (Firearm Upgrade)")
    assert not ok
    assert "Firearms Rules" in msg


def test_filtered_standard_items_hides_firearms_when_rules_disabled(fresh_warband):
    """app.py's _filtered_standard_items() drives the Workshop panel, the
    upgrade table, and the item-slot picker's primary list alike — the
    firearm base items and their upgrade items must all disappear together."""
    import app as app_module

    wb = fresh_warband
    hr = wb["homerules"]
    hr["firearms_rules_enabled"] = False
    items = app_module._filtered_standard_items(game_content.load_standard_items(), hr)
    names = [it["name"] for it in items]
    assert "Pistol" not in names
    assert "Musket" not in names
    assert "Blunderbuss" not in names
    assert "Double-barrelled (Firearm Upgrade)" not in names

    hr["firearms_rules_enabled"] = True
    items = app_module._filtered_standard_items(game_content.load_standard_items(), hr)
    names = [it["name"] for it in items]
    assert "Pistol" in names
    assert "Double-barrelled (Firearm Upgrade)" in names
