"""
Frostgrave Warband Creator & Maintainer
Create wizards (name, school, picture, spells), apprentices, soldiers,
level-up, post-game loot, and PDF rosters. Data saved locally (no login).
"""

from __future__ import annotations

import logging
import os
import subprocess
import sys
import threading
import webbrowser
from collections.abc import Callable
from logging.handlers import RotatingFileHandler

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

import expansions
import paths
from frostgrave_data import (
    ALIGNED_SCHOOL_SPELLS,
    APPRENTICE_COST,
    BASE_LOCATIONS,
    BASE_RESOURCES,
    CAPTAIN_ITEM_SLOTS,
    CAPTAIN_MIND_CONTROL_LABELS,
    CAPTAIN_MIND_CONTROL_OPTIONS,
    CAPTAIN_MODE_LABELS,
    CAPTAIN_MODE_OPTIONS,
    CAPTAIN_TRICK_BY_ID,
    CAPTAIN_TRICKS,
    GIANT_BLOODED_COST,
    KNIGHTLY_ORDER_ELIGIBLE,
    KNIGHTLY_ORDERS,
    LEVEL_UP_OPTIONS,
    LEVELUP_STATS,
    MAX_SOLDIERS,
    MAX_SPECIALISTS,
    NEUTRAL_SPELLS,
    OWN_SCHOOL_SPELLS,
    PENTANGLE_SCHOOLS,
    PERMANENT_INJURIES,
    PERMANENT_INJURY_BY_ID,
    PROSTHETIC_UPGRADES,
    PROSTHETIC_UPGRADE_BY_ID,
    PROMOTE_CAPTAIN_ITEM_SLOTS,
    SCHOOL_ALIGNED,
    SCHOOL_NEUTRAL,
    SCHOOL_OPPOSED,
    SCHOOL_RELATIONS,
    SCHOOLS,
    SOLDIERS,
    SOURCE_BOOK_BY_SLUG,
    SOURCE_BOOK_OPTIONS,
    SOURCE_BOOKS,
    SPELLS,
    STANDARD_CONSTRUCT_TYPE_KEYS,
    STARTING_GOLD,
    STARTING_SPELL_COUNT,
    TEMPORARY_MEMBER_LIMIT,
    XP_PER_LEVEL,
    all_spells_flat,
    animal_companion_type_keys,
    bonus_choice_amount,
    cn_penalty,
    construct_type_keys,
    format_stat,
    giant_blooded_eligible_type_keys,
    group_soldiers_by_source,
    illusion_source_choices,
    level_from_xp,
    soldier_list_for_ui,
    spells_for_wizard_ui,
)
from game_content import (
    construct_modifications,
    enrich_spells_with_descriptions,
    group_magic_items,
    load_bestiary,
    load_core_rules,
    load_expansion_rules,
    load_ghost_archipelago,
    load_grave_mutations,
    load_loot_tables,
    load_magic_items,
    load_potion_choices,
    load_potion_choices_detailed,
    load_quick_reference,
    load_random_encounters,
    load_spell_descriptions,
    load_spell_names,
    load_spellcaster_items,
    load_standard_items,
    load_traits,
    magic_items_for_sources,
)
from idle_watchdog import note_closing, note_heartbeat
from warband_store import (
    ALT_XP_CONVERSIONS,
    add_apprentice_mutation,
    add_apprentice_permanent_injury,
    add_captain_mutation,
    add_captain_permanent_injury,
    add_captain_xp,
    add_construct_modification,
    add_history,
    add_pact_tier,
    add_soldier,
    add_soldier_mutation,
    add_soldier_permanent_injury,
    add_soldier_xp,
    add_vault_item,
    add_wizard_mutation,
    add_wizard_permanent_injury,
    add_wizard_xp,
    adjust_gold,
    advance_beastcrafter,
    animal_companion_limit,
    apply_captain_level_up,
    apply_captain_trick,
    apply_animal_companion_crit_bonus,
    become_vampire,
    apply_level_up,
    apply_portrait,
    apply_soldier_level_up,
    base_summary,
    break_wizard_pact,
    buy_base_resource,
    captain_effective_stats,
    create_warband,
    delete_warband,
    dismiss_all_temporary_members,
    dismiss_apprentice,
    dismiss_captain,
    duplicate_warband,
    enabled_sources,
    enrich_soldier,
    export_warband_json,
    has_animal_companion,
    hire_apprentice,
    hire_captain,
    import_warband_json,
    known_spell_ids,
    known_spell_names,
    list_unreadable_warbands,
    list_warbands,
    load_warband,
    normalize_item_slots,
    portrait_filesystem_path,
    portraits_root_dir,
    promote_soldier_to_captain,
    raise_revenant,
    recompute_spell_cns,
    record_game_loot,
    remove_apprentice_mutation,
    remove_apprentice_permanent_injury,
    remove_captain_mutation,
    remove_captain_permanent_injury,
    remove_construct_modification,
    remove_portrait,
    remove_revenant,
    remove_soldier,
    remove_soldier_mutation,
    remove_soldier_permanent_injury,
    remove_vault_item,
    remove_wizard_mutation,
    remove_wizard_permanent_injury,
    random_core_wizard,
    reorder_soldiers,
    reorder_spells,
    resolve_portrait_path,
    restore_portraits_by_name,
    reverse_last_captain_level_up,
    reverse_last_level_up,
    add_apprentice_prosthetic_upgrade,
    add_captain_prosthetic_upgrade,
    add_wizard_prosthetic_upgrade,
    remove_apprentice_prosthetic_upgrade,
    remove_captain_prosthetic_upgrade,
    remove_wizard_prosthetic_upgrade,
    reverse_last_soldier_level_up,
    roll_random_recruits,
    save_warband,
    sell_or_remove_base_resource,
    set_animal_feature,
    set_base_location,
    set_permanent_injury_prosthetic,
    set_soldier_giant_blooded,
    set_soldier_status,
    set_wizard_state,
    soldier_count,
    soldier_from_book_enabled,
    spend_alt_xp,
    update_homerules,
    warband_dir,
    warband_limits,
    wizard_effective_stats,
)

logger = logging.getLogger(__name__)


