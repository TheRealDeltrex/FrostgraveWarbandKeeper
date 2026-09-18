"""Regression guard on the new-warband form actually submitting.

The Create warband button silently stopped working between v5.1.2 and v5.1.9.
Two submit handlers disagreed about one piece of state: base.html gives busy
feedback from a *capture-phase* listener on document, disabling the pressed
button, and warband_new.html's guard — which cancels the submit while the spell
pick is incomplete — decided that by reading the very same `.disabled`. Capture
runs before bubble, so the guard always saw the flag base.html had just set,
cancelled every create, and left the button reading "Saving..." for good.

Nothing server-side could catch it: no request was ever made, so a test client
POST (which bypasses the page's JS entirely) passed throughout, and
test_form_nesting.py renders and parses the page but never submits one. Only a
real browser running the page's own scripts reproduces it, which is what this
does.

Playwright is not in requirements-dev.txt, so both it and its browser download
are optional: the module skips cleanly where either is missing, and nothing in
CI runs pytest anyway (see CLAUDE.md).
"""

from __future__ import annotations

import socket
import threading

import pytest

pytest.importorskip("playwright", reason="playwright not installed")

from playwright.sync_api import Error as PlaywrightError  # noqa: E402
from playwright.sync_api import sync_playwright  # noqa: E402
from werkzeug.serving import make_server  # noqa: E402

import app as app_module  # noqa: E402
import warband_store as ws  # noqa: E402

# A legal Chronomancer opening pick: 3 own, 1 from each aligned school, 2 from
# different neutrals. Kept in the same shape as conftest's fresh_warband so the
# rules behind it stay in validate_starting_spells, not re-derived here.
SCHOOL = "Elementalist"
LEGAL_PICK = [
    "Elementalist::Wall",
    "Elementalist::Elemental Bolt",
    "Elementalist::Elemental Shield",
    "Chronomancer::Fast Act",
    "Enchanter::Enchant Weapon",
    "Summoner::Leap",
    "Necromancer::Bone Dart",
    "Thaumaturge::Heal",
]


@pytest.fixture(scope="module")
def live_server():
    """The real app on a real port. The Flask test client can't be used here:
    it never runs the page's JavaScript, which is the whole subject."""
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()
    server = make_server("127.0.0.1", port, app_module.app, threaded=True)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{port}"
    finally:
        server.shutdown()
        thread.join(timeout=5)


@pytest.fixture(scope="module")
def browser():
    with sync_playwright() as p:
        try:
            b = p.chromium.launch()
        except PlaywrightError as exc:  # browser binary not downloaded
            pytest.skip(f"chromium unavailable: {exc}")
        try:
            yield b
        finally:
            b.close()


def _open_new_warband_form(browser, live_server, name: str):
    page = browser.new_page()
    page.goto(f"{live_server}/warband/new?school={SCHOOL}", wait_until="load")
    page.fill("[name=warband_name]", name)
    page.fill("[name=wizard_name]", "Test Wizard")
    return page


def _tick(page, spell_keys: list[str]) -> None:
    """Tick spells by dispatching a real click on each box.

    Not page.check(): the boxes live inside per-school <details> that start
    collapsed, so Playwright's visibility-aware helpers can't reach them
    without first expanding every section, which is scenery for this test. The
    click still fires the page's own change handlers, which is what keeps
    spell_order and the submit gating current. The submit button itself is
    clicked for real below — that is the path under test."""
    picked = page.evaluate(
        """(keys) => keys.filter(k => {
            const b = [...document.querySelectorAll('input[name="spells"]')]
                .find(x => x.value === k);
            if (!b || b.disabled) return false;
            if (!b.checked) b.click();
            return b.checked;
        }).length""",
        spell_keys,
    )
    assert picked == len(spell_keys), f"only {picked}/{len(spell_keys)} spells could be picked"


def test_create_warband_button_submits(browser, live_server):
    """The button posts the form and lands on the new warband's page.

    Asserting on the URL and on the file is deliberate: the bug left the page
    sitting on /warband/new with no error of any kind, so 'the page still
    renders' proves nothing."""
    page = _open_new_warband_form(browser, live_server, "Submit Guard")
    _tick(page, LEGAL_PICK)
    assert page.is_enabled("#submit-btn"), "a legal pick should enable create"

    page.click("#submit-btn")
    page.wait_for_url("**/warband/*", timeout=15000)

    warband_id = page.url.rstrip("/").rsplit("/", 1)[-1]
    assert warband_id != "new"
    assert ws.warband_path(warband_id).is_file(), "create redirected but saved nothing"
    page.close()


def test_incomplete_pick_is_blocked(browser, live_server):
    """An incomplete spell pick must not create a warband."""
    page = _open_new_warband_form(browser, live_server, "Incomplete")
    _tick(page, LEGAL_PICK[:1])
    assert not page.is_enabled("#submit-btn")

    # requestSubmit(), not click(): a disabled button swallows the click, and
    # it's the guard's cancellation path that this is about.
    page.evaluate("document.getElementById('create-form').requestSubmit()")
    page.wait_for_timeout(500)

    assert "/warband/new" in page.url, "an incomplete pick must not create a warband"
    page.close()


def test_cancelled_submit_restores_the_button(browser, live_server):
    """base.html's busy feedback must not strand a button whose submit a later
    listener cancels.

    It relabels the pressed button to "Saving..." and disables it from a
    capture-phase listener, before any listener that might call
    preventDefault() has run. Nothing navigates then, so without the restore
    the button is left disabled reading "Saving..." for good and the form can
    never be submitted again — which is exactly how the create button failed.

    The cancelling listener is added here rather than relying on the page's own
    guard: that guard only fires while the pick is incomplete, and the button is
    then already disabled, so base.html skips it and the restore path never
    runs. This reproduces the shape that matters — a *live* button whose submit
    is cancelled — which is what any future guard on any page would hit."""
    page = _open_new_warband_form(browser, live_server, "Cancelled")
    _tick(page, LEGAL_PICK)
    assert page.is_enabled("#submit-btn")

    page.evaluate(
        """document.getElementById('create-form').addEventListener(
               'submit', e => e.preventDefault())"""
    )
    page.click("#submit-btn")
    page.wait_for_timeout(500)

    assert "/warband/new" in page.url, "the cancelling listener should have stopped this"
    assert page.inner_text("#submit-btn").strip() == "Create warband", (
        "button left stranded mid-save after a cancelled submit"
    )
    assert page.is_enabled("#submit-btn"), "button left disabled after a cancelled submit"
    assert not page.evaluate(
        "document.getElementById('submit-btn').classList.contains('busy')"
    )
    page.close()
