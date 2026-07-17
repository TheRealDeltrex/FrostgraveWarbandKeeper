"""Generate a printable PDF roster for a Frostgrave warband."""

from __future__ import annotations

from io import BytesIO
from pathlib import Path

from fpdf import FPDF
from PIL import Image

from frostgrave_data import (
    APPRENTICE_ITEM_SLOTS,
    CAPTAIN_TRICK_BY_ID,
    WIZARD_ITEM_SLOTS,
    format_stat,
)
from game_content import item_slot_cost
from warband_store import (
    captain_effective_stats,
    enrich_soldier,
    normalize_item_slots,
    portrait_filesystem_path,
    recompute_spell_cns,
)

# Apprentice casts with -2 to the roll => effective difficulty is wizard CN + 2
APPRENTICE_CAST_PENALTY = 2
EMPTY_SLOT = "___"


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


def _stat_line(stats: dict, include_health: bool = False) -> str:
    """Combat stats with bold labels; render with markdown=True. Health optional (soldiers)."""
    parts = [
        f"**Move:** {stats.get('move', 0)}",
        f"**Fight:** {format_stat(int(stats.get('fight', 0)))}",
        f"**Shoot:** {format_stat(int(stats.get('shoot', 0)))}",
        f"**Armour:** {stats.get('armour', 10)}",
        f"**Will:** {format_stat(int(stats.get('will', 0)))}",
    ]
    if include_health:
        parts.append(f"**Health:** {stats.get('health', 0)}")
    return _t("   ".join(parts))


def _health_line(max_health: object) -> str:
    """Max health only, bold label; render with markdown=True."""
    return _t(f"**Health:** {max_health}")


def _crop_to_square(path: Path) -> BytesIO | None:
    """Center-crop to square (no stretch); cut off excess sides/top/bottom."""
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
    except Exception:
        return None


def _draw_portrait(
    pdf: FPDF,
    rel: str | None,
    x: float,
    y: float,
    size: float = 26,
) -> None:
    """Framed portrait; crop-to-fit (no stretch). Empty frame if no image."""
    pdf.set_draw_color(50, 80, 110)
    pdf.set_line_width(0.4)
    pdf.set_fill_color(245, 248, 252)
    pdf.rect(x, y, size, size, style="DF")

    path = portrait_filesystem_path(rel)
    if path:
        cropped = _crop_to_square(path)
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
            except Exception:
                pass

    pdf.set_draw_color(40, 70, 100)
    pdf.set_line_width(0.5)
    pdf.rect(x, y, size, size, style="D")


def _spell_cn_pair(sp: dict) -> str:
    try:
        wiz_cn = int(sp.get("cn", sp.get("base_cn", 0)))
    except (TypeError, ValueError):
        wiz_cn = 0
    return f"{wiz_cn}/{wiz_cn + APPRENTICE_CAST_PENALTY}"


