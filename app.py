"""
Frostgrave Warband Creator & Maintainer
Create wizards (name, school, picture, spells), apprentices, soldiers,
level-up, post-game loot, and PDF rosters. Data saved locally (no login).
"""

from __future__ import annotations

import os
import subprocess
import sys
import threading
import webbrowser

import paths
from flask import (
    Flask,
    Response,
    abort,
    flash,
    redirect,
    render_template,
    request,
    send_from_directory,
    url_for,
)
from werkzeug.utils import secure_filename

from frostgrave_data import (
    ALIGNED_SCHOOL_SPELLS,
    APPRENTICE_COST,
    APPRENTICE_ITEM_SLOTS,
    BASE_LOCATIONS,
    BASE_RESOURCES,
    bonus_choice_amount,
    CAPTAIN_MIND_CONTROL_LABELS,
    CAPTAIN_MIND_CONTROL_OPTIONS,
    CAPTAIN_MODE_LABELS,
    CAPTAIN_MODE_OPTIONS,
    CAPTAIN_TRICK_BY_ID,
    CAPTAIN_TRICKS,
    LEVEL_UP_OPTIONS,
    LEVELUP_STATS,
    MAX_SOLDIERS,
    MAX_SPECIALISTS,
    NEUTRAL_SPELLS,
    OWN_SCHOOL_SPELLS,
    SCHOOL_ALIGNED,
    SCHOOL_NEUTRAL,
    SCHOOL_OPPOSED,
    SCHOOL_RELATIONS,
    SCHOOLS,
    PENTANGLE_SCHOOLS,
    SOLDIERS,
    SOURCE_BOOK_BY_SLUG,
    SOURCE_BOOK_OPTIONS,
    SOURCE_BOOKS,
    SPELLS,
    STARTING_GOLD,
    STARTING_SPELL_COUNT,
    WIZARD_ITEM_SLOTS,
    XP_PER_LEVEL,
    all_spells_flat,
    cn_penalty,
    format_stat,
    level_from_xp,
    group_soldiers_by_source,
    soldier_list_for_ui,
    spell_id,
    spells_for_wizard_ui,
)
from game_content import (
    enrich_spells_with_descriptions,
    group_magic_items,
    load_bestiary,
    load_expansion_rules,
    load_ghost_archipelago,
    load_magic_items,
    magic_items_for_sources,
    load_loot_tables,
    load_potion_choices,
    load_potion_choices_detailed,
    load_random_encounters,
    load_spell_descriptions,
    load_spell_names,
    load_spellcaster_items,
    load_standard_items,
    spell_description,
)
import expansions
from idle_watchdog import note_closing, note_heartbeat
from warband_store import (
    PORTRAIT_DIR,
    WARBAND_DIR,
    add_captain_xp,
    add_history,
    add_pact_tier,
    add_soldier,
    add_soldier_xp,
    add_vault_item,
    add_wizard_xp,
    adjust_gold,
    apply_captain_level_up,
    apply_captain_trick,
    apply_level_up,
    apply_soldier_level_up,
    advance_beastcrafter,
    break_wizard_pact,
    reverse_last_captain_level_up,
    reverse_last_level_up,
    reverse_last_soldier_level_up,
    base_summary,
    buy_base_resource,
    captain_effective_stats,
    create_warband,
    default_homerules,
    delete_warband,
    dismiss_apprentice,
    dismiss_captain,
    duplicate_warband,
    enabled_sources,
    enrich_soldier,
    export_warband_json,
    hire_apprentice,
    hire_captain,
    import_warband_json,
    animal_companion_limit,
    default_portrait_name,
    portrait_filesystem_path,
    has_animal_companion,
    known_spell_ids,
    known_spell_names,
    list_warbands,
    load_warband,
    normalize_item_slots,
    promote_soldier_to_captain,
    raise_revenant,
    recompute_spell_cns,
    record_game_loot,
    recruit_preview,
    remove_soldier,
    remove_vault_item,
    reorder_soldiers,
    reorder_spells,
    save_portrait,
    save_warband,
    sell_or_remove_base_resource,
    set_animal_feature,
    set_base_location,
    set_soldier_status,
    set_wizard_state,
    update_homerules,
    warband_limits,
)

_BUNDLE_DIR = paths.bundle_dir()
app = Flask(
    __name__,
    template_folder=str(_BUNDLE_DIR / "templates"),
    static_folder=str(_BUNDLE_DIR / "static"),
)
app.secret_key = os.environ.get("SECRET_KEY", "frostgrave-dev-key")
app.config["MAX_CONTENT_LENGTH"] = 8 * 1024 * 1024  # 8 MB uploads

# Set by the in-browser (Pyodide) build. When on, the UI drops the desktop-only
# Settings/native-folder-picker affordance and shows a "session only — export to
# save" reminder, since nothing persists. PDF export and portrait uploads both
# still work — they just don't survive a refresh or round-trip through export.
BROWSER_MODE = os.environ.get("FWK_BROWSER") == "1"


def portrait_src(portrait: str | None, kind: str, type_key: str | None = None) -> str | None:
    """URL of the picture to show for a character: their uploaded one, else the
    default artwork shipped with the app. None means neither exists, and the
    template should fall back to its "?" placeholder.

    Checks the file actually exists (same as resolve_portrait_path(), used for
    the PDF) rather than trusting the stored path blindly — a warband can carry
    a portrait reference to a file that's no longer there (e.g. an imported
    .warbands file, since portrait bytes are never included in the export)."""
    if portrait and portrait_filesystem_path(portrait):
        return url_for("portrait_file", relpath=portrait)
    name = default_portrait_name(kind, type_key)
    return url_for("static", filename=f"portraits/{name}") if name else None