def _configure_logging() -> None:
    """E4: the packaged .exe has no console (frostgrave.spec, console=False),
    so that's the one case that needs its own handler — a small rotating file
    in the data dir. Everywhere else (dev server, tests, the in-browser build)
    keeps Python's normal stderr-on-WARNING+ default."""
    if not paths.is_frozen():
        return
    data_dir = paths.user_data_dir()
    data_dir.mkdir(parents=True, exist_ok=True)
    log_path = data_dir / "fwk.log"
    handler = RotatingFileHandler(log_path, maxBytes=512 * 1024, backupCount=2, encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    root = logging.getLogger()
    root.addHandler(handler)
    root.setLevel(logging.INFO)


_configure_logging()

_BUNDLE_DIR = paths.bundle_dir()
app = Flask(
    __name__,
    template_folder=str(_BUNDLE_DIR / "templates"),
    static_folder=str(_BUNDLE_DIR / "static"),
)
app.secret_key = os.environ.get("SECRET_KEY") or paths.get_or_create_secret_key()
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

    Delegates the "does a file actually exist" decision to resolve_portrait_path()
    (also used by the PDF export) rather than duplicating that fallback chain —
    a warband can carry a portrait reference to a file that's no longer there
    (e.g. an imported .warbands file, since portrait bytes are never included
    in the export), so the stored path can't be trusted blindly."""
    path = resolve_portrait_path(portrait, kind, type_key)
    if not path:
        return None
    if portrait and portrait_filesystem_path(portrait):
        return url_for("portrait_file", relpath=portrait)
    return url_for("static", filename=f"portraits/{path.name}")


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
    CAPTAIN_MIND_CONTROL_OPTIONS=CAPTAIN_MIND_CONTROL_OPTIONS,
    CAPTAIN_MIND_CONTROL_LABELS=CAPTAIN_MIND_CONTROL_LABELS,
    CAPTAIN_MODE_OPTIONS=CAPTAIN_MODE_OPTIONS,
    CAPTAIN_MODE_LABELS=CAPTAIN_MODE_LABELS,
    CAPTAIN_TRICKS=CAPTAIN_TRICKS,
    CAPTAIN_TRICK_BY_ID=CAPTAIN_TRICK_BY_ID,
    PERMANENT_INJURIES=PERMANENT_INJURIES,
    PERMANENT_INJURY_BY_ID=PERMANENT_INJURY_BY_ID,
    PROSTHETIC_UPGRADES=PROSTHETIC_UPGRADES,
    PROSTHETIC_UPGRADE_BY_ID=PROSTHETIC_UPGRADE_BY_ID,
    KNIGHTLY_ORDERS=KNIGHTLY_ORDERS,
    KNIGHTLY_ORDER_ELIGIBLE=KNIGHTLY_ORDER_ELIGIBLE,
    ILLUSION_SOURCE_CHOICES=illusion_source_choices(),
    ANIMAL_COMPANION_TYPE_KEYS=animal_companion_type_keys(),
    CONSTRUCT_TYPE_KEYS=construct_type_keys(),
    STANDARD_CONSTRUCT_TYPE_KEYS=STANDARD_CONSTRUCT_TYPE_KEYS,
    GIANT_BLOODED_COST=GIANT_BLOODED_COST,
    LEVELUP_STATS=LEVELUP_STATS,
    level_from_xp=level_from_xp,
    captain_effective_stats=captain_effective_stats,
    soldier_item_slots=expansions.soldier_item_slots,
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


def _mutation_number_from_form() -> tuple[bool, int | None]:
    """Reads mutation_action/mutation_number from the current POST.
    Returns (True, None) for a random roll, (True, N) for a specific pick, or
    (False, None) if a pick was required but nothing valid was submitted."""
    if request.form.get("mutation_action") == "random":
        return True, None
    raw = (request.form.get("mutation_number") or "").strip()
    if not raw.isdigit():
        return False, None
    return True, int(raw)


def _mutation_index_from_form() -> int:
    """Which entry in a character's mutations list to remove — -1 (never a
    valid list index) if the form didn't send one, so remove_*_mutation()
    cleanly reports "not found" instead of removing the wrong entry."""
    raw = (request.form.get("mutation_index") or "").strip()
    return int(raw) if raw.isdigit() else -1


@app.route("/")
def home() -> str:
    return render_template(
        "index.html",
        warbands=list_warbands(),
        unreadable_warbands=list_unreadable_warbands(),
    )


@app.route("/reference")
def reference() -> str:
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
        traits=load_traits(),
        quick_reference=load_quick_reference(),
        core_rules=load_core_rules(),
        base_locations=BASE_LOCATIONS,
        base_resources=BASE_RESOURCES,
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
def about() -> str:
    return render_template("about.html")


@app.route("/heartbeat", methods=["POST"])
def heartbeat() -> tuple[str, int]:
    """Pinged periodically by every open page — see idle_watchdog.py."""
    note_heartbeat()
    return ("", 204)


@app.route("/heartbeat/closing", methods=["POST"])
def heartbeat_closing() -> tuple[str, int]:
    """Pinged via sendBeacon when a page unloads — see idle_watchdog.py."""
    note_closing()
    return ("", 204)


@app.route("/portraits/<path:relpath>")
def portrait_file(relpath: str) -> Response:
    if ".." in relpath:
        abort(404)
    return send_from_directory(portraits_root_dir(), relpath)


# ---- Create warband (wizard + spells + apprentice) ------------------------

@app.route("/warband/new", methods=["GET", "POST"])
def warband_new() -> str | Response:
    if request.method == "POST":
        name = (request.form.get("warband_name") or "").strip()
        wizard = (request.form.get("wizard_name") or "").strip()
        school = request.form.get("school") or SCHOOLS[0]
        pentangle = request.form.get("pentangle_schools_playable") == "on"
        fire_giant = request.form.get("fire_giant_wizard_playable") == "on"
        vampire = request.form.get("vampire_wizard_playable") == "on"
        if school not in _new_schools(_posted_sources(request.form), pentangle, fire_giant, vampire):
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
        try:
            starting_gold = int(request.form.get("starting_gold") or STARTING_GOLD)
        except ValueError:
            starting_gold = STARTING_GOLD
        try:
            wizard_starting_xp = int(request.form.get("wizard_starting_xp") or 0)
        except ValueError:
            wizard_starting_xp = 0
        try:
            max_soldiers = int(request.form.get("max_soldiers") or MAX_SOLDIERS)
        except ValueError:
            max_soldiers = MAX_SOLDIERS
        try:
            max_specialists = int(request.form.get("max_specialists") or MAX_SPECIALISTS)
        except ValueError:
            max_specialists = MAX_SPECIALISTS

        if not name or not wizard:
            flash("Warband name and wizard name are required.", "error")
            return _render_new(school=school, selected=spell_keys, sources=sources,
                               pentangle=pentangle, fire_giant=fire_giant, vampire=vampire,
                               warband_name=name, wizard_name=wizard,
                               with_apprentice=with_apprentice, apprentice_name=apprentice_name,
                               starting_gold=starting_gold, wizard_starting_xp=wizard_starting_xp,
                               max_soldiers=max_soldiers, max_specialists=max_specialists)

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
            fire_giant_playable=fire_giant,
            vampire_playable=vampire,
            starting_gold=starting_gold,
            wizard_starting_xp=wizard_starting_xp,
            max_soldiers=max_soldiers,
            max_specialists=max_specialists,
        )
        if not wb:
            flash(msg, "error")
            return _render_new(school=school, selected=spell_keys, sources=sources,
                               pentangle=pentangle, fire_giant=fire_giant, vampire=vampire,
                               warband_name=name, wizard_name=wizard,
                               with_apprentice=with_apprentice, apprentice_name=apprentice_name,
                               starting_gold=starting_gold, wizard_starting_xp=wizard_starting_xp,
                               max_soldiers=max_soldiers, max_specialists=max_specialists)

        try:
            wiz_file = request.files.get("wizard_portrait")
            apply_portrait(wb["wizard"], wb["id"], "wizard", wiz_file)
            if with_apprentice and wb.get("apprentice"):
                ap_file = request.files.get("apprentice_portrait")
                apply_portrait(wb["apprentice"], wb["id"], "apprentice", ap_file)
        except ValueError as exc:
            flash(str(exc), "error")

        save_warband(wb)
        flash(f"Warband “{wb['name']}” created with {wb['gold']} gc.", "success")
        return redirect(url_for("warband_view", warband_id=wb["id"]))

    school = request.args.get("school") or SCHOOLS[0]
    # Source toggles survive the school-change round-trip via the query string
    # (fgNewReload always sets sources_touched), so switching school doesn't
    # silently untick the books already chosen. On a genuine first visit (no
    # query string at all) there's nothing to preserve, so every source book
    # defaults to on — Pentangle stays off either way; the book's own scroll-
    # only default needs an explicit opt-in.
    if request.args.get("sources_touched"):
        sources = _posted_sources(request.args)
        pentangle = request.args.get("pentangle_schools_playable") == "on"
        fire_giant = request.args.get("fire_giant_wizard_playable") == "on"
        vampire = request.args.get("vampire_wizard_playable") == "on"
    else:
        sources = {book: True for book in SOURCE_BOOKS}
        pentangle = False
        fire_giant = False
        vampire = False

    if request.args.get("randomize"):
        # "Random wizard" button (core rules only): generates a random, legal
        # school + 8 starting spells server-side (random_core_wizard already
        # self-validates), plus random warband/wizard/apprentice names. Never
        # repeats the school currently on the page, so pressing the button
        # again always changes it. Delivered through the same #creation-dynamic
        # swap the school dropdown already uses (see fgRandomWizard in
        # warband_new.html) — random_identity is read out of that swapped
        # region by the client and copied onto the name/apprentice fields,
        # which live outside the swap and so must not be re-rendered here.
        rand_school, rand_keys, rand_names = random_core_wizard(
            exclude_school=request.args.get("exclude_school") or school
        )
        return _render_new(
            school=rand_school, selected=rand_keys, sources=sources,
            pentangle=pentangle, fire_giant=fire_giant, vampire=vampire,
            with_apprentice=True, random_identity=rand_names,
        )
    return _render_new(school=school, sources=sources, pentangle=pentangle,
                        fire_giant=fire_giant, vampire=vampire)


