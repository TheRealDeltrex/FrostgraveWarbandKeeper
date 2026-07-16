# Frostgrave Warband Keeper

A local Flask app for creating and maintaining warbands for **Frostgrave (2nd Edition)**. No login, no server — your warbands are saved as plain files on your own machine.

Not affiliated with Osprey Games / Joseph A. McCullough.

## Features

- **Create a warband**: wizard (name, school, portrait), starting spells (3 own / 1 each aligned / 2 neutral, per 2e rules), an optional apprentice, and starting soldiers.
- **Maintain between games**: level up your wizard (stat increases, learn spells, improve spells), record post-game loot (gold, XP, items), manage the vault, and keep a campaign log.
- **Soldiers**: hire from the full 2e roster with correct cost/unit limits (max 8 soldiers, max 4 specialists), track status (active/injured/dead), and reorder the roster.
- **Home base**: set a base location and buy base resources, per the 2e core rules.
- **Reference pages**: full spell list per school with casting numbers and descriptions, school relationship table (own/aligned/neutral/opposed), and the standard arms & armour list.
- **PDF roster export**: a clean, printable warband sheet.
- **Import/export**: warbands are saved as `.warbands` files (plain JSON) that can be exported, shared, and re-imported.

## Running it

```bash
python -m venv .venv
.venv/Scripts/activate   # or source .venv/bin/activate on macOS/Linux
pip install -r requirements.txt
python app.py
```

Then open http://127.0.0.1:5000.

Warband data, portraits, and uploads are saved under `data/` and are not tracked in git.