app.jinja_env.globals.update(
    portrait_src=portrait_src,
    bonus_choice_amount=bonus_choice_amount,
    format_stat=format_stat,
    STARTING_GOLD=STARTING_GOLD,
    APPRENTICE_COST=APPRENTICE_COST,
    MAX_SOLDIERS=MAX_SOLDIERS,
    MAX_SPECIALISTS=MAX_SPECIALISTS,
    STARTING_SPELL_COUNT=STARTING_SPELL_COUNT,
    XP_PER_LEVEL=XP_PER_LEVEL,
    OWN_SCHOOL_SPELLS=OWN_SCHOOL_SPELLS,
    ALIGNED_SCHOOL_SPELLS=ALIGNED_SCHOOL_SPELLS,
    NEUTRAL_SPELLS=NEUTRAL_SPELLS,
    LEVEL_UP_OPTIONS=LEVEL_UP_OPTIONS,
    WIZARD_ITEM_SLOTS=WIZARD_ITEM_SLOTS,
    APPRENTICE_ITEM_SLOTS=APPRENTICE_ITEM_SLOTS,
    CAPTAIN_MIND_CONTROL_OPTIONS=CAPTAIN_MIND_CONTROL_OPTIONS,
    CAPTAIN_MIND_CONTROL_LABELS=CAPTAIN_MIND_CONTROL_LABELS,
    CAPTAIN_MODE_OPTIONS=CAPTAIN_MODE_OPTIONS,
    CAPTAIN_MODE_LABELS=CAPTAIN_MODE_LABELS,
    CAPTAIN_TRICKS=CAPTAIN_TRICKS,
    CAPTAIN_TRICK_BY_ID=CAPTAIN_TRICK_BY_ID,
    LEVELUP_STATS=LEVELUP_STATS,
    level_from_xp=level_from_xp,
    captain_effective_stats=captain_effective_stats,
    IS_FROZEN=paths.is_frozen(),
    BROWSER_MODE=BROWSER_MODE,
    # Wizard states (Lich / Beastcrafter / Demonic Pact).
    STATE_LABELS=expansions.STATE_LABELS,
    STATE_SOURCE=expansions.STATE_SOURCE,
    STATE_NONE=expansions.STATE_NONE,
    STATE_LICH=expansions.STATE_LICH,
    STATE_BEASTCRAFTER=expansions.STATE_BEASTCRAFTER,
    STATE_PACT=expansions.STATE_PACT,
    LICH_FAILURE_TABLE=expansions.LICH_FAILURE_TABLE,
    LICH_NOTES=expansions.LICH_NOTES,
    LICH_XP_PER_LEVEL=expansions.LICH_XP_PER_LEVEL,
    LICH_STAT_CAPS=expansions.LICH_STAT_CAPS,
    LICH_FORBIDDEN_LEVELUP=expansions.LICH_FORBIDDEN_LEVELUP,
    LICH_FORBIDDEN_SPELLS=expansions.LICH_FORBIDDEN_SPELLS,
    BEASTCRAFTER_TIERS=expansions.BEASTCRAFTER_TIERS,
    ANIMAL_FEATURES=expansions.ANIMAL_FEATURES,
    ANIMAL_FEATURE_BY_ID=expansions.ANIMAL_FEATURE_BY_ID,
    PACT_SACRIFICES=expansions.PACT_SACRIFICES,
    PACT_BOONS=expansions.PACT_BOONS,
    PACT_SACRIFICE_BY_ID=expansions.PACT_SACRIFICE_BY_ID,
    PACT_BOON_BY_ID=expansions.PACT_BOON_BY_ID,
    PACT_TIER_LEVELS=expansions.PACT_TIER_LEVELS,
    PACT_MAX_TIERS=expansions.PACT_MAX_TIERS,
)


def _stats_with_state_bonus(wb: dict) -> dict:
    """The wizard's stats as they play, with any wizard-state bonus folded in."""
    stats = dict((wb.get("wizard") or {}).get("stats") or {})
    for stat, amount in expansions.wizard_state_stat_bonus(wb).items():
        stats[stat] = int(stats.get(stat, 0)) + amount
    return stats


def _require_warband(warband_id: str) -> dict:
    wb = load_warband(warband_id)
    if not wb:
        abort(404)
    return wb


def _parse_signed_int(raw: str | None) -> int | None:
    """Accepts "30", "+30", or "-30" (surrounding whitespace ok); None if not a whole number."""
    raw = (raw or "").strip()
    if not raw:
        return None
    try:
        return int(raw)
    except ValueError:
        return None


@app.route("/")
def home():
    return render_template("index.html", warbands=list_warbands())


@app.route("/reference")
def reference():
    descs = load_spell_descriptions()
    spells_with_desc = {
        school: [
            {
                **sp,
                "source": sp.get("source", "Core Rules"),
                "description": descs.get(sp["name"], "") or "No description available.",
            }
            for sp in splist
        ]
        for school, splist in SPELLS.items()
    }
    all_soldiers = soldier_list_for_ui()
    return render_template(
        "reference.html",
        soldiers=all_soldiers,
        soldier_groups=group_soldiers_by_source(all_soldiers),
        schools=SCHOOLS,
        pentangle_schools=PENTANGLE_SCHOOLS,
        spells=spells_with_desc,
        opposed=SCHOOL_OPPOSED,
        aligned=SCHOOL_ALIGNED,
        neutral=SCHOOL_NEUTRAL,
        relations=SCHOOL_RELATIONS,
        standard_items=load_standard_items(),  # full list incl. armour (for reference)
        potion_choices=load_potion_choices(),
        potions_detailed=load_potion_choices_detailed(),
        bestiary=load_bestiary(),
        spell_names=load_spell_names(),
        # The Lexicon is a browsable reference, so unlike the warband page none
        # of this is filtered by source toggles — same as the bestiary already is.
        magic_item_groups=group_magic_items(load_magic_items()),
        magic_item_count=len(load_magic_items()),
        expansion_rules=load_expansion_rules(),
        random_encounters=load_random_encounters(),
        loot_tables=load_loot_tables(),
        ghost=load_ghost_archipelago(),
    )


