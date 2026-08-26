"""Generate a printable PDF roster for a Frostgrave warband."""

from __future__ import annotations

import logging
from io import BytesIO
from pathlib import Path

from fpdf import FPDF

import expansions

try:
    from PIL import Image
except ImportError:  # pragma: no cover - only hit if Pillow genuinely isn't installed
    # fpdf2 itself hard-requires Pillow to embed any image (see _draw_portrait),
    # so this is a hard requirement, not an optional nicety. The in-browser
    # (Pyodide) build loads Pillow as a native Pyodide package (not a PyPI/
    # micropip install — Pillow has C extensions with no plain wheel Pyodide
    # can build from source) specifically so this import succeeds there too.
    Image = None

from frostgrave_data import (
    CAPTAIN_ITEM_SLOTS,
    CAPTAIN_TRICK_BY_ID,
    KNIGHTLY_ORDER_BY_ID,
    PROMOTE_CAPTAIN_ITEM_SLOTS,
    PROSTHETIC_LIMB_NAME_BY_INJURY_ID,
    PROSTHETIC_UPGRADE_BY_ID,
    SOLDIER_COMPANION_BY_TYPE_KEY,
    SOURCE_BOOKS,
    animal_companion_type_keys,
    construct_type_keys,
    format_stat,
    unused_xp,
)
from game_content import item_slot_cost
from warband_store import (
    apprentice_effective_stats,
    base_summary,
    captain_effective_stats,
    enrich_soldier,
    normalize_item_slots,
    recompute_spell_cns,
    resolve_portrait_path,
    specialist_count,
    wizard_effective_stats,
)

# The on-screen trick picker uses the full rules text, but "Coup de Grâce" and
# "Leadership" wrap onto a second line in the PDF's tighter column. Shortened
# for print only (full effect + declare inline); the canonical rules text in
# CAPTAIN_TRICKS is unchanged.
PDF_TRICK_LINE_OVERRIDES = {
    "coup_de_grace": "+2 Damage in melee attack that has dealt 1< Damage (After damage calculation)",
    "leadership": "Group Activation allows up to three soldiers (Upon activation)",
}

logger = logging.getLogger(__name__)

# Pillow raises this for an absurdly large image rather than an OSError, and it
# has to be resolvable even on the no-Pillow path above, where _crop_to_square's
# except clause would otherwise be an AttributeError waiting to happen.
DecompressionBombError = getattr(Image, "DecompressionBombError", OSError) if Image else OSError

# Apprentice casts with -2 to the roll => effective difficulty is wizard CN + 2
APPRENTICE_CAST_PENALTY = 2
# What an empty item slot prints as, after its bold "**N:**" label.
EMPTY_SLOT = " -"


class RosterPDF(FPDF):
    def footer(self):
        self.set_y(-12)
        self.set_font("Helvetica", "I", 8)
        self.set_text_color(100, 100, 100)
        self.cell(
            0,
            8,
            _t(f"Page {self.page_no()}/{{nb}} - Frostgrave Warband Keeper"),
            align="C",
        )


def _t(text: object) -> str:
    """Core PDF fonts need latin-1; normalize common unicode."""
    s = str(text or "")
    for a, b in (
        ("\u2014", "-"),
        ("\u2013", "-"),
        ("\u2018", "'"),
        ("\u2019", "'"),
        ("\u201c", '"'),
        ("\u201d", '"'),
        ("\u2022", "*"),
        ("\u00b7", "-"),
        ("\u2026", "..."),
        ("\u2212", "-"),
    ):
        s = s.replace(a, b)
    return s.encode("latin-1", errors="replace").decode("latin-1")


def _stat_line(stats: dict, include_health: bool = False, unmounted: dict | None = None) -> str:
    """Combat stats with bold labels; render with markdown=True. Health optional
    (soldiers). unmounted, if given, is this figure's Move/Fight/Armour before
    the warband horse's mount bonus — shown in brackets behind the current
    (mounted) value, matching the web UI."""

    move_bracket = f" ({unmounted['move']})" if unmounted else ""
    fight_bracket = f" ({format_stat(int(unmounted['fight']))})" if unmounted else ""
    armour_bracket = f" ({unmounted['armour']})" if unmounted else ""
    parts = [
        f"**Move:** {stats.get('move', 0)}{move_bracket}",
        f"**Fight:** {format_stat(int(stats.get('fight', 0)))}{fight_bracket}",
        f"**Shoot:** {format_stat(int(stats.get('shoot', 0)))}",
        f"**Armour:** {stats.get('armour', 10)}{armour_bracket}",
        f"**Will:** {format_stat(int(stats.get('will', 0)))}",
    ]
    if include_health:
        parts.append(f"**Health:** {stats.get('health', 0)}")
    return _t("   ".join(parts))


def _horse_rider_match(wb: dict, kind: str, soldier_id: str | None = None) -> bool:
    return expansions.is_horse_rider(wb, kind, soldier_id)


def _unmounted_overlay(wb: dict) -> dict | None:
    """This figure's Move/Fight/Armour before it climbed on the warband's
    horse, straight from the mount's stored backup — not derived by
    subtracting the Mounted Modifier from the current effective stat, because
    Armour is floored at expansions.MOUNTED_ARMOUR_FLOOR while mounted (see
    captain_effective_stats() et al.), which would make that subtraction
    silently wrong whenever the floor is doing anything. None if no one is
    currently mounted."""
    rider = (wb.get("horse") or {}).get("rider")
    return rider.get("backup") if rider else None


