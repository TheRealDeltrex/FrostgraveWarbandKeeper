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

## Branches

- `devversion` (this branch) — the application source.
- `main` — distribution only: README, license and the two workflows. No source, no `docs/`.
