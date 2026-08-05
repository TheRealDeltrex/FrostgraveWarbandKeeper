"""Route-level tests for the local-only request guards and error reporting.

The app has no accounts, but it listens on a predictable 127.0.0.1:5000 while
the user browses the rest of the web — so cross-site form POSTs and DNS
rebinding are the two things standing in for authentication here. These pin
that _reject_cross_site() blocks both without blocking the app itself.
"""

from __future__ import annotations

import json

import pytest

import app as appmod
import warband_store as ws

EVIL = "https://evil.example"


@pytest.fixture
def client():
    return appmod.app.test_client()


@pytest.fixture
def saved_warband(fresh_warband):
    ws.save_warband(fresh_warband)
    return fresh_warband


# --- Host header (DNS rebinding) --------------------------------------------


@pytest.mark.parametrize("host", ["127.0.0.1:5000", "localhost:5000", "127.0.0.1", "[::1]:5000"])
def test_local_hosts_are_accepted(client, host):
    assert client.get("/", headers={"Host": host}).status_code == 200


@pytest.mark.parametrize("host", ["attacker.example", "frostgrave.evil:5000", "192.168.1.5:5000"])
def test_foreign_host_header_is_rejected(client, host):
    assert client.get("/", headers={"Host": host}).status_code == 403


# --- Cross-site writes ------------------------------------------------------


def test_cross_site_post_to_update_is_rejected(client, saved_warband):
    before = int(saved_warband["gold"])
    resp = client.post(
        f"/warband/{saved_warband['id']}/update",
        data={"action": "set_gold", "amount": "99999"},
        headers={"Origin": EVIL},
    )
    assert resp.status_code == 403
    assert int(ws.load_warband(saved_warband["id"])["gold"]) == before


def test_cross_site_post_via_referer_is_rejected(client, saved_warband):
    resp = client.post(
        f"/warband/{saved_warband['id']}/update",
        data={"action": "set_gold", "amount": "1"},
        headers={"Referer": f"{EVIL}/page"},
    )
    assert resp.status_code == 403


def test_cross_site_post_to_settings_is_rejected(client):
    """The worst case: no warband id needed, and it silently repoints the data
    folder so the app looks empty on next launch."""
    assert client.post("/settings", data={"data_dir": "C:/evil"},
                       headers={"Origin": EVIL}).status_code == 403


def test_same_origin_post_still_works(client, saved_warband):
    resp = client.post(
        f"/warband/{saved_warband['id']}/update",
        data={"action": "set_gold", "amount": "1234"},
        headers={"Origin": "http://127.0.0.1:5000", "Host": "127.0.0.1:5000"},
    )
    assert resp.status_code == 302
    assert int(ws.load_warband(saved_warband["id"])["gold"]) == 1234


def test_post_without_origin_or_referer_still_works(client, saved_warband):
    """A non-browser client can't be a CSRF victim, and same-origin form posts
    don't always carry Origin."""
    resp = client.post(
        f"/warband/{saved_warband['id']}/update",
        data={"action": "set_gold", "amount": "77"},
    )
    assert resp.status_code == 302
    assert int(ws.load_warband(saved_warband["id"])["gold"]) == 77


def test_cross_site_get_is_still_allowed(client):
    """Reads are guarded by the Host check, not the Origin check — blocking
    cross-origin GETs would break ordinary inbound links."""
    assert client.get("/", headers={"Origin": EVIL}).status_code == 200


# --- Security headers -------------------------------------------------------


def test_security_headers_present(client):
    headers = client.get("/").headers
    assert headers["X-Frame-Options"] == "DENY"
    assert headers["X-Content-Type-Options"] == "nosniff"
    assert "frame-ancestors 'none'" in headers["Content-Security-Policy"]
    assert headers["Referrer-Policy"] == "same-origin"


# --- Hostile warband renders rather than 500s -------------------------------


def test_imported_warband_with_nameless_vault_item_renders(client, fresh_warband):
    raw = json.loads(ws.export_warband_json(fresh_warband))
    raw["id"] = "route-vault"
    raw["vault_items"] = [{"id": "a", "notes": "n"}]
    ws.save_warband(ws.import_warband_json(json.dumps(raw)))
    assert client.get("/warband/route-vault").status_code == 200


def test_imported_warband_with_bad_homerule_renders(client, fresh_warband):
    raw = json.loads(ws.export_warband_json(fresh_warband))
    raw["id"] = "route-homerule"
    raw["homerules"]["max_soldiers"] = "lots"
    ws.save_warband(ws.import_warband_json(json.dumps(raw)))
    assert client.get("/warband/route-homerule").status_code == 200


# --- Error reporting --------------------------------------------------------


def test_rejected_image_reports_the_real_reason(client, saved_warband):
    """warband_update catches ValueError across every handler; an unsupported
    image type used to be reported as "Please enter a valid number."."""
    import io

    resp = client.post(
        f"/warband/{saved_warband['id']}/update",
        data={
            "action": "details",
            "warband_name": saved_warband["name"],
            "wizard_name": saved_warband["wizard"]["name"],
            "wizard_portrait": (io.BytesIO(b"BM-not-really"), "portrait.bmp"),
        },
        content_type="multipart/form-data",
        follow_redirects=True,
    )
    body = resp.get_data(as_text=True)
    assert "Image must be jpg, png, gif, or webp." in body
    assert "Please enter a valid number." not in body
