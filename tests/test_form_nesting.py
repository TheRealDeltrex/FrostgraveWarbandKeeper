"""Regression guard on nested <form> elements in the rendered warband page.

HTML forbids a form inside a form, and browsers don't error: the parser drops
the inner start tag, so its controls silently join the outer form, and the
inner </form> pops the outer one off the stack early, orphaning everything
after it. Both halves have shipped — apprentice/captain equipment never saving,
and "Dismiss apprentice" posting the enclosing card's action=details because
request.form.get("action") returns the first of the two action fields the
browser then sends.

The template can't be checked by reading it: the wizard/apprentice card and the
soldier rows open long forms across many {% if %} branches, so source-level
nesting is invisible. This renders the page instead and parses what a browser
would actually receive.
"""

from __future__ import annotations

from html.parser import HTMLParser

import pytest

import app as app_module
import expansions
import warband_store as ws
from frostgrave_data import spell_id

# Client-side-only controls, deliberately outside every form because nothing
# ever submits them: the roster reorder radio is read by the page's own JS,
# which then posts a separate reorder form.
JS_ONLY_CONTROLS = {"soldier-select"}


class _FormNesting(HTMLParser):
    """Records (inner_line, outer_line) for every <form> opened inside another,
    and every named control that ended up outside a form entirely."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.open_forms: list[int] = []
        self.nested: list[tuple[int, int]] = []
        self.orphans: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "form":
            if self.open_forms:
                self.nested.append((self.getpos()[0], self.open_forms[-1]))
            self.open_forms.append(self.getpos()[0])
        elif tag in ("input", "select", "textarea", "button"):
            a = dict(attrs)
            # form="..." deliberately points a control at a form it isn't
            # inside; that's the fix for this bug class, not a symptom of it.
            name = a.get("name")
            if name in JS_ONLY_CONTROLS:
                return
            if not self.open_forms and "form" not in a and (name or a.get("type") == "submit"):
                self.orphans.append(name or (a.get("type") or tag))

    def handle_endtag(self, tag: str) -> None:
        if tag == "form" and self.open_forms:
            self.open_forms.pop()


def _all_on(wb: dict) -> dict:
    hr = wb["homerules"]
    for key, value in ws.default_homerules().items():
        if isinstance(value, bool):
            hr[key] = True
    for book in hr["enabled_sources"]:
        hr["enabled_sources"][book] = True
    hr["captain_mode"] = "both"
    wb["gold"] = 90000
    return wb


def _warband(name: str) -> dict:
    school = "Elementalist"
    spells = [
        spell_id(school, "Wall"),
        spell_id(school, "Elemental Bolt"),
        spell_id(school, "Elemental Shield"),
        spell_id("Chronomancer", "Fast Act"),
        spell_id("Enchanter", "Enchant Weapon"),
        spell_id("Summoner", "Leap"),
        spell_id("Necromancer", "Bone Dart"),
        spell_id("Thaumaturge", "Heal"),
    ]
    wb, msg = ws.create_warband(
        warband_name=name, wizard_name="W", school=school, spell_keys=spells
    )
    assert wb is not None, msg
    return _all_on(wb)


def _with_apprentice_and_captain() -> dict:
    wb = _warband("nesting-full")
    ws.hire_apprentice(wb, "Appy")
    ws.hire_captain(wb, "Capy")
    for type_key in ("thug", "thief", "man_at_arms", "war_hound"):
        ws.add_soldier(wb, type_key, type_key, "", "")
    return wb


def _no_apprentice() -> dict:
    wb = _warband("nesting-noapp")
    ws.hire_captain(wb, "Capy")
    ws.add_soldier(wb, "thug", "Thug", "", "")
    return wb


def _vampire() -> dict:
    wb = _warband("nesting-vamp")
    ws.hire_apprentice(wb, "Appy")
    ws.become_vampire(wb)
    return wb


def _lich() -> dict:
    wb = _warband("nesting-lich")
    ws.hire_apprentice(wb, "Appy")
    ws.hire_captain(wb, "Capy")
    ws.set_wizard_state(wb, "lich")
    ws.add_soldier(wb, "thug", "Thug", "", "")
    return wb


def _every_soldier_type() -> dict:
    """Every hireable type at once: each soldier row's own template branches
    (companions, constructs, firearms, mounts, legendaries...) rendered on one
    page. Caps are lifted so as many as the rules allow actually get hired."""
    from frostgrave_data import SOLDIERS

    wb = _warband("nesting-all")
    ws.hire_apprentice(wb, "Appy")
    ws.hire_captain(wb, "Capy")
    wb["homerules"]["max_soldiers"] = wb["homerules"]["max_specialists"] = 500
    wb["wizard"]["level"] = 20
    for type_key in SOLDIERS:
        illusion = "thug" if type_key == "illusionary_soldier" else ""
        ws.add_soldier(wb, type_key, type_key, "", illusion)
    assert len(wb["soldiers"]) > 60, "roster should hold most soldier types"
    return wb


def _mounted_horse() -> dict:
    """Workshop horse panel, owned and ridden. Its Mount / Dismount / Release
    buttons share one row and each points at its own standalone form via
    form="", so the panel only renders its controls at all once a Stable is
    built and a horse bought — the shape this list would otherwise never see."""
    wb = _warband("nesting-horse")
    ws.hire_apprentice(wb, "Appy")
    ws.hire_captain(wb, "Capy")
    ws.add_soldier(wb, "thug", "Thug", "", "")
    wb.setdefault("base", {}).setdefault("resources", []).append("stable")
    ok, msg = ws.buy_horse(wb)
    assert ok, msg
    ok, msg = ws.mount_horse(wb, "wizard")
    assert ok, msg
    return wb


def _shop_open() -> dict:
    """The Shop card with the open shop showing: buy rows with their variant
    dropdowns and the sell-from-vault list, plus the Workshop's Write Scroll,
    Brew Potion and Alchemical Workshop panels over in the Treasury card —
    all of them small forms inside a card, which is exactly the shape this
    test guards."""
    wb = _warband("nesting-shop")
    ws.hire_apprentice(wb, "Appy")
    wb["homerules"]["black_market_enabled"] = False
    wb["base"] = {"location": "brewery", "resources": ["scriptorium", "giant_cauldron", "alchemical_workshop"]}
    ws.add_vault_item(wb, "Potion of Healing")
    ws.add_vault_item(wb, "Poison")
    for spell_name, school in (("Write Scroll", "Sigilist"), ("Brew Potion", "Witch")):
        sp = ws.find_spell(spell_id(school, spell_name))
        wb["wizard"]["spells"].append(
            {"id": sp["id"], "name": sp["name"], "school": sp["school"], "base_cn": sp["cn"], "cn": sp["cn"]}
        )
    return wb


def _shop_black_market() -> dict:
    """The other half of the Shop card: Black Market on, with a rolled offer
    whose Buy buttons are their own forms."""
    wb = _warband("nesting-bm")
    wb["homerules"]["black_market_enabled"] = True
    for _ in range(3):
        ws.black_market_roll(wb, "Treasure Table", 8)
    return wb


def _inn_and_underworld() -> dict:
    """The Inn's stay-behind picker, the campaign-reputation panel, and the
    Underworld Muscle / Intimidation forms — three cards' worth of new controls."""
    wb = _warband("nesting-inn")
    wb["base"] = {"location": "inn", "resources": []}
    wb["wizard"]["level"] = 25
    wb["homerules"]["underworld_favors_enabled"] = True
    ws.add_soldier(wb, "thug", "Thug", "", "")
    ws.hire_underworld_muscle(wb, "thief")
    ws.set_wizard_reputation(wb, expansions.REPUTATION_DEATH_OF_THE_LICH_LORD, True)
    ws.set_inn_resident(wb, wb["soldiers"][0]["id"])
    return wb


