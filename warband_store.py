"""Load / save Frostgrave warbands, portraits, leveling, loot."""

from __future__ import annotations

import json
import re
import shutil
import uuid
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path

from frostgrave_data import (
    ALIGNED_SCHOOL_SPELLS,
    APPRENTICE_BASE,
    APPRENTICE_COST,
    APPRENTICE_ITEM_SLOTS,
    APPRENTICE_STAT_OFFSET,
    BASE_LOCATIONS,
    BASE_RESOURCES,
    MAX_SOLDIERS,
    MAX_SPECIALISTS,
    NEUTRAL_SPELLS,
    OWN_SCHOOL_SPELLS,
    SCHOOL_ALIGNED,
    SCHOOL_NEUTRAL,
    SCHOOL_OPPOSED,
    SCHOOL_RELATIONS,
    SCHOOLS,
    SOLDIERS,
    STARTING_GOLD,
    STARTING_SPELL_COUNT,
    WIZARD_BASE,
    WIZARD_ITEM_SLOTS,
    cn_penalty,
    effective_cn,
    find_spell,
    get_soldier,
    level_from_xp,
    school_relation,
    spell_id,
    xp_for_level,
    xp_to_next_level,
)

BASE_DIR = Path(__file__).resolve().parent
WARBAND_DIR = BASE_DIR / "data" / "warbands"
PORTRAIT_DIR = BASE_DIR / "data" / "portraits"
WARBAND_DIR.mkdir(parents=True, exist_ok=True)
PORTRAIT_DIR.mkdir(parents=True, exist_ok=True)

ALLOWED_IMAGE_EXT = {".jpg", ".jpeg", ".png", ".gif", ".webp"}


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _slug(name: str) -> str:
    s = re.sub(r"[^a-zA-Z0-9]+", "-", (name or "warband").strip().lower()).strip("-")
    return s[:40] or "warband"


def new_warband_id(name: str) -> str:
    return f"{_slug(name)}-{uuid.uuid4().hex[:8]}"


def empty_slots(n: int) -> list[str]:
    return [""] * n


def empty_base() -> dict:
    return {
        "location": "none",  # key in BASE_LOCATIONS
        "resources": [],  # list of BASE_RESOURCES keys
        "notes": "",
    }


def normalize_item_slots(raw, n: int) -> list[str]:
    """Convert legacy item formats into a fixed-length list of slot strings."""
    slots: list[str] = []
    if isinstance(raw, list):
        for entry in raw:
            if isinstance(entry, dict):
                slots.append(str(entry.get("name") or "").strip())
            else:
                slots.append(str(entry or "").strip())
    elif isinstance(raw, str):
        slots = [line.strip() for line in raw.splitlines() if line.strip()]
    # pad / trim
    if len(slots) < n:
        slots.extend([""] * (n - len(slots)))
    return slots[:n]


def empty_wizard(name: str = "", school: str = "Elementalist") -> dict:
    stats = deepcopy(WIZARD_BASE)
    return {
        "name": name,
        "school": school,
        "level": 0,
        "xp": 0,
        "stats": stats,
        "item_slots": empty_slots(WIZARD_ITEM_SLOTS),
        "has_dagger": False,  # free slot (2e: first dagger takes no slot)
        "items": [],  # legacy
        "spells": [],
        "notes": "",
        "portrait": None,
        "level_history": [],
    }


def empty_apprentice(name: str = "") -> dict:
    stats = deepcopy(APPRENTICE_BASE)
    return {
        "name": name,
        "level": 0,
        "stats": stats,
        "item_slots": empty_slots(APPRENTICE_ITEM_SLOTS),
        "has_dagger": False,
        "items": [],
        "notes": "",
        "portrait": None,
    }


def sync_apprentice(wb: dict) -> None:
    """Apprentice stats from wizard (2e p.27): M same, F-2, S same, A10, W-2, H-2."""
    ap = wb.get("apprentice")
    wiz = wb.get("wizard") or {}
    if not ap or not wiz:
        return
    wstats = wiz.get("stats") or WIZARD_BASE
    wiz_h = int(wstats.get("health", 14))
    ap_stats = {
        "move": int(wstats.get("move", 6)),
        "fight": int(wstats.get("fight", 2)) - 2,
        "shoot": int(wstats.get("shoot", 0)),
        "armour": 10,
        "will": int(wstats.get("will", 4)) - 2,
        "health": max(1, wiz_h - 2),  # starting: 14-2 = 12
    }
    ap["stats"] = ap_stats
    ap["level"] = int(wiz.get("level", 0)) // 2
    ap.setdefault("has_dagger", False)
    ap["item_slots"] = normalize_item_slots(
        ap.get("item_slots", ap.get("items")), APPRENTICE_ITEM_SLOTS
    )