def _new_schools(sources: dict, pentangle: bool, fire_giant: bool = False, vampire: bool = False) -> list[str]:
    """Schools offered on the creation page for these toggles."""
    schools = list(SCHOOLS)
    if pentangle and sources.get("The Maze of Malcor"):
        schools += list(PENTANGLE_SCHOOLS)
    if fire_giant and sources.get("Blood Legacy"):
        schools.append("Fire Giant")
    if vampire and sources.get("Blood Legacy"):
        schools.append("Vampire")
    return schools


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
    fire_giant: bool = False,
    vampire: bool = False,
    warband_name: str = "",
    wizard_name: str = "",
    with_apprentice: bool = False,
    apprentice_name: str = "",
    starting_gold: int = STARTING_GOLD,
    wizard_starting_xp: int = 0,
    max_soldiers: int = MAX_SOLDIERS,
    max_specialists: int = MAX_SPECIALISTS,
    random_identity: dict | None = None,
):
    sources = sources or {}
    schools = _new_schools(sources, pentangle, fire_giant, vampire)
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
        fire_giant_playable=fire_giant,
        vampire_playable=vampire,
        PENTANGLE_SCHOOLS=PENTANGLE_SCHOOLS,
        neutral_needed=neutral_needed,
        warband_name=warband_name,
        wizard_name=wizard_name,
        with_apprentice=with_apprentice,
        apprentice_name=apprentice_name,
        starting_gold=starting_gold,
        wizard_starting_xp=wizard_starting_xp,
        max_soldiers=max_soldiers,
        max_specialists=max_specialists,
        random_identity=random_identity,
    )


# ---- View / maintain ------------------------------------------------------

