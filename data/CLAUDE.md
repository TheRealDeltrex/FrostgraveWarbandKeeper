# data/ — reference JSON

Loaded through `game_content.py`. Warband saves, portraits and uploads live in the user data
dir, never here. **Read the `game-data-files` skill before editing anything here** (item restrictions
in code, spell-name collisions, sourcing from the rulebook PDFs, folder in `CLAUDE.local.md`).
The books are fully extracted and the extractor scripts are gone: the JSON is the source of
truth, edited by hand as textual insertions (parts are hand-compacted onto single lines, so a
`json.dumps()` round-trip reformats hundreds of lines).

- **`common_items.json`** — Core Rules price list (potions, magic weapons/armour, magic items,
  grimoires and scrolls at p.104 prices); feeds the Shop and the loot picker's "Common items".
- **`supplement_item_prices.json`** — the same for supplements, **keyed by `(source, name)`**
  (`sale_estimated` marks a sale price the book doesn't print: 40% of purchase, p.199).
  The key travels as `"Source::Name"` in form fields and a vault entry's `catalog_key`
  (`warband_store.supplement_catalog_key()`); `shop_prices()` takes that or a bare Core name.
- **Core Rules reprice what they reprint** (Construct Oil, Construct Hammer, Ring of
  Transference). Supplement rows priced in `common_items.json` are left out, and
  `shop_sale_price()` reads Core first. Where two *supplements* share a name, a found item
  gets no price suggestion rather than a guess.
- **`magic_items.json`, `expansion_rules.json`, `ghost_archipelago.json`** are ahead of the
  hand-compiled reference docs they were first built from.
- **`spell_codex.json`** — Advanced Spellcraft's flourishes, notes and Casting Roll Criticals
  for the 80 core spells, with Spellcaster Issue 7's criticals beside them. Entries the same in
  both books carry both in `sources`; changed ones are two entries.
  **`spellcraft_rules.json`** holds the book's optional rules. The ebook stamps a purchaser line
  on every page; keep it out of any text taken from it.
- **Advanced Spellcraft additions** to `magic_items.json`, `loot_tables.json`, `bestiary.json`,
  `traits.json`, `expansion_rules.json` and `random_encounters.json`: an entry printed unchanged in
  two books carries a `sources` list (read via `frostgrave_data.entry_sources()`); a changed
  reprint is a second entry under the new book.
- **`expansion_overviews.json`** — app-written, three-sentence overview per supplement for the
  Lexicon's Expansion Rules card. Not game text; hand-edited.
- **House pronoun style overrides the book's.** People (wizard, apprentice, spellcaster,
  caster, captain, soldier, player) and vampires are he/him, she/her when clearly female;
  figures, targets, creatures, demons and things stay "it"; a singular "they" takes the same
  rule. Apply it to new text taken from the books too.