def spells_from_keys(keys: list[str], wizard_school: str) -> list[dict]:
    """Build spell list with base CN and effective CN for this wizard."""
    spells = []
    for key in keys:
        sp = find_spell(key)
        if not sp:
            continue
        base = int(sp["cn"])
        pen = cn_penalty(wizard_school, sp["school"])
        spells.append(
            {
                "id": sp["id"],
                "name": sp["name"],
                "school": sp["school"],
                "base_cn": base,
                "cn_penalty": pen,
                "cn": base + pen,  # effective casting number for this wizard
                "type": sp["type"],
                "relation": school_relation(wizard_school, sp["school"]),
            }
        )
    return spells


def recompute_spell_cns(wb: dict) -> None:
    """Refresh effective CN if school changed or spells improved."""
    wiz = wb.get("wizard") or {}
    school = wiz.get("school") or "Elementalist"
    for s in wiz.get("spells") or []:
        base = int(s.get("base_cn", s.get("cn", 10)))
        # If spell was improved, base_cn is original, cn may be lower than base+penalty
        # Store improvements as cn_bonus (negative reduction)
        pen = cn_penalty(school, s.get("school", school))
        improve = int(s.get("cn_improve", 0))  # number of -1 improvements
        s["cn_penalty"] = pen
        s["relation"] = school_relation(school, s.get("school", school))
        s["base_cn"] = base
        s["cn"] = max(5, base + pen - improve)


def validate_starting_spells(school: str, spell_keys: list[str]) -> tuple[bool, str]:
    """2e Choosing Spells p.24: 3 own, 1 each aligned, 2 neutral (diff schools), no opposed."""
    if len(spell_keys) != STARTING_SPELL_COUNT:
        return False, f"Pick exactly {STARTING_SPELL_COUNT} spells (got {len(spell_keys)})."
    if len(set(spell_keys)) != len(spell_keys):
        return False, "Duplicate spells selected."

    rel = SCHOOL_RELATIONS.get(school)
    if not rel:
        return False, "Invalid school."

    by_school: dict[str, int] = {}
    for key in spell_keys:
        sp = find_spell(key)
        if not sp:
            return False, f"Unknown spell: {key}"
        by_school[sp["school"]] = by_school.get(sp["school"], 0) + 1

    # No opposed
    opp = rel["opposed"]
    if by_school.get(opp, 0) > 0:
        return False, f"Starting wizards cannot take spells from opposed school ({opp})."

    # Own: exactly 3
    own_n = by_school.get(school, 0)
    if own_n != OWN_SCHOOL_SPELLS:
        return False, f"Need exactly {OWN_SCHOOL_SPELLS} spells from {school} (have {own_n})."

    # Each aligned: exactly 1
    for al in rel["aligned"]:
        n = by_school.get(al, 0)
        if n != ALIGNED_SCHOOL_SPELLS:
            return False, f"Need exactly 1 spell from aligned school {al} (have {n})."

    # Neutrals: exactly 2 spells from two different neutral schools (1 each)
    neutral_picks = {s: n for s, n in by_school.items() if s in rel["neutral"]}
    total_neutral = sum(neutral_picks.values())
    if total_neutral != NEUTRAL_SPELLS:
        return False, f"Need exactly {NEUTRAL_SPELLS} spells from neutral schools (have {total_neutral})."
    if any(n != 1 for n in neutral_picks.values()):
        return False, "The two neutral spells must each come from a different school."
    if len(neutral_picks) != NEUTRAL_SPELLS:
        return False, "Pick neutral spells from two different neutral schools."

    # No extras
    allowed = {school, *rel["aligned"], *rel["neutral"]}
    for s in by_school:
        if s not in allowed:
            return False, f"Spell school {s} is not allowed at creation."

    return True, "OK"


def create_warband(
    warband_name: str,
    wizard_name: str,
    school: str,
    spell_keys: list[str],
    with_apprentice: bool = False,
    apprentice_name: str = "",
    soldiers: list[dict] | None = None,
) -> tuple[dict | None, str]:
    """
    soldiers: optional list of {type_key, name} hired at creation (costs deducted).
    """
    if school not in SCHOOLS:
        return None, "Invalid school."
    ok, msg = validate_starting_spells(school, spell_keys)
    if not ok:
        return None, msg

    gold = STARTING_GOLD
    apprentice = None
    if with_apprentice:
        if gold < APPRENTICE_COST:
            return None, f"Not enough gold for apprentice ({APPRENTICE_COST} gc)."
        gold -= APPRENTICE_COST
        apprentice = empty_apprentice(apprentice_name or "Apprentice")

    # Validate soldiers before committing
    hired: list[dict] = []
    specs = 0
    if soldiers:
        if len(soldiers) > MAX_SOLDIERS:
            return None, f"Max {MAX_SOLDIERS} soldiers."
        for entry in soldiers:
            type_key = entry.get("type_key") or ""
            info = get_soldier(type_key)
            if not info:
                return None, f"Unknown soldier type: {type_key}"
            if info["category"] == "specialist":
                specs += 1
                if specs > MAX_SPECIALISTS:
                    return None, f"Max {MAX_SPECIALISTS} specialists."
            cost = int(info["cost"])
            if gold < cost:
                return None, f"Not enough gold for {info['name']} (need {cost} gc)."
            gold -= cost
            hired.append(
                {
                    "id": uuid.uuid4().hex[:10],
                    "type_key": type_key,
                    "name": (entry.get("name") or info["name"]).strip(),
                    "status": "active",
                    "items": [],
                    "notes": "",
                    "portrait": None,
                }
            )

    wb = {
        "id": new_warband_id(warband_name),
        "name": warband_name.strip() or "Unnamed Warband",
        "created": _now(),
        "updated": _now(),
        "gold": gold,
        "notes": "",
        "wizard": empty_wizard(wizard_name.strip() or "Wizard", school),
        "apprentice": apprentice,
        "soldiers": hired,
        "vault_items": [],
        "base": empty_base(),
        "history": [],
    }
    wb["wizard"]["spells"] = spells_from_keys(spell_keys, school)
    if apprentice:
        sync_apprentice(wb)
    parts = [f"Warband founded with {gold} gc remaining"]
    if with_apprentice:
        parts.append("apprentice hired")
    if hired:
        parts.append(f"{len(hired)} soldiers recruited")
    wb["history"].append({"when": _now(), "text": "; ".join(parts) + "."})
    return wb, "Created."


