# Code Audit — Frostgrave Warband Keeper

Date: 2026-08-05 · audited at 3.9.0 (`353abf7`) · **all findings resolved**

Full pass over `app.py`, `warband_store.py`, `expansions.py`, `game_content.py`,
`paths.py`, `pdf_export.py` and the templates. Every finding was reproduced
against running code before being fixed, and each fix re-verified the same way.

**Before:** 191 tests, 2 confirmed remote-ish holes, 3 crash paths.
**After:** 232 tests, `ruff` clean apart from the pre-existing `E501` baseline.

| # | Severity | Finding | Fix |
| --- | --- | --- | --- |
| 1 | HIGH | Portrait path traversal → arbitrary local file read via PDF export | `warband_store.portrait_filesystem_path` |
| 2 | HIGH | No CSRF protection; no `Host` validation | `app._reject_cross_site` |
| 3 | MED | Imported JSON under-validated → permanently unviewable warband | `warband_store._normalize_warband` |
| 4 | MED | `None` vault name 500s the warband page | `app.py` paren fix |
| 5 | MED | `revert_vampire` leaks the raised soldier cap | `warband_store.revert_vampire` |
| 6 | LOW | `set_user_data_dir` escapes the `FWK_DATA_DIR` sandbox | `paths.set_user_data_dir` |
| 7 | LOW | `_sanitize_filename` passes `..` through | `warband_store._sanitize_filename` |
| 8 | LOW | Ragged Warbands force-enables a different homerule | `warband_store.update_homerules` |
| 9 | LOW | `debug=True` in the dev entry point | `FWK_DEBUG` opt-in |
| 10 | LOW | No security response headers | `app._security_headers` |
| 11 | — | Debt call drains treasury — **checked, correct** | source citation added |
| 12 | LOW | Creation-time soldier costs bypass `expansions.soldier_cost` | `warband_store.create_warband` |
| 13 | LOW | `pdf_export` spacing, stale docstring, magic number, narrow `except` | `pdf_export.py` |
| 14 | LOW | Blanket `except ValueError` mislabels upload errors | `InvalidUpload` |
| 15 | Style | 3 × E402, 7 × I001 | fixed; E501 baseline untouched |
| 16 | Tests | No adversarial or route-level coverage | +41 tests |

---

## 1. HIGH — Path traversal via portrait paths (arbitrary local file read)

`warband_store.py` · `portrait_filesystem_path`

The guard blocked `..` but not an absolute path, and pathlib's `/` discards the
left operand when the right is absolute — so `portraits_root / "C:/x.png"` is
just `C:/x.png`. Confirmed end-to-end: importing a `.warbands` whose
`wizard.portrait` was an absolute path and requesting `/warband/<id>/pdf`
returned 200 with that out-of-tree image embedded.

Worth recording, since the earlier quick audit pointed at the wrong place: the
`/portraits/<path:relpath>` **route was never the hole** — `send_from_directory`
runs `safe_join`, which rejects traversal and absolute paths regardless of the
`".." in relpath` check above it. The sink was `resolve_portrait_path` → PDF
export.

**Fixed** by rejecting absolute paths *and* resolving the final path and
checking containment under the portraits root, which also covers symlinks and
drive-relative (`C:foo`) forms that a flag check alone misses.
`_safe_portrait_ref()` additionally scrubs the stored value at load/import time,
so a bad reference is dropped once rather than re-checked forever.

## 2. HIGH — No CSRF protection on any state-changing route

`app.py`

No token, no `Origin`/`Referer` check, no `SameSite`. Cross-origin HTML form
POSTs aren't subject to CORS preflight, so any page in any tab could drive the
app on its predictable `127.0.0.1:5000`. Confirmed with `Origin:
https://evil.example`: `set_gold` applied, and `/settings` silently repointed
the data folder — the worst one, since it needs no warband id and makes the app
look empty on next launch.

`GET /` with `Host: attacker.example` also returned 200, i.e. DNS rebinding
would make a remote page same-origin and able to read warbands.

