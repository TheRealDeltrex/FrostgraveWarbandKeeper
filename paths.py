"""Filesystem path resolution for both dev mode (`python app.py`) and a
PyInstaller-frozen executable.

Two concerns are kept separate:
- bundle_dir(): read-only resources shipped with the app (templates, static,
  reference JSON) — resolves into PyInstaller's _MEIPASS when frozen.
- user_data_dir(): writable per-user data (warbands, portraits) — never
  inside the (read-only, temp-extracted) bundle; defaults to Documents,
  overridable via the FWK_DATA_DIR env var or a saved config file.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

APP_NAME = "FrostgraveWarbandKeeper"


def is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def bundle_dir() -> Path:
    """Read-only resources: templates, static, bundled reference data."""
    if is_frozen():
        return Path(sys._MEIPASS)  # type: ignore[attr-defined]
    return Path(__file__).resolve().parent


def _config_path() -> Path:
    appdata = os.environ.get("APPDATA")
    base = Path(appdata) if appdata else Path.home() / ".config"
    return base / APP_NAME / "config.json"


def load_config() -> dict:
    path = _config_path()
    if not path.is_file():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def save_config(config: dict) -> None:
    path = _config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(config, indent=2), encoding="utf-8")


def default_user_data_dir() -> Path:
    # Dev mode keeps data next to the source checkout (unchanged behavior,
    # existing .warbands files stay where they are). Only the frozen exe
    # defaults to Documents, since its bundle dir is a read-only temp extract.
    if is_frozen():
        return Path.home() / "Documents" / APP_NAME
    return bundle_dir() / "data"


def user_data_dir() -> Path:
    """Writable data folder (warbands + portraits). Priority:
    FWK_DATA_DIR env var > saved config > Documents/FrostgraveWarbandKeeper."""
    env = os.environ.get("FWK_DATA_DIR")
    if env:
        return Path(env)
    saved = load_config().get("data_dir")
    if saved:
        return Path(saved)
    return default_user_data_dir()


def set_user_data_dir(path: Path | str) -> None:
    cfg = load_config()
    cfg["data_dir"] = str(path)
    save_config(cfg)
