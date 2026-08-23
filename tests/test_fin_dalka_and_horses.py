"""Blood Legacy's Grimoire of Fin Dalka and Spellcaster Magazine's Horses in
Frostgrave — both previously reference-only Lexicon entries, now real,
interactive mechanics."""

import expansions
import warband_store
from frostgrave_data import BASE_LOCATIONS, FIN_DALKA_ITEM_NAME, fin_dalka_spell_ids

# --- Grimoire of Fin Dalka ----------------------------------------------------
#
# Ownership is derived from the vault (see expansions.fin_dalka_owned()) —
# found/bought like any other magic item — so tests give it to the warband
# via add_vault_item() rather than a dedicated acquire action.


def test_fin_dalka_owned_reflects_vault_contents(fresh_warband):
    wb = fresh_warband
    assert not expansions.fin_dalka_owned(wb)
    warband_store.add_vault_item(wb, FIN_DALKA_ITEM_NAME)
    assert expansions.fin_dalka_owned(wb)


def test_fin_dalka_owned_with_book_suffix_from_loot_picker(fresh_warband):
    """The "pick from a rulebook" loot picker (warband_view.html's
    composeRow()) appends " (<book>)" to whatever item it fills into the
    Vault's Add item field, same as any other magic item — the natural way
    the help text tells a player to add this one. Ownership must still be
    recognized, not just the bare-name case add_vault_item() uses above."""
    wb = fresh_warband
    warband_store.add_vault_item(wb, f"{FIN_DALKA_ITEM_NAME} (Blood Legacy)")
    assert expansions.fin_dalka_owned(wb)


def test_sell_fin_dalka_grimoire_removes_book_suffixed_vault_entry(fresh_warband):
    wb = fresh_warband
    wb["homerules"]["enabled_sources"]["Blood Legacy"] = True
    warband_store.add_vault_item(wb, f"{FIN_DALKA_ITEM_NAME} (Blood Legacy)")
    ok, msg = warband_store.sell_fin_dalka_grimoire(wb)
    assert ok, msg
    assert not expansions.fin_dalka_owned(wb)


def test_fin_dalka_decipher_requires_blood_legacy(fresh_warband):
    wb = fresh_warband
    wb["homerules"]["enabled_sources"]["Blood Legacy"] = False
    warband_store.add_vault_item(wb, FIN_DALKA_ITEM_NAME)
    sid = fin_dalka_spell_ids()[0]
    ok, msg = warband_store.fin_dalka_decipher(wb, sid, "success")
    assert not ok
    assert "blood legacy" in msg.lower()


def test_fin_dalka_decipher_requires_ownership(fresh_warband):
    wb = fresh_warband
    wb["homerules"]["enabled_sources"]["Blood Legacy"] = True
    sid = fin_dalka_spell_ids()[0]
    ok, msg = warband_store.fin_dalka_decipher(wb, sid, "success")
    assert not ok
    assert "doesn't own" in msg.lower()


def test_fin_dalka_decipher_success_learns_spell_and_costs_gold(fresh_warband):
    wb = fresh_warband
    wb["homerules"]["enabled_sources"]["Blood Legacy"] = True
    wb["gold"] = 1000
    warband_store.add_vault_item(wb, FIN_DALKA_ITEM_NAME)
    sid = fin_dalka_spell_ids()[0]
    ok, msg = warband_store.fin_dalka_decipher(wb, sid, "success")
    assert ok, msg
    assert wb["gold"] == 900
    assert any(s["id"] == sid for s in wb["wizard"]["spells"])


def test_fin_dalka_fail_adds_cumulative_bonus(fresh_warband):
    wb = fresh_warband
    wb["homerules"]["enabled_sources"]["Blood Legacy"] = True
    wb["gold"] = 1000
    warband_store.add_vault_item(wb, FIN_DALKA_ITEM_NAME)
    sid = fin_dalka_spell_ids()[0]
    warband_store.fin_dalka_decipher(wb, sid, "fail")
    ok, msg = warband_store.fin_dalka_decipher(wb, sid, "fail")
    assert ok, msg
    assert wb["wizard"]["fin_dalka"]["attempts"][sid]["bonus"] == 2


def test_fin_dalka_natural_1_locks_spell_forever(fresh_warband):
    wb = fresh_warband
    wb["homerules"]["enabled_sources"]["Blood Legacy"] = True
    wb["gold"] = 1000
    warband_store.add_vault_item(wb, FIN_DALKA_ITEM_NAME)
    sid = fin_dalka_spell_ids()[0]
    warband_store.fin_dalka_decipher(wb, sid, "nat1")
    ok, msg = warband_store.fin_dalka_decipher(wb, sid, "success")
    assert not ok
    assert "locked" in msg.lower()


