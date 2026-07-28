# Frostgrave Warband Keeper — dev version

This branch (`devversion`) holds the **full Python/Flask source code**. It exists so the app can be
run from source, read, and altered — if you (or your gaming group) need a feature, rule tweak, or
homerule this app doesn't already support, this is the branch to work from.

If you just want to run the app and don't need to touch the code, you don't need this branch —
**download a build** (Windows or Linux) from the
[download page](https://therealdeltrex.github.io/FrostgraveWarbandKeeper/), the
[`main` branch](../../tree/main), or the [latest Release](../../releases/latest).

A local Flask app for creating and maintaining warbands for **Frostgrave (2nd Edition)**. No login, no server — your warbands are saved as plain files on your own machine.

Not affiliated with Osprey Games / Joseph A. McCullough.

## Features

- **Create a warband**: wizard (name, school, portrait), starting spells (3 own / 1 each aligned / 2 neutral, per 2e rules), and an optional apprentice. Soldiers are recruited afterwards on the warband page.
- **Maintain between games**: level up your wizard (stat increases, learn spells, improve spells), record post-game loot (gold, XP, items), and manage the vault. XP can be added or removed (negative XP auto-reverses lost level-ups).
- **Soldiers**: hire from the full 2e roster with correct cost/unit limits (max 8 soldiers, max 4 specialists), track status (active/injured/dead), reorder the roster, and optionally level them up.
- **Supplement content**: 12 extra mercenaries and 43 extra creatures from Thaw of the Lich Lord, Into the Breeding Pits, Forgotten Pacts, The Maze of Malcor and The Perilous Dark — each labelled with its source book.
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
`.github/workflows/build-linux.yml` on a GitHub Actions Ubuntu runner rather than locally):

```bash
pip install -r requirements-dev.txt
python -m PyInstaller frostgrave-linux.spec --noconfirm
```

This produces a single `dist/FrostgraveWarbandKeeper` binary (onefile, unlike the Windows onedir
build — simpler to hand to someone with just `chmod +x` and run). It skips the tray icon (see
`tray.py` / `app.py`'s `main()`) since that needs GTK/AppIndicator or X11 libraries a generic
Linux build can't assume are present; auto-shutdown-on-browser-close (`idle_watchdog.py`) still
works the same as on Windows.

## In-browser (online) build — currently not deployed

> **Removed from the live site for now.** `docs/app/` no longer exists on `main`, so there is no
> online version published at the moment. The tooling below stays in this branch so it can be
> regenerated and re-published later — to bring it back, run the generator, restore/commit
> `docs/app/index.html` (the shell) and `docs/app/bundle.json` on `main`, and re-add the
> "Play online" link to `docs/index.html`.

The online build is a zero-backend build of the app that runs entirely in the browser via
[Pyodide](https://pyodide.org/): it loads Python + Flask in the tab, unpacks the app, and drives it
through Flask's test client. Storage is in-memory only, so it's session-only — export a warband to a
file to keep it.

It embeds a copy of the app's Python, templates and reference data in a single bundle:

```bash
python scripts/build_browser_bundle.py   # writes docs/app/bundle.json
```

Browser-specific UI (session-only banner, no portraits/Settings) is gated behind `FWK_BROWSER=1` in
`app.py` and the templates.

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
