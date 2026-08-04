"""Rangifer troop types (Spellcaster Magazine, Issue 3) are only fieldable via
the Book of the Rangifer (Thaw of the Lich Lord) in the vault, at +80gc over
their listed cost — except the Rangifer Boar, which isn't hireable at all."""

import expansions
import warband_store


def _enable(wb: dict) -> None:
    wb["homerules"]["enabled_sources"]["Spellcaster Magazine"] = True
    wb["homerules"]["spellcaster_magazine_soldiers"] = True


def test_rangifer_troop_type_blocked_without_the_book(fresh_warband):
    wb = fresh_warband
    _enable(wb)
    assert expansions.soldier_state_block(wb, "rangifer_ambusher") is not None
    ok, msg = warband_store.add_soldier(wb, "rangifer_ambusher", "Scout")
    assert not ok
    assert "rangifer" in msg.lower()


def test_rangifer_troop_type_hireable_with_the_book_in_vault(fresh_warband):
    wb = fresh_warband
    _enable(wb)
    warband_store.add_vault_item(wb, "Book of the Rangifer")
    assert expansions.soldier_state_block(wb, "rangifer_ambusher") is None
    before_gold = wb["gold"]
    ok, msg = warband_store.add_soldier(wb, "rangifer_ambusher", "Scout")
    assert ok, msg
    assert wb["gold"] == before_gold - 100


def test_rangifer_boar_never_hireable(fresh_warband):
    wb = fresh_warband
    _enable(wb)
    warband_store.add_vault_item(wb, "Book of the Rangifer")
    assert expansions.soldier_state_block(wb, "rangifer_boar") is not None
    ok, msg = warband_store.add_soldier(wb, "rangifer_boar", "Tusk")
    assert not ok