def test_fin_dalka_sell_price_drops_per_learned_spell(fresh_warband):
    wb = fresh_warband
    wb["homerules"]["enabled_sources"]["Blood Legacy"] = True
    wb["gold"] = 1000
    warband_store.add_vault_item(wb, FIN_DALKA_ITEM_NAME)
    sid = fin_dalka_spell_ids()[0]
    warband_store.fin_dalka_decipher(wb, sid, "success")
    before = wb["gold"]
    ok, msg = warband_store.sell_fin_dalka_grimoire(wb)
    assert ok, msg
    assert wb["gold"] == before + 900
    assert not expansions.fin_dalka_owned(wb)


# --- Horses in Frostgrave -----------------------------------------------------


def _give_stable(wb):
    loc = next(k for k in BASE_LOCATIONS if k != "none")
    warband_store.set_base_location(wb, loc)
    return warband_store.buy_base_resource(wb, "stable")


def test_horse_requires_spellcaster_magazine(fresh_warband):
    wb = fresh_warband
    wb["homerules"]["enabled_sources"]["Spellcaster Magazine"] = False
    ok, msg = warband_store.buy_horse(wb)
    assert not ok
    assert "spellcaster magazine" in msg.lower()


def test_horse_requires_stable(fresh_warband):
    wb = fresh_warband
    wb["gold"] = 1000
    ok, msg = warband_store.buy_horse(wb)
    assert not ok
    assert "stable" in msg.lower()


def test_mounting_applies_and_reverts_stat_delta(fresh_warband):
    wb = fresh_warband
    wb["homerules"]["enabled_sources"]["Spellcaster Magazine"] = True
    wb["gold"] = 1000
    ok, msg = _give_stable(wb)
    assert ok, msg
    ok, msg = warband_store.buy_horse(wb)
    assert ok, msg
    before_move = wb["wizard"]["stats"]["move"]
    before_fight = wb["wizard"]["stats"]["fight"]
    before_armour = wb["wizard"]["stats"]["armour"]
    ok, msg = warband_store.mount_horse(wb, "wizard")
    assert ok, msg
    assert wb["wizard"]["stats"]["move"] == before_move + 2
    assert wb["wizard"]["stats"]["fight"] == before_fight + 1
    assert wb["wizard"]["stats"]["armour"] == before_armour - 2
    ok, msg = warband_store.dismount_horse(wb)
    assert ok, msg
    assert wb["wizard"]["stats"]["move"] == before_move
    assert wb["wizard"]["stats"]["fight"] == before_fight
    assert wb["wizard"]["stats"]["armour"] == before_armour


def test_mounting_someone_new_auto_dismounts_previous_rider(fresh_warband):
    wb = fresh_warband
    wb["homerules"]["enabled_sources"]["Spellcaster Magazine"] = True
    wb["gold"] = 1000
    _give_stable(wb)
    warband_store.buy_horse(wb)
    warband_store.add_soldier(wb, "thug")
    sid = wb["soldiers"][0]["id"]
    before_wiz_move = wb["wizard"]["stats"]["move"]
    warband_store.mount_horse(wb, "wizard")
    ok, msg = warband_store.mount_horse(wb, "soldier", sid)
    assert ok, msg
    assert wb["wizard"]["stats"]["move"] == before_wiz_move
    assert wb["soldiers"][0]["move"] == warband_store.get_soldier("thug")["move"] + 2


def test_ineligible_soldier_cannot_mount(fresh_warband):
    wb = fresh_warband
    wb["homerules"]["enabled_sources"]["Spellcaster Magazine"] = True
    wb["gold"] = 1000
    _give_stable(wb)
    warband_store.buy_horse(wb)
    warband_store.add_soldier(wb, "war_hound")
    sid = wb["soldiers"][0]["id"]
    ok, msg = warband_store.mount_horse(wb, "soldier", sid)
    assert not ok


def test_removing_mounted_soldier_clears_rider(fresh_warband):
    wb = fresh_warband
    wb["homerules"]["enabled_sources"]["Spellcaster Magazine"] = True
    wb["gold"] = 1000
    _give_stable(wb)
    warband_store.buy_horse(wb)
    warband_store.add_soldier(wb, "thug")
    sid = wb["soldiers"][0]["id"]
    warband_store.mount_horse(wb, "soldier", sid)
    warband_store.remove_soldier(wb, sid)
    assert wb["horse"]["rider"] is None