@app.route("/warband/<warband_id>")
def warband_view(warband_id: str) -> str:
    wb = _require_warband(warband_id)
    recompute_spell_cns(wb)
    all_soldiers = wb.get("soldiers") or []
    def _is_temporary(s):
        return bool(SOLDIERS.get(s.get("type_key", ""), {}).get("temporary"))
    # Temporary members (Raise Zombie, Summon Demon) show up in the same roster
    # table as everyone else, but always sorted after the permanent soldiers —
    # recomputed on every render so a manual reorder can't leave one stranded
    # above a permanent soldier.
    soldiers = [
        enrich_soldier(wb, s)
        for s in sorted(all_soldiers, key=lambda s: _is_temporary(s))
    ]
    limits = warband_limits(wb)
    known = known_spell_ids(wb)
    wschool = (wb.get("wizard") or {}).get("school") or "Elementalist"
    wb_sources = enabled_sources(wb)
    grave_mutations_enabled = "Grave Mutations" in wb_sources
    mutation_picker_data = load_grave_mutations() if grave_mutations_enabled else []
    fireheart_enabled = "Fireheart" in wb_sources
    construct_modification_data = construct_modifications() if fireheart_enabled else []
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
    # Temporary members skip the known-spell check: hiring one is bookkeeping
    # for a spell the player already cast for real, not a request the app
    # needs to gate (see add_soldier()'s matching exemption).
    hireable = [
        {**c, "cost": expansions.soldier_cost(wb, c, c["key"])}
        for c in soldier_list_for_ui()
        if c["source"] in wb_sources
        and soldier_from_book_enabled(wb, c["source"])
        and (c.get("temporary") or not c.get("requires_spell") or c["requires_spell"] in wb_spells)
        and expansions.soldier_state_block(wb, c["key"]) is None
    ]
    # The temporary-member catalog (Raise Zombie, Summon Demon) gets its own
    # "Hire temporary member" panel instead of living in the main hire table.
    temporary_catalog = [c for c in hireable if c.get("temporary")]
    hireable = [c for c in hireable if not c.get("temporary")]
    # Total temporary members on the table right now — one shared cap across
    # zombies and demons (no per-type sub-limit), disables every "Hire"
    # button in that panel once reached, mirroring Animal Companion's block.
    temporary_member_count = sum(
        1 for s in all_soldiers if s.get("status") != "dead" and _is_temporary(s)
    )
    # Blood Legacy's Giant-Blooded: a single global picker (see
    # set_soldier_giant_blooded) rather than a button repeated on every
    # soldier's row, since only one soldier in the warband may take it.
    giant_blooded_enabled = "Blood Legacy" in wb_sources and bool(
        (wb.get("homerules") or {}).get("giant_blooded_enabled")
    )
    giant_blooded_eligible_keys = giant_blooded_eligible_type_keys()
    giant_blooded_soldier = next(
        (s for s in all_soldiers if s.get("giant_blooded")), None
    )
    giant_blooded_choices = [
        {"id": s["id"], "name": s.get("name") or "Unnamed"}
        for s in all_soldiers
        if s.get("status") != "dead" and s.get("type_key") in giant_blooded_eligible_keys
    ]
    # The Red King's Ragged Warbands & Random Recruits: a single "Fill
    # roster" control (see roll_random_recruits), same idiom as Giant-Blooded
    # above — a warband-level toggle gates one shared control rather than a
    # button repeated anywhere per-soldier.
    ragged_warbands_enabled = "The Red King" in wb_sources and bool(
        (wb.get("homerules") or {}).get("ragged_warbands_enabled")
    )
    ragged_warbands_have = 1 + (1 if wb.get("apprentice") else 0) + soldier_count(wb)
    ragged_warbands_rules = next(
        (
            row
            for row in load_expansion_rules().get("The Red King", [])
            if row.get("title", "").startswith("Ragged Warbands")
        ),
        None,
    )
    return render_template(
        "warband_view.html",
        wb=wb,
        soldiers=soldiers,
        temporary_member_count=temporary_member_count,
        temporary_member_limit=TEMPORARY_MEMBER_LIMIT,
        limits=limits,
        catalog_groups=group_soldiers_by_source(hireable),
        temporary_catalog=temporary_catalog,
        known_spell_names=wb_spells,
        has_animal_companion=has_animal_companion(wb),
        animal_companion_limit=animal_companion_limit(wb),
        giant_blooded_enabled=giant_blooded_enabled,
        giant_blooded_soldier=giant_blooded_soldier,
        giant_blooded_choices=giant_blooded_choices,
        ragged_warbands_enabled=ragged_warbands_enabled,
        ragged_warbands_have=ragged_warbands_have,
        ragged_warbands_rules=ragged_warbands_rules,
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
        wizard_display_stats=wizard_effective_stats(wb),
        wizard_state_bonus=expansions.wizard_state_stat_bonus(wb),
        beastcrafter_tier=expansions.beastcrafter_tier(wb),
        pact_tiers=expansions.pact_tiers(wb),
        can_advance_beastcrafter=expansions.can_advance_beastcrafter(wb),
        can_add_pact_tier=expansions.can_add_pact_tier(wb),
        pact_break_penalty=expansions.pact_break_penalty(wb),
        wizard_level_up_options=expansions.level_up_options(wb),
        # Blood Legacy: High-Level Wizards (per-wizard-level bonuses, each its
        # own homerule toggle — see expansions.py).
        wizard_item_slots=expansions.wizard_item_slots(wb),
        apprentice_item_slots=expansions.apprentice_item_slots(wb),
        casting_number_minimum=expansions.casting_number_minimum(wb),
        alt_xp_enabled=expansions.alt_xp_enabled(wb),
        alt_xp_conversions=ALT_XP_CONVERSIONS,
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
        grave_mutations_enabled=grave_mutations_enabled,
        mutation_picker_data=mutation_picker_data,
        fireheart_enabled=fireheart_enabled,
        construct_modification_data=construct_modification_data,
    )


ActionHandler = Callable[[dict], tuple[bool, str]]
ACTION_HANDLERS: dict[str, ActionHandler] = {}


def register_action(name: str) -> Callable[[ActionHandler], ActionHandler]:
    """Registers a `warband_update` form handler under `action=<name>`.

    Handlers take the warband dict (mutating it in place as needed) and return
    `(ok, message)`. The route flashes the message and saves the warband iff
    `ok` is true — see `warband_update` below. Handlers read `request.form`/
    `request.files` directly, same as the branches they replace.
    """

    def deco(fn: ActionHandler) -> ActionHandler:
        ACTION_HANDLERS[name] = fn
        return fn

    return deco


@app.route("/warband/<warband_id>/update", methods=["POST"])
def warband_update(warband_id: str) -> Response:
    wb = _require_warband(warband_id)
    action_name = request.form.get("action") or ""
    handler = ACTION_HANDLERS.get(action_name)

    try:
        if handler is None:
            flash("Unknown action.", "error")
        else:
            ok, msg = handler(wb)
            if msg:
                flash(msg, "success" if ok else "error")
            if ok:
                save_warband(wb)
    except ValueError:
        flash("Please enter a valid number.", "error")

    return redirect(url_for("warband_view", warband_id=warband_id))


@register_action("details")
def _act_details(wb: dict) -> tuple[bool, str]:
    _update_details(wb)
    return True, "Details saved."


@register_action("set_notes")
def _act_set_notes(wb: dict) -> tuple[bool, str]:
    wb["notes"] = request.form.get("notes") or ""
    return True, "Notes saved."


@register_action("hire_soldier")
def _act_hire_soldier(wb: dict) -> tuple[bool, str]:
    ok, msg = add_soldier(
        wb,
        request.form.get("type_key") or "",
        (request.form.get("soldier_name") or "").strip(),
        request.form.get("knightly_order") or "",
        request.form.get("illusion_source") or "",
    )
    if ok:
        # optional portrait on hire
        f = request.files.get("soldier_portrait")
        if f and f.filename and wb["soldiers"]:
            sid = wb["soldiers"][-1]["id"]
            apply_portrait(wb["soldiers"][-1], wb["id"], f"soldier_{sid}", f)
    return ok, msg


@register_action("remove_soldier")
def _act_remove_soldier(wb: dict) -> tuple[bool, str]:
    return remove_soldier(
        wb,
        request.form.get("soldier_id") or "",
        refund=request.form.get("refund") == "on",
    )


@register_action("dismiss_all_temporary")
def _act_dismiss_all_temporary(wb: dict) -> tuple[bool, str]:
    return dismiss_all_temporary_members(wb)


@register_action("soldier_status")
def _act_soldier_status(wb: dict) -> tuple[bool, str]:
    return set_soldier_status(
        wb,
        request.form.get("soldier_id") or "",
        request.form.get("status") or "active",
    )


