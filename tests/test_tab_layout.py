"""The tab layout's rail and the cards it switches between must stay in step.

Each rail button names a card by id (data-tab). A renamed card id leaves a dead
tab, and a new card with no rail entry is unreachable in the tab layout, which
is the default. Neither shows up in classic, so this renders the page and checks.
"""

from __future__ import annotations

from html.parser import HTMLParser

import pytest
from test_form_nesting import _no_apprentice, _vampire, _with_apprentice_and_captain

import app as app_module
import warband_store as ws


class _Rail(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.tabs: list[str] = []
        self.cards: list[str] = []
        self.ids: set[str] = set()
        self.subtab_labels: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        a = dict(attrs)
        if a.get("id"):
            self.ids.add(a["id"])
        if tag == "button" and a.get("data-tab"):
            self.tabs.append(a["data-tab"])
        if tag == "details" and "card" in (a.get("class") or "").split() and a.get("id"):
            self.cards.append(a["id"])
        if a.get("data-subtab-label"):
            self.subtab_labels.append(a["data-subtab-label"])


@pytest.mark.parametrize(
    "build",
    [_with_apprentice_and_captain, _no_apprentice, _vampire],
    ids=["apprentice+captain", "no-apprentice", "vampire"],
)
def test_rail_and_cards_match(build):
    wb = build()
    ws.save_warband(wb)
    html = app_module.app.test_client().get(f"/warband/{wb['id']}").get_data(as_text=True)
    rail = _Rail()
    rail.feed(html)

    assert rail.tabs, "no rail rendered"
    assert [t for t in rail.tabs if t not in rail.ids] == [], "rail tab with no card"
    assert [c for c in rail.cards if c not in rail.tabs] == [], "card with no rail tab"
    assert "Level Up" in rail.subtab_labels


def test_creation_page_rail_and_cards_match():
    html = app_module.app.test_client().get("/warband/new").get_data(as_text=True)
    rail = _Rail()
    rail.feed(html)

    assert rail.tabs, "no rail rendered"
    assert [t for t in rail.tabs if t not in rail.ids] == [], "rail tab with no card"
    assert [c for c in rail.cards if c not in rail.tabs] == [], "card with no rail tab"
