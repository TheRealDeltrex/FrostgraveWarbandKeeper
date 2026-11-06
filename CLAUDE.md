# Frostgrave Warband Keeper — agent operating manual

Read this before working on this project. A local Flask app (no login, plain-file JSON
storage) for **Frostgrave (2nd Edition)** warbands. `README.md` covers user-facing behaviour,
running and build commands.

**Current state only**, not a changelog: update this file (or the nested one) in the same
commit as any change that makes it wrong or adds a gotcha a future session would re-derive.

## Where the detail lives

Area detail sits in nested `CLAUDE.md` files beside the code. Read the one for the area you
touch (other agents: they are not auto-loaded, open them yourself).

- **`templates/CLAUDE.md`** — any UI work (templates, `static/style.css`, tab script): nested
  forms, the two layouts, the Jinja `{% set %}` leak, roster-table info cells, UI copy and
  heading rules, the base64 font/logo.
- **`data/CLAUDE.md`** — reference JSON, price lists, extractors.
- **`tests/CLAUDE.md`** — fixtures, CI, what a green run does and doesn't cover.

Skills (outside the repo; location in `CLAUDE.local.md`): `game-data-files` before editing `data/`,
`homerule-feature` for book-gated mechanics, `e501-baseline` before touching long lines,
`shipping-a-release` when shipping.

## Architecture

Four layers, strictly ordered — each may depend on those above it, never below.

1. **`frostgrave_data.py`** — static game data (`SOLDIERS`, `SPELLS`, `SOURCE_BOOKS`, items,
   costs, caps) plus pure helpers over it. No persistence, no request handling.
2. **`expansions.py`** — pure rules: reads warband dicts, returns values, never mutates.
   Any *calculation* over a warband belongs here.
3. **`warband_store.py`** — persistence and every state-changing operation. Mutators return
   `(ok: bool, msg: str)`.
4. **`app.py`** — Flask routes and Jinja context. Thin: parse request, call the layers, render.

Supporting: `game_content.py` (cached loaders for `data/`), `paths.py` (bundle vs. user data
dir), `pdf_export.py` (fpdf2 roster), `tray.py` / `idle_watchdog.py` (packaged exe only).

## Core patterns

**Action dispatch.** Every state-changing form POSTs to `/warband/<id>/update` with a hidden
`action`, dispatched via `@register_action("<name>")` in `app.py`; the route flashes `msg` and
saves iff `ok`. New mutations go in `warband_store.py` with a thin wrapper in `app.py`.

**`enrich_soldier(wb, s)`** merges `{**catalog, **soldier}`; templates get this, not raw
`wb["soldiers"]`. Move and Armour are catalog-only, never stored per soldier, so a data fix
reaches existing warbands — repair a stored wrong one, never add one.

**Bookkeeping, not rule enforcement.** The app records what a group decides. Dice rolls are
optional, mechanics stay circumventable (hand-edit gold, leave a Pact via the state dropdown),
and a rule the player is breaking gets a warning and a confirm, not a refusal. Never a
**silent** divergence: where two controls differ in what they apply, one line says so.

**Gating.** A supplement mechanic is gated by its **source-book toggle alone**; it earns its
own homerule flag only when intrusive or world-changing (firearms, `dire_hound_counts_as_hound`).
Existing features mostly carry both (the `homerule-feature` skill's shape — due a revision,
not the model for new work). Apply the gate everywhere the feature can be acquired: buy,
upgrade *and* hire. **Acquisition is gated, possession persists**: gate the button, never the
stored state (`can_enter_state()` checks the book, `beastcrafter_tier()` does not).

**Untrusted warband files.** `.warbands` files are the exchange format, so `load_warband()`
and `import_warband_json()` take semi-untrusted input. `_normalize_warband()` is the single
place types are enforced and **every new field goes through it** — `setdefault` alone isn't
enough (an explicit `null` survives it). `_as_int()` for arithmetic, `_as_list()` for anything
iterated or `|length`ed, `_safe_portrait_ref()` for paths, `isinstance(str)` for dict keys,
and a literal fallback behind catalog lookups (`get_soldier()` returns `{}` for an unknown
`type_key`). A field that slips through imports fine, then 500s `warband_view` forever — and
the delete button is on that page. Vault entries are rebuilt by `_normalize_vault_items()`:
copy any new vault field through it. Helper docstrings carry each trap. `list_warbands()` reads
raw JSON and never normalizes so the list stays reachable; keep it that way.

**Local-only guard.** `_reject_cross_site()` (global `before_request`: local `Host`, plus
`Origin`/`Referer` on writes) stands in for auth. New routes need nothing; a non-browser
client must send a local `Host`.

## Non-obvious design decisions