@app.route("/about")
def about():
    return render_template("about.html")


@app.route("/heartbeat", methods=["POST"])
def heartbeat():
    """Pinged periodically by every open page — see idle_watchdog.py."""
    note_heartbeat()
    return ("", 204)


@app.route("/heartbeat/closing", methods=["POST"])
def heartbeat_closing():
    """Pinged via sendBeacon when a page unloads — see idle_watchdog.py."""
    note_closing()
    return ("", 204)


@app.route("/portraits/<path:relpath>")
def portrait_file(relpath: str):
    if ".." in relpath:
        abort(404)
    return send_from_directory(PORTRAIT_DIR, relpath)


# ---- Create warband (wizard + spells + apprentice) ------------------------

@app.route("/warband/new", methods=["GET", "POST"])
def warband_new():
    if request.method == "POST":
        name = (request.form.get("warband_name") or "").strip()
        wizard = (request.form.get("wizard_name") or "").strip()
        school = request.form.get("school") or SCHOOLS[0]
        pentangle = request.form.get("pentangle_schools_playable") == "on"
        if school not in _new_schools(_posted_sources(request.form), pentangle):
            school = SCHOOLS[0]
        # Order preserved from hidden field if present
        order_raw = (request.form.get("spell_order") or "").strip()
        if order_raw:
            spell_keys = [k for k in order_raw.split("|") if k]
        else:
            spell_keys = request.form.getlist("spells")
        with_apprentice = request.form.get("with_apprentice") == "on"
        apprentice_name = (request.form.get("apprentice_name") or "").strip()
        sources = _posted_sources(request.form)

        if not name or not wizard:
            flash("Warband name and wizard name are required.", "error")
            return _render_new(school=school, selected=spell_keys, sources=sources,
                               pentangle=pentangle)

        # Soldiers are not hired at creation — they're recruited later on the
        # warband page (from the full roster, including supplement mercenaries).
        wb, msg = create_warband(
            name,
            wizard,
            school,
            spell_keys,
            with_apprentice,
            apprentice_name,
            enabled_sources_map=sources,
            pentangle_playable=pentangle,
        )
        if not wb:
            flash(msg, "error")
            return _render_new(school=school, selected=spell_keys, sources=sources,
                               pentangle=pentangle)

        try:
            wiz_file = request.files.get("wizard_portrait")
            if wiz_file and wiz_file.filename:
                rel = save_portrait(wb["id"], "wizard", wiz_file)
                wb["wizard"]["portrait"] = rel
            if with_apprentice and wb.get("apprentice"):
                ap_file = request.files.get("apprentice_portrait")
                if ap_file and ap_file.filename:
                    rel = save_portrait(wb["id"], "apprentice", ap_file)
                    wb["apprentice"]["portrait"] = rel
        except ValueError as exc:
            flash(str(exc), "error")

        save_warband(wb)
        flash(f"Warband “{wb['name']}” created with {wb['gold']} gc.", "success")
        return redirect(url_for("warband_view", warband_id=wb["id"]))

    school = request.args.get("school") or SCHOOLS[0]
    # Source toggles survive the school-change round-trip via the query string,
    # so switching school doesn't silently untick the books already chosen.
    return _render_new(
        school=school,
        sources=_posted_sources(request.args),
        pentangle=request.args.get("pentangle_schools_playable") == "on",
    )


def _new_schools(sources: dict, pentangle: bool) -> list[str]:
    """Schools offered on the creation page for these toggles."""
    if pentangle and sources.get("The Maze of Malcor"):
        return list(SCHOOLS) + list(PENTANGLE_SCHOOLS)
    return list(SCHOOLS)


def _posted_sources(form) -> dict:
    """{book name: bool} from the source_enabled_<slug> checkboxes, in whichever
    form or query string they arrived."""
    return {
        book: form.get(f"source_enabled_{slug}") == "on"
        for slug, book in SOURCE_BOOK_BY_SLUG.items()
    }


def _render_new(
    school: str = "Elementalist",
    selected: list | None = None,
    sources: dict | None = None,
    pentangle: bool = False,
):
    sources = sources or {}
    schools = _new_schools(sources, pentangle)
    school = school if school in schools else SCHOOLS[0]
    rel = SCHOOL_RELATIONS[school]
    # A Pentangle school has two aligned schools where a core school has three,
    # so the leftover neutral picks differ. Derived the same way
    # validate_starting_spells derives it, so the counter can't drift from the
    # rule it is counting towards.
    neutral_needed = (
        STARTING_SPELL_COUNT - OWN_SCHOOL_SPELLS - len(rel["aligned"]) * ALIGNED_SCHOOL_SPELLS
    )
    picked = {"Core Rules"} | {book for book, on in sources.items() if on}
    # Starting spells come only from books the player has switched on here. The
    # spell-only schools (Beastcrafter) never appear: they aren't in any wizard's
    # own/aligned/neutral set, which the picker is already built from.
    spells_ui = [sp for sp in spells_for_wizard_ui(school) if sp["source"] in picked]
    spells_ui = enrich_spells_with_descriptions(spells_ui)
    return render_template(
        "warband_new.html",
        schools=schools,
        school=school,
        spells_for_wizard=spells_ui,
        spells_by_school=SPELLS,
        opposed=SCHOOL_OPPOSED,
        aligned=SCHOOL_ALIGNED,
        neutral=SCHOOL_NEUTRAL,
        relations=rel,
        selected=selected or [],
        source_books=SOURCE_BOOK_OPTIONS,
        enabled_sources_map=sources,
        pentangle_playable=pentangle,
        PENTANGLE_SCHOOLS=PENTANGLE_SCHOOLS,
        neutral_needed=neutral_needed,
    )


