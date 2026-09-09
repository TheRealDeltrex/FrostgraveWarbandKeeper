"""The Red King's artefacts (pp.76-77) do nothing until a post-game Will Roll
unlocks them. The app records that outcome; it does not roll it, since the
target number is printed per item and the roll happens at the table."""

import re

import app as app_module
import expansions
import warband_store


def test_only_red_king_artefacts_are_recognised():
    assert expansions.is_artefact("Wraith Bow")
    # The loot picker composes names with their book.
    assert expansions.is_artefact("Wraith Bow (The Red King)")
    assert not expansions.is_artefact("Potion of Healing")
    assert not expansions.is_artefact("Construct Hammer")
    assert not expansions.is_artefact("")


def test_activation_round_trips_through_a_save(fresh_warband):
    wb = fresh_warband
    wb["vault_items"] = [{"id": "a1", "name": "Wraith Bow"}]

    ok, msg = warband_store.set_vault_item_activated(wb, "a1", True)
    assert ok, msg
    warband_store.save_warband(wb)
    # _normalize_vault_items() rebuilds each entry, so this is the real check.
    assert warband_store.load_warband(wb["id"])["vault_items"][0]["activated"] is True

    ok, msg = warband_store.set_vault_item_activated(wb, "a1", False)
    assert ok, msg
    warband_store.save_warband(wb)
    assert "activated" not in warband_store.load_warband(wb["id"])["vault_items"][0]


def test_unknown_item_is_reported_not_silently_ignored(fresh_warband):
    ok, msg = warband_store.set_vault_item_activated(fresh_warband, "nope", True)
    assert not ok and "not found" in msg.lower()


def test_the_vault_offers_the_toggle_only_on_artefacts(fresh_warband):
    wb = fresh_warband
    wb["vault_items"] = [
        {"id": "a1", "name": "Wraith Bow"},
        {"id": "a2", "name": "Potion of Healing"},
    ]
    warband_store.save_warband(wb)
    client = app_module.app.test_client()
    url = f"/warband/{wb['id']}"
    headers = {"Host": "127.0.0.1:5000"}

    page = client.get(url, headers=headers).get_data(as_text=True)
    assert page.count('value="toggle_vault_activated"') == 1
    assert "(activated)" not in page

    client.post(
        url + "/update",
        headers={**headers, "Referer": "http://127.0.0.1:5000/"},
        data={"action": "toggle_vault_activated", "item_id": "a1", "activated": "on"},
        follow_redirects=True,
    )
    page = client.get(url, headers=headers).get_data(as_text=True)
    assert re.search(r"Wraith Bow \(activated\)", page)
    assert "Deactivate" in page
