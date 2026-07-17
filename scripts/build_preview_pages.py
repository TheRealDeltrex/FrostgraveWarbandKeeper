"""Generate the static "Live Preview" pages published on the download landing page
(docs/ on the `main` branch, GitHub Pages — no backend there at all).

Drives the real app (Flask test client) through a demo warband instead of hand-writing
approximate HTML, so the captured markup can never drift from what the templates/CSS
actually render. Re-run this after any change to templates/warband_view.html,
templates/reference.html, templates/base.html, or static/style.css — then copy the
regenerated docs/preview-*.html + docs/static/* over to the `main` branch.

Usage (from the repo root, on devversion, with the venv active):
    python scripts/build_preview_pages.py

Writes docs/preview-warband.html, docs/preview-reference.html, docs/static/style.css,
docs/static/item_slots.js — all relative to the repo root. The demo warband itself is
built in a throwaway OS temp directory (via FWK_DATA_DIR), never touching data/warbands/.
"""

from __future__ import annotations

import os
import re
import shutil
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

# Must happen before importing app/warband_store — WARBAND_DIR is resolved once at import time.
os.environ["FWK_DATA_DIR"] = tempfile.mkdtemp(prefix="fwk-preview-")

sys.path.insert(0, str(REPO_ROOT))
import app as app_module  # noqa: E402
from frostgrave_data import spell_id  # noqa: E402

client = app_module.app.test_client()


def post(path: str, data: dict, follow: bool = False):
    resp = client.post(path, data=data, follow_redirects=follow)
    assert resp.status_code < 400, f"POST {path} -> {resp.status_code}: {resp.get_data(as_text=True)[:500]}"
    return resp


def build_sample_warband() -> str:
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
    resp = post(
        "/warband/new",
        {
            "warband_name": "The Icebound Circle",
            "wizard_name": "Mireille Voss",
            "school": school,
            "spells": spells,
            "with_apprentice": "on",
            "apprentice_name": "Toby Ash",
            "soldier_type_0": "thug",
            "soldier_name_0": "Garrik",
            "soldier_type_1": "thief",
            "soldier_name_1": "Nissa",
            "soldier_type_2": "archer",
            "soldier_name_2": "Wren",
        },
    )
    location = resp.headers["Location"]
    warband_id = location.rstrip("/").rsplit("/", 1)[-1]

    def update(data: dict):
        post(f"/warband/{warband_id}/update", data)

    update({"action": "update_homerules", "captain_mode": "hire", "soldier_leveling_enabled": "on"})
    update({"action": "hire_captain", "captain_name": "Kess Thorne", "captain_tricks": ["furious_attack", "riposte"]})

    update({"action": "add_xp", "xp": "100"})
    update({"action": "level_up", "choice": "fight"})
    update({"action": "add_xp", "xp": "100"})
    update({"action": "level_up", "choice": "will"})
    update({"action": "add_xp", "xp": "60"})  # leaves a pending level-up on display

    update({"action": "captain_add_xp", "amount": "100"})
    update({"action": "captain_level_up", "choice": "fight"})

    from warband_store import load_warband

    wb = load_warband(warband_id)
    wren_id = next(s["id"] for s in wb["soldiers"] if s["name"] == "Wren")
    update({"action": "soldier_add_xp", "soldier_id": wren_id, "amount": "50"})

    update(
        {
            "action": "post_game",
            "loot_gold": "50",
            "loot_xp": "80",
            "loot_captain_xp": "40",
            "loot_items": "Potion of Healing\nScroll of Wall",
            "loot_notes": "Cleared a warded vault beneath the old chapel.",
        }
    )
    update({"action": "set_base_location", "location": "inn"})

    return warband_id


def strip_block(html: str, open_tag_re: str, close_tag: str) -> str:
    m = re.search(open_tag_re, html)
    if not m:
        return html
    start = m.start()
    end = html.index(close_tag, m.end()) + len(close_tag)
    return html[:start] + html[end:]