# ---- View / maintain ------------------------------------------------------

@app.route("/warband/<warband_id>")
def warband_view(warband_id: str):
    wb = _require_warband(warband_id)
    recompute_spell_cns(wb)
    all_soldiers = wb.get("soldiers") or []
    def _is_temporary(s):
        return bool(SOLDIERS.get(s.get("type_key", ""), {}).get("temporary"))
    soldiers = [enrich_soldier(wb, s) for s in all_soldiers if not _is_temporary(s)]
    temporary_members = [enrich_soldier(wb, s) for s in all_soldiers if _is_temporary(s)]
    limits = warband_limits(wb)
    known = known_spell_ids(wb)
    wschool = (wb.get("wizard") or {}).get("school") or "Elementalist"
    wb_sources = enabled_sources(wb)
    # Only spells this warband could actually learn: its books are on and the
    # wizard's state allows them. Spells already known are excluded here but are
    # never hidden from the wizard's own list, even if their book is later
    # switched off — that would read as the app deleting a learned spell.
    learnable = [
        {**s, "effective_cn": s["cn"] + cn_penalty(wschool, s["school"])}
        for s in all_spells_flat()
        if s["id"] not in known and expansions.spell_available(wb, s, wb_sources)
    ]
    wiz_spells = (wb.get("wizard") or {}).get("spells") or []
    wiz_spells = enrich_spells_with_descriptions(wiz_spells)
    learnable = enrich_spells_with_descriptions(learnable)
    vault_names = []
    seen = set()
    for it in wb.get("vault_items") or []:
        name = (it.get("name") if isinstance(it, dict) else str(it) or "").strip()
        if name and name not in seen:
            seen.add(name)
            vault_names.append(name)
    # Only what this warband can actually hire: books it has switched on, the
    # spell-summoned members its wizard knows the spell for, and nothing its
    # wizard's state forbids. Filtering here rather than in the template keeps
    # empty source groups from rendering a heading with nothing under it.
    wb_spells = known_spell_names(wb)
    hireable = [
        {**c, "cost": expansions.soldier_cost(wb, c, c["key"])}
        for c in soldier_list_for_ui()
        if c["source"] in wb_sources
        and (not c.get("requires_spell") or c["requires_spell"] in wb_spells)
        and expansions.soldier_state_block(wb, c["key"]) is None
    ]
    # The temporary-member catalog (Raise Zombie, Summon Demon) gets its own
    # "Hire temporary member" panel instead of living in the main hire table.
    temporary_catalog = [c for c in hireable if c.get("temporary")]
    hireable = [c for c in hireable if not c.get("temporary")]
    # Groups (zombie/demon) that already have a live member on the table —
    # disables the matching Hire button, mirroring Animal Companion's block.
    temporary_groups_occupied = {
        SOLDIERS[s["type_key"]]["temporary_group"]
        for s in all_soldiers
        if s.get("status") != "dead" and _is_temporary(s)
    }
    return render_template(
        "warband_view.html",
        wb=wb,
        soldiers=soldiers,
        temporary_members=temporary_members,
        temporary_groups_occupied=temporary_groups_occupied,
        limits=limits,
        catalog_groups=group_soldiers_by_source(hireable),
        temporary_catalog=temporary_catalog,
        known_spell_names=wb_spells,
        has_animal_companion=has_animal_companion(wb),
        animal_companion_limit=animal_companion_limit(wb),
        schools=SCHOOLS,
        learnable=learnable,
        pending_levels=limits["pending_levels"],
        relations=SCHOOL_RELATIONS.get(wschool, {}),
        base=base_summary(wb),
        base_locations=BASE_LOCATIONS,
        # Supplement resources (Crow Roost, Gondola Repair Shop) only appear once
        # their book is on. Anything already owned stays listed regardless, so a
        # book switched off later never hides something the warband paid for.
        base_resources={
            key: info
            for key, info in BASE_RESOURCES.items()
            if info.get("source", "Core Rules") in wb_sources
            or key in ((wb.get("base") or {}).get("resources") or [])
        },
        standard_items=load_spellcaster_items(),  # no armour for wizard/apprentice UI
        full_standard_items=load_standard_items(),  # includes armour/shield: captain picker + reference list
        wizard_spells_ui=wiz_spells,
        vault_names=vault_names,
        potion_choices=load_potion_choices(),
        # Scroll / Grimoire item slots list spell names, so they follow the same
        # source gating as everything else — a warband with a book off should not
        # be offered a Scroll of Lichdom.
        spell_names=sorted(
            {s["name"] for s in all_spells_flat() if s["source"] in wb_sources}, key=str.lower
        ),
        source_books=SOURCE_BOOK_OPTIONS,
        enabled_source_names=wb_sources,
        wizard_state=expansions.wizard_state(wb),
        wizard_state_kind=expansions.state_kind(wb),
        # The Beastcrafter III Animal Feature (Fast / Scales) is a real stat
        # change, so the wizard card shows the boosted value. The stored stats
        # stay clean — the feature is reversible by picking another one.
        wizard_display_stats=_stats_with_state_bonus(wb),
        wizard_state_bonus=expansions.wizard_state_stat_bonus(wb),
        beastcrafter_tier=expansions.beastcrafter_tier(wb),
        pact_tiers=expansions.pact_tiers(wb),
        can_advance_beastcrafter=expansions.can_advance_beastcrafter(wb),
        can_add_pact_tier=expansions.can_add_pact_tier(wb),
        pact_break_penalty=expansions.pact_break_penalty(wb),
        wizard_level_up_options=expansions.level_up_options(wb),
        # Treasure from the enabled books, offered as suggestions on the vault's
        # "Add item" field. It stays a free-text box — this only saves typing.
        magic_item_names=sorted(
            {it["name"] for it in magic_items_for_sources(wb_sources)}, key=str.lower
        ),
        knows_revenant=expansions.REVENANT_SPELL in wb_spells,
        # Rulebook -> item -> power level/spell cascading picker, shared by the
        # After the Game card and the Vault's Add item field. Scoped to this
        # warband's enabled sources, same as magic_item_names above and the
        # learnable-spell list — a book that's off shouldn't leak its content
        # into the page even inside a picker; "Other / write-in" is the escape
        # hatch for anything else actually found at the table.
        loot_picker_books=sorted(wb_sources, key=lambda b: (b != "Core Rules", b)),
        loot_picker_data={
            "items_by_book": {
                book: sorted(
                    {it["name"] for it in magic_items_for_sources({book})}, key=str.lower
                )
                for book in wb_sources
            },
            "spell_names": sorted(
                {s["name"] for s in all_spells_flat() if s["source"] in wb_sources}, key=str.lower
            ),
        },
    )