@register_action("soldier_edit")
def _act_soldier_edit(wb: dict) -> tuple[bool, str]:
    sid = request.form.get("soldier_id") or ""
    for s in wb.get("soldiers") or []:
        if s.get("id") == sid:
            s["name"] = (request.form.get("soldier_name") or s.get("name", "")).strip()
            s["notes"] = request.form.get("notes") or ""
            slot_n = expansions.soldier_item_slots(wb, s.get("type_key", ""))
            slots = [(request.form.get(f"soldier_{sid}_slot_{i}") or "").strip() for i in range(slot_n)]
            s["item_slots"] = normalize_item_slots(slots, slot_n)
            if request.form.get("soldier_portrait_remove") == "on":
                remove_portrait(s, wb["id"], f"soldier_{sid}")
            f = request.files.get("soldier_portrait")
            apply_portrait(s, wb["id"], f"soldier_{sid}", f)
            return True, f"Updated {s['name']}."
    return False, "Soldier not found."


@register_action("hire_apprentice")
def _act_hire_apprentice(wb: dict) -> tuple[bool, str]:
    ok, msg = hire_apprentice(wb, (request.form.get("apprentice_name") or "").strip())
    if ok:
        f = request.files.get("apprentice_portrait")
        apply_portrait(wb["apprentice"], wb["id"], "apprentice", f)
    return ok, msg


@register_action("dismiss_apprentice")
def _act_dismiss_apprentice(wb: dict) -> tuple[bool, str]:
    return dismiss_apprentice(wb, refund=request.form.get("refund") == "on")


@register_action("update_homerules")
def _act_update_homerules(wb: dict) -> tuple[bool, str]:
    return update_homerules(wb, request.form)


@register_action("set_wizard_state")
def _act_set_wizard_state(wb: dict) -> tuple[bool, str]:
    return set_wizard_state(wb, request.form.get("state_kind") or "")


@register_action("become_vampire")
def _act_become_vampire(wb: dict) -> tuple[bool, str]:
    return become_vampire(wb)


@register_action("advance_beastcrafter")
def _act_advance_beastcrafter(wb: dict) -> tuple[bool, str]:
    return advance_beastcrafter(wb)


@register_action("set_animal_feature")
def _act_set_animal_feature(wb: dict) -> tuple[bool, str]:
    return set_animal_feature(wb, request.form.get("feature") or "")


@register_action("add_pact_tier")
def _act_add_pact_tier(wb: dict) -> tuple[bool, str]:
    return add_pact_tier(
        wb,
        request.form.get("sacrifice") or "",
        request.form.get("boon") or "",
        (request.form.get("demon") or "").strip(),
    )


@register_action("break_pact")
def _act_break_pact(wb: dict) -> tuple[bool, str]:
    return break_wizard_pact(wb)


@register_action("raise_revenant")
def _act_raise_revenant(wb: dict) -> tuple[bool, str]:
    return raise_revenant(wb, request.form.get("soldier_id") or "")


@register_action("remove_revenant")
def _act_remove_revenant(wb: dict) -> tuple[bool, str]:
    return remove_revenant(wb, request.form.get("soldier_id") or "")


@register_action("hire_captain")
def _act_hire_captain(wb: dict) -> tuple[bool, str]:
    ok, msg = hire_captain(
        wb,
        (request.form.get("captain_name") or "").strip(),
        request.form.get("captain_extra_stat") or None,
        request.form.getlist("captain_tricks"),
    )
    if ok:
        f = request.files.get("captain_portrait")
        apply_portrait(wb["captain"], wb["id"], "captain", f)
    return ok, msg


@register_action("dismiss_captain")
def _act_dismiss_captain(wb: dict) -> tuple[bool, str]:
    return dismiss_captain(wb, refund=request.form.get("refund") == "on")


@register_action("captain_edit")
def _act_captain_edit(wb: dict) -> tuple[bool, str]:
    cap = wb.get("captain")
    if not cap:
        return False, "No captain hired."
    cap["name"] = (request.form.get("captain_name") or cap.get("name", "")).strip()
    cap["notes"] = request.form.get("captain_notes") or ""
    cap["has_dagger"] = request.form.get("captain_dagger") == "on"
    hr = wb.get("homerules") or {}
    if cap.get("origin") == "promoted":
        n = int(hr.get("promote_captain_item_slots", PROMOTE_CAPTAIN_ITEM_SLOTS))
    else:
        n = int(hr.get("captain_item_slots", CAPTAIN_ITEM_SLOTS))
    slots = [(request.form.get(f"captain_slot_{i}") or "").strip() for i in range(n)]
    cap["item_slots"] = normalize_item_slots(slots, n)
    if request.form.get("captain_portrait_remove") == "on":
        remove_portrait(cap, wb["id"], "captain")
    f = request.files.get("captain_portrait")
    apply_portrait(cap, wb["id"], "captain", f)
    return True, f"Updated {cap['name']}."


@register_action("captain_level_up")
def _act_captain_level_up(wb: dict) -> tuple[bool, str]:
    return apply_captain_level_up(wb, request.form.get("choice") or "")


@register_action("reverse_captain_level_up")
def _act_reverse_captain_level_up(wb: dict) -> tuple[bool, str]:
    return reverse_last_captain_level_up(wb)


@register_action("captain_pick_trick")
def _act_captain_pick_trick(wb: dict) -> tuple[bool, str]:
    return apply_captain_trick(wb, request.form.get("trick_id") or "")


@register_action("captain_add_xp")
def _act_captain_add_xp(wb: dict) -> tuple[bool, str]:
    amount = _parse_signed_int(request.form.get("amount"))
    if amount is None:
        return False, "Enter a whole number for XP."
    return add_captain_xp(wb, amount)


@register_action("promote_soldier")
def _act_promote_soldier(wb: dict) -> tuple[bool, str]:
    return promote_soldier_to_captain(
        wb,
        request.form.get("soldier_id") or "",
        request.form.get("extra_stat") or None,
        request.form.getlist("tricks"),
    )


@register_action("soldier_add_xp")
def _act_soldier_add_xp(wb: dict) -> tuple[bool, str]:
    amount = _parse_signed_int(request.form.get("amount"))
    if amount is None:
        return False, "Enter a whole number for XP."
    return add_soldier_xp(wb, request.form.get("soldier_id") or "", amount)


@register_action("soldier_level_up")
def _act_soldier_level_up(wb: dict) -> tuple[bool, str]:
    return apply_soldier_level_up(
        wb, request.form.get("soldier_id") or "", request.form.get("choice") or ""
    )


@register_action("reverse_soldier_level_up")
def _act_reverse_soldier_level_up(wb: dict) -> tuple[bool, str]:
    return reverse_last_soldier_level_up(wb, request.form.get("soldier_id") or "")


@register_action("soldier_crit_bonus")
def _act_soldier_crit_bonus(wb: dict) -> tuple[bool, str]:
    return apply_animal_companion_crit_bonus(wb, request.form.get("soldier_id") or "")