- **Spellcaster Magazine is one source book**, not seven per-issue toggles.
- **Never read `SCHOOL_RELATIONS` directly** — supplement schools are stored one-way. Go
  through `school_relation()`/`cn_penalty()`, passing `warband_store.school_symmetry(wb)`
  (the `school_relations_symmetric` homerule); flipping it re-runs `recompute_spell_cns()`.
- **The apprentice derives from the wizard's *base* stats.** `sync_apprentice()` rebuilds
  them each save, netting out the wizard's mutation/injury offsets via
  `figure_stat_offsets()` and re-adding the apprentice's own; level-ups still flow down.
- **Shop and Black Market are alternatives** (p.104: Black Market Contacts *replaces* open
  buying). Its toggle sits on the Shop card, so `update_homerules()` keeps the stored
  `black_market_enabled` rather than reading the absent form field.
- **Item restrictions match a trait-tagged role token** (`"wizard:undead"`), built only by
  `expansions.figure_item_role()`; `excluded_traits` covers exclusion-phrased items (Mind
  Lock Ring). `item_restricted_for_type_key()` still wants the untagged key.
- **Campaign reputations live on the wizard** (`wizard["reputations"]`):
  `set_base_location()` wipes `base["resources"]` on every move.
- **The homunculus is `wizard["homunculus"]`**, not a vault entry. Its −2 Health is
  display-only (`homunculus_health_penalty()`); caps stay untouched. There is no post-game
  survival check, so `homunculus_claim_soul()` is a player-pressed button.
- **Campaign log UI is commented out** (planned); tab view shows a "Coming soon" card. Keep
  the `add_log` handler and `add_history()`.

## Working rules

**Testing is minimal and targeted.** Verify the specific change — one narrow test, a direct
call or a single render. Don't run the full suite or browser tests unless asked; CI runs the
full suite. If a change feels risky enough for more, ask.

```bash
.venv/Scripts/python.exe -m pytest tests/test_<thing>.py -q
.venv/Scripts/python.exe -m ruff check <files.py>
```

- **Only pass `.py` files to ruff** — on a template it emits thousands of false errors.
- **Leave the `E501` baseline alone** (see `e501-baseline`); check line numbers against your diff.
- Keep diffs minimal: mature single-maintainer app, no refactors beyond the task.
- **`todo.md`** holds accepted deferred work — add findings there rather than dropping them;
  `rules_coverage_audit.md` records what was ruled out.
- Comments explain non-obvious *why*, never *what*.
- **Never invent or paraphrase game text** — extract from the PDFs (see `data/CLAUDE.md`).
- **Never write verbose** — this file, skills, comments, commit messages, chat replies. Write
  it tight the first time. Skill descriptions are resident in every session.

## Running the app locally

`paths.user_data_dir()` resolves `FWK_DATA_DIR` → `%APPDATA%\FrostgraveWarbandKeeper\config.json`
→ default. That config points at the user's **real** warbands (path in `CLAUDE.local.md`), so a plain `python app.py` reads and writes real data. Always set `FWK_DATA_DIR` to
a throwaway temp dir outside the repo and a non-default `PORT`, inline in a subshell:

```bash
(FWK_DATA_DIR="/tmp/fwk-scratch" PORT=5099 ".venv/Scripts/python.exe" app.py > log 2>&1 &)
```

Don't remove `paths.set_user_data_dir()`'s refusal under `FWK_DATA_DIR` (docstring has why).
The exe honours the same vars plus `BROWSER=/nonexistent`. Stop a test server by the PID on
its port; **never kill by process name** — the user runs a real instance on 5000. No debugger
by default (`FWK_DEBUG=1` opts in). Reach it as `127.0.0.1`/`localhost`, else 403.

## Commit, ship, backup

- **"commit"** = commit and push. **"ship"** = commit plus update all release channels
  (`shipping-a-release` skill).
- **Never commit or ship without being asked, every time.** An earlier approval doesn't carry
  forward; don't chain "tests pass" → commit → build/release.
- **The backup follows the same rule.** `AGENTS.md`, `CLAUDE.local.md` and the skills are
  gitignored or outside the repo; the backup folder named in `CLAUDE.local.md` is their only
  restore point. **Never refresh it unless asked**, and never right after the
  edit it would back up — an unprompted refresh after a bad edit destroys the good copy. That
  has happened.

## Branches

- **`devversion`** — application source; all work happens here.
- **`main`** — distribution only (README, LICENSE, `.gitignore`, two `workflow_dispatch`
  workflows), hand-authored history. Pages builds from `devversion`.

## Persistent memory

The auto-memory folder (path in `CLAUDE.local.md`) holds only transient,
in-flight state. Durable rules live here; this file wins on conflict.