**Fixed** with `_reject_cross_site()`: a `Host` allowlist matching the
`127.0.0.1` bind, plus an `Origin`/`Referer` check on every non-GET. Chose this
over Flask-WTF deliberately — there's no session to protect and ~60 forms would
each need a hidden field, whereas the threat here is entirely about request
provenance. Requests with neither header still pass (a non-browser client can't
be a CSRF victim). `SESSION_COOKIE_SAMESITE = "Lax"` as a second layer.
`BROWSER_MODE` is exempt: the Pyodide build is served from its own origin.

## 3. MEDIUM — Imported warband JSON under-validated

`warband_store.py` · `_normalize_warband`

Defaults were backfilled but types never checked, and `.warbands` is the
exchange format. Two confirmed paths produced a warband that *saved fine* and
then 500'd on every view — with the delete button on the crashing page:

- `homerules.max_soldiers: "lots"` → `int()` in `expansions.max_soldiers()` →
  `ValueError` in `warband_limits()`, called unguarded by `warband_view`.
- `vault_items: [{"id": "a"}]` → see §4.

**Fixed** in `_normalize_warband` rather than only in `import_warband_json`, so
a file corrupted by any route (hand-edit, older bug, partial write) also loads
safely. `_coerce_numeric_homerules()` is driven off `default_homerules()` so new
numeric homerules are covered without a hand-kept list; `bool` is checked before
`int` because it's a subclass and every toggle would otherwise become `0`/`1`.

## 4. MEDIUM — `None` vault-item name crashes the warband page

`app.py`

```python
name = (it.get("name") if isinstance(it, dict) else str(it) or "").strip()
```

Misplaced parens: this parses as `… else (str(it) or "")`, so the `or ""` guard
only ever protected the non-dict branch and a dict with a null `name` gave
`None.strip()`. `expansions.has_vault_item` had the same expression written
correctly, which is what this was meant to be. **Fixed**, plus
`_normalize_vault_items()` now drops nameless entries at the source.

## 5. MEDIUM — `revert_vampire` leaked the raised soldier cap

`warband_store.py`

`become_vampire` raises `max_soldiers` to the Vampire's 9-soldier floor
*unconditionally* and records the prior value unconditionally, but the restore
sat inside `if savepoint.get("apprentice")`. A wizard who transformed without an
apprentice kept the raised cap forever (verified 8 → 9 → 9; with an apprentice,
8 → 9 → 8). **Fixed** by moving the restore out of the branch. The docstring's
"does not restore clamped stats" carve-out is deliberate and separate.

## 6. LOW — `set_user_data_dir` escaped the `FWK_DATA_DIR` sandbox

`paths.py`

`FWK_DATA_DIR` wins on *read*, but `set_user_data_dir` wrote to the real
`%APPDATA%\FrostgraveWarbandKeeper\config.json` regardless — so the documented
sandbox was one-way. **I hit this during the §2 check and had to restore your
config by hand**, which is exactly why it's worth a guard rather than a habit.

**Fixed:** returns `False` writing nothing when `FWK_DATA_DIR` is set;
`/settings` reports why. Now matches the principle
`get_or_create_secret_key()`'s docstring already states.

## 7. LOW — `_sanitize_filename` passed `..` through

`warband_store.py`

The charset keeps `.`, so `_sanitize_filename("..") == ".."` and
`portrait_dir("..")` resolved to the data-dir root. Not reachable over HTTP
(Werkzeug normalises `..` out of the path before routing — verified: every
`/warband/../…` request 302s to home), but an id also arrives from imported JSON
via `restore_portraits_by_name`, and `delete_warband("..")` would have
`unlink()`ed every loose file in the data dir including `.secret_key`.
**Fixed** — `.`/`..`/empty now collapse to `warband`.

## 8. LOW — Ragged Warbands force-enabled soldier permanent injuries

`warband_store.py` · `update_homerules`

`… == "on" or ragged_warbands_enabled` meant ticking one homerule silently
enabled a different, separately-labelled one, whose checkbox then reverted on
every save. The coupling wasn't even load-bearing: the Random Recruit Status
Table calls `add_permanent_injury()` directly, below the gate (which lives only
in the `add_soldier_permanent_injury` wrapper). **Fixed** — each reads its own
checkbox.

## 9. LOW — `debug=True` in the dev entry point

`app.py`

Dev-only (the frozen build uses waitress), but it applies to anyone following
`README.md`, and the Werkzeug debugger is an interactive RCE console.
**Fixed:** reloader stays on, debugger is `FWK_DEBUG=1` opt-in.

