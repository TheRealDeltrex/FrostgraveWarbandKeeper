# Frostgrave Warband Keeper

[![Frostgrave Warband Keeper](https://raw.githubusercontent.com/TheRealDeltrex/FrostgraveWarbandKeeper/devversion/static/logo.webp)](https://therealdeltrex.github.io/FrostgraveWarbandKeeper/)

A warband tracker for **Frostgrave (2nd Edition)**: wizard, apprentice, soldiers, spells, vault,
between-game upkeep, supplement source books, homerules, a rules lexicon and a printable roster.
No login, no server, no cloud.

Not affiliated with Osprey Games / Joseph A. McCullough.

## Play online or download

- **▶ [Play online — no install](https://therealdeltrex.github.io/FrostgraveWarbandKeeper/app/)** —
  the app runs in your browser tab. Warbands are saved in that browser only (this device, this
  browser), so **use "Export warband" for a backup** or to move a warband elsewhere. The first load
  takes a few seconds.
- **💾 [Download page](https://therealdeltrex.github.io/FrostgraveWarbandKeeper/)** — packaged
  builds that save your warbands as files on your own machine. You can also take a build from the
  [Releases page](../../releases/latest).

Windows is built for every release. Linux is discontinued and only occasionally updated, so the
latest release may not include a Linux build; the Releases page shows the most recent one.

### Windows

1. Download `FrostgraveWarbandKeeper-win64.zip` from a release.
2. Unzip it anywhere.
3. Run `FrostgraveWarbandKeeper.exe`. It opens in your default browser and adds a system tray
   icon to reopen or quit.

The exe is signed ("Deltrex") with a self-signed certificate, so Windows SmartScreen may warn the
first time: click "More info" → "Run anyway".

### Linux

1. Download `FrostgraveWarbandKeeper-linux-x64.tar.gz` from a release that has one.
2. Extract it: `tar -xzf FrostgraveWarbandKeeper-linux-x64.tar.gz`.
3. Run it: `chmod +x FrostgraveWarbandKeeper && ./FrostgraveWarbandKeeper`.

There is no tray icon; the app shuts itself down once you close the browser tab.

### Where your data goes

Packaged builds save warbands in `Documents/FrostgraveWarbandKeeper` by default. The in-app
**Settings** page lets you pick another folder. Warbands are `.warbands` files (plain JSON) that
can be exported, shared and re-imported.

## About this branch

`main` is the distribution branch: this README, the license and the release workflows. The
download and online site is built from
[`devversion`](../../tree/devversion) by the "Deploy Pages" workflow, so it always matches the
source. The full Python/Flask source lives on `devversion`; use it to run from source or change
anything.

## License

See [LICENSE](LICENSE).