def _horse_companion_line(wb: dict) -> str:
    """The Riderless Horse profile (with any Advanced Horsemanship upgrade's
    effect folded in), formatted the same way SOLDIER_COMPANION_BY_TYPE_KEY's
    Blood Crow line is (see the Crow Master) — no portrait asset exists for
    it, so this is text-only."""
    s = expansions.horse_riderless_stats(wb)
    return (
        f"riding the warband's horse  "
        f"(Move {s['move']}\"  Fight {format_stat(s['fight'])}  "
        f"Armour {s['armour']}  Will {format_stat(s['will'])}  Health {s['health']})"
    )


def _health_line(max_health: object) -> str:
    """Max health only, bold label; render with markdown=True."""
    return _t(f"**Health:** {max_health}")


def _status_note(status: str | None) -> str:
    """'  -  Hungry' / '  -  Very Hungry' next to a name, mirroring how the
    web roster's status control reads; empty for active/injured/dead/unset,
    whose bookkeeping stays reminder-only rather than printed."""
    if status == "hungry":
        return "  -  Hungry"
    if status == "very_hungry":
        return "  -  Very Hungry"
    return ""


def _mutation_lines(mutations: list[dict] | None) -> list[str] | None:
    """One bold-name line per recorded mutation, same layout as a captain's
    tricks (see the "Tricks:" block below) — precise enough to resolve at
    the table, not the full rulebook prose (that stays in-app only). A
    mutation's own "short" field already reads "Name: effect", so that
    prefix is stripped here to avoid bolding the name twice. None if there's
    nothing to print, so a character with no mutations gets no block at all."""
    if not mutations:
        return None
    lines = []
    for m in mutations:
        name = m.get("name", "")
        short = m.get("short") or m.get("text", "")
        prefix = f"{name}: "
        rest = short[len(prefix):] if short.startswith(prefix) else short
        if m.get("prosthetic"):
            limb = PROSTHETIC_LIMB_NAME_BY_INJURY_ID.get(m.get("id"), "Animated Prosthetic")
            rest += f" ({limb} fitted — penalty removed)"
        for up in m.get("upgrades") or []:
            up_row = PROSTHETIC_UPGRADE_BY_ID.get(up.get("id")) or {}
            up_name = up_row.get("name", up.get("name", "?"))
            up_text = up_row.get("text")
            rest += f"; {up_name} Prosthetic Upgrade" + (f" ({up_text})" if up_text else "")
        lines.append(_t(f"**{name}:** {rest}"))
    return lines


def _restricted_item_notes(names: list[str]) -> list[dict]:
    """Every equipped item name that matches a named magic item (Lexicon
    magic_items.json, via expansions.item_restriction()) gets its rules text
    printed here, the same idea as a captain's Tricks block, so the player has
    it at the table without reopening the Lexicon — not just the ones with a
    restriction. A hand-curated `note` (extra text beyond what the numeric
    bonus fields already convey, e.g. Betrayer's Blade's support-reduction
    clause) takes priority when present; otherwise the plain Lexicon `effect`
    text is used. Mundane gear (not in magic_items.json at all) has no
    item_restriction() entry and is skipped."""
    out = []
    seen = set()
    for raw in names or []:
        name = (raw or "").strip()
        key = name.lower()
        if not name or key in seen:
            continue
        r = expansions.item_restriction(name)
        text = (r.get("note") or r.get("effect")) if r else None
        if not text:
            continue
        seen.add(key)
        out.append({"name": name, "note": text})
    return out


def _write_restricted_item_notes(pdf: FPDF, left: float, names: list[str]) -> None:
    notes = _restricted_item_notes(names)
    if not notes:
        return
    pdf.set_x(left)
    pdf.multi_cell(0, 4.5, _t("**Item notes:**"), new_x="LMARGIN", new_y="NEXT", markdown=True)
    for note in notes:
        pdf.set_x(left)
        pdf.multi_cell(
            0,
            4.5,
            _t(f"**{note['name']}** - {note['note']}"),
            new_x="LMARGIN",
            new_y="NEXT",
            markdown=True,
        )


def _component_lines(components: list[dict] | None) -> list[str] | None:
    """One line per held Monster Hunting component (Spellcaster Magazine,
    Issue 5) — name plus what it's a +1 to, same layout as _mutation_lines.
    None if there's nothing held, so a figure with an empty pouch gets no
    block at all."""
    if not components:
        return None
    lines = []
    for c in components:
        name = c.get("name", "")
        target = c.get("target")
        suffix = f" +1 {target}" if target else ""
        lines.append(_t(f"**{name}:**{suffix}"))
    return lines


def _revenant_line(is_revenant: bool) -> str | None:
    """Short rules-reminder for a soldier reanimated with the Revenant spell —
    same one-line-at-the-table treatment as _mutations_line. None if the
    soldier was never raised as a revenant."""
    if not is_revenant:
        return None
    return _t(
        "**Undead (Revenant):** Immune to poison, never counts as wounded; "
        "keeps its own weapons/armour; Will +0."
    )


