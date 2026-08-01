"""G6: the PDF roster must show the wizard's buffed stats (wizard state bonus,
e.g. Beastcrafter III's Fast/Scales), same as the web view — not raw stats."""

import pdf_export
import warband_store


def test_wizard_effective_stats_includes_state_bonus(fresh_warband):
    wb = fresh_warband
    base_move = wb["wizard"]["stats"]["move"]
    wb["wizard"]["state"] = {
        "kind": "beastcrafter",
        "tier": 3,
        "feature": "fast",
        "demon": "",
        "pacts": [],
    }
    effective = warband_store.wizard_effective_stats(wb)
    assert effective["move"] == base_move + 1
    # Raw stats on the wizard dict must be untouched — only the derived view changes.
    assert wb["wizard"]["stats"]["move"] == base_move


def test_pdf_export_uses_effective_stats(fresh_warband, monkeypatch):
    wb = fresh_warband
    wb["wizard"]["state"] = {
        "kind": "beastcrafter",
        "tier": 3,
        "feature": "fast",
        "demon": "",
        "pacts": [],
    }
    seen = {}
    real = warband_store.wizard_effective_stats

    def spy(wb_arg):
        result = real(wb_arg)
        seen["move"] = result["move"]
        return result

    monkeypatch.setattr(pdf_export, "wizard_effective_stats", spy)
    pdf_export.build_warband_pdf(wb)
    assert seen.get("move") == wb["wizard"]["stats"]["move"] + 1