## 10. LOW — No security response headers

**Fixed:** `X-Frame-Options: DENY`, `Content-Security-Policy: frame-ancestors
'none'`, `X-Content-Type-Options: nosniff`, `Referrer-Policy: same-origin`. The
frame ones matter most here — several controls act with no confirmation step.

Templates were already clean: no `|safe`, and the `| tojson` blobs sit in
`<script type="application/json">` where Flask escapes `<`/`>`/`&`. The
`innerHTML` writes interpolate static game data only.

## 11. Not a bug — the debt call is *supposed* to drain the treasury

`warband_store.py` · `roll_underworld_debt_call`

Flagged during the audit (5 Markers, 1000gc → one call took 750gc) but **checked
against the source rather than assumed**. Spellcaster Magazine Issue 3,
Underworld Debts Table, 1–6 "Pay what you owe": *"The warband must immediately
pay off as many Underworld Markers (at 150gc each) as possible with the gold in
its Treasury."* The `while` loop is correct, and the `cascaded` fallback matches
the table's "if no Markers can be removed, treat as 7–12". **No code change** —
added the citation so it isn't re-flagged.

## 12. LOW — Creation-time soldier costs bypassed the cost rule

`warband_store.py` · `create_warband` used the raw catalog `cost` while every
other path goes through `expansions.soldier_cost()` (Edition 2 correction,
Beastcrafter surcharge, base discount). Latent — `app.py` never passes
`soldiers` — but a divergent second implementation of a rule that has since
grown three modifiers. **Fixed** to use the shared helper.

## 13. LOW — `pdf_export.py`

All fixed: item slots printed `**1:**Staff` with no space (vs `**1+2:** Two-
Handed Weapon`); `EMPTY_SLOT` was `""` while the docstring promised `___` (now
a visible ` -`); `int(homerules.get(key, 6))` hardcoded a fallback that can
drift from `frostgrave_data` (now `CAPTAIN_ITEM_SLOTS` /
`PROMOTE_CAPTAIN_ITEM_SLOTS`); `_crop_to_square` caught only `OSError`, so a
malformed or oversized image 500'd the export instead of falling back to the
empty frame (now also `ValueError` / `DecompressionBombError`, resolved at
import so the no-Pillow path stays safe); duplicate mid-function
`warband_store` import removed.

## 14. LOW — Blanket `except ValueError` mislabelled upload errors

`app.py` · `warband_update` wraps every handler, so an unsupported image type
reported **"Please enter a valid number."**. Flashing `str(exc)` instead would
have leaked `invalid literal for int() with base 10: 'x'` to users, so
`save_portrait` now raises `InvalidUpload(ValueError)` — the one genuinely
user-facing raise site — caught first. `_mutation_target`'s programming-error
`ValueError` deliberately still gets the generic message.

## 15. Style

`ruff check` is now clean except the pre-existing `E501` baseline (unchanged on
every touched file — `pdf_export.py` improved by one). The 3 × `E402` traced to
`logger = logging.getLogger(__name__)` sitting *above* the import block, not to
the constant I first suspected; moved below. 7 × `I001` auto-fixed.

## 16. Tests — 191 → 232

- `tests/test_untrusted_import.py` (20) — portrait containment, type coercion,
  vault normalisation, `..` ids.
- `tests/test_request_guards.py` (17) — Host allowlist, cross-site writes,
  same-origin and header-less writes still working, security headers, hostile
  warbands rendering 200, upload error text.
- 4 more in the existing vampire and homerule files, next to the behaviour they
  cover.

## Positive findings (unchanged)

- Secret-key handling: random per-install, inside the sandboxed data dir,
  env-overridable.
- `save_warband`: tmp-file + `fsync` + `.bak` + `os.replace`.
- The `(ok, msg)` convention, `_<feature>_gate` pattern and `stat_backup` idiom
  are applied consistently across ~5,000 lines. The reversibility design
  (back up the prior value rather than inverting a possibly non-invertible op)
  is the right call and is followed everywhere.
- `_normalize_warband`'s per-key, never-version-gated backfill genuinely
  delivers on "old files must keep loading" — the type coercion added in §3
  follows the same rule.
