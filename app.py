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
    SPELLS,
    STARTING_GOLD,
    STARTING_SPELL_COUNT,
    WIZARD_ITEM_SLOTS,
    all_spells_flat,
    cn_penalty,
    format_stat,
    level_from_xp,
    soldier_list_for_ui,
    spell_id,
    spells_for_wizard_ui,
)
from game_content import (
    enrich_spells_with_descriptions,
    load_potion_choices,
    load_spell_descriptions,
    load_spell_names,
    load_spellcaster_items,
    load_standard_items,
    spell_description,
)
from pdf_export import build_warband_pdf
from warband_store import (
    PORTRAIT_DIR,
    WARBAND_DIR,
    add_captain_xp,
    add_history,
    add_soldier,
    add_soldier_xp,
    add_vault_item,
    adjust_gold,
    apply_captain_level_up,
    apply_captain_trick,
    apply_level_up,
    apply_soldier_level_up,
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
    enrich_soldier,
    export_warband_json,
    hire_apprentice,
    hire_captain,
    import_warband_json,
    known_spell_ids,
    list_warbands,
    load_warband,
    normalize_item_slots,
    promote_soldier_to_captain,
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
    set_base_location,
    set_soldier_status,
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

app.jinja_env.globals.update(
    format_stat=format_stat,
    STARTING_GOLD=STARTING_GOLD,
    APPRENTICE_COST=APPRENTICE_COST,
    MAX_SOLDIERS=MAX_SOLDIERS,
    MAX_SPECIALISTS=MAX_SPECIALISTS,
    STARTING_SPELL_COUNT=STARTING_SPELL_COUNT,
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
)


def _require_warband(warband_id: str) -> dict:
    wb = load_warband(warband_id)
    if not wb:
        abort(404)
    return wb


@app.route("/")
def home():
    return render_template("index.html", warbands=list_warbands())


@app.route("/reference")
def reference():
    descs = load_spell_descriptions()
    spells_with_desc = {
        school: [
            {**sp, "description": descs.get(sp["name"], "") or "No description available."}
            for sp in splist
        ]
        for school, splist in SPELLS.items()
    }
    return render_template(
        "reference.html",
        soldiers=soldier_list_for_ui(),
        schools=SCHOOLS,
        spells=spells_with_desc,
        opposed=SCHOOL_OPPOSED,
        aligned=SCHOOL_ALIGNED,
        neutral=SCHOOL_NEUTRAL,
        relations=SCHOOL_RELATIONS,
        standard_items=load_standard_items(),  # full list incl. armour (for reference)
        potion_choices=load_potion_choices(),
        spell_names=load_spell_names(),
    )


@app.route("/about")
def about():
    return render_template("about.html")


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
        if school not in SCHOOLS:
            school = SCHOOLS[0]
        # Order preserved from hidden field if present
        order_raw = (request.form.get("spell_order") or "").strip()
        if order_raw:
            spell_keys = [k for k in order_raw.split("|") if k]
        else:
            spell_keys = request.form.getlist("spells")
        with_apprentice = request.form.get("with_apprentice") == "on"
        apprentice_name = (request.form.get("apprentice_name") or "").strip()

        # Soldiers from creation form: soldier_type_N, soldier_name_N
        soldiers = []
        for key in request.form:
            if key.startswith("soldier_type_"):
                idx = key[len("soldier_type_") :]
                type_key = request.form.get(key) or ""
                if type_key:
                    soldiers.append(
                        {
                            "type_key": type_key,
                            "name": (request.form.get(f"soldier_name_{idx}") or "").strip(),
                        }
                    )

        if not name or not wizard:
            flash("Warband name and wizard name are required.", "error")
            return _render_new(school=school, selected=spell_keys)

        wb, msg = create_warband(
            name,
            wizard,
            school,
            spell_keys,
            with_apprentice,
            apprentice_name,
            soldiers=soldiers or None,
        )
        if not wb:
            flash(msg, "error")
            return _render_new(school=school, selected=spell_keys)

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
            for i, s in enumerate(wb.get("soldiers") or []):
                f = request.files.get(f"soldier_portrait_{i}")
                if f and f.filename:
                    s["portrait"] = save_portrait(wb["id"], f"soldier_{s['id']}", f)
        except ValueError as exc:
            flash(str(exc), "error")

        save_warband(wb)
        flash(f"Warband “{wb['name']}” created with {wb['gold']} gc.", "success")
        return redirect(url_for("warband_view", warband_id=wb["id"]))

    school = request.args.get("school") or SCHOOLS[0]
    return _render_new(school=school)


def _render_new(school: str = "Elementalist", selected: list | None = None):
    school = school if school in SCHOOLS else SCHOOLS[0]
    rel = SCHOOL_RELATIONS[school]
    spells_ui = enrich_spells_with_descriptions(spells_for_wizard_ui(school))
    return render_template(
        "warband_new.html",
        schools=SCHOOLS,
        school=school,
        spells_for_wizard=spells_ui,
        spells_by_school=SPELLS,
        opposed=SCHOOL_OPPOSED,
        aligned=SCHOOL_ALIGNED,
        neutral=SCHOOL_NEUTRAL,
        relations=rel,
        selected=selected or [],
        catalog=soldier_list_for_ui(),
        standard_items=load_spellcaster_items(),
        potion_choices=load_potion_choices(),
        spell_names=load_spell_names(),
    )


# ---- View / maintain ------------------------------------------------------

@app.route("/warband/<warband_id>")
def warband_view(warband_id: str):
    wb = _require_warband(warband_id)
    recompute_spell_cns(wb)
    soldiers = [enrich_soldier(s) for s in wb.get("soldiers") or []]
    limits = warband_limits(wb)
    known = known_spell_ids(wb)
    wschool = (wb.get("wizard") or {}).get("school") or "Elementalist"
    learnable = [
        {**s, "effective_cn": s["cn"] + cn_penalty(wschool, s["school"])}
        for s in all_spells_flat()
        if s["id"] not in known
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
    return render_template(
        "warband_view.html",
        wb=wb,
        soldiers=soldiers,
        limits=limits,
        catalog=soldier_list_for_ui(),
        schools=SCHOOLS,
        learnable=learnable,
        pending_levels=limits["pending_levels"],
        relations=SCHOOL_RELATIONS.get(wschool, {}),
        base=base_summary(wb),
        base_locations=BASE_LOCATIONS,
        base_resources=BASE_RESOURCES,
        standard_items=load_spellcaster_items(),  # no armour for wizard/apprentice UI
        full_standard_items=load_standard_items(),  # includes armour/shield: captain picker + reference list
        wizard_spells_ui=wiz_spells,
        vault_names=vault_names,
        potion_choices=load_potion_choices(),
        spell_names=load_spell_names(),
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
            amount = int(request.form.get("amount") or 0)
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
            amount = int(request.form.get("amount") or 0)
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
            delta = int(request.form.get("delta") or 0)
            reason = (request.form.get("reason") or "").strip()
            if delta == 0:
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
            xp = int(request.form.get("xp") or 0)
            if xp <= 0:
                flash("Enter positive XP.", "error")
            else:
                wiz = wb.setdefault("wizard", {})
                wiz["xp"] = int(wiz.get("xp", 0)) + xp
                add_history(wb, f"Wizard gained {xp} XP (total {wiz['xp']}).")
                save_warband(wb)
                flash(f"+{xp} XP. Pending level-ups: {warband_limits(wb)['pending_levels']}.", "success")

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
    wb["notes"] = request.form.get("notes") or ""
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

        serve(app, host="127.0.0.1", port=port)
    else:
        app.run(debug=True, host="127.0.0.1", port=port)


if __name__ == "__main__":
    main()
