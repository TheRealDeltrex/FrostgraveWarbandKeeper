# Frostgrave Warband Keeper — dev version

[![Frostgrave Warband Keeper](https://raw.githubusercontent.com/TheRealDeltrex/FrostgraveWarbandKeeper/devversion/static/logo.webp)](https://therealdeltrex.github.io/FrostgraveWarbandKeeper/)

A local Flask app for creating and maintaining warbands for **Frostgrave (2nd Edition)**. No login,
no server. Not affiliated with Osprey Games / Joseph A. McCullough.

This branch (`devversion`) holds the **full source**. To just use the app, get a build from the
[download page](https://therealdeltrex.github.io/FrostgraveWarbandKeeper/) or the
[latest Release](../../releases/latest). What the app does is best seen in the app itself and its
Lexicon page.

## Running from source

```bash
python -m venv .venv
.venv/Scripts/activate   # or source .venv/bin/activate on macOS/Linux
pip install -r requirements.txt
python app.py
```

Then open http://127.0.0.1:5000. Warband data, portraits and uploads are saved under `data/` and
are not tracked in git, unless a different folder is set in the app's Settings.

## Building the executables

Windows (build on Windows — PyInstaller can't cross-compile):

```bash
pip install -r requirements-dev.txt
python -m PyInstaller frostgrave.spec --noconfirm
```

This produces `dist/FrostgraveWarbandKeeper/`, a folder to copy wherever you want to run it from.

Linux is built on a GitHub Actions Ubuntu runner by `.github/workflows/build-linux.yml`, run
manually and only occasionally; it is not part of shipping a release. The spec is
`frostgrave-linux.spec`.

## In-browser (online) build

A zero-backend build that runs in the browser via [Pyodide](https://pyodide.org/): it loads Python
and Flask in the tab and drives the app through Flask's test client. Browser-specific UI is gated
behind `FWK_BROWSER=1`. `scripts/build_browser_bundle.py` produces it under `docs/app/`; its
docstring explains the storage and portrait handling.

## Publishing the site

`.github/workflows/deploy-pages.yml` (manual dispatch) builds `docs/` fresh from `devversion` and
deploys it straight to GitHub Pages. **Do not hand-sync generated files into `main`.**

## Static preview pages

The landing page also hosts read-only preview snapshots (`docs/preview-*.html`). Regenerate them
after template or CSS changes:

```bash
python scripts/build_preview_pages.py
```

## Branches

- `devversion` (this branch) — the application source.
- `main` — distribution only: README, license and the two workflows. No source, no `docs/`.