def _crop_to_square(path: Path) -> BytesIO | None:
    """Center-crop to square (no stretch); cut off excess sides/top/bottom."""
    if Image is None:
        return None
    try:
        img = Image.open(path)
        img = img.convert("RGB")
        w, h = img.size
        if w <= 0 or h <= 0:
            return None
        side = min(w, h)
        left = (w - side) // 2
        top = (h - side) // 2
        img = img.crop((left, top, left + side, top + side))
        # Reasonable size for PDF
        if side > 400:
            img = img.resize((400, 400), Image.Resampling.LANCZOS)
        buf = BytesIO()
        img.save(buf, format="JPEG", quality=90)
        buf.seek(0)
        return buf
    except (OSError, ValueError, DecompressionBombError) as exc:
        # Corrupt/truncated file or a format Pillow can't identify
        # (UnidentifiedImageError is itself a subclass of OSError). ValueError
        # and DecompressionBombError cover a malformed or absurdly large image
        # — a portrait is arbitrary user-supplied bytes, and failing to crop
        # one should drop back to the empty frame, not 500 the whole export.
        logger.warning("Could not crop portrait %s for PDF export: %s", path, exc)
        return None


def _draw_portrait(
    pdf: FPDF,
    rel: str | None,
    x: float,
    y: float,
    size: float = 26,
    kind: str = "",
    type_key: str | None = None,
    gender: str | None = None,
    state: str | None = None,
) -> None:
    """Framed portrait; crop-to-fit (no stretch). Falls back to the default
    artwork shipped with the app, then to an empty frame if there is none."""
    pdf.set_draw_color(50, 80, 110)
    pdf.set_line_width(0.4)
    pdf.set_fill_color(245, 248, 252)
    pdf.rect(x, y, size, size, style="DF")

    path = resolve_portrait_path(rel, kind, type_key, gender, state)
    if path:
        cropped = _crop_to_square(path)
        # fpdf2 itself hard-requires Pillow to embed any image at all (it raises
        # OSError otherwise, regardless of input type) — there is no Pillow-free
        # fallback here. The in-browser build loads Pyodide's native Pillow
        # package for exactly this reason (see docs/app/index.html's boot()).
        if cropped is not None:
            try:
                inset = 1.0
                pdf.image(
                    cropped,
                    x=x + inset,
                    y=y + inset,
                    w=size - 2 * inset,
                    h=size - 2 * inset,
                )
            except OSError as exc:
                logger.warning("Could not embed portrait %s in PDF: %s", path, exc)

    pdf.set_draw_color(40, 70, 100)
    pdf.set_line_width(0.5)
    pdf.rect(x, y, size, size, style="D")


def _spell_cn_pair(sp: dict) -> str:
    try:
        wiz_cn = int(sp.get("cn", sp.get("base_cn", 0)))
    except (TypeError, ValueError):
        wiz_cn = 0
    return f"{wiz_cn}/{wiz_cn + APPRENTICE_CAST_PENALTY}"


def _strip_source_suffix(name: str) -> str:
    """Drop a trailing " (Book Name)" tag off an item name for display, the
    provenance the loot picker appends when an item is picked from a rulebook
    (composeRow() in warband_view.html) — useful in the app but redundant
    weight on the printed roster. Only strips when the parenthesized text is
    an exact, known source book, so a real item name with its own parens
    (e.g. "Pistol (Double-barrelled)") is left alone."""
    for book in SOURCE_BOOKS:
        suffix = f" ({book})"
        if name.endswith(suffix):
            return name[: -len(suffix)]
    return name


def _format_slots(slots: list[str], n: int, has_dagger: bool = False) -> str:
    """Format item slots (bold slot numbers, render with markdown=True); empty
    slots as EMPTY_SLOT; 2-slot items as e.g. **2+3:** Two-Handed Weapon."""
    normalized = normalize_item_slots(slots, n)
    parts = []
    if has_dagger:
        parts.append("Dagger")
    i = 0
    while i < n:
        val = (normalized[i] or "").strip()
        if not val:
            parts.append(f"**{i + 1}:**{EMPTY_SLOT}")
            i += 1
            continue
        cost = item_slot_cost(val)
        disp = _strip_source_suffix(val)
        if cost >= 2 and i + 1 < n:
            nxt = (normalized[i + 1] or "").strip()
            # Second slot empty, same name, or a continuation marker
            if not nxt or nxt.lower() == val.lower() or nxt in ("—", "-", "(2h)", "(2H)"):
                parts.append(f"**{i + 1}+{i + 2}:** {disp}")
                i += 2
                continue
        parts.append(f"**{i + 1}:** {disp}")
        i += 1
    return "  ".join(parts)


def _write_item_block(
    pdf: FPDF,
    left: float,
    slots: list,
    n: int,
    has_dagger: bool,
    label: str = "Equipment",
) -> None:
    pdf.set_x(left)
    pdf.set_font("Helvetica", "", 9)
    line = f"**{label}:** {_format_slots(slots, n, has_dagger)}"
    pdf.multi_cell(0, 4.5, _t(line), new_x="LMARGIN", new_y="NEXT", markdown=True)


