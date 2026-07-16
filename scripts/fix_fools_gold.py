import json
from pathlib import Path

p = Path(__file__).resolve().parents[1] / "data" / "spell_descriptions.json"
d = json.loads(p.read_text(encoding="utf-8"))
d["Fool's Gold"] = (
    "This spell may only be cast on a figure carrying a treasure token. "
    "That figure must make an immediate Will Roll with a Target Number equal to the Casting Roll. "
    "If it fails, the spellcaster may take the treasure token from the figure and move it up to 4\" "
    "in any direction, provided the final spot is within line of sight of the spellcaster."
)
for k, v in list(d.items()):
    d[k] = " ".join(str(v).split())[:800]
p.write_text(json.dumps(d, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
print("ok", len(d["Fool's Gold"]))