def _homunculus_warband(warband_id: str, *, held: bool) -> dict:
    wb = _warband(warband_id)
    wb["homerules"]["enabled_sources"]["Thaw of the Lich Lord"] = True
    sp = ws.find_spell(spell_id("Witch", "Homunculus"))
    wb["wizard"]["spells"].append(
        {"id": sp["id"], "name": sp["name"], "school": sp["school"], "base_cn": sp["cn"], "cn": sp["cn"]}
    )
    wb["wizard"]["homunculus"] = held
    return wb


def _homunculus_held() -> dict:
    """The wizard card carrying a homunculus: the badge is a bare button inside
    the card's big autosave form, driving a top-level hidden form through the
    dialog. Exactly the shape that has gone wrong before."""
    return _homunculus_warband("nesting-homunculus", held=True)


def _homunculus_castable() -> dict:
    """The other half — no homunculus yet, so the Workshop's cast panel renders
    instead of the badge and dialog."""
    return _homunculus_warband("nesting-homunculus-cast", held=False)


def _vault_artefact() -> dict:
    """A Red King artefact in the vault, which gives each vault row a second
    inline form (Activate) beside the remove button."""
    wb = _warband("nesting-artefact")
    wb["homerules"]["enabled_sources"]["The Red King"] = True
    ws.add_vault_item(wb, "Wraith Bow")
    ws.add_vault_item(wb, "Potion of Healing")
    wb["vault_items"][0]["activated"] = True
    return wb


@pytest.mark.parametrize(
    "build",
    [
        _with_apprentice_and_captain,
        _no_apprentice,
        _vampire,
        _lich,
        _every_soldier_type,
        _mounted_horse,
        _shop_open,
        _shop_black_market,
        _inn_and_underworld,
        _homunculus_held,
        _homunculus_castable,
        _vault_artefact,
    ],
    ids=[
        "apprentice+captain",
        "no-apprentice",
        "vampire",
        "lich",
        "every-soldier-type",
        "mounted-horse",
        "shop-open",
        "shop-black-market",
        "inn-and-underworld",
        "homunculus-held",
        "homunculus-castable",
        "vault-artefact",
    ],
)
def test_warband_page_has_no_nested_forms(build):
    wb = build()
    ws.save_warband(wb)
    resp = app_module.app.test_client().get(f"/warband/{wb['id']}")
    assert resp.status_code == 200

    parser = _FormNesting()
    parser.feed(resp.get_data(as_text=True))
    assert parser.nested == [], (
        "nested <form> in the rendered page at (inner, outer) rendered lines "
        f"{parser.nested} — point the inner controls at a standalone hidden "
        'form via form="..." instead'
    )
    assert parser.orphans == [], (
        f"named controls outside every form: {parser.orphans}"
    )


def test_dismiss_apprentice_button_posts_its_own_action():
    """The button lives inside the card's action=details autosave form, so it
    must carry form="dismiss-apprentice-form"; nested, the browser sent both
    action fields and the server read 'details'."""
    wb = _with_apprentice_and_captain()
    ws.save_warband(wb)
    html = app_module.app.test_client().get(f"/warband/{wb['id']}").get_data(as_text=True)
    assert 'id="dismiss-apprentice-form"' in html
    assert 'value="dismiss_apprentice" form="dismiss-apprentice-form"' in html