def build_warband_pdf(wb: dict) -> bytes:
    recompute_spell_cns(wb)

    pdf = RosterPDF(format="A4", unit="mm")
    pdf.alias_nb_pages()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()
    pdf.set_draw_color(40, 70, 100)
    pdf.set_fill_color(230, 240, 248)

    pdf.set_font("Helvetica", "B", 18)
    pdf.set_text_color(20, 40, 60)
    pdf.cell(0, 10, _t(wb.get("name", "Warband")), new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 10)
    pdf.set_text_color(60, 60, 60)
    pdf.cell(
        0,
        6,
        _t(f"Current gold: {wb.get('gold', 0)} gc"),
        new_x="LMARGIN",
        new_y="NEXT",
    )
    # Flagged, never auto-resolved (e.g. a Fireheart Projectile Weapon
    # modification can push an existing warband over its specialist cap) —
    # the player decides whether to dismiss someone or raise the cap
    # (Additional Rules and Homerules).
    spec_cap = expansions.max_specialists(wb)
    specs = specialist_count(wb)
    if specs > spec_cap:
        pdf.set_font("Helvetica", "B", 18)
        pdf.set_text_color(180, 30, 30)
        pdf.cell(
            0,
            10,
            _t(f"TOO MANY SPECIALISTS HIRED ({specs}/{spec_cap})"),
            new_x="LMARGIN",
            new_y="NEXT",
        )
        pdf.set_text_color(60, 60, 60)
    pdf.ln(2)

    wiz = wb.get("wizard") or {}
    ap = wb.get("apprentice")
    cap = wb.get("captain")
    homerules = wb.get("homerules") or {}
    portrait_gap = 4
    wiz_size = 28
    sol_size = 20

    section_no = [1]

    def _next_section(title: str) -> None:
        _section(pdf, f"{section_no[0]}. {title}")
        section_no[0] += 1

    # --- Wizard ---
    _next_section("Wizard")
    y0 = pdf.get_y()
    school = wiz.get("school", "")
    # Lich / Beastcrafter / pact-holder, if any — it changes how the wizard levels
    # and what they may field, so it belongs on the printed sheet. Vampire and
    # Lich are also the two states with their own default portrait art.
    state_kind = expansions.state_kind(wb)
    portrait_state = "vampire" if school == "Vampire" else (
        "lich" if state_kind == expansions.STATE_LICH else None
    )
    _draw_portrait(
        pdf, wiz.get("portrait"), pdf.l_margin, y0, wiz_size, "wizard",
        gender=wiz.get("gender"), state=portrait_state,
    )
    left = pdf.l_margin + wiz_size + portrait_gap
    pdf.set_xy(left, y0)
    pdf.set_font("Helvetica", "B", 12)
    wstats = wizard_effective_stats(wb)
    state_note = ""
    if state_kind != expansions.STATE_NONE:
        state_note = f"  -  {expansions.STATE_LABELS[state_kind]}"
        if state_kind == expansions.STATE_BEASTCRAFTER:
            tier = expansions.beastcrafter_tier(wb)
            if tier:
                state_note = f"  -  {expansions.BEASTCRAFTER_TIER_BY_N[tier]['name']}"
        elif state_kind == expansions.STATE_PACT:
            held = len(expansions.pact_tiers(wb))
            state_note += f" ({held} pact{'' if held == 1 else 's'})"
    wiz_unused_xp = unused_xp(wiz.get("xp", 0), wiz.get("level", 0), expansions.xp_per_level(wb))
    pdf.cell(
        0,
        6,
        _t(
            f"{wiz.get('name', 'Wizard')}  -  {school}  -  "
            f"Level {wiz.get('level', 0)}  -  XP {wiz_unused_xp}{state_note}"
            f"{_status_note(wiz.get('status'))}"
        ),
        new_x="LMARGIN",
        new_y="NEXT",
    )
    wiz_mounted = _horse_rider_match(wb, "wizard")
    if wiz_mounted:
        pdf.set_x(left)
        pdf.set_font("Helvetica", "I", 8)
        pdf.cell(0, 4, _t(_horse_companion_line(wb)), new_x="LMARGIN", new_y="NEXT")
    pdf.set_x(left)
    pdf.set_font("Helvetica", "", 10)
    pdf.cell(
        0, 5, _health_line(wstats.get("health", 14)), new_x="LMARGIN", new_y="NEXT", markdown=True
    )
    pdf.set_x(left)
    pdf.cell(
        0,
        5,
        _stat_line(wstats, unmounted=_unmounted_overlay(wb) if wiz_mounted else None),
        new_x="LMARGIN",
        new_y="NEXT",
        markdown=True,
    )
    slots = wiz.get("item_slots", wiz.get("items") or [])
    _write_item_block(
        pdf,
        left,
        slots,
        expansions.wizard_item_slots(wb),
        bool(wiz.get("has_dagger")),
        "Equipment",
    )
    _write_restricted_item_notes(pdf, left, slots)
    wiz_mut_lines = _mutation_lines(wiz.get("mutations"))
    if wiz_mut_lines:
        pdf.set_x(left)
        pdf.multi_cell(0, 4.5, _t("**Mutations:**"), new_x="LMARGIN", new_y="NEXT", markdown=True)
        for line in wiz_mut_lines:
            pdf.set_x(left)
            pdf.multi_cell(0, 4.5, line, new_x="LMARGIN", new_y="NEXT", markdown=True)
    wiz_inj_lines = _mutation_lines(wiz.get("permanent_injuries"))
    if wiz_inj_lines:
        pdf.set_x(left)
        pdf.multi_cell(0, 4.5, _t("**Permanent Injuries:**"), new_x="LMARGIN", new_y="NEXT", markdown=True)
        for line in wiz_inj_lines:
            pdf.set_x(left)
            pdf.multi_cell(0, 4.5, line, new_x="LMARGIN", new_y="NEXT", markdown=True)
    pdf.set_y(max(pdf.get_y(), y0 + wiz_size + 2))
    pdf.ln(2)

    # --- Apprentice ---
    if ap:
        _next_section("Apprentice")
        y0 = pdf.get_y()
        _draw_portrait(
            pdf, ap.get("portrait"), pdf.l_margin, y0, wiz_size, "apprentice", gender=ap.get("gender")
        )
        left = pdf.l_margin + wiz_size + portrait_gap
        pdf.set_xy(left, y0)
        pdf.set_font("Helvetica", "B", 12)
        astats = apprentice_effective_stats(wb)
        pdf.cell(
            0,
            6,
            _t(f"{ap.get('name', 'Apprentice')}  -  {school}{_status_note(ap.get('status'))}"),
            new_x="LMARGIN",
            new_y="NEXT",
        )
        ap_mounted = _horse_rider_match(wb, "apprentice")
        if ap_mounted:
            pdf.set_x(left)
            pdf.set_font("Helvetica", "I", 8)
            pdf.cell(0, 4, _t(_horse_companion_line(wb)), new_x="LMARGIN", new_y="NEXT")
        pdf.set_x(left)
        pdf.set_font("Helvetica", "", 10)
        pdf.cell(
            0,
            5,
            _health_line(astats.get("health", 12)),
            new_x="LMARGIN",
            new_y="NEXT",
            markdown=True,
        )
        pdf.set_x(left)
        pdf.cell(
            0,
            5,
            _stat_line(astats, unmounted=_unmounted_overlay(wb) if ap_mounted else None),
            new_x="LMARGIN",
            new_y="NEXT",
            markdown=True,
        )
        ap_slots = ap.get("item_slots", ap.get("items") or [])
        _write_item_block(
            pdf,
            left,
            ap_slots,
            expansions.apprentice_item_slots(wb),
            bool(ap.get("has_dagger")),
            "Equipment",
        )
        _write_restricted_item_notes(pdf, left, ap_slots)
        ap_mut_lines = _mutation_lines(ap.get("mutations"))
        if ap_mut_lines:
            pdf.set_x(left)
            pdf.multi_cell(0, 4.5, _t("**Mutations:**"), new_x="LMARGIN", new_y="NEXT", markdown=True)
            for line in ap_mut_lines:
                pdf.set_x(left)
                pdf.multi_cell(0, 4.5, line, new_x="LMARGIN", new_y="NEXT", markdown=True)
        ap_inj_lines = _mutation_lines(ap.get("permanent_injuries"))
        if ap_inj_lines:
            pdf.set_x(left)
            pdf.multi_cell(0, 4.5, _t("**Permanent Injuries:**"), new_x="LMARGIN", new_y="NEXT", markdown=True)
            for line in ap_inj_lines:
                pdf.set_x(left)
                pdf.multi_cell(0, 4.5, line, new_x="LMARGIN", new_y="NEXT", markdown=True)
        pdf.set_y(max(pdf.get_y(), y0 + wiz_size + 2))
        pdf.ln(2)

    # --- Spells ---
    _next_section("Spells")
    spells = list(wiz.get("spells") or [])
    if not spells:
        pdf.set_font("Helvetica", "I", 10)
        pdf.cell(0, 6, _t("No spells recorded."), new_x="LMARGIN", new_y="NEXT")
    else:
        pdf.set_font("Helvetica", "I", 8)
        pdf.multi_cell(
            0,
            4,
            _t(
                "Difficulty = Wizard CN / Apprentice CN. "
                "Apprentice CN is Wizard CN + 2 ( -2 to cast roll )."
            ),
            new_x="LMARGIN",
            new_y="NEXT",
        )
        pdf.ln(1)
        pdf.set_font("Helvetica", "B", 9)
        pdf.set_fill_color(220, 232, 242)
        col_w = [50, 36, 32, 60]
        headers = ["Spell", "School", "Difficulty", "Type"]
        for w, h in zip(col_w, headers):
            pdf.cell(w, 6, _t(h), border=1, fill=True)
        pdf.ln()
        pdf.set_font("Helvetica", "", 9)
        for sp in spells:
            row = [
                str(sp.get("name", "")),
                str(sp.get("school", "")),
                _spell_cn_pair(sp),
                str(sp.get("type", "")),
            ]
            for w, val in zip(col_w, row):
                pdf.cell(w, 5.5, _t(val[:42]), border=1)
            pdf.ln()
    pdf.ln(3)

    # --- Component Bag (Spellcaster Magazine, Issue 5: Monster Hunting) ---
    # Held components get one shared field at the bottom of the front page
    # instead of duplicated under the wizard's/apprentice's own block above —
    # it's bag inventory, not a per-figure stat, so it reads better grouped.
    wiz_comp_lines = _component_lines(wiz.get("components"))
    ap_comp_lines = _component_lines(ap.get("components")) if ap else None
    if wiz_comp_lines or ap_comp_lines:
        _next_section("Component Bag")
        pdf.set_font("Helvetica", "", 9)
        if wiz_comp_lines:
            pdf.set_x(pdf.l_margin)
            wiz_comp_label = _t(f"**{wiz.get('name') or 'Wizard'}:**")
            pdf.multi_cell(0, 4.5, wiz_comp_label, new_x="LMARGIN", new_y="NEXT", markdown=True)
            for line in wiz_comp_lines:
                pdf.set_x(pdf.l_margin)
                pdf.multi_cell(0, 4.5, line, new_x="LMARGIN", new_y="NEXT", markdown=True)
        if ap_comp_lines:
            pdf.set_x(pdf.l_margin)
            ap_comp_label = _t(f"**{ap.get('name') or 'Apprentice'}:**")
            pdf.multi_cell(0, 4.5, ap_comp_label, new_x="LMARGIN", new_y="NEXT", markdown=True)
            for line in ap_comp_lines:
                pdf.set_x(pdf.l_margin)
                pdf.multi_cell(0, 4.5, line, new_x="LMARGIN", new_y="NEXT", markdown=True)
        pdf.ln(3)

    # Captain (if any) shares a fresh page with the Soldiers roster, above them.
    if cap:
        pdf.add_page()
        promoted = cap.get("origin") == "promoted"
        cap_slot_key = "promote_captain_item_slots" if promoted else "captain_item_slots"
        cap_slot_default = PROMOTE_CAPTAIN_ITEM_SLOTS if promoted else CAPTAIN_ITEM_SLOTS
        cap_slots_n = int(homerules.get(cap_slot_key, cap_slot_default))
        _next_section("Captain")
        y0 = pdf.get_y()
        _draw_portrait(pdf, cap.get("portrait"), pdf.l_margin, y0, wiz_size, "captain", cap.get("type_key"))
        left = pdf.l_margin + wiz_size + portrait_gap
        pdf.set_xy(left, y0)
        pdf.set_font("Helvetica", "B", 12)
        cap_unused_xp = unused_xp(cap.get("xp", 0), cap.get("level", 0))
        pdf.cell(
            0,
            6,
            _t(
                f"{cap.get('name', 'Captain')}  -  Level {cap.get('level', 0)}  -  "
                f"XP {cap_unused_xp}{_status_note(cap.get('status'))}"
            ),
            new_x="LMARGIN",
            new_y="NEXT",
        )
        cap_mounted = _horse_rider_match(wb, "captain")
        if cap_mounted:
            pdf.set_x(left)
            pdf.set_font("Helvetica", "I", 8)
            pdf.cell(0, 4, _t(_horse_companion_line(wb)), new_x="LMARGIN", new_y="NEXT")
        pdf.set_x(left)
        pdf.set_font("Helvetica", "", 10)
        cstats_eff = captain_effective_stats(wb, cap)
        pdf.cell(
            0, 5, _health_line(cstats_eff.get("health", 14)), new_x="LMARGIN", new_y="NEXT", markdown=True
        )
        pdf.set_x(left)
        pdf.cell(
            0,
            5,
            _stat_line(cstats_eff, unmounted=_unmounted_overlay(wb) if cap_mounted else None),
            new_x="LMARGIN",
            new_y="NEXT",
            markdown=True,
        )
        cap_slots = cap.get("item_slots") or []
        _write_item_block(
            pdf, left, cap_slots, cap_slots_n, bool(cap.get("has_dagger")), "Equipment"
        )
        _write_restricted_item_notes(pdf, left, cap_slots)
        tricks = [
            CAPTAIN_TRICK_BY_ID[tid]
            for tid in cap.get("known_tricks") or []
            if tid in CAPTAIN_TRICK_BY_ID
        ]
        pdf.set_x(left)
        if not tricks:
            pdf.multi_cell(0, 4.5, _t("**Tricks:** none"), new_x="LMARGIN", new_y="NEXT", markdown=True)
        else:
            pdf.multi_cell(0, 4.5, _t("**Tricks:**"), new_x="LMARGIN", new_y="NEXT", markdown=True)
            for trick in tricks:
                pdf.set_x(left)
                line = PDF_TRICK_LINE_OVERRIDES.get(
                    trick["id"], f"{trick['effect']} ({trick['declare']})"
                )
                pdf.multi_cell(
                    0,
                    4.5,
                    _t(f"**{trick['name']}** - {line}"),
                    new_x="LMARGIN",
                    new_y="NEXT",
                    markdown=True,
                )
        cap_mut_lines = _mutation_lines(cap.get("mutations"))
        if cap_mut_lines:
            pdf.set_x(left)
            pdf.multi_cell(0, 4.5, _t("**Mutations:**"), new_x="LMARGIN", new_y="NEXT", markdown=True)
            for line in cap_mut_lines:
                pdf.set_x(left)
                pdf.multi_cell(0, 4.5, line, new_x="LMARGIN", new_y="NEXT", markdown=True)
        cap_inj_lines = _mutation_lines(cap.get("permanent_injuries"))
        if cap_inj_lines:
            pdf.set_x(left)
            pdf.multi_cell(0, 4.5, _t("**Permanent Injuries:**"), new_x="LMARGIN", new_y="NEXT", markdown=True)
            for line in cap_inj_lines:
                pdf.set_x(left)
                pdf.multi_cell(0, 4.5, line, new_x="LMARGIN", new_y="NEXT", markdown=True)
        pdf.set_y(max(pdf.get_y(), y0 + wiz_size + 2))
        pdf.ln(2)
    else:
        # No captain: Soldiers still starts on its own fresh page.
        pdf.add_page()

    # --- Soldiers ---
    _next_section("Soldiers")
    soldiers = [enrich_soldier(wb, s) for s in wb.get("soldiers") or []]
    if not soldiers:
        pdf.set_font("Helvetica", "I", 10)
        pdf.cell(0, 6, _t("No soldiers hired."), new_x="LMARGIN", new_y="NEXT")
    else:
        for s in soldiers:
            if pdf.get_y() > 250:
                pdf.add_page()
            y0 = pdf.get_y()
            _draw_portrait(pdf, s.get("portrait"), pdf.l_margin, y0, sol_size, "soldier", s.get("type_key"))
            left = pdf.l_margin + sol_size + portrait_gap
            pdf.set_xy(left, y0)
            pdf.set_font("Helvetica", "B", 10)
            level_suffix = ""
            s_type_key = s.get("type_key")
            s_allow_animal = homerules.get("soldier_leveling_animal_companions")
            s_allow_construct = homerules.get("soldier_leveling_constructs")
            s_can_level = (
                homerules.get("soldier_leveling_enabled")
                and not s.get("temporary")
                and (s_type_key not in animal_companion_type_keys() or s_allow_animal)
                and (s_type_key not in construct_type_keys() or s_allow_construct)
            )
            if s_can_level:
                s_unused_xp = unused_xp(s.get("xp", 0), s.get("level", 0))
                level_suffix = f"  ·  Level {s.get('level', 0)}  -  XP {s_unused_xp}"
            pdf.cell(
                0,
                5,
                _t(
                    f"{s.get('name', '?')}  -  {s.get('type_name', s.get('type_key', '?'))}"
                    f"{level_suffix}{_status_note(s.get('status'))}"
                ),
                new_x="LMARGIN",
                new_y="NEXT",
            )
            companion = SOLDIER_COMPANION_BY_TYPE_KEY.get(s.get("type_key", ""))
            if companion:
                cstats = companion["stats"]
                cline = (
                    f"with {companion['name']}  "
                    f"(Move {cstats['move']}\"  Fight {format_stat(cstats['fight'])}  "
                    f"Shoot {format_stat(cstats['shoot'])}  Armour {cstats['armour']}  "
                    f"Will {format_stat(cstats['will'])}  Health {cstats['health']})"
                )
                comp_size = 9.0
                comp_y0 = pdf.get_y()
                comp_x = left + 3
                _draw_portrait(
                    pdf,
                    (s.get("companion") or {}).get("portrait"),
                    comp_x,
                    comp_y0,
                    comp_size,
                    "companion",
                    companion.get("portrait_key"),
                )
                pdf.set_xy(comp_x + comp_size + 1.5, comp_y0 + (comp_size - 3.5) / 2)
                pdf.set_font("Helvetica", "I", 7)
                pdf.cell(0, 3.5, _t(f"- {cline}"), new_x="LMARGIN", new_y="NEXT")
                pdf.set_y(comp_y0 + comp_size + 1)
            s_mounted = _horse_rider_match(wb, "soldier", s.get("id"))
            if s_mounted:
                pdf.set_x(left)
                pdf.set_font("Helvetica", "I", 7)
                pdf.cell(0, 3.5, _t(_horse_companion_line(wb)), new_x="LMARGIN", new_y="NEXT")
            pdf.set_x(left)
            pdf.set_font("Helvetica", "", 9)
            stats = {
                "move": s.get("move"),
                "fight": s.get("fight"),
                "shoot": s.get("shoot"),
                "armour": s.get("armour"),
                "will": s.get("will"),
                "health": s.get("health"),
            }
            pdf.cell(
                0,
                4.5,
                _health_line(s.get("health", 10)),
                new_x="LMARGIN",
                new_y="NEXT",
                markdown=True,
            )
            s_unmounted = _unmounted_overlay(wb) if s_mounted else None
            pdf.set_x(left)
            pdf.multi_cell(
                0,
                4.5,
                _t(
                    f"{_stat_line(stats, unmounted=s_unmounted)}  -  "
                    f"{s.get('category', '')} - {s.get('cost', 0)} gc"
                ),
                new_x="LMARGIN",
                new_y="NEXT",
                markdown=True,
            )
            pdf.set_x(left)
            pdf.multi_cell(
                0,
                4.5,
                _t(f"**Equipment:** {s.get('gear', '')}"),
                new_x="LMARGIN",
                new_y="NEXT",
                markdown=True,
            )
            s_order = KNIGHTLY_ORDER_BY_ID.get(s.get("knightly_order"))
            if s_order:
                pdf.set_x(left)
                pdf.multi_cell(
                    0,
                    4.5,
                    _t(f"**{s_order['name']}:** {s_order['ability']}"),
                    new_x="LMARGIN",
                    new_y="NEXT",
                    markdown=True,
                )
            s_slot_n = expansions.soldier_item_slots(wb, s.get("type_key", ""), s.get("item_slots"))
            s_slots = s.get("item_slots") or []
            # Creatures (animal companions/constructs) only have a slot at all
            # under the creature_item_slot_enabled homerule, and printing an
            # empty "Carried — 1: -" line for one with nothing equipped is
            # noise the user explicitly doesn't want on the roster — every
            # other soldier type keeps printing all N slots, empty or not.
            is_creature = s.get("type_key", "") in (
                expansions.animal_companion_type_keys() | expansions.construct_type_keys()
            )
            has_any_item = any((x or "").strip() for x in s_slots)
            if s_slot_n and (not is_creature or has_any_item):
                _write_item_block(pdf, left, s_slots, s_slot_n, False, "Carried")
                _write_restricted_item_notes(pdf, left, s_slots)
            s_mut_lines = _mutation_lines(s.get("mutations"))
            if s_mut_lines:
                pdf.set_x(left)
                pdf.multi_cell(0, 4.5, _t("**Mutations:**"), new_x="LMARGIN", new_y="NEXT", markdown=True)
                for line in s_mut_lines:
                    pdf.set_x(left)
                    pdf.multi_cell(0, 4.5, line, new_x="LMARGIN", new_y="NEXT", markdown=True)
            s_mod_lines = _mutation_lines(s.get("modifications"))
            if s_mod_lines:
                pdf.set_x(left)
                pdf.multi_cell(0, 4.5, _t("**Construct Modification:**"), new_x="LMARGIN", new_y="NEXT", markdown=True)
                for line in s_mod_lines:
                    pdf.set_x(left)
                    pdf.multi_cell(0, 4.5, line, new_x="LMARGIN", new_y="NEXT", markdown=True)
            s_inj_lines = _mutation_lines(s.get("permanent_injuries"))
            if s_inj_lines:
                pdf.set_x(left)
                pdf.multi_cell(0, 4.5, _t("**Permanent Injuries:**"), new_x="LMARGIN", new_y="NEXT", markdown=True)
                for line in s_inj_lines:
                    pdf.set_x(left)
                    pdf.multi_cell(0, 4.5, line, new_x="LMARGIN", new_y="NEXT", markdown=True)
            s_rev_line = _revenant_line(s.get("revenant"))
            if s_rev_line:
                pdf.set_x(left)
                pdf.multi_cell(0, 4.5, s_rev_line, new_x="LMARGIN", new_y="NEXT", markdown=True)
            pdf.set_y(max(pdf.get_y(), y0 + sol_size + 2))
            pdf.ln(1.5)

    # --- Base & Vault — always the last page; Vault always shown (see below) ---
    base = base_summary(wb)
    has_location = base.get("location_key") not in (None, "", "none")
    has_resources = bool(base.get("resources"))
    has_notes = bool((base.get("notes") or "").strip())
    has_base = has_location or has_resources or has_notes
    vault = wb.get("vault_items") or []

    pdf.add_page()  # Home base + Vault always get their own last page.

    if has_base:
        _next_section("Home base")
        if has_location:
            pdf.set_font("Helvetica", "B", 10)
            pdf.cell(
                0,
                5,
                _t(f"Location: {base['location_name']}"),
                new_x="LMARGIN",
                new_y="NEXT",
            )
            pdf.set_font("Helvetica", "", 9)
            pdf.multi_cell(
                0, 4, _t(f"Effects: {base['location_effects']}"), new_x="LMARGIN", new_y="NEXT"
            )
        if has_resources:
            pdf.set_x(pdf.l_margin)
            pdf.set_font("Helvetica", "B", 9)
            pdf.cell(0, 5, _t("Resources:"), new_x="LMARGIN", new_y="NEXT")
            pdf.set_font("Helvetica", "", 9)
            for res in base["resources"]:
                pdf.set_x(pdf.l_margin)
                pdf.multi_cell(
                    0,
                    4,
                    _t(f"* {res['name']} ({res['cost']} gc) - {res['effects']}"),
                    new_x="LMARGIN",
                    new_y="NEXT",
                )
        if has_notes:
            pdf.set_x(pdf.l_margin)
            pdf.set_font("Helvetica", "", 9)
            pdf.multi_cell(0, 4, _t(f"Notes: {base['notes']}"), new_x="LMARGIN", new_y="NEXT")

    # Vault always shows, even with no items and 0 gold — the printed sheet
    # doubles as a place to write treasure down by hand at the table.
    if has_base:
        pdf.ln(6)  # one free line between the Home base and Vault sections
    if pdf.get_y() > 250:
        pdf.add_page()
    pdf.set_x(pdf.l_margin)
    _next_section("Vault")
    pdf.set_font("Helvetica", "B", 9)
    pdf.cell(0, 5, _t(f"Current gold: {wb.get('gold', 0)} gc"), new_x="LMARGIN", new_y="NEXT")
    pdf.set_x(pdf.l_margin)
    pdf.cell(0, 5, _t("Items:"), new_x="LMARGIN", new_y="NEXT")
    if vault:
        pdf.set_font("Helvetica", "", 9)
        for it in vault:
            pdf.set_x(pdf.l_margin)
            line = f"* {it.get('name', '')}"
            if it.get("notes"):
                line += f" - {it.get('notes')}"
            pdf.multi_cell(0, 5, _t(line), new_x="LMARGIN", new_y="NEXT")

    out = BytesIO()
    pdf.output(out)
    return out.getvalue()


def _section(pdf: FPDF, title: str) -> None:
    pdf.set_x(pdf.l_margin)
    pdf.set_font("Helvetica", "B", 13)
    pdf.set_text_color(25, 55, 85)
    pdf.cell(0, 8, _t(title), new_x="LMARGIN", new_y="NEXT")
    pdf.set_draw_color(90, 140, 180)
    pdf.line(pdf.l_margin, pdf.get_y(), pdf.w - pdf.r_margin, pdf.get_y())
    pdf.ln(3)
    pdf.set_text_color(30, 30, 30)