def reorder_spells(wb: dict, spell_ids_in_order: list[str]) -> tuple[bool, str]:
    wiz = wb.get("wizard") or {}
    spells = wiz.get("spells") or []
    by_id = {s.get("id"): s for s in spells}
    if set(spell_ids_in_order) != set(by_id.keys()) or len(spell_ids_in_order) != len(spells):
        return False, "Spell list does not match known spells."
    wiz["spells"] = [by_id[i] for i in spell_ids_in_order]
    return True, "Spell order updated."


def reorder_soldiers(wb: dict, soldier_ids_in_order: list[str]) -> tuple[bool, str]:
    soldiers = wb.get("soldiers") or []
    by_id = {s.get("id"): s for s in soldiers}
    if set(soldier_ids_in_order) != set(by_id.keys()) or len(soldier_ids_in_order) != len(soldiers):
        return False, "Soldier list does not match roster."
    wb["soldiers"] = [by_id[i] for i in soldier_ids_in_order]
    return True, "Soldier order updated."


def list_warbands() -> list[dict]:
    items = []
    for path in sorted(
        WARBAND_DIR.glob("*.warbands"), key=lambda p: p.stat().st_mtime, reverse=True
    ):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        items.append(
            {
                "id": data.get("id", path.stem),
                "name": data.get("name", path.stem),
                "wizard": (data.get("wizard") or {}).get("name", "—"),
                "school": (data.get("wizard") or {}).get("school", "—"),
                "level": (data.get("wizard") or {}).get("level", 0),
                "gold": data.get("gold", 0),
                "soldiers": len(
                    [s for s in (data.get("soldiers") or []) if s.get("status") != "dead"]
                ),
                "updated": data.get("updated", ""),
                "portrait": (data.get("wizard") or {}).get("portrait"),
            }
        )
    return items


def warband_path(warband_id: str) -> Path:
    """Warband files use a .warbands extension; the content is plain JSON."""
    safe = re.sub(r"[^a-zA-Z0-9._-]", "", warband_id)
    return WARBAND_DIR / f"{safe}.warbands"


def portrait_dir(warband_id: str) -> Path:
    safe = re.sub(r"[^a-zA-Z0-9._-]", "", warband_id)
    d = PORTRAIT_DIR / safe
    d.mkdir(parents=True, exist_ok=True)
    return d


def load_warband(warband_id: str) -> dict | None:
    path = warband_path(warband_id)
    if not path.is_file():
        return None
    try:
        wb = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    # Migrate older formats
    wiz = wb.setdefault("wizard", empty_wizard())
    wiz.setdefault("stats", deepcopy(WIZARD_BASE))
    # Fix pre-2e health base (was H10; 2e starting wizard is H14)
    wstats = wiz["stats"]
    old_h = int(wstats.get("health", 14))
    if old_h == 10:
        # Old default base — bump to 14 (preserve any extra from level-ups if somehow >10)
        wstats["health"] = 14
    wstats.setdefault("health", 14)
    wiz.pop("health_current", None)
    wiz.setdefault("has_dagger", False)
    # Migrate items -> item_slots
    if "item_slots" not in wiz or not isinstance(wiz.get("item_slots"), list):
        wiz["item_slots"] = normalize_item_slots(wiz.get("items"), WIZARD_ITEM_SLOTS)
    else:
        wiz["item_slots"] = normalize_item_slots(wiz["item_slots"], WIZARD_ITEM_SLOTS)

    if isinstance(wiz.get("spells"), str):
        wiz["spells"] = []
    wb.setdefault("vault_items", [])
    if isinstance(wb.get("vault"), str) and wb["vault"] and not wb["vault_items"]:
        wb["vault_items"] = [
            {"name": line, "notes": "migrated", "source": "vault"}
            for line in wb["vault"].splitlines()
            if line.strip()
        ]
    if not isinstance(wb.get("base"), dict):
        wb["base"] = empty_base()
    else:
        wb["base"].setdefault("location", "none")
        wb["base"].setdefault("resources", [])
        wb["base"].setdefault("notes", "")
        if wb["base"]["location"] not in BASE_LOCATIONS:
            wb["base"]["location"] = "none"
        wb["base"]["resources"] = [
            r for r in wb["base"]["resources"] if r in BASE_RESOURCES
        ]
    if wb.get("apprentice"):
        ap = wb["apprentice"]
        ap.setdefault("has_dagger", False)
        ap.pop("health_current", None)
        if "item_slots" not in ap or not isinstance(ap.get("item_slots"), list):
            ap["item_slots"] = normalize_item_slots(ap.get("items"), APPRENTICE_ITEM_SLOTS)
        sync_apprentice(wb)
    for s in wb.get("soldiers") or []:
        s.setdefault("portrait", None)
        s.setdefault("items", [])
        s.pop("health_current", None)
        if isinstance(s.get("items"), str):
            text = s["items"].strip()
            s["items"] = (
                [{"name": line, "notes": ""} for line in text.splitlines() if line.strip()]
                if text
                else []
            )
    return wb