@register_action("adjust_gold")
def _act_adjust_gold(wb: dict) -> tuple[bool, str]:
    delta = _parse_signed_int(request.form.get("delta"))
    reason = (request.form.get("reason") or "").strip()
    if delta is None:
        return False, "Enter a whole number for the gold amount."
    if delta == 0:
        return False, "Enter a non-zero gold amount."
    adjust_gold(wb, delta, reason)
    return True, f"Treasury updated ({delta:+d} gc → {wb['gold']} gc)."


@register_action("set_gold")
def _act_set_gold(wb: dict) -> tuple[bool, str]:
    amount = _parse_signed_int(request.form.get("amount"))
    if amount is None:
        return False, "Enter a whole number for gold."
    old = int(wb.get("gold", 0))
    wb["gold"] = amount
    add_history(wb, f"Gold set to {amount} gc (was {old}).")
    return True, f"Treasury set to {amount} gc."


@register_action("add_log")
def _act_add_log(wb: dict) -> tuple[bool, str]:
    text = (request.form.get("log_text") or "").strip()
    if not text:
        return False, "Log entry was empty."
    add_history(wb, text)
    return True, "Log entry added."


@register_action("level_up")
def _act_level_up(wb: dict) -> tuple[bool, str]:
    choice = request.form.get("choice") or ""
    return apply_level_up(
        wb,
        choice,
        spell_key=request.form.get("learn_spell") or None,
        improve_spell_id=request.form.get("improve_spell") or None,
    )


@register_action("reverse_level_up")
def _act_reverse_level_up(wb: dict) -> tuple[bool, str]:
    return reverse_last_level_up(wb)


@register_action("add_xp")
def _act_add_xp(wb: dict) -> tuple[bool, str]:
    xp = _parse_signed_int(request.form.get("xp"))
    if xp is None:
        return False, "Enter a whole number for XP."
    ok, msg = add_wizard_xp(wb, xp)
    if ok:
        return True, f"{msg} Pending level-ups: {warband_limits(wb)['pending_levels']}."
    return False, msg


@register_action("spend_alt_xp")
def _act_spend_alt_xp(wb: dict) -> tuple[bool, str]:
    return spend_alt_xp(
        wb,
        request.form.get("conversion") or "",
        request.form.get("xp_amount") or "0",
    )


@register_action("post_game")
def _act_post_game(wb: dict) -> tuple[bool, str]:
    gold_raw = (request.form.get("loot_gold") or "").strip()
    xp_raw = (request.form.get("loot_xp") or "").strip()
    captain_xp_raw = (request.form.get("loot_captain_xp") or "").strip()
    gold = _parse_signed_int(gold_raw) if gold_raw else 0
    xp = _parse_signed_int(xp_raw) if xp_raw else 0
    captain_xp = _parse_signed_int(captain_xp_raw) if captain_xp_raw else 0
    if gold is None or xp is None or captain_xp is None:
        return False, "Enter whole numbers for gold and XP."
    notes = request.form.get("loot_notes") or ""
    items_raw = request.form.get("loot_items") or ""
    items = [line.strip() for line in items_raw.splitlines() if line.strip()]
    # also support comma-separated single line
    if len(items) == 1 and "," in items[0]:
        items = [x.strip() for x in items[0].split(",") if x.strip()]
    # Rows from the rulebook -> item -> spell picker, alongside the freeform textarea.
    items += [x.strip() for x in request.form.getlist("loot_structured_items") if x.strip()]
    summary = record_game_loot(wb, gold, items, xp, notes, captain_xp)
    return True, summary


@register_action("remove_vault_item")
def _act_remove_vault_item(wb: dict) -> tuple[bool, str]:
    if remove_vault_item(wb, request.form.get("item_id") or ""):
        return True, "Item removed from vault."
    return False, "Item not found."


@register_action("add_vault_item")
def _act_add_vault_item(wb: dict) -> tuple[bool, str]:
    name = (request.form.get("item_name") or "").strip()
    if not name:
        return False, "Item name required."
    add_vault_item(wb, name, request.form.get("item_notes") or "", "manual")
    return True, f"Added “{name}” to vault."


@register_action("upload_wizard_portrait")
def _act_upload_wizard_portrait(wb: dict) -> tuple[bool, str]:
    f = request.files.get("wizard_portrait")
    if not (f and f.filename):
        return False, "Choose an image file."
    apply_portrait(wb["wizard"], wb["id"], "wizard", f)
    return True, "Wizard portrait updated."


@register_action("upload_apprentice_portrait")
def _act_upload_apprentice_portrait(wb: dict) -> tuple[bool, str]:
    if not wb.get("apprentice"):
        return False, "No apprentice."
    f = request.files.get("apprentice_portrait")
    if not (f and f.filename):
        return False, "Choose an image file."
    apply_portrait(wb["apprentice"], wb["id"], "apprentice", f)
    return True, "Apprentice portrait updated."


@register_action("reorder_spells")
def _act_reorder_spells(wb: dict) -> tuple[bool, str]:
    order_raw = (request.form.get("spell_order") or "").strip()
    ids = [x for x in order_raw.split("|") if x]
    return reorder_spells(wb, ids)


@register_action("reorder_soldiers")
def _act_reorder_soldiers(wb: dict) -> tuple[bool, str]:
    order_raw = (request.form.get("soldier_order") or "").strip()
    ids = [x for x in order_raw.split("|") if x]
    return reorder_soldiers(wb, ids)


@register_action("set_base_location")
def _act_set_base_location(wb: dict) -> tuple[bool, str]:
    loc = request.form.get("location") or "none"
    ok, msg = set_base_location(wb, loc)
    notes = (request.form.get("base_notes") or "").strip()
    wb.setdefault("base", {})["notes"] = notes
    return ok, msg


@register_action("buy_base_resource")
def _act_buy_base_resource(wb: dict) -> tuple[bool, str]:
    return buy_base_resource(wb, request.form.get("resource") or "")


@register_action("remove_base_resource")
def _act_remove_base_resource(wb: dict) -> tuple[bool, str]:
    return sell_or_remove_base_resource(
        wb,
        request.form.get("resource") or "",
        refund=request.form.get("refund") == "on",
    )


@register_action("add_soldier_mutation")
def _act_add_soldier_mutation(wb: dict) -> tuple[bool, str]:
    has_input, number = _mutation_number_from_form()
    if not has_input:
        return False, "Pick a mutation to add, or use “Add random mutation”."
    return add_soldier_mutation(wb, request.form.get("soldier_id") or "", number)


@register_action("remove_soldier_mutation")
def _act_remove_soldier_mutation(wb: dict) -> tuple[bool, str]:
    return remove_soldier_mutation(wb, request.form.get("soldier_id") or "", _mutation_index_from_form())


