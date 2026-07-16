"""One-off extractor: spell descriptions from local 2e PDFs into JSON."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from frostgrave_data import SCHOOLS, SPELLS  # noqa: E402
from pypdf import PdfReader  # noqa: E402

CORE = Path(r"E:\RPG\Tabletop\Frostgrave\Frostgrave - 2e - Core Rules.pdf")
CARDS = Path(r"E:\RPG\Tabletop\Frostgrave\FG2E - Spellcards_2nd-1.pdf")
OUT = ROOT / "data" / "spell_descriptions.json"


def load_text(path: Path, start: int | None = None, end: int | None = None) -> str:
    r = PdfReader(str(path))
    pages = r.pages
    if start is not None:
        pages = pages[start:end]
    return "\n".join((p.extract_text() or "") for p in pages)


def clean_body(s: str) -> str:
    s = re.sub(r"\s+", " ", s).strip()
    return s


def name_variants(name: str) -> list[str]:
    vs = [name, name.upper(), name.replace("'", ""), name.upper().replace("'", "")]
    # OCR sometimes inserts spaces inside words: BONE DAR T
    broken = " ".join(" ".join(list(w)) for w in name.upper().split())
    vs.append(broken)
    return vs


def extract_for(name: str, sources: list[str]) -> str:
    school_pat = "|".join(re.escape(s) for s in SCHOOLS)
    for src in sources:
        for nv in name_variants(name):
            pat = re.escape(nv).replace(r"\ ", r"\s+")
            m = re.search(pat, src, re.I)
            if not m:
                continue
            rest = src[m.end() : m.end() + 1000]
            m2 = re.match(
                rf"\s*({school_pat})\s*/\s*(\d+)\s*/\s*([^\n]+)\s*(.+)",
                rest,
                re.S,
            )
            if not m2:
                continue
            body = clean_body(m2.group(4))
            # stop before next spell header-ish
            body = re.split(
                rf"(?=[A-Z][A-Z][A-Z]+(?:\s+[A-Z][A-Z]+)*\s+(?:{school_pat})\s*/)",
                body,
            )[0]
            body = clean_body(body)
            if len(body) > 40:
                return body[:750]
    return ""


def main() -> None:
    core = load_text(CORE, 111, 138)
    cards = load_text(CARDS)
    sources = [core, cards]
    names = [sp["name"] for _, sps in SPELLS.items() for sp in sps]
    descs = {name: extract_for(name, sources) for name in names}
    good = sum(1 for v in descs.values() if len(v) > 40)
    print(f"good={good} empty={len(descs) - good}")
    for n, v in descs.items():
        if len(v) <= 40:
            print("BAD", n)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(descs, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print("wrote", OUT)


if __name__ == "__main__":
    main()