@app.route("/warband/<warband_id>/update", methods=["POST"])
def warband_update(warband_id: str):
    wb = _require_warband(warband_id)
    action = request.form.get("action") or ""

    try:
        if action == "details":
            _update_details(wb)
            save_warband(wb)
            flash("Details saved.", "success")

        elif action == "set_notes":
            wb["notes"] = request.form.get("notes") or ""
            save_warband(wb)
            flash("Notes saved.", "success")

        elif action == "hire_soldier":
            ok, msg = add_soldier(
                wb,
                request.form.get("type_key") or "",
                (request.form.get("soldier_name") or "").strip(),
            )
            flash(msg, "success" if ok else "error")
            if ok:
                # optional portrait on hire
                f = request.files.get("soldier_portrait")
                if f and f.filename and wb["soldiers"]:
                    sid = wb["soldiers"][-1]["id"]
                    rel = save_portrait(wb["id"], f"soldier_{sid}", f)
                    wb["soldiers"][-1]["portrait"] = rel
                save_warband(wb)

        elif action == "remove_soldier":
            ok, msg = remove_soldier(
                wb,
                request.form.get("soldier_id") or "",
                refund=request.form.get("refund") == "on",
            )
            flash(msg, "success" if ok else "error")
            if ok:
                save_warband(wb)

        elif action == "soldier_status":
            ok, msg = set_soldier_status(
                wb,
                request.form.get("soldier_id") or "",
                request.form.get("status") or "active",
            )
            flash(msg, "success" if ok else "error")
            if ok:
                save_warband(wb)

        elif action == "soldier_edit":
            sid = request.form.get("soldier_id") or ""
            for s in wb.get("soldiers") or []:
                if s.get("id") == sid:
                    s["name"] = (request.form.get("soldier_name") or s.get("name", "")).strip()
                    s["notes"] = request.form.get("notes") or ""
                    f = request.files.get("soldier_portrait")
                    if f and f.filename:
                        s["portrait"] = save_portrait(wb["id"], f"soldier_{sid}", f)
                    save_warband(wb)
                    flash(f"Updated {s['name']}.", "success")
                    break
            else:
                flash("Soldier not found.", "error")

        elif action == "hire_apprentice":
            ok, msg = hire_apprentice(wb, (request.form.get("apprentice_name") or "").strip())
            flash(msg, "success" if ok else "error")
            if ok:
                f = request.files.get("apprentice_portrait")
                if f and f.filename:
                    wb["apprentice"]["portrait"] = save_portrait(wb["id"], "apprentice", f)
                save_warband(wb)

        elif action == "dismiss_apprentice":
            ok, msg = dismiss_apprentice(wb, refund=request.form.get("refund") == "on")
            flash(msg, "success" if ok else "error")
            if ok:
                save_warband(wb)

        elif action == "update_homerules":
            ok, msg = update_homerules(wb, request.form)
            flash(msg, "success" if ok else "error")
            if ok:
                save_warband(wb)

        elif action == "set_wizard_state":
            ok, msg = set_wizard_state(wb, request.form.get("state_kind") or "")
            flash(msg, "success" if ok else "error")
            if ok:
                save_warband(wb)

        elif action == "advance_beastcrafter":
            ok, msg = advance_beastcrafter(wb)
            flash(msg, "success" if ok else "error")
            if ok:
                save_warband(wb)

        elif action == "set_animal_feature":
            ok, msg = set_animal_feature(wb, request.form.get("feature") or "")
            flash(msg, "success" if ok else "error")
            if ok:
                save_warband(wb)

        elif action == "add_pact_tier":
            ok, msg = add_pact_tier(
                wb,
                request.form.get("sacrifice") or "",
                request.form.get("boon") or "",
                (request.form.get("demon") or "").strip(),
            )
            flash(msg, "success" if ok else "error")
            if ok:
                save_warband(wb)

        elif action == "break_pact":
            ok, msg = break_wizard_pact(wb)
            flash(msg, "success" if ok else "error")
            if ok:
                save_warband(wb)

        elif action == "raise_revenant":
            ok, msg = raise_revenant(wb, request.form.get("soldier_id") or "")
            flash(msg, "success" if ok else "error")
            if ok:
                save_warband(wb)

        elif action == "hire_captain":
            ok, msg = hire_captain(
                wb,
                (request.form.get("captain_name") or "").strip(),
                request.form.get("captain_extra_stat") or None,
                request.form.getlist("captain_tricks"),
            )
            flash(msg, "success" if ok else "error")
            if ok:
                f = request.files.get("captain_portrait")
                if f and f.filename:
                    wb["captain"]["portrait"] = save_portrait(wb["id"], "captain", f)
                save_warband(wb)

        elif action == "dismiss_captain":
            ok, msg = dismiss_captain(wb, refund=request.form.get("refund") == "on")
            flash(msg, "success" if ok else "error")
            if ok:
                save_warband(wb)

        elif action == "captain_edit":
            cap = wb.get("captain")
            if not cap:
                flash("No captain hired.", "error")
            else:
                cap["name"] = (request.form.get("captain_name") or cap.get("name", "")).strip()
                cap["notes"] = request.form.get("captain_notes") or ""
                cap["has_dagger"] = request.form.get("captain_dagger") == "on"
                hr = wb.get("homerules") or {}
                slot_key = (
                    "promote_captain_item_slots"
                    if cap.get("origin") == "promoted"
                    else "captain_item_slots"
                )
                n = int(hr.get(slot_key, 6))
                slots = [(request.form.get(f"captain_slot_{i}") or "").strip() for i in range(n)]
                cap["item_slots"] = normalize_item_slots(slots, n)
                f = request.files.get("captain_portrait")
                if f and f.filename:
                    cap["portrait"] = save_portrait(wb["id"], "captain", f)
                save_warband(wb)
                flash(f"Updated {cap['name']}.", "success")

        elif action == "captain_level_up":
            ok, msg = apply_captain_level_up(wb, request.form.get("choice") or "")
            flash(msg, "success" if ok else "error")
            if ok:
                save_warband(wb)

        elif action == "reverse_captain_level_up":
            ok, msg = reverse_last_captain_level_up(wb)
            flash(msg, "success" if ok else "error")
            if ok:
                save_warband(wb)

        elif action == "captain_pick_trick":
            ok, msg = apply_captain_trick(wb, request.form.get("trick_id") or "")
            flash(msg, "success" if ok else "error")
            if ok:
                save_warband(wb)

        elif action == "captain_add_xp":
            amount = _parse_signed_int(request.form.get("amount"))
            if amount is None:
                flash("Enter a whole number for XP.", "error")
            else:
                ok, msg = add_captain_xp(wb, amount)
                flash(msg, "success" if ok else "error")
                if ok:
                    save_warband(wb)

        elif action == "promote_soldier":
            ok, msg = promote_soldier_to_captain(
                wb,
                request.form.get("soldier_id") or "",
                request.form.get("extra_stat") or None,
                request.form.getlist("tricks"),
            )
            flash(msg, "success" if ok else "error")
            if ok:
                save_warband(wb)

        elif action == "soldier_add_xp":
            amount = _parse_signed_int(request.form.get("amount"))
            if amount is None:
                flash("Enter a whole number for XP.", "error")
            else:
                ok, msg = add_soldier_xp(wb, request.form.get("soldier_id") or "", amount)
                flash(msg, "success" if ok else "error")
                if ok:
                    save_warband(wb)

        elif action == "soldier_level_up":
            ok, msg = apply_soldier_level_up(
                wb, request.form.get("soldier_id") or "", request.form.get("choice") or ""
            )
            flash(msg, "success" if ok else "error")
            if ok:
                save_warband(wb)

        elif action == "reverse_soldier_level_up":
            ok, msg = reverse_last_soldier_level_up(wb, request.form.get("soldier_id") or "")
            flash(msg, "success" if ok else "error")
            if ok:
                save_warband(wb)

        elif action == "adjust_gold":
            delta = _parse_signed_int(request.form.get("delta"))
            reason = (request.form.get("reason") or "").strip()
            if delta is None:
                flash("Enter a whole number for the gold amount.", "error")
            elif delta == 0:
                flash("Enter a non-zero gold amount.", "error")
            else:
                adjust_gold(wb, delta, reason)
                save_warband(wb)
                flash(f"Treasury updated ({delta:+d} gc → {wb['gold']} gc).", "success")

        elif action == "set_gold":
            amount = int(request.form.get("amount") or 0)
            old = int(wb.get("gold", 0))
            wb["gold"] = amount
            add_history(wb, f"Gold set to {amount} gc (was {old}).")
            save_warband(wb)
            flash(f"Treasury set to {amount} gc.", "success")

        elif action == "add_log":
            text = (request.form.get("log_text") or "").strip()
            if text:
                add_history(wb, text)
                save_warband(wb)
                flash("Log entry added.", "success")
            else:
                flash("Log entry was empty.", "error")

        elif action == "level_up":
            choice = request.form.get("choice") or ""
            ok, msg = apply_level_up(
                wb,
                choice,
                spell_key=request.form.get("learn_spell") or None,
                improve_spell_id=request.form.get("improve_spell") or None,
            )
            flash(msg, "success" if ok else "error")
            if ok:
                save_warband(wb)

        elif action == "reverse_level_up":
            ok, msg = reverse_last_level_up(wb)
            flash(msg, "success" if ok else "error")
            if ok:
                save_warband(wb)

        elif action == "add_xp":
            xp = _parse_signed_int(request.form.get("xp"))
            if xp is None:
                flash("Enter a whole number for XP.", "error")
            else:
                ok, msg = add_wizard_xp(wb, xp)
                if ok:
                    save_warband(wb)
                    flash(f"{msg} Pending level-ups: {warband_limits(wb)['pending_levels']}.", "success")
                else:
                    flash(msg, "error")

        elif action == "post_game":
            gold = int(request.form.get("loot_gold") or 0)
            xp = int(request.form.get("loot_xp") or 0)
            captain_xp = int(request.form.get("loot_captain_xp") or 0)
            notes = request.form.get("loot_notes") or ""
            items_raw = request.form.get("loot_items") or ""
            items = [line.strip() for line in items_raw.splitlines() if line.strip()]
            # also support comma-separated single line
            if len(items) == 1 and "," in items[0]:
                items = [x.strip() for x in items[0].split(",") if x.strip()]
            # Rows from the rulebook -> item -> spell picker, alongside the freeform textarea.
            items += [x.strip() for x in request.form.getlist("loot_structured_items") if x.strip()]
            summary = record_game_loot(wb, gold, items, xp, notes, captain_xp)
            save_warband(wb)
            flash(summary, "success")

        elif action == "remove_vault_item":
            if remove_vault_item(wb, request.form.get("item_id") or ""):
                save_warband(wb)
                flash("Item removed from vault.", "success")
            else:
                flash("Item not found.", "error")

        elif action == "add_vault_item":
            name = (request.form.get("item_name") or "").strip()
            if name:
                add_vault_item(wb, name, request.form.get("item_notes") or "", "manual")
                save_warband(wb)
                flash(f"Added “{name}” to vault.", "success")
            else:
                flash("Item name required.", "error")

        elif action == "upload_wizard_portrait":
            f = request.files.get("wizard_portrait")
            if f and f.filename:
                wb["wizard"]["portrait"] = save_portrait(wb["id"], "wizard", f)
                save_warband(wb)
                flash("Wizard portrait updated.", "success")
            else:
                flash("Choose an image file.", "error")

        elif action == "upload_apprentice_portrait":
            if not wb.get("apprentice"):
                flash("No apprentice.", "error")
            else:
                f = request.files.get("apprentice_portrait")
                if f and f.filename:
                    wb["apprentice"]["portrait"] = save_portrait(wb["id"], "apprentice", f)
                    save_warband(wb)
                    flash("Apprentice portrait updated.", "success")
                else:
                    flash("Choose an image file.", "error")

        elif action == "reorder_spells":
            order_raw = (request.form.get("spell_order") or "").strip()
            ids = [x for x in order_raw.split("|") if x]
            ok, msg = reorder_spells(wb, ids)
            flash(msg, "success" if ok else "error")
            if ok:
                save_warband(wb)

        elif action == "reorder_soldiers":
            order_raw = (request.form.get("soldier_order") or "").strip()
            ids = [x for x in order_raw.split("|") if x]
            ok, msg = reorder_soldiers(wb, ids)
            flash(msg, "success" if ok else "error")
            if ok:
                save_warband(wb)

        elif action == "set_base_location":
            loc = request.form.get("location") or "none"
            ok, msg = set_base_location(wb, loc)
            notes = (request.form.get("base_notes") or "").strip()
            wb.setdefault("base", {})["notes"] = notes
            flash(msg, "success" if ok else "error")
            if ok:
                save_warband(wb)

        elif action == "buy_base_resource":
            ok, msg = buy_base_resource(wb, request.form.get("resource") or "")
            flash(msg, "success" if ok else "error")
            if ok:
                save_warband(wb)

        elif action == "remove_base_resource":
            ok, msg = sell_or_remove_base_resource(
                wb,
                request.form.get("resource") or "",
                refund=request.form.get("refund") == "on",
            )
            flash(msg, "success" if ok else "error")
            if ok:
                save_warband(wb)

        else:
            flash("Unknown action.", "error")

    except ValueError as exc:
        flash(str(exc), "error")

    return redirect(url_for("warband_view", warband_id=warband_id))


