"""Pytest scaffolding (C1). Sets FWK_DATA_DIR to a scratch directory so every
test runs against a throwaway warbands/portraits folder, never the user's
real data dir. warband_store resolves its data folder lazily per call (B4),
so strictly this only needs to be set before the first call that touches
disk — set before import anyway for a single obvious point of truth."""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ["FWK_DATA_DIR"] = tempfile.mkdtemp(prefix="fwk-test-")

import warband_store  # noqa: E402
from frostgrave_data import spell_id  # noqa: E402


@pytest.fixture
def fresh_warband() -> dict:
    """A minimal, valid warband dict (Elementalist wizard, no apprentice) built
    the same way scripts/build_preview_pages.py does, so the 8-spell starting
    pick satisfies validate_starting_spells without re-deriving those rules here."""
    school = "Elementalist"
    spells = [
        spell_id(school, "Wall"),
        spell_id(school, "Elemental Bolt"),
        spell_id(school, "Elemental Shield"),
        spell_id("Chronomancer", "Fast Act"),
        spell_id("Enchanter", "Enchant Weapon"),
        spell_id("Summoner", "Leap"),
        spell_id("Necromancer", "Bone Dart"),
        spell_id("Thaumaturge", "Heal"),
    ]
    wb, msg = warband_store.create_warband(
        warband_name="Test Warband",
        wizard_name="Test Wizard",
        school=school,
        spell_keys=spells,
    )
    assert wb is not None, msg
    return wb
