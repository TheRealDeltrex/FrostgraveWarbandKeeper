# Rules Coverage Audit — Frostgrave Warband Keeper

Date: 2026-09-08 · audited against Core Rules + all 13 `SOURCE_BOOKS` supplements + all 7
Spellcaster Magazine issues. Six parallel passes, each extracting the source PDFs directly
(never the unreliable HTML reference) and cross-checking `frostgrave_data.py`,
`expansions.py`, `warband_store.py`, `data/*.json` and `templates/`.

**Headline: coverage is very thorough.** Every new soldier, spell (CN/school correct), magic
item, bestiary entry and base resource across all books was found present and correctly
source-gated, with the exceptions below. Only gaps are listed — nothing fully implemented is
repeated here. Scenario/terrain-only content with no warband-bookkeeping state is out of
scope and skipped throughout.

---

## Real bugs (behave wrong, not just "not modeled")

1. **Beastcrafter surcharge wrongly hits war hounds.** `expansions.soldier_surcharge()`
   (`expansions.py:470-473`) adds the tier surcharge to every soldier type; *Into the
   Breeding Pits* explicitly exempts war hounds at all three tiers (pp.30-31). One-line
   fix — `war_hound` key already exists (`KENNEL_ELIGIBLE_TYPE_KEYS`).
2. **Leaving a Pact via the state dropdown skips the pact-break penalty.**
   `set_wizard_state()` (`warband_store.py:6035-6074`) overwrites `wiz["state"]` directly;
   only the dedicated `break_wizard_pact()` applies the level/Health penalty. *Forgotten
   Pacts* p.11 requires the penalty whenever a pact ends, including forced breaks from
   becoming a Lich/Beastcrafter.

## Missing mechanics (cataloged/described but not wired)

- **Homunculus spell** (Thaw of the Lich Lord, p.39) — spell exists in the catalog but none
  of its split-Health / soul-transfer bookkeeping is implemented, unlike Lichdom/Revenant
  which got full treatment.
- **"New Wizards" apprentice promotion on wizard death** (Core Rules p.103) — no
  promote-apprentice-to-wizard function exists anywhere.
- **Core (non-Black-Market) buying/selling rule** (Core Rules p.104) — grimoire/scroll/
  potion/item buy-sell prices have no enforcing code; only the optional Black Market
  Contacts path is costed. Vault items are free-text with gold adjusted by hand.
- **Soldier/Spellcaster Survival Tables** (Core Rules p.73-80) — exist only as Lexicon
  reference text. No action applies Badly Wounded's 150gc fee (100gc off with an
  Apothecary), Close Call's item loss, or Dead's item loss.
- **Base resource/location mechanical effects** (Core Rules p.106-107) — `BASE_LOCATIONS`/
  `BASE_RESOURCES` store descriptive text only. Not wired: Inn's extra roster slot, Temple/
  Crypt/Tower/Cauldron/Workshop/Ball/Scriptorium spell-CN bonuses in
  `recompute_spell_cns()`, and Treasury/Brewery/Library/Laboratory post-game income or XP.
- **Out of Game spells generically, plus Brew Potion / Write Scroll** (Core Rules p.81) —
  no tracking beyond Blood Legacy's bespoke Thralldom handling; produced items must be
  hand-added to the vault.
- **Rangifer Shaman as a playable spellcaster**, **Rangifer War-Leader as Captain
  replacement**, and the **Rangifer Treasure Table** (Spellcaster Issue 3) — all three
  already flagged as deferred in code comments.
- **The Perilous Dark's dungeon-generation toolkit** — Dungeons Deep Room/Encounter/
  Treasure tables and The Vaults' 10-card deck exist only as two prose blurbs in
  `expansion_rules.json`; no `random_encounters.json` entry for the book at all. Its
  scenario-specific encounter tables (Zombie Horde, Writhing Fumes, Isher's Weapon Shop,
  Hunting Ground, Doorway Clue/Fire and Ash) are missing entirely, even as reference.
- **Book of the Construct** (Fireheart, p.71-72) — names its 5-construct sub-table in the
  item text, but nothing lets a wizard actually add one of those constructs, unlike
  `construct_hound_summoned`/`construct_familiar`.
- **8 Ulterior Motives cards from Spellcaster Issue 4** — `ghost_archipelago.json` has
  Issues 3, 5, 7's sets (32 cards) but no Issue 4 set, so the GA reference is missing 8 of
  the documented 40 total cards.
- **Alchemical Workshop's potion-mixing roll** (Spellcaster Issue 7, p.13) — descriptive
  base resource only; the app's own precedent (`roll_underworld_debt_call`) would suggest
  wiring this as an action, but it isn't.

## Missing base content

- **Weapons Rack base resource** (The Frostgrave Folio, p.61, 50gc) — the only one of the
  Folio's 11 base resources absent from `frostgrave_data.py` `BASE_RESOURCES`.

## Small/edge-case gaps

- **Mind Lock Ring** (Maze of Malcor) has no "cannot be worn by undead/demon" exclusion —
  `game_content.MAGIC_ITEM_RESTRICTIONS` only supports allow-lists, not exclusions, and this
  item has no restriction entry at all.
- **Level-up spending has no per-game cap.** `apply_level_up()` lets a wizard who banked
  2+ levels in one game spend more than one stat increase or spell improvement from it,
  which the core rules cap at one each per game (only "learn a new spell" is uncapped).
- **Learning a spell via level-up doesn't check for an owned grimoire** (Core Rules p.84).
- **New Apprentice hire cost is a flat 100gc** regardless of wizard level; the book scales
  it `(level-6)×10+160gc` for a replacement apprentice on an experienced wizard.
- **"Death of the Lich Lord" campaign reward** (-5gc soldier / -10gc apprentice hire
  discount) isn't tracked — same shape as the already-implemented Carrier Pigeons discount.
- **Potion of Preservation, Construct Oil, Elixir of Life** (Core Rules) — no bookkeeping
  hooks since potions/items are free-text vault entries.
- **Bane Weapon Table and Orb Plinth Table** (Perilous Dark) — outcome paraphrased in item
  text, but the actual roll tables aren't exposed for in-app resolution.
- **Red King "Artefact" rules** have no Lexicon explanation of what the Artefact tag means
  mechanically (unlock/sell/loss rules), only per-item unlock conditions.
- **Ragged Warbands (Red King)** — only Random Recruit Tables I-III are a real mechanic;
  survival rolls, vault lockout, and no-hiring restrictions are prose-only (self-documented
  in `expansion_rules.json`).
- **Construct Battery / Key / Patch** (Fireheart) — descriptive only, no mechanical wiring.
  Possibly intentional given the app's general pattern; flagged for a judgment call.
- **Underworld Favours: Intimidation and Muscle** (Spellcaster Issue 3) — only Loan has a
  concrete effect; the other two just add a Marker via the generic favor claim. Possibly
  intentional for the same reason as above.

## Checked and confirmed correct (called out because they looked risky)

- Underworld Debts table and its cascading "pay what you owe" logic (Spellcaster Issue 3) —
  verified against source text, matches exactly.
- Malcor's optional core-rule updates and Pentangle homerule — fully and correctly
  implemented per the six-step gating pattern.
- Construct Modification table (40/40), Grave Mutations table (1000/1000, spot-checked),
  Monster Hunting table (92/92), Casting Roll Criticals 2E (77/77) — all exact matches.