def _update_details(wb: dict) -> None:
    wb["name"] = (request.form.get("warband_name") or wb["name"]).strip()
    wiz = wb.setdefault("wizard", {})
    wiz["name"] = (request.form.get("wizard_name") or wiz.get("name", "")).strip()
    school = request.form.get("school") or wiz.get("school")
    if school in SCHOOLS:
        wiz["school"] = school
    wiz["notes"] = request.form.get("wizard_notes") or ""
    wiz["has_dagger"] = request.form.get("wizard_dagger") == "on"

    # Wizard item slots (fixed 5)
    wiz_slots = []
    for i in range(WIZARD_ITEM_SLOTS):
        wiz_slots.append((request.form.get(f"wizard_slot_{i}") or "").strip())
    wiz["item_slots"] = normalize_item_slots(wiz_slots, WIZARD_ITEM_SLOTS)

    f = request.files.get("wizard_portrait")
    if f and f.filename:
        wiz["portrait"] = save_portrait(wb["id"], "wizard", f)

    if wb.get("apprentice"):
        ap = wb["apprentice"]
        ap["name"] = (request.form.get("apprentice_name") or ap.get("name", "")).strip()
        ap["notes"] = request.form.get("apprentice_notes") or ""
        ap["has_dagger"] = request.form.get("apprentice_dagger") == "on"
        ap_slots = []
        for i in range(APPRENTICE_ITEM_SLOTS):
            ap_slots.append((request.form.get(f"apprentice_slot_{i}") or "").strip())
        ap["item_slots"] = normalize_item_slots(ap_slots, APPRENTICE_ITEM_SLOTS)
        af = request.files.get("apprentice_portrait")
        if af and af.filename:
            ap["portrait"] = save_portrait(wb["id"], "apprentice", af)


