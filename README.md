# Frostgrave Warband Keeper

A local warband tracker for **Frostgrave (2nd Edition)**. No login, no server, no cloud — your
warbands are saved as plain files on your own machine.

Not affiliated with Osprey Games / Joseph A. McCullough.

## Download

- **💾 [Download page](https://therealdeltrex.github.io/FrostgraveWarbandKeeper/)** — packaged
  Windows and Linux builds, one click each, that save your warbands as files on your own machine.

This is the **distribution branch** — it just contains this README plus the
[download site](https://therealdeltrex.github.io/FrostgraveWarbandKeeper/). You can also grab a
packaged build directly from the [Releases page](../../releases/latest). No Python install needed on
either platform.

### Windows

1. Download `FrostgraveWarbandKeeper-win64.zip` from the latest release.
2. Unzip it anywhere (e.g. your Desktop or Documents).
3. Run `FrostgraveWarbandKeeper.exe` inside the unzipped folder. It opens in your default browser
   automatically at `http://127.0.0.1:5000`, and adds an icon to the system tray you can use to
   reopen it or quit.

Windows may show a SmartScreen warning the first time (unsigned exe) — click "More info" → "Run
anyway".

### Linux

1. Download `FrostgraveWarbandKeeper-linux-x64.tar.gz` from the latest release.
2. Extract it: `tar -xzf FrostgraveWarbandKeeper-linux-x64.tar.gz`.
3. Make it executable and run it: `chmod +x FrostgraveWarbandKeeper && ./FrostgraveWarbandKeeper`
   (or, from a file manager, right-click → Properties → allow executing, then double-click).

It opens your default browser automatically at `http://127.0.0.1:5000`. There's no tray icon on
Linux, but the app still shuts itself down on its own once you close the browser tab.

### Where your data goes

Your warband data is stored in a `Documents/FrostgraveWarbandKeeper` folder under your home
directory by default, on both platforms; the in-app **Settings** page lets you pick a different
folder.

## Features

- **Create a warband**: wizard (name, school, portrait), starting spells (3 own / 1 each aligned / 2 neutral, per 2e rules), and an optional apprentice. Soldiers are recruited afterwards on the warband page.
- **Maintain between games**: level up your wizard (stat increases, learn spells, improve spells), record post-game loot (gold, XP, items), and manage the vault. XP can be added or removed (negative XP auto-reverses lost level-ups).
- **Soldiers**: hire from the full 2e roster with correct cost/unit limits (max 8 soldiers, max 4 specialists), track status (active/injured/dead), reorder the roster, and optionally level them up.
- **Supplement content**: 12 extra mercenaries and 43 extra creatures from Thaw of the Lich Lord, Into the Breeding Pits, Forgotten Pacts, The Maze of Malcor and The Perilous Dark — each labelled with its source book.
- **Additional Rules and Homerules**: a per-warband tab with a toggle for every supplement source book (its mercenaries become hireable only when switched on), plus the optional Captain house rule — hire a Captain or promote an existing soldier into one.
- **Home base**: set a base location and buy base resources, per the 2e core rules.
- **Frostgrave Lexicon**: full spell list per school with casting numbers and descriptions, the school relationship table (own/aligned/neutral/opposed), the standard arms & armour list, and a full bestiary — every creature with its source and rules text.
- **PDF roster export**: a clean, printable warband sheet.
- **Import/export**: warbands are saved as `.warbands` files (plain JSON) that can be exported, shared, and re-imported.

## Want to modify the code?

The full Python/Flask source lives on the [`devversion` branch](../../tree/devversion) — use
that if you want to run it from source, add a house rule, or change anything.

## License

See [LICENSE](LICENSE).
