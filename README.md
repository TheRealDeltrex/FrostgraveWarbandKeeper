# Frostgrave Warband Keeper

A local warband tracker for **Frostgrave (2nd Edition)**. No login, no server, no cloud — your
warbands are saved as plain files on your own machine.

Not affiliated with Osprey Games / Joseph A. McCullough.

## Download

This is the **distribution branch** — it just contains this README. Grab the packaged Windows
app from the [Releases page](../../releases/latest):

1. Download `FrostgraveWarbandKeeper-win64.zip` from the latest release.
2. Unzip it anywhere (e.g. your Desktop or Documents).
3. Run `FrostgraveWarbandKeeper.exe` inside the unzipped folder. It opens in your default browser
   automatically at `http://127.0.0.1:5000`.

No Python install needed. Windows may show a SmartScreen warning the first time (unsigned exe) —
click "More info" → "Run anyway".

Your warband data is stored in `Documents\FrostgraveWarbandKeeper` by default; the in-app
**Settings** page lets you pick a different folder.

## Features

- **Create a warband**: wizard (name, school, portrait), starting spells (3 own / 1 each aligned / 2 neutral, per 2e rules), an optional apprentice, and starting soldiers.
- **Maintain between games**: level up your wizard (stat increases, learn spells, improve spells), record post-game loot (gold, XP, items), manage the vault, and keep a campaign log.
- **Soldiers**: hire from the full 2e roster with correct cost/unit limits (max 8 soldiers, max 4 specialists), track status (active/injured/dead), reorder the roster, and optionally level them up.
- **Captain homerule**: an optional, fully-tunable per-warband house rule — hire a Captain or promote an existing soldier into one.
- **Home base**: set a base location and buy base resources, per the 2e core rules.
- **Reference pages**: full spell list per school with casting numbers and descriptions, school relationship table (own/aligned/neutral/opposed), and the standard arms & armour list.
- **PDF roster export**: a clean, printable warband sheet.
- **Import/export**: warbands are saved as `.warbands` files (plain JSON) that can be exported, shared, and re-imported.

## Want to modify the code?

The full Python/Flask source lives on the [`devversion` branch](../../tree/devversion) — use
that if you want to run it from source, add a house rule, or change anything.

## License

See [LICENSE](LICENSE).