@register_action("add_construct_modification")
def _act_add_construct_modification(wb: dict) -> tuple[bool, str]:
    name = (request.form.get("modification_name") or "").strip()
    if not name:
        return False, "Pick a Construct Modification to add."
    stat = (request.form.get("modification_stat") or "").strip() or None
    return add_construct_modification(wb, request.form.get("soldier_id") or "", name, stat)


@register_action("remove_construct_modification")
def _act_remove_construct_modification(wb: dict) -> tuple[bool, str]:
    return remove_construct_modification(
        wb, request.form.get("soldier_id") or "", _mutation_index_from_form()
    )


@register_action("add_wizard_mutation")
def _act_add_wizard_mutation(wb: dict) -> tuple[bool, str]:
    has_input, number = _mutation_number_from_form()
    if not has_input:
        return False, "Pick a mutation to add, or use “Add random mutation”."
    return add_wizard_mutation(wb, number)


@register_action("remove_wizard_mutation")
def _act_remove_wizard_mutation(wb: dict) -> tuple[bool, str]:
    return remove_wizard_mutation(wb, _mutation_index_from_form())


@register_action("add_apprentice_mutation")
def _act_add_apprentice_mutation(wb: dict) -> tuple[bool, str]:
    has_input, number = _mutation_number_from_form()
    if not has_input:
        return False, "Pick a mutation to add, or use “Add random mutation”."
    return add_apprentice_mutation(wb, number)


@register_action("remove_apprentice_mutation")
def _act_remove_apprentice_mutation(wb: dict) -> tuple[bool, str]:
    return remove_apprentice_mutation(wb, _mutation_index_from_form())


@register_action("add_captain_mutation")
def _act_add_captain_mutation(wb: dict) -> tuple[bool, str]:
    has_input, number = _mutation_number_from_form()
    if not has_input:
        return False, "Pick a mutation to add, or use “Add random mutation”."
    return add_captain_mutation(wb, number)


@register_action("remove_captain_mutation")
def _act_remove_captain_mutation(wb: dict) -> tuple[bool, str]:
    return remove_captain_mutation(wb, _mutation_index_from_form())


def _injury_id_from_form() -> str:
    return (request.form.get("injury_id") or "").strip()


@register_action("add_wizard_permanent_injury")
def _act_add_wizard_permanent_injury(wb: dict) -> tuple[bool, str]:
    injury_id = _injury_id_from_form()
    if not injury_id:
        return False, "Pick a permanent injury to add."
    return add_wizard_permanent_injury(wb, injury_id)


@register_action("remove_wizard_permanent_injury")
def _act_remove_wizard_permanent_injury(wb: dict) -> tuple[bool, str]:
    return remove_wizard_permanent_injury(wb, _mutation_index_from_form())


@register_action("add_apprentice_permanent_injury")
def _act_add_apprentice_permanent_injury(wb: dict) -> tuple[bool, str]:
    injury_id = _injury_id_from_form()
    if not injury_id:
        return False, "Pick a permanent injury to add."
    return add_apprentice_permanent_injury(wb, injury_id)


@register_action("remove_apprentice_permanent_injury")
def _act_remove_apprentice_permanent_injury(wb: dict) -> tuple[bool, str]:
    return remove_apprentice_permanent_injury(wb, _mutation_index_from_form())


@register_action("add_captain_permanent_injury")
def _act_add_captain_permanent_injury(wb: dict) -> tuple[bool, str]:
    injury_id = _injury_id_from_form()
    if not injury_id:
        return False, "Pick a permanent injury to add."
    return add_captain_permanent_injury(wb, injury_id)


@register_action("remove_captain_permanent_injury")
def _act_remove_captain_permanent_injury(wb: dict) -> tuple[bool, str]:
    return remove_captain_permanent_injury(wb, _mutation_index_from_form())


def _fitted_from_form() -> bool:
    return (request.form.get("fitted") or "") == "1"


@register_action("toggle_wizard_injury_prosthetic")
def _act_toggle_wizard_injury_prosthetic(wb: dict) -> tuple[bool, str]:
    return set_permanent_injury_prosthetic(wb, "wizard", _mutation_index_from_form(), _fitted_from_form())


@register_action("toggle_apprentice_injury_prosthetic")
def _act_toggle_apprentice_injury_prosthetic(wb: dict) -> tuple[bool, str]:
    return set_permanent_injury_prosthetic(wb, "apprentice", _mutation_index_from_form(), _fitted_from_form())


@register_action("toggle_captain_injury_prosthetic")
def _act_toggle_captain_injury_prosthetic(wb: dict) -> tuple[bool, str]:
    return set_permanent_injury_prosthetic(wb, "captain", _mutation_index_from_form(), _fitted_from_form())


def _upgrade_id_from_form() -> str:
    return (request.form.get("upgrade_id") or "").strip()


def _upgrade_index_from_form() -> int:
    raw = (request.form.get("upgrade_index") or "").strip()
    return int(raw) if raw.lstrip("-").isdigit() else -1


@register_action("add_wizard_prosthetic_upgrade")
def _act_add_wizard_prosthetic_upgrade(wb: dict) -> tuple[bool, str]:
    return add_wizard_prosthetic_upgrade(wb, _mutation_index_from_form(), _upgrade_id_from_form())


@register_action("remove_wizard_prosthetic_upgrade")
def _act_remove_wizard_prosthetic_upgrade(wb: dict) -> tuple[bool, str]:
    return remove_wizard_prosthetic_upgrade(wb, _mutation_index_from_form(), _upgrade_index_from_form())


@register_action("add_apprentice_prosthetic_upgrade")
def _act_add_apprentice_prosthetic_upgrade(wb: dict) -> tuple[bool, str]:
    return add_apprentice_prosthetic_upgrade(wb, _mutation_index_from_form(), _upgrade_id_from_form())


@register_action("remove_apprentice_prosthetic_upgrade")
def _act_remove_apprentice_prosthetic_upgrade(wb: dict) -> tuple[bool, str]:
    return remove_apprentice_prosthetic_upgrade(wb, _mutation_index_from_form(), _upgrade_index_from_form())


@register_action("add_captain_prosthetic_upgrade")
def _act_add_captain_prosthetic_upgrade(wb: dict) -> tuple[bool, str]:
    return add_captain_prosthetic_upgrade(wb, _mutation_index_from_form(), _upgrade_id_from_form())


@register_action("remove_captain_prosthetic_upgrade")
def _act_remove_captain_prosthetic_upgrade(wb: dict) -> tuple[bool, str]:
    return remove_captain_prosthetic_upgrade(wb, _mutation_index_from_form(), _upgrade_index_from_form())


@register_action("add_soldier_permanent_injury")
def _act_add_soldier_permanent_injury(wb: dict) -> tuple[bool, str]:
    injury_id = _injury_id_from_form()
    if not injury_id:
        return False, "Pick a permanent injury to add."
    return add_soldier_permanent_injury(wb, request.form.get("soldier_id") or "", injury_id)


