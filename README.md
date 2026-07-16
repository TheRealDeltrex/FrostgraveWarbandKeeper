# Frostgrave Warband Keeper — dev version

This branch (`devversion`) holds the **full Python/Flask source code**. It exists so the app can be
run from source, read, and altered — if you (or your gaming group) need a feature, rule tweak, or
homerule this app doesn't already support, this is the branch to work from.

If you just want to run the app and don't need to touch the code, use the prebuilt Windows
executable instead: see the [`main` branch](../../tree/main) / the
[latest Release](../../releases/latest).

A local Flask app for creating and maintaining warbands for **Frostgrave (2nd Edition)**. No login, no server — your warbands are saved as plain files on your own machine.

Not affiliated with Osprey Games / Joseph A. McCullough.

## Features

- **Create a warband**: wizard (name, school, portrait), starting spells (3 own / 1 each aligned / 2 neutral, per 2e rules), an optional apprentice, and starting soldiers.
- **Maintain between games**: level up your wizard (stat increases, learn spells, improve spells), record post-game loot (gold, XP, items), manage the vault, and keep a campaign log.
- **Soldiers**: hire from the full 2e roster with correct cost/unit limits (max 8 soldiers, max 4 specialists), track status (active/injured/dead), reorder the roster, and optionally level them up.
- **Captain homerule**: an optional, fully-tunable per-warband house rule — hire a Captain or promote an existing soldier into one, with configurable cost, starting stats, item slots, and Mind Control setting.
- **Home base**: set a base location and buy base resources, per the 2e core rules.
- **Reference pages**: full spell list per school with casting numbers and descriptions, school relationship table (own/aligned/neutral/opposed), and the standard arms & armour list.
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

## Building the Windows executable yourself

The `main` branch's Release is built from this source via [PyInstaller](https://pyinstaller.org/):

```bash
pip install -r requirements-dev.txt
python -m PyInstaller frostgrave.spec --noconfirm
```

This produces `dist/FrostgraveWarbandKeeper/` — a folder containing `FrostgraveWarbandKeeper.exe`
plus its bundled resources. Copy the whole folder wherever you want to run it from.

## Repo layout

- `main` — the distribution branch: just a README pointing at the built Windows executable (via
  GitHub Releases). No source code.
- `devversion` (this branch) — the actual application source, for anyone who wants to run it from
  source or modify it.
