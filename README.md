# Frostgrave Warband Keeper — dev version

This branch (`devversion`) holds the **full Python/Flask source code**. It exists so the app can be
run from source, read, and altered — if you (or your gaming group) need a feature, rule tweak, or
homerule this app doesn't already support, this is the branch to work from.

If you just want to run the app and don't need to touch the code, you don't need this branch —
**download a build** (Windows, or the browser build) from the
[download page](https://therealdeltrex.github.io/FrostgraveWarbandKeeper/), the
[`main` branch](../../tree/main), or the [latest Release](../../releases/latest). v4.5.0 is (for
now) the last release with a Linux binary — see "Building the executables yourself" below.

A local Flask app for creating and maintaining warbands for **Frostgrave (2nd Edition)**. No login, no server — your warbands are saved as plain files on your own machine.

Not affiliated with Osprey Games / Joseph A. McCullough.

## Features

- **Create a warband**: wizard (name, school, portrait), starting spells (3 own / 1 each aligned / 2 neutral, per 2e rules), and an optional apprentice. Soldiers are recruited afterwards on the warband page.
- **Maintain between games**: level up your wizard (stat increases, learn spells, improve spells), record post-game loot (gold, XP, items), and manage the vault. XP can be added or removed (negative XP auto-reverses lost level-ups).
- **Soldiers**: hire from the full 2e roster with correct cost/unit limits (max 8 soldiers, max 4 specialists), track status (active/injured/dead), reorder the roster, and optionally level them up.
- **Character pictures**: every wizard, apprentice and soldier type ships with its own artwork, shown until you upload a picture of your own. Defaults appear on the warband page and in the PDF roster.
- **Supplement content**: switching on a source book unlocks everything it adds — 16 extra soldiers, 42 extra spells, 128 magic items, 2 base resources and 43 extra creatures from Thaw of the Lich Lord, Into the Breeding Pits, Forgotten Pacts, The Maze of Malcor and The Perilous Dark, each labelled with its source. Books can be picked at warband creation, so supplement spells are available as starting spells.
- **Wizard states**: the three long-term states the supplements introduce — **Lichdom** (150 XP per level, no Fight/Shoot advances, Will and Health capped, no Rangifer), the **Beastcrafter** track (three tiers, a soldier surcharge, extra Animal Companions, a permanent Animal Feature) and **Demonic Pacts** (Sacrifice/Boon pairs unlocking at levels 10/25/50, needing a True Name in the vault). They are mutually exclusive, and each is gated behind its own source book.
- **The Pentangle**: the five lost schools from The Maze of Malcor with all 30 of their Lost Spells. Scroll-only by the book, or playable as real schools via an optional homerule.
- **Expansion rules**: the table rules each book adds — traps, underground play, demonic attributes, mystic brands, Malcor's optional core-rule updates, the Perilous Dark solo/co-op and dungeon-generation toolkits — shown per enabled book, and always browsable in the Lexicon.
- **Ghost Archipelago**: a read-only Lexicon section for Osprey's sister ruleset (Heritor abilities, Warden spells, crew types, treasure, bestiary, ship upgrades). Not a source book — nothing here is hireable.
- **Additional Rules and Homerules**: a per-warband tab with a toggle for every supplement source book (supplement mercenaries only become hireable once their book is switched on) plus the optional Captain house rule — hire a Captain or promote an existing soldier into one, with configurable cost, starting stats, item slots, and Mind Control setting.
- **Home base**: set a base location and buy base resources, per the 2e core rules.
- **Frostgrave Lexicon**: full spell list per school with casting numbers and descriptions, the school relationship table (own/aligned/neutral/opposed), the standard arms & armour list, and a full bestiary — every creature browsable with its source and rules text.
- **PDF roster export**: a clean, printable warband sheet.
- **Import/export**: warbands are saved as `.warbands` files (plain JSON) that can be exported, shared, and re-imported.
- **Settings page**: choose where warband data is saved on disk (used mainly by the packaged executable — see below).

## Running from source

```bash
python -m venv .venv
.venv/Scripts/activate   # or source .venv/bin/activate on macOS/Linux
pip install -r requirements.txt
python app.py
```

Then open http://127.0.0.1:5000.

Warband data, portraits, and uploads are saved under `data/` and are not tracked in git.

## Building the executables yourself

Windows (build on Windows — PyInstaller can't cross-compile):

```bash
pip install -r requirements-dev.txt
python -m PyInstaller frostgrave.spec --noconfirm
```

This produces `dist/FrostgraveWarbandKeeper/` — a folder containing `FrostgraveWarbandKeeper.exe`
plus its bundled resources. Copy the whole folder wherever you want to run it from.

Linux (build on Linux, for the same cross-compile reason — this repo builds it via
`.github/workflows/build-linux.yml` on a GitHub Actions Ubuntu runner rather than locally).
**v4.5.0 is (for now) the last release this is built and published for** — the workflow still
exists and still works, it's just no longer dispatched as part of shipping a new version:

```bash
pip install -r requirements-dev.txt
python -m PyInstaller frostgrave-linux.spec --noconfirm
```

This produces a single `dist/FrostgraveWarbandKeeper` binary (onefile, unlike the Windows onedir
build — simpler to hand to someone with just `chmod +x` and run). It skips the tray icon (see
`tray.py` / `app.py`'s `main()`) since that needs GTK/AppIndicator or X11 libraries a generic
Linux build can't assume are present; auto-shutdown-on-browser-close (`idle_watchdog.py`) still
works the same as on Windows.

## In-browser (online) build

The online build is a zero-backend build of the app that runs entirely in the browser via
[Pyodide](https://pyodide.org/): it loads Python + Flask in the tab, unpacks the app, and drives it
through Flask's test client.

Pyodide's filesystem is in-memory and dies with the tab, so `docs/app/index.html` snapshots it out to
`localStorage` (`fwk_warbands_v1` / `fwk_portraits_v1`) after every mutating request and restores it
at boot before the first render. Warbands therefore survive a refresh — but only in *that* browser on
*that* device; there's no account and no server, so exporting to a file is still the only portable
backup. Portrait uploads work normally (a small Python↔JS bridge turns file inputs into real
multipart uploads against the test client, and inlines uploaded/default portraits as data URIs when
rendering each page) and persist the same way, subject to the browser's ~5 MB storage quota — the
snapshot writes warbands first and drops portraits if the quota is hit, so game data always wins.

It embeds a copy of the app's Python, templates and reference data in a single bundle, and mirrors
the default character artwork as plain sibling files (not bundled — see the script's docstring):

```bash
python scripts/build_browser_bundle.py   # writes docs/app/bundle.json + docs/app/static/portraits/
```

Browser-specific UI (browser-storage banner, no Settings/native folder picker) is gated behind
`FWK_BROWSER=1` in `app.py` and the templates.

### Publishing the site

GitHub Pages is published by `.github/workflows/deploy-pages.yml` (manual dispatch), which builds
`docs/` fresh from `devversion` and deploys the artifact directly. **Do not hand-sync generated files
into `main`.** The site used to be served from `main`'s `/docs`, with `bundle.json` copied across by
hand while `index.html` was maintained as a second, separate copy — the two silently diverged and
`main`'s shell sat frozen at a pre-`localStorage` version for several releases, so the online build
appeared to save nothing at all. Building from one branch in CI is what prevents that recurring.

## Static preview pages

The download landing page also hosts click-around, read-only preview snapshots
(`docs/preview-*.html`). Regenerate them after template/CSS changes:

```bash
python scripts/build_preview_pages.py    # writes docs/preview-*.html + docs/static/*
```

## Repo layout

- `main` — the distribution branch: a README pointing at the built executables (via GitHub
  Releases), plus `docs/` — a static, server-free GitHub Pages site: `index.html` (download
  landing page) and `preview-*.html` (live preview snapshots). No application source code.
- `devversion` (this branch) — the actual application source, for anyone who wants to run it from
  source or modify it.