@register_action("remove_soldier_permanent_injury")
def _act_remove_soldier_permanent_injury(wb: dict) -> tuple[bool, str]:
    return remove_soldier_permanent_injury(
        wb, request.form.get("soldier_id") or "", _mutation_index_from_form()
    )


@register_action("toggle_soldier_giant_blooded")
def _act_toggle_soldier_giant_blooded(wb: dict) -> tuple[bool, str]:
    return set_soldier_giant_blooded(
        wb, request.form.get("soldier_id") or "", _fitted_from_form()
    )


@register_action("roll_random_recruits")
def _act_roll_random_recruits(wb: dict) -> tuple[bool, str]:
    return roll_random_recruits(wb, with_status=request.form.get("with_status") == "on")


def _update_details(wb: dict) -> None:
    wb["name"] = (request.form.get("warband_name") or wb["name"]).strip()
    wiz = wb.setdefault("wizard", {})
    wiz["name"] = (request.form.get("wizard_name") or wiz.get("name", "")).strip()
    school = request.form.get("school") or wiz.get("school")
    if school in SCHOOLS:
        wiz["school"] = school
    wiz["notes"] = request.form.get("wizard_notes") or ""
    wiz["has_dagger"] = request.form.get("wizard_dagger") == "on"

    # Wizard item slots (base 5, +1/+2 under Blood Legacy's Increased Item Slots)
    wiz_slot_n = expansions.wizard_item_slots(wb)
    wiz_slots = []
    for i in range(wiz_slot_n):
        wiz_slots.append((request.form.get(f"wizard_slot_{i}") or "").strip())
    wiz["item_slots"] = normalize_item_slots(wiz_slots, wiz_slot_n)

    if request.form.get("wizard_portrait_remove") == "on":
        remove_portrait(wiz, wb["id"], "wizard")
    f = request.files.get("wizard_portrait")
    apply_portrait(wiz, wb["id"], "wizard", f)

    if wb.get("apprentice"):
        ap = wb["apprentice"]
        ap["name"] = (request.form.get("apprentice_name") or ap.get("name", "")).strip()
        ap["notes"] = request.form.get("apprentice_notes") or ""
        ap["has_dagger"] = request.form.get("apprentice_dagger") == "on"
        ap_slot_n = expansions.apprentice_item_slots(wb)
        ap_slots = []
        for i in range(ap_slot_n):
            ap_slots.append((request.form.get(f"apprentice_slot_{i}") or "").strip())
        ap["item_slots"] = normalize_item_slots(ap_slots, ap_slot_n)
        if request.form.get("apprentice_portrait_remove") == "on":
            remove_portrait(ap, wb["id"], "apprentice")
        af = request.files.get("apprentice_portrait")
        apply_portrait(ap, wb["id"], "apprentice", af)


@app.route("/warband/<warband_id>/delete", methods=["POST"])
def warband_delete(warband_id: str) -> Response:
    wb = _require_warband(warband_id)
    name = wb.get("name", warband_id)
    delete_warband(warband_id)
    flash(f"Deleted warband “{name}”.", "success")
    return redirect(url_for("home"))


@app.route("/warband/<warband_id>/duplicate", methods=["POST"])
def warband_duplicate(warband_id: str) -> Response:
    _require_warband(warband_id)
    custom = (request.form.get("new_name") or "").strip() or None
    wb, msg = duplicate_warband(warband_id, custom)
    if not wb:
        flash(msg, "error")
        return redirect(url_for("home"))
    flash(msg, "success")
    return redirect(url_for("warband_view", warband_id=wb["id"]))


@app.route("/warband/<warband_id>/export")
def warband_export(warband_id: str) -> Response:
    wb = _require_warband(warband_id)
    payload = export_warband_json(wb)
    filename = f"{wb.get('id', 'warband')}.warbands"
    return Response(
        payload,
        mimetype="application/json",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@app.route("/warband/<warband_id>/pdf")
def warband_pdf(warband_id: str) -> Response:
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
def warband_import() -> str | Response:
    if request.method == "POST":
        uploaded = request.files.get("file")
        raw = ""
        if uploaded and uploaded.filename:
            raw = uploaded.read().decode("utf-8", errors="replace")
        else:
            raw = request.form.get("json_text") or ""
        if not raw.strip():
            flash("Paste JSON or choose a file.", "error")
            return render_template("import.html", json_text=raw)
        try:
            wb = import_warband_json(raw)
        except Exception as exc:
            # Genuine last-resort guard — imported JSON is arbitrary user
            # input and can fail in any number of ways (bad JSON, missing
            # keys, wrong types); log it so a "could not import" report is
            # diagnosable without the user having to reproduce it live.
            logger.warning("Warband import failed: %s", exc, exc_info=True)
            flash(f"Could not import: {exc}", "error")
            return render_template("import.html", json_text=raw)
        restored = restore_portraits_by_name(wb, request.files.getlist("pictures"))
        save_warband(wb)
        msg = f"Imported “{wb.get('name', 'warband')}”."
        if restored:
            msg += f" Restored {restored} picture(s)."
        flash(msg, "success")
        return redirect(url_for("warband_view", warband_id=wb["id"]))
    return render_template("import.html")


# ---- Settings (data folder) ------------------------------------------------

@app.route("/settings", methods=["GET", "POST"])
def settings() -> str | Response:
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
            flash(f"Data folder set to “{new_dir}”.", "success")
        return redirect(url_for("settings"))
    return render_template(
        "settings.html",
        active_dir=str(warband_dir().parent),
        configured_dir=str(paths.user_data_dir()),
        default_dir=str(paths.default_user_data_dir()),
    )


@app.route("/settings/browse", methods=["POST"])
def settings_browse() -> tuple[dict, int] | dict:
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
        # Genuine last-resort guard — the subprocess/tkinter dialog can fail
        # in ways that vary by OS and desktop environment (missing tkinter,
        # no display, timeout); log it since it's otherwise reported to the
        # user only as the raw exception string in the JSON response.
        logger.warning("Folder picker subprocess failed: %s", exc, exc_info=True)
        return {"path": "", "error": str(exc)}, 500
    return {"path": chosen}


@app.errorhandler(404)
def not_found(_e: Exception) -> Response:
    flash("That page or warband was not found.", "error")
    return redirect(url_for("home"))


def main() -> None:
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
            except Exception as exc:
                # Genuine last-resort guard — tray backends vary by Windows
                # version/desktop environment and can fail in ways we can't
                # enumerate; fall back to idle_watchdog alone, but log why.
                logger.info("Tray icon unavailable, falling back to idle_watchdog: %s", exc)

        threading.Event().wait()  # keep the main thread alive; idle_watchdog exits the process
    else:
        app.run(debug=True, host="127.0.0.1", port=port)


if __name__ == "__main__":
    main()