@app.route("/warband/<warband_id>/delete", methods=["POST"])
def warband_delete(warband_id: str):
    wb = _require_warband(warband_id)
    name = wb.get("name", warband_id)
    delete_warband(warband_id)
    flash(f"Deleted warband “{name}”.", "success")
    return redirect(url_for("home"))


@app.route("/warband/<warband_id>/duplicate", methods=["POST"])
def warband_duplicate(warband_id: str):
    _require_warband(warband_id)
    custom = (request.form.get("new_name") or "").strip() or None
    wb, msg = duplicate_warband(warband_id, custom)
    if not wb:
        flash(msg, "error")
        return redirect(url_for("home"))
    flash(msg, "success")
    return redirect(url_for("warband_view", warband_id=wb["id"]))


@app.route("/warband/<warband_id>/export")
def warband_export(warband_id: str):
    wb = _require_warband(warband_id)
    payload = export_warband_json(wb)
    filename = f"{wb.get('id', 'warband')}.warbands"
    return Response(
        payload,
        mimetype="application/json",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@app.route("/warband/<warband_id>/pdf")
def warband_pdf(warband_id: str):
    wb = _require_warband(warband_id)
    # Imported lazily so the app can start without the PDF stack (fpdf / Pillow)
    # present — e.g. the in-browser build, where PDF export is not offered.
    from pdf_export import build_warband_pdf

    data = build_warband_pdf(wb)
    filename = secure_filename(f"{wb.get('name', 'warband')}-roster.pdf") or "roster.pdf"
    return Response(
        data,
        mimetype="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@app.route("/import", methods=["GET", "POST"])
def warband_import():
    if request.method == "POST":
        uploaded = request.files.get("file")
        raw = ""
        if uploaded and uploaded.filename:
            raw = uploaded.read().decode("utf-8", errors="replace")
        else:
            raw = request.form.get("json_text") or ""
        if not raw.strip():
            flash("Paste JSON or choose a file.", "error")
            return render_template("import.html")
        try:
            wb = import_warband_json(raw)
        except Exception as exc:
            flash(f"Could not import: {exc}", "error")
            return render_template("import.html")
        save_warband(wb)
        flash(f"Imported “{wb.get('name', 'warband')}”.", "success")
        return redirect(url_for("warband_view", warband_id=wb["id"]))
    return render_template("import.html")


# ---- Settings (data folder) ------------------------------------------------

@app.route("/settings", methods=["GET", "POST"])
def settings():
    if BROWSER_MODE:
        # Unreachable via the UI (no nav link in browser mode) — this is just
        # defense-in-depth, since a real filesystem config write makes no sense
        # against a session-only in-memory filesystem.
        abort(404)
    if request.method == "POST":
        new_dir = (request.form.get("data_dir") or "").strip()
        if not new_dir:
            flash("Enter a folder path.", "error")
        else:
            paths.set_user_data_dir(new_dir)
            flash(
                f"Data folder set to “{new_dir}”. Restart the app for this to take effect.",
                "success",
            )
        return redirect(url_for("settings"))
    return render_template(
        "settings.html",
        active_dir=str(WARBAND_DIR.parent),
        configured_dir=str(paths.user_data_dir()),
        default_dir=str(paths.default_user_data_dir()),
    )


@app.route("/settings/browse", methods=["POST"])
def settings_browse():
    """Show a native folder picker via a short-lived subprocess — tkinter's
    dialog is not safe to call directly from a waitress worker thread."""
    if BROWSER_MODE:
        # Unreachable via the UI — a real subprocess/tkinter dialog is
        # meaningless under Pyodide, which has neither.
        abort(404)
    try:
        if paths.is_frozen():
            # Re-invoke the frozen exe itself; --pick-folder makes it just
            # show the dialog, print the chosen path, and exit immediately.
            cmd = [sys.executable, "--pick-folder"]
        else:
            script = (
                "import tkinter, tkinter.filedialog\n"
                "r = tkinter.Tk(); r.withdraw()\n"
                "print(tkinter.filedialog.askdirectory() or '')\n"
            )
            cmd = [sys.executable, "-c", script]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        chosen = (result.stdout or "").strip()
    except Exception as exc:
        return {"path": "", "error": str(exc)}, 500
    return {"path": chosen}


@app.errorhandler(404)
def not_found(_e):
    flash("That page or warband was not found.", "error")
    return redirect(url_for("home"))


def main():
    # Hidden flag: re-invoked by /settings/browse in a frozen build to show a
    # native folder picker without calling tkinter from a waitress worker
    # thread. Just print the chosen path and exit — no server involved.
    if "--pick-folder" in sys.argv:
        import tkinter
        from tkinter import filedialog

        root = tkinter.Tk()
        root.withdraw()
        print(filedialog.askdirectory() or "")
        return

    port = int(os.environ.get("PORT", 5000))
    if paths.is_frozen():
        url = f"http://127.0.0.1:{port}/"
        threading.Timer(1.0, lambda: webbrowser.open(url)).start()
        from waitress import serve

        threading.Thread(
            target=serve,
            args=(app,),
            kwargs={"host": "127.0.0.1", "port": port},
            daemon=True,
        ).start()

        import idle_watchdog

        # This is a windowless, console-less build — without these, the server
        # would keep running invisibly after the browser tab (and even the
        # browser itself) is closed, with no way to stop it short of killing
        # the process by hand.
        idle_watchdog.start()

        if sys.platform.startswith("win"):
            try:
                import tray

                tray.run(url)  # blocks on the tray icon's event loop until Quit
                return
            except Exception:
                pass  # no usable tray backend — fall back to idle_watchdog alone

        threading.Event().wait()  # keep the main thread alive; idle_watchdog exits the process
    else:
        app.run(debug=True, host="127.0.0.1", port=port)


if __name__ == "__main__":
    main()