def _format_slots(slots: list[str], n: int, has_dagger: bool = False) -> str:
    """Format item slots (bold slot numbers, render with markdown=True); empty as ___;
    2-slot items as e.g. **2+3:** Two-Handed Weapon."""
    normalized = normalize_item_slots(slots, n)
    parts = []
    if has_dagger:
        parts.append("Dagger (free)")
    i = 0
    while i < n:
        val = (normalized[i] or "").strip()
        if not val:
            parts.append(f"**{i + 1}:**{EMPTY_SLOT}")
            i += 1
            continue
        cost = item_slot_cost(val)
        if cost >= 2 and i + 1 < n:
            nxt = (normalized[i + 1] or "").strip()
            # Second slot empty, same name, or a continuation marker
            if not nxt or nxt.lower() == val.lower() or nxt in ("—", "-", "(2h)", "(2H)"):
                parts.append(f"**{i + 1}+{i + 2}:** {val}")
                i += 2
                continue
        parts.append(f"**{i + 1}:**{val}")
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
    _draw_portrait(pdf, wiz.get("portrait"), pdf.l_margin, y0, wiz_size)
    left = pdf.l_margin + wiz_size + portrait_gap
    pdf.set_xy(left, y0)
    pdf.set_font("Helvetica", "B", 12)
    wstats = wiz.get("stats") or {}
    school = wiz.get("school", "")
    pdf.cell(
        0,
        6,
        _t(
            f"{wiz.get('name', 'Wizard')}  -  {school}  -  "
            f"Level {wiz.get('level', 0)}  -  XP {wiz.get('xp', 0)}"
        ),
        new_x="LMARGIN",
        new_y="NEXT",
    )
    pdf.set_x(left)
    pdf.set_font("Helvetica", "", 10)
    pdf.cell(
        0, 5, _health_line(wstats.get("health", 14)), new_x="LMARGIN", new_y="NEXT", markdown=True
    )
    pdf.set_x(left)
    pdf.cell(0, 5, _stat_line(wstats), new_x="LMARGIN", new_y="NEXT", markdown=True)
    slots = wiz.get("item_slots", wiz.get("items") or [])
    _write_item_block(
        pdf,
        left,
        slots,
        WIZARD_ITEM_SLOTS,
        bool(wiz.get("has_dagger")),
        "Equipment",
    )
    pdf.set_y(max(pdf.get_y(), y0 + wiz_size + 2))
    pdf.ln(2)

    # --- Apprentice ---
    if ap:
        _next_section("Apprentice")
        y0 = pdf.get_y()
        _draw_portrait(pdf, ap.get("portrait"), pdf.l_margin, y0, wiz_size)
        left = pdf.l_margin + wiz_size + portrait_gap
        pdf.set_xy(left, y0)
        pdf.set_font("Helvetica", "B", 12)
        astats = ap.get("stats") or {}
        pdf.cell(
            0,
            6,
            _t(f"{ap.get('name', 'Apprentice')}  -  {school}"),
            new_x="LMARGIN",
            new_y="NEXT",
        )
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
        pdf.cell(0, 5, _stat_line(astats), new_x="LMARGIN", new_y="NEXT", markdown=True)
        ap_slots = ap.get("item_slots", ap.get("items") or [])
        _write_item_block(
            pdf,
            left,
            ap_slots,
            APPRENTICE_ITEM_SLOTS,
            bool(ap.get("has_dagger")),
            "Equipment",
        )
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
        col_w = [58, 36, 32, 52]
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

    # Captain (if any) shares a fresh page with the Soldiers roster, above them.
    if cap:
        pdf.add_page()
        cap_slot_key = "promote_captain_item_slots" if cap.get("origin") == "promoted" else "captain_item_slots"
        cap_slots_n = int(homerules.get(cap_slot_key, 6))
        _next_section("Captain")
        y0 = pdf.get_y()
        _draw_portrait(pdf, cap.get("portrait"), pdf.l_margin, y0, wiz_size)
        left = pdf.l_margin + wiz_size + portrait_gap
        pdf.set_xy(left, y0)
        pdf.set_font("Helvetica", "B", 12)
        pdf.cell(
            0,
            6,
            _t(f"{cap.get('name', 'Captain')}  -  Level {cap.get('level', 0)}  -  XP {cap.get('xp', 0)}"),
            new_x="LMARGIN",
            new_y="NEXT",
        )
        pdf.set_x(left)
        pdf.set_font("Helvetica", "", 10)
        cstats = cap.get("stats") or {}
        cstats_eff = captain_effective_stats(cap)
        pdf.cell(
            0, 5, _health_line(cstats.get("health", 14)), new_x="LMARGIN", new_y="NEXT", markdown=True
        )
        pdf.set_x(left)
        pdf.cell(0, 5, _stat_line(cstats_eff), new_x="LMARGIN", new_y="NEXT", markdown=True)
        cap_slots = cap.get("item_slots") or []
        _write_item_block(
            pdf, left, cap_slots, cap_slots_n, bool(cap.get("has_dagger")), "Equipment"
        )
        trick_names = [
            CAPTAIN_TRICK_BY_ID[tid]["name"]
            for tid in cap.get("known_tricks") or []
            if tid in CAPTAIN_TRICK_BY_ID
        ]
        pdf.set_x(left)
        pdf.multi_cell(
            0,
            4.5,
            _t(f"**Tricks:** {', '.join(trick_names) if trick_names else 'none'}"),
            new_x="LMARGIN",
            new_y="NEXT",
            markdown=True,
        )
        pdf.set_y(max(pdf.get_y(), y0 + wiz_size + 2))
        pdf.ln(2)
    else:
        # No captain: Soldiers still starts on its own fresh page.
        pdf.add_page()

    # --- Soldiers ---
    _next_section("Soldiers")
    soldiers = [enrich_soldier(s) for s in wb.get("soldiers") or []]
    if not soldiers:
        pdf.set_font("Helvetica", "I", 10)
        pdf.cell(0, 6, _t("No soldiers hired."), new_x="LMARGIN", new_y="NEXT")
    else:
        for s in soldiers:
            if pdf.get_y() > 250:
                pdf.add_page()
            y0 = pdf.get_y()
            _draw_portrait(pdf, s.get("portrait"), pdf.l_margin, y0, sol_size)
            left = pdf.l_margin + sol_size + portrait_gap
            pdf.set_xy(left, y0)
            pdf.set_font("Helvetica", "B", 10)
            level_suffix = ""
            if homerules.get("soldier_leveling_enabled") and s.get("level", 0) > 0:
                level_suffix = f"  ·  Level {s['level']}"
            pdf.cell(
                0,
                5,
                _t(
                    f"{s.get('name', '?')}  -  {s.get('type_name', s.get('type_key', '?'))}{level_suffix}"
                ),
                new_x="LMARGIN",
                new_y="NEXT",
            )
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
            pdf.set_x(left)
            pdf.multi_cell(
                0,
                4.5,
                _t(
                    f"{_stat_line(stats)}  -  "
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
            pdf.set_y(max(pdf.get_y(), y0 + sol_size + 2))
            pdf.ln(1.5)

    # --- Base & Vault (only if something is set) — always the last page ---
    from warband_store import base_summary

    base = base_summary(wb)
    has_location = base.get("location_key") not in (None, "", "none")
    has_resources = bool(base.get("resources"))
    has_notes = bool((base.get("notes") or "").strip())
    has_base = has_location or has_resources or has_notes
    vault = wb.get("vault_items") or []

    if has_base or vault:
        pdf.add_page()

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

    if vault:
        if has_base:
            pdf.ln(6)  # one free line between the Home base and Vault sections
        if pdf.get_y() > 250:
            pdf.add_page()
        pdf.set_x(pdf.l_margin)
        _next_section("Vault")
        pdf.set_font("Helvetica", "B", 9)
        pdf.cell(0, 5, _t(f"Current gold: {wb.get('gold', 0)} gc"), new_x="LMARGIN", new_y="NEXT")
        pdf.set_x(pdf.l_margin)
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