def save_warband(wb: dict) -> None:
    if wb.get("apprentice"):
        sync_apprentice(wb)
    wb["updated"] = _now()
    path = warband_path(wb["id"])
    path.write_text(json.dumps(wb, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def delete_warband(warband_id: str) -> bool:
    path = warband_path(warband_id)
    ok = False
    if path.is_file():
        path.unlink()
        ok = True
    pdir = portrait_dir(warband_id)
    if pdir.is_dir():
        for f in pdir.iterdir():
            try:
                f.unlink()
            except OSError:
                pass
        try:
            pdir.rmdir()
        except OSError:
            pass
    return ok


def _copy_portrait_file(rel: str | None, old_id: str, new_id: str) -> str | None:
    """Copy a portrait file into the new warband folder; return new relative path."""
    if not rel:
        return None
    src = portrait_filesystem_path(rel)
    if not src:
        # try as old_id/filename
        name = Path(rel).name
        src = PORTRAIT_DIR / old_id / name
        if not src.is_file():
            return None
    dest_dir = portrait_dir(new_id)
    dest = dest_dir / src.name
    try:
        shutil.copy2(src, dest)
    except OSError:
        return None
    return f"{new_id}/{dest.name}"


def duplicate_warband(source_id: str, new_name: str | None = None) -> tuple[dict | None, str]:
    """Deep-copy a warband (data + portraits) under a new id and name."""
    src = load_warband(source_id)
    if not src:
        return None, "Warband not found."

    wb = deepcopy(src)
    old_id = src.get("id") or source_id
    base_name = (new_name or "").strip() or f"{src.get('name', 'Warband')} (copy)"
    new_id = new_warband_id(base_name)

    wb["id"] = new_id
    wb["name"] = base_name
    wb["created"] = _now()
    wb["updated"] = _now()

    # Portraits: wizard
    wiz = wb.setdefault("wizard", {})
    wiz["portrait"] = _copy_portrait_file(wiz.get("portrait"), old_id, new_id)

    # Apprentice
    if wb.get("apprentice"):
        ap = wb["apprentice"]
        ap["portrait"] = _copy_portrait_file(ap.get("portrait"), old_id, new_id)

    # Soldiers: new ids + portraits
    for s in wb.get("soldiers") or []:
        old_sid = s.get("id")
        s["id"] = uuid.uuid4().hex[:10]
        old_por = s.get("portrait")
        # portrait may be named soldier_<old_sid>.ext
        new_por = _copy_portrait_file(old_por, old_id, new_id)
        if new_por and old_sid:
            # rename file to match new soldier id if possible
            src_path = portrait_filesystem_path(new_por)
            if src_path and src_path.is_file():
                ext = src_path.suffix
                dest = portrait_dir(new_id) / f"soldier_{s['id']}{ext}"
                try:
                    if dest != src_path:
                        shutil.move(str(src_path), str(dest))
                        new_por = f"{new_id}/{dest.name}"
                except OSError:
                    pass
        s["portrait"] = new_por

    # Vault item ids unique
    for it in wb.get("vault_items") or []:
        it["id"] = uuid.uuid4().hex[:8]

    hist = wb.setdefault("history", [])
    hist.append(
        {
            "when": _now(),
            "text": f"Duplicated from “{src.get('name', old_id)}” as “{base_name}”.",
        }
    )

    save_warband(wb)
    return wb, f"Duplicated as “{base_name}”."


def export_warband_json(wb: dict) -> str:
    return json.dumps(wb, indent=2, ensure_ascii=False)


def import_warband_json(raw: str) -> dict:
    data = json.loads(raw)
    if not isinstance(data, dict) or "wizard" not in data:
        raise ValueError("Invalid warband file")
    old_id = data.get("id") or new_warband_id(data.get("name", "imported"))
    if warband_path(old_id).is_file():
        data["id"] = new_warband_id(data.get("name", "imported"))
    else:
        data["id"] = old_id
    data.setdefault("soldiers", [])
    data.setdefault("history", [])
    data.setdefault("gold", STARTING_GOLD)
    data.setdefault("notes", "")
    data.setdefault("vault_items", [])
    data.setdefault("apprentice", None)
    data.setdefault("created", _now())
    return data


def save_portrait(warband_id: str, role: str, file_storage) -> str | None:
    """Save uploaded image. role = wizard | apprentice | soldier_<id>. Returns relative path."""
    if not file_storage or not file_storage.filename:
        return None
    ext = Path(file_storage.filename).suffix.lower()
    if ext not in ALLOWED_IMAGE_EXT:
        raise ValueError("Image must be jpg, png, gif, or webp.")
    safe_role = re.sub(r"[^a-zA-Z0-9._-]", "", role)
    dest = portrait_dir(warband_id) / f"{safe_role}{ext}"
    # Remove old portraits for same role
    for old in portrait_dir(warband_id).glob(f"{safe_role}.*"):
        if old != dest:
            try:
                old.unlink()
            except OSError:
                pass
    file_storage.save(dest)
    return f"{warband_id}/{dest.name}"


def portrait_filesystem_path(rel: str | None) -> Path | None:
    if not rel:
        return None
    parts = Path(rel)
    # prevent traversal
    if ".." in parts.parts:
        return None
    path = PORTRAIT_DIR / parts
    return path if path.is_file() else None


def count_specialists(wb: dict) -> int:
    n = 0
    for s in wb.get("soldiers") or []:
        if s.get("status") == "dead":
            continue
        info = SOLDIERS.get(s.get("type_key", ""), {})
        if info.get("category") == "specialist":
            n += 1
    return n


def active_soldiers(wb: dict) -> list[dict]:
    return [s for s in (wb.get("soldiers") or []) if s.get("status") != "dead"]


def warband_limits(wb: dict) -> dict:
    soldiers = active_soldiers(wb)
    specs = count_specialists(wb)
    spent = 0
    # Approximate gold spent on current roster from costs (not perfect for refunds)
    if wb.get("apprentice"):
        spent += APPRENTICE_COST
    for s in soldiers:
        info = SOLDIERS.get(s.get("type_key", ""), {})
        spent += int(info.get("cost", 0))
    wiz = wb.get("wizard") or {}
    xp = int(wiz.get("xp", 0))
    level = int(wiz.get("level", 0))
    return {
        "soldiers": len(soldiers),
        "max_soldiers": MAX_SOLDIERS,
        "specialists": specs,
        "max_specialists": MAX_SPECIALISTS,
        "soldiers_ok": len(soldiers) <= MAX_SOLDIERS,
        "specialists_ok": specs <= MAX_SPECIALISTS,
        "has_apprentice": wb.get("apprentice") is not None,
        "apprentice_cost": APPRENTICE_COST,
        "starting_gold": STARTING_GOLD,
        "gold": int(wb.get("gold", 0)),
        "roster_cost_estimate": spent,
        "xp": xp,
        "level": level,
        "xp_to_next": xp_to_next_level(xp, level),
        "pending_levels": max(0, level_from_xp(xp) - level),
    }


def enrich_soldier(s: dict) -> dict:
    cat = get_soldier(s.get("type_key", "")) or {}
    out = {**cat, **s}
    out["type_name"] = cat.get("name", s.get("type_key", "?"))
    out["category"] = cat.get("category", "standard")
    out["cost"] = cat.get("cost", s.get("cost", 0))
    return out


def _next_type_name(wb: dict, type_key: str, type_name: str) -> str:
    """Default name for a newly hired soldier: 'Archer 1', 'Archer 2', ..."""
    existing = [s for s in wb.get("soldiers") or [] if s.get("type_key") == type_key]
    return f"{type_name} {len(existing) + 1}"


def add_soldier(wb: dict, type_key: str, name: str = "") -> tuple[bool, str]:
    info = get_soldier(type_key)
    if not info:
        return False, "Unknown soldier type."
    active = active_soldiers(wb)
    if len(active) >= MAX_SOLDIERS:
        return False, f"Soldier limit reached ({MAX_SOLDIERS})."
    if info["category"] == "specialist" and count_specialists(wb) >= MAX_SPECIALISTS:
        return False, f"Specialist limit reached ({MAX_SPECIALISTS})."
    cost = info["cost"]
    if wb.get("gold", 0) < cost:
        return False, f"Not enough gold (need {cost} gc, have {wb.get('gold', 0)} gc)."

    soldier = {
        "id": uuid.uuid4().hex[:10],
        "type_key": type_key,
        "name": (name or _next_type_name(wb, type_key, info["name"])).strip(),
        "status": "active",
        "items": [],
        "notes": "",
        "portrait": None,
    }
    wb["gold"] = int(wb.get("gold", 0)) - cost
    wb.setdefault("soldiers", []).append(soldier)
    wb.setdefault("history", []).append(
        {"when": _now(), "text": f"Hired {soldier['name']} ({info['name']}) for {cost} gc."}
    )
    return True, f"Hired {soldier['name']} ({info['name']}) for {cost} gc. Treasury: {wb['gold']} gc."


def remove_soldier(wb: dict, soldier_id: str, refund: bool = False) -> tuple[bool, str]:
    soldiers = wb.get("soldiers") or []
    for i, s in enumerate(soldiers):
        if s.get("id") == soldier_id:
            info = get_soldier(s.get("type_key", "")) or {}
            cost = int(info.get("cost", 0))
            name = s.get("name", "Soldier")
            if refund and cost:
                wb["gold"] = int(wb.get("gold", 0)) + cost
                text = f"Dismissed {name} and refunded {cost} gc."
            else:
                text = f"Removed {name} from the roster."
            soldiers.pop(i)
            wb["soldiers"] = soldiers
            wb.setdefault("history", []).append({"when": _now(), "text": text})
            return True, text
    return False, "Soldier not found."


def set_soldier_status(wb: dict, soldier_id: str, status: str) -> tuple[bool, str]:
    if status not in ("active", "injured", "dead"):
        return False, "Invalid status."
    for s in wb.get("soldiers") or []:
        if s.get("id") == soldier_id:
            s["status"] = status
            text = f"{s.get('name', 'Soldier')} marked {status}."
            wb.setdefault("history", []).append({"when": _now(), "text": text})
            return True, text
    return False, "Soldier not found."


def hire_apprentice(wb: dict, name: str = "") -> tuple[bool, str]:
    if wb.get("apprentice"):
        return False, "Warband already has an apprentice."
    if int(wb.get("gold", 0)) < APPRENTICE_COST:
        return False, f"Need {APPRENTICE_COST} gc for an apprentice."
    wb["gold"] = int(wb["gold"]) - APPRENTICE_COST
    wizard_name = (wb.get("wizard") or {}).get("name", "Wizard")
    wb["apprentice"] = empty_apprentice(name or f"{wizard_name}'s Apprentice")
    sync_apprentice(wb)
    text = f"Hired apprentice for {APPRENTICE_COST} gc."
    wb.setdefault("history", []).append({"when": _now(), "text": text})
    return True, text


def dismiss_apprentice(wb: dict, refund: bool = False) -> tuple[bool, str]:
    if not wb.get("apprentice"):
        return False, "No apprentice to dismiss."
    if refund:
        wb["gold"] = int(wb.get("gold", 0)) + APPRENTICE_COST
        text = f"Dismissed apprentice and refunded {APPRENTICE_COST} gc."
    else:
        text = "Dismissed apprentice (no refund)."
    wb["apprentice"] = None
    wb.setdefault("history", []).append({"when": _now(), "text": text})
    return True, text


def adjust_gold(wb: dict, delta: int, reason: str = "") -> None:
    wb["gold"] = int(wb.get("gold", 0)) + int(delta)
    sign = "+" if delta >= 0 else ""
    text = f"Gold {sign}{delta} gc (now {wb['gold']})"
    if reason:
        text += f" — {reason}"
    wb.setdefault("history", []).append({"when": _now(), "text": text})


def add_history(wb: dict, text: str) -> None:
    wb.setdefault("history", []).append({"when": _now(), "text": text.strip()})


def add_vault_item(wb: dict, name: str, notes: str = "", source: str = "loot") -> None:
    name = name.strip()
    if not name:
        return
    wb.setdefault("vault_items", []).append(
        {"id": uuid.uuid4().hex[:8], "name": name, "notes": notes.strip(), "source": source}
    )


def remove_vault_item(wb: dict, item_id: str) -> bool:
    items = wb.get("vault_items") or []
    for i, it in enumerate(items):
        if it.get("id") == item_id:
            items.pop(i)
            wb["vault_items"] = items
            return True
    return False


def record_game_loot(
    wb: dict,
    gold: int,
    items: list[str],
    xp: int = 0,
    notes: str = "",
) -> str:
    parts = []
    if gold:
        adjust_gold(wb, gold, "after-game loot")
        parts.append(f"{gold:+d} gc")
    for item_name in items:
        item_name = item_name.strip()
        if item_name:
            add_vault_item(wb, item_name, notes="Found in game", source="game")
            parts.append(item_name)
    if xp:
        wiz = wb.setdefault("wizard", {})
        wiz["xp"] = int(wiz.get("xp", 0)) + int(xp)
        parts.append(f"+{xp} XP")
        # Do not auto-raise level — player spends level-ups consciously
    if notes.strip():
        add_history(wb, f"Game notes: {notes.strip()}")
    summary = "After-game: " + (", ".join(parts) if parts else "no loot")
    if not notes.strip():
        add_history(wb, summary)
    return summary


def apply_level_up(
    wb: dict,
    choice: str,
    spell_key: str | None = None,
    improve_spell_id: str | None = None,
) -> tuple[bool, str]:
    """Spend one pending level-up on the wizard; apprentice auto-syncs."""
    wiz = wb.setdefault("wizard", {})
    xp = int(wiz.get("xp", 0))
    level = int(wiz.get("level", 0))
    earned = level_from_xp(xp)
    if level >= earned:
        return False, f"No pending level-ups (level {level}, XP {xp}). Earn more XP first."

    stats = wiz.setdefault("stats", deepcopy(WIZARD_BASE))
    detail = ""
    meta: dict = {"choice": choice}

    if choice in ("fight", "shoot", "will", "health"):
        stats[choice] = int(stats.get(choice, 0)) + 1
        detail = f"+1 {choice.capitalize()}"
        meta["stat"] = choice
    elif choice == "learn_spell":
        if not spell_key:
            return False, "Pick a spell to learn."
        sp = find_spell(spell_key)
        if not sp:
            return False, "Unknown spell."
        known_ids = {s.get("id") for s in wiz.get("spells") or []}
        if sp["id"] in known_ids:
            return False, "Spell already known."
        wschool = wiz.get("school") or "Elementalist"
        pen = cn_penalty(wschool, sp["school"])
        eff = int(sp["cn"]) + pen
        wiz.setdefault("spells", []).append(
            {
                "id": sp["id"],
                "name": sp["name"],
                "school": sp["school"],
                "base_cn": int(sp["cn"]),
                "cn_penalty": pen,
                "cn_improve": 0,
                "cn": eff,
                "type": sp["type"],
                "relation": school_relation(wschool, sp["school"]),
            }
        )
        detail = f"Learned {sp['name']} (effective CN {eff})"
        meta["spell_id"] = sp["id"]
        meta["spell_name"] = sp["name"]
    elif choice == "improve_spell":
        if not improve_spell_id:
            return False, "Pick a spell to improve."
        found = False
        for s in wiz.get("spells") or []:
            if s.get("id") == improve_spell_id:
                s["cn_improve"] = int(s.get("cn_improve", 0)) + 1
                base = int(s.get("base_cn", s.get("cn", 10)))
                pen = int(s.get("cn_penalty", 0))
                s["cn"] = max(5, base + pen - int(s["cn_improve"]))
                detail = f"Improved {s['name']} to CN {s['cn']}"
                meta["spell_id"] = s["id"]
                meta["spell_name"] = s["name"]
                found = True
                break
        if not found:
            return False, "Spell not found on wizard."
    else:
        return False, "Invalid level-up choice."

    wiz["level"] = level + 1
    wiz.setdefault("level_history", []).append(
        {
            "level": wiz["level"],
            "choice": choice,
            "detail": detail,
            "when": _now(),
            **meta,
        }
    )
    recompute_spell_cns(wb)
    sync_apprentice(wb)
    ap_note = ""
    if wb.get("apprentice"):
        ap = wb["apprentice"]
        ap_note = f" Apprentice auto-updated to level {ap.get('level', 0)}."
    msg = f"Wizard reached level {wiz['level']}: {detail}.{ap_note}"
    add_history(wb, msg)
    return True, msg


def reverse_last_level_up(wb: dict) -> tuple[bool, str]:
    """Undo the most recent level-up (LIFO). XP is unchanged; level and benefits reverse."""
    wiz = wb.setdefault("wizard", {})
    history = wiz.setdefault("level_history", [])
    if not history:
        return False, "No level-ups to reverse."
    if int(wiz.get("level", 0)) <= 0:
        return False, "Wizard is already level 0."

    entry = history[-1]
    choice = entry.get("choice") or ""
    detail = entry.get("detail") or choice
    stats = wiz.setdefault("stats", deepcopy(WIZARD_BASE))

    if choice in ("fight", "shoot", "will", "health") or entry.get("stat") in (
        "fight",
        "shoot",
        "will",
        "health",
    ):
        stat = entry.get("stat") or choice
        if stat not in ("fight", "shoot", "will", "health"):
            return False, f"Cannot reverse unknown stat choice: {choice}"
        base_val = int(WIZARD_BASE.get(stat, 0))
        new_val = int(stats.get(stat, base_val)) - 1
        if new_val < base_val:
            return False, f"Cannot reverse: {stat} is already at starting value ({base_val})."
        stats[stat] = new_val
    elif choice == "learn_spell":
        spell_id = entry.get("spell_id")
        spell_name = entry.get("spell_name")
        spells = wiz.get("spells") or []
        removed = False
        if spell_id:
            for i, s in enumerate(spells):
                if s.get("id") == spell_id:
                    # only remove if no improvements were made after learning via later undos... 
                    # If improved later, those should have been undone first (LIFO).
                    spells.pop(i)
                    removed = True
                    break
        if not removed and spell_name:
            for i, s in enumerate(spells):
                if s.get("name") == spell_name and int(s.get("cn_improve", 0)) == 0:
                    spells.pop(i)
                    removed = True
                    break
        if not removed:
            # parse "Learned Name (...)"
            import re

            m = re.match(r"Learned\s+(.+?)\s*\(", detail)
            if m:
                name = m.group(1).strip()
                for i, s in enumerate(spells):
                    if s.get("name") == name:
                        spells.pop(i)
                        removed = True
                        break
        if not removed:
            return False, f"Could not find learned spell to remove ({detail})."
        wiz["spells"] = spells
    elif choice == "improve_spell":
        spell_id = entry.get("spell_id")
        spells = wiz.get("spells") or []
        target = None
        if spell_id:
            for s in spells:
                if s.get("id") == spell_id:
                    target = s
                    break
        if target is None:
            import re

            m = re.match(r"Improved\s+(.+?)\s+to", detail)
            if m:
                name = m.group(1).strip()
                for s in spells:
                    if s.get("name") == name:
                        target = s
                        break
        if target is None:
            return False, f"Could not find improved spell to reverse ({detail})."
        imp = int(target.get("cn_improve", 0))
        if imp <= 0:
            return False, f"{target.get('name')} has no improvements left to reverse."
        target["cn_improve"] = imp - 1
        base = int(target.get("base_cn", target.get("cn", 10)))
        pen = int(target.get("cn_penalty", 0))
        target["cn"] = max(5, base + pen - int(target["cn_improve"]))
    else:
        return False, f"Cannot reverse level-up type “{choice}” (missing undo data)."

    history.pop()
    wiz["level"] = max(0, int(wiz.get("level", 1)) - 1)
    recompute_spell_cns(wb)
    sync_apprentice(wb)
    msg = f"Reversed level-up: {detail}. Wizard is now level {wiz['level']}."
    if wb.get("apprentice"):
        msg += f" Apprentice re-synced to level {wb['apprentice'].get('level', 0)}."
    add_history(wb, msg)
    return True, msg


def known_spell_ids(wb: dict) -> set[str]:
    return {s.get("id") for s in (wb.get("wizard") or {}).get("spells") or []}


def set_base_location(wb: dict, location_key: str) -> tuple[bool, str]:
    if location_key not in BASE_LOCATIONS:
        return False, "Unknown base location."
    old = (wb.get("base") or {}).get("location", "none")
    base = wb.setdefault("base", empty_base())
    if old == location_key:
        return True, "Base location unchanged."
    # Changing base loses upgrades (2e p.106)
    lost = list(base.get("resources") or [])
    base["location"] = location_key
    if location_key == "none":
        base["resources"] = []
        text = "Base cleared (no location)."
    else:
        if lost and old != "none":
            base["resources"] = []
            text = (
                f"Base moved to {BASE_LOCATIONS[location_key]['name']}. "
                f"Previous upgrades lost ({len(lost)})."
            )
        else:
            text = f"Base established: {BASE_LOCATIONS[location_key]['name']}."
    add_history(wb, text)
    return True, text


def buy_base_resource(wb: dict, resource_key: str) -> tuple[bool, str]:
    info = BASE_RESOURCES.get(resource_key)
    if not info:
        return False, "Unknown base resource."
    base = wb.setdefault("base", empty_base())
    if base.get("location", "none") == "none":
        return False, "Establish a base location first (free)."
    owned = base.setdefault("resources", [])
    if resource_key in owned:
        return False, f"Already own {info['name']} (each type once)."
    cost = int(info["cost"])
    if int(wb.get("gold", 0)) < cost:
        return False, f"Need {cost} gc for {info['name']}."
    wb["gold"] = int(wb["gold"]) - cost
    owned.append(resource_key)
    text = f"Purchased base resource {info['name']} for {cost} gc."
    add_history(wb, text)
    return True, text


def sell_or_remove_base_resource(wb: dict, resource_key: str, refund: bool = False) -> tuple[bool, str]:
    base = wb.setdefault("base", empty_base())
    owned = base.setdefault("resources", [])
    if resource_key not in owned:
        return False, "Resource not owned."
    info = BASE_RESOURCES.get(resource_key, {"name": resource_key, "cost": 0})
    owned.remove(resource_key)
    if refund:
        half = int(info.get("cost", 0)) // 2
        wb["gold"] = int(wb.get("gold", 0)) + half
        text = f"Removed {info['name']} (refunded {half} gc)."
    else:
        text = f"Removed base resource {info['name']}."
    add_history(wb, text)
    return True, text


def base_summary(wb: dict) -> dict:
    base = wb.get("base") or empty_base()
    loc_key = base.get("location", "none")
    loc = BASE_LOCATIONS.get(loc_key, BASE_LOCATIONS["none"])
    resources = []
    for key in base.get("resources") or []:
        info = BASE_RESOURCES.get(key)
        if info:
            resources.append({"key": key, **info})
    return {
        "location_key": loc_key,
        "location_name": loc["name"],
        "location_effects": loc["effects"],
        "resources": resources,
        "notes": base.get("notes", ""),
    }


def recruit_preview(wb: dict, type_key: str) -> dict:
    """Info for hire UI: cost, whether affordable, limit warnings."""
    info = get_soldier(type_key) or {}
    cost = int(info.get("cost", 0))
    active = len(active_soldiers(wb))
    specs = count_specialists(wb)
    is_spec = info.get("category") == "specialist"
    gold = int(wb.get("gold", 0))
    return {
        "cost": cost,
        "affordable": gold >= cost,
        "gold_after": gold - cost,
        "soldiers_after": active + 1,
        "specialists_after": specs + (1 if is_spec else 0),
        "hits_soldier_limit": active >= MAX_SOLDIERS,
        "hits_specialist_limit": is_spec and specs >= MAX_SPECIALISTS,
        "category": info.get("category", "standard"),
        "name": info.get("name", type_key),
    }
