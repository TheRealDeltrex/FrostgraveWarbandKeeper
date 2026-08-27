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


@pytest.mark.parametrize(
    "build",
    [_with_apprentice_and_captain, _no_apprentice, _vampire],
    ids=["apprentice+captain", "no-apprentice", "vampire"],
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
