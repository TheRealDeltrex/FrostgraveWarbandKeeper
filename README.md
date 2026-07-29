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

The exe is signed ("Deltrex"), but with a self-signed certificate rather than a paid/trusted one,
so Windows SmartScreen may still show a warning the first time — click "More info" → "Run anyway".

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
- **Autosave**: most fields (homerules, wizard/apprentice, captain, soldier edits, spell/soldier reordering) save the instant you change them — no Save button to remember. Scroll position, open cards and your reorder selection are all preserved across the save. "After the game", "Home base" and "Treasury and Vault" stay explicit, one-shot actions.
- **Maintain between games**: level up your wizard (stat increases, learn spells, improve spells), record post-game loot with a rulebook → item → variant picker (or write in your own), and manage the vault from a combined **Treasury and Vault** card that also holds your warband notes. XP can be added or removed (negative XP auto-reverses lost level-ups).
- **Soldiers**: hire from the full 2e roster with correct cost/unit limits (max 8 soldiers, max 4 specialists), track status (active/injured/dead), reorder the roster, and optionally level them up. An optional "Adjust soldiers to Edition 2" homerule corrects a handful of costs/gear to match the second-edition rulebook, and stays in sync for soldiers already hired.
- **Captain house rule**: hire a Captain or promote an existing soldier into one, with tunable promotion cost, stat-gain caps, and absolute stat limits.
- **Character pictures**: every wizard, apprentice, captain and soldier type comes with its own artwork, shown until you upload a picture of your own. Defaults appear on the warband page and in the PDF roster.
- **Supplement content**: 12 extra mercenaries and 43 extra creatures from Thaw of the Lich Lord, Into the Breeding Pits, Forgotten Pacts, The Maze of Malcor and The Perilous Dark — each labelled with its source book. Wizard states (Lichdom, Beastcrafter, Demonic Pacts) are tracked right on the Wizard card.
- **Additional Rules and Homerules**: a per-warband tab with a toggle for every supplement source book (its mercenaries become hireable only when switched on).
- **Home base**: set a base location and buy base resources, per the 2e core rules.
- **Frostgrave Lexicon**: the full spell list per school (including the Lost Schools from The Maze of Malcor) with casting numbers and descriptions, the school relationship table, arms/armour/consumables, a full bestiary, random encounter tables, per-book loot tables, and a collapsible magic items & treasure reference — every entry tagged with its source book.
- **PDF roster export**: a clean, printable warband sheet.
- **Import/export**: warbands are saved as `.warbands` files (plain JSON) that can be exported, shared, and re-imported.

## Want to modify the code?

The full Python/Flask source lives on the [`devversion` branch](../../tree/devversion) — use
that if you want to run it from source, add a house rule, or change anything.

## License

See [LICENSE](LICENSE).