PREVIEW_SCRIPT = """
    <script>
      // This is a static preview — nothing here is real. Belt-and-suspenders: block both the
      // normal submit event AND HTMLFormElement.submit() (the soldier-status dropdown calls the
      // latter directly, which per spec does NOT fire a 'submit' event).
      document.addEventListener('submit', function (e) { e.preventDefault(); }, true);
      HTMLFormElement.prototype.submit = function () {};
    </script>
"""


BANNER_STYLE = """
    <style>
      /* Scoped to the preview banner only — kept out of the shared style.css copy so that file
         stays a verbatim, byte-for-byte copy of the real app's stylesheet. */
      .preview-banner {
        background: var(--surface-2);
        border: 1px solid var(--border);
        border-radius: 8px;
        padding: 0.65rem 1rem;
        margin: 1rem 0;
        font-size: 0.9rem;
        color: var(--text);
      }
      .preview-banner a { color: var(--accent); margin-left: 0.4rem; }
      .preview-banner a:hover { color: var(--accent-hover); }
    </style>
"""


def sanitize(html: str, *, other_preview: str, page_label: str) -> str:
    html = strip_block(html, r'<ul class="flashes">', "</ul>")
    html = strip_block(html, r'<nav class="nav">', "</nav>")
    html = html.replace("</head>", BANNER_STYLE + "</head>")

    banner = f"""
      <div class="preview-banner">
        <strong>Live Preview</strong> — a static, read-only sample. Nothing here saves.
        <a href="index.html">&larr; Download the app</a> &middot;
        <a href="{other_preview}">{page_label}</a>
      </div>
    """
    html = html.replace('<div class="container">', '<div class="container">' + banner, 1)

    html = re.sub(r'<link rel="stylesheet" href="[^"]*style\.css"[^>]*/?>',
                  '<link rel="stylesheet" href="static/style.css" />', html)
    html = re.sub(r'<script src="[^"]*item_slots\.js"[^>]*></script>',
                  '<script src="static/item_slots.js" defer></script>', html)

    # Hero action row (warband page only) — PDF/export don't exist statically.
    html = re.sub(
        r'<a class="btn" href="[^"]*/pdf"',
        '<a class="btn" href="#" onclick="return false;" title="Not available in this static preview."',
        html,
    )
    html = re.sub(
        r'<a class="btn secondary" href="[^"]*/export"',
        '<a class="btn secondary" href="#" onclick="return false;" title="Not available in this static preview."',
        html,
    )
    html = re.sub(
        r'<a class="btn secondary" href="[^"]*"( )?>\s*All warbands\s*</a>',
        '<a class="btn secondary" href="index.html">All warbands</a>',
        html,
    )

    # Confirm() prompts are confusing on a page where nothing is real.
    html = re.sub(r'\s*onsubmit="return confirm\([^"]*\);"', "", html)
    html = re.sub(r'\s*onclick="return confirm\([^"]*\);"', "", html)

    # form.submit() bypasses the 'submit' event; neutralize the one caller directly too.
    html = html.replace('onchange="this.form.submit()"', 'onchange="return false;"')

    html = html.replace("</body>", PREVIEW_SCRIPT + "</body>")
    return html


def main():
    warband_id = build_sample_warband()
    warband_html = client.get(f"/warband/{warband_id}").get_data(as_text=True)
    reference_html = client.get("/reference").get_data(as_text=True)

    docs = REPO_ROOT / "docs"
    (docs / "static").mkdir(parents=True, exist_ok=True)

    (docs / "preview-warband.html").write_text(
        sanitize(warband_html, other_preview="preview-reference.html", page_label="See the reference pages"),
        encoding="utf-8",
    )
    (docs / "preview-reference.html").write_text(
        sanitize(reference_html, other_preview="preview-warband.html", page_label="See a sample warband"),
        encoding="utf-8",
    )
    shutil.copyfile(REPO_ROOT / "static" / "style.css", docs / "static" / "style.css")
    shutil.copyfile(REPO_ROOT / "static" / "item_slots.js", docs / "static" / "item_slots.js")

    print(f"Sample warband id: {warband_id}")
    for f in ["preview-warband.html", "preview-reference.html", "static/style.css", "static/item_slots.js"]:
        p = docs / f
        print(f"  wrote {p} ({p.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
