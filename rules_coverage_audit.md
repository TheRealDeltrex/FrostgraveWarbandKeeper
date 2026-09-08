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

## Verification corrections (2026-09-08, re-checked against source and code)

Several findings below did not survive re-verification. **Verify each remaining claim against
the code before building it** — the audit produced two false negatives by grepping for a
feature's name rather than its mechanism.

- **"No promote-apprentice-to-wizard function exists anywhere" is false.**
  `apprentice_takes_over()` (`warband_store.py:3734`) is complete — level−6 maths, the
  level-5-or-below refusal, gear loss, state clearing — wired as
  `@register_action("apprentice_takes_over")` (`app.py:1728`) with a button in the template.
  The grep hit only the Folio's soldier→captain `promote_*` code. Entry removed.
- **"Nothing lets a wizard add a Book of the Construct construct" is false.** All nine types
  (`blade_dog`, `glass_man` ×2, `candle_jack` ×4, `demonic_prison`, `construct_of_burden`)
  exist in `SOLDIERS` and are gated through `expansions.VAULT_ITEM_SOLDIERS`. Entry removed.
- **Weapons Rack is correctly absent.** The Folio (p.61, 50gc) grants *"non-magic weapons may
  be bought or replaced for free"* — a 1st-edition rule that is a no-op in 2e, where ordinary
  gear is already free (see `buy_standard_item()`'s docstring). Not a gap. Entry removed.
- **"Only the optional Black Market Contacts path is costed" is false — nothing is costed.**
  `black_market_buy_item()` (`warband_store.py:3154`) marks the offer bought and calls
  `add_vault_item()` without touching gold. Being fixed with the Shop card.
- **The proposed fix for the Beastcrafter surcharge was wrong** — see below.
- **The proposed fix for base resources was wrong** — those are Casting *Roll* bonuses, not
  CN reductions; folding them into `recompute_spell_cns()` would print a wrong CN on the
  wizard sheet and in the PDF. See below.

Two gaps the audit missed:

- **11 `BASE_RESOURCES` carry unwired casting bonuses**, not just the `BASE_LOCATIONS` the
  audit flagged: Giant Cauldron, Enchanter's Workshop, Crystal Ball, Scriptorium, Arcane
  Candle, Summoning Candle, Homunculus Jar, Lectern, Sacrificial Altar, Shrine, Breeding Cages.
- **`break_wizard_pact()` doesn't consume the True Name.** *Forgotten Pacts* p.11: a wizard who
  breaks a pact "voluntarily or otherwise" immediately loses the True Name used to forge it and
  may never pact with that demon again. Today the vault item survives and can re-forge at once.

## Real bugs (behave wrong, not just "not modeled")

1. **Beastcrafter surcharge wrongly hits war hounds.** `expansions.soldier_surcharge()`
   (`expansions.py:581`, not 470) adds the tier surcharge to every soldier type; *Into the
   Breeding Pits* (pp.29-30) exempts war hounds at all three tiers.
   **The audit's suggested fix — exempting `KENNEL_ELIGIBLE_TYPE_KEYS` — is wrong.** That set
   is a *roster-slot* concept, not a war-hound equivalence: Fireheart p.29 says construct
   hounds *"count as standard soldiers"* and substitute only for the kennel slot. Two of the
   five members cost 0 and are unaffected anyway. Agreed fix: exempt `war_hound` always
   (hounds are beasts, constructs are not), and `dire_hound` behind a new
   `dire_hound_counts_as_hound` homerule (default on) governing both kennel eligibility and
   the surcharge exemption — it is both a beast and a Legendary, which a group must settle.

## Intentional — not to be "fixed"

- **Leaving a Pact via the state dropdown skips the pact-break penalty.** Reported as a bug;
  it is the escape hatch. A player who tried a Pact to see what it did needs a free way out
  that doesn't cost them their warband. `break_wizard_pact()` is the genuine mechanic; the
  dropdown is deliberate circumvention. The dropdown gains one line saying the two differ.
- **Weapons Rack absent** — a 1e no-op in 2e; see Verification corrections.
- **Base casting bonuses not applied to Casting Numbers.** CNs stay as printed; applying the
  bonus is the player's job at the table. The exception is where the app itself rolls (Write
  Scroll, Brew Potion, Alchemical Workshop): there the bonus is included *and* shown, since
  most players will roll their own dice.

## Missing mechanics (cataloged/described but not wired)

- **Homunculus spell** (Thaw of the Lich Lord, p.39) — spell exists in the catalog but none
  of its split-Health / soul-transfer bookkeeping is implemented, unlike Lichdom/Revenant
  which got full treatment. → `todo.md`
- **Core (non-Black-Market) buying/selling rule** (Core Rules p.104) — grimoire/scroll/
  potion/item buy-sell prices have no code, and neither does the Black Market (see
  Verification corrections). Scheduled as a **Shop card**, sited after Treasury and before
  Home base, carrying Core prices first and the Black Market absorbed into it — the two are
  alternatives in the book, so the card shows one or the other and the toggle moves out of
  Additional Rules to the top of the card. Both charge gold; `add_vault_item()` stays free,
  for items found or acquired otherwise. Supplement prices → `todo.md`.
- **Soldier/Spellcaster Survival Tables** (Core Rules p.73-80). **Intentional** — these do
  not belong in the app. The After-the-game card gains a "Gold lost" field beside "Gold
  gained" instead, which covers the 150gc fee and anything else, applied together on Record
  loot.
- **Base resource/location mechanical effects** (Core Rules p.106-107) — `BASE_LOCATIONS`/
  `BASE_RESOURCES` store descriptive text only. Scheduled: Inn's extra roster slot (a
  conditional slot like `kennel_bonus_available()`, since the extra body may not play),
  Brewery's +1 Will as a Home base toggle applied to soldiers, and Laboratory/Brewery flat
  post-game income plus Temple/Library/Treasury optional post-game rolls, in the After-the-game
  card. The casting bonuses are **not** wired into `recompute_spell_cns()` — see Intentional
  above. The 300 XP cap the Laboratory is exempt from needs nothing: the app enforces no caps
  and does not track when a game was played.
- **Out of Game spells generically** — **won't do**; table play. **Brew Potion and Write
  Scroll** are scheduled as a secondary way to gain the item, with the relevant base casting
  bonus included in the optional roll and shown beside it.
- **Rangifer Shaman / War-Leader / Treasure Table** (Spellcaster Issue 3) — deferred in
  code comments already; that decision stands.
- **The Perilous Dark's dungeon-generation toolkit** — **won't do**: scenario generation,
  not warband state.
- **8 Ulterior Motives cards from Spellcaster Issue 4** — `ghost_archipelago.json` has
  Issues 3, 5, 7's sets (32 cards) but no Issue 4 set, so the GA reference is missing 8 of
  the documented 40 total cards. → `todo.md`
- **Alchemical Workshop's potion-mixing roll** (Spellcaster Issue 7, p.13) — scheduled, as
  an optional roll.

## Small/edge-case gaps

- **Mind Lock Ring** (Maze of Malcor) — needs exclusion support in
  `game_content.MAGIC_ITEM_RESTRICTIONS`, which is allow-list only. → `todo.md`
- **Level-up spending has no per-game cap.** Won't fix: the app tracks no games, so there is
  no "per game" to enforce.
- **Learning a spell via level-up doesn't check for an owned grimoire** (Core Rules p.84).
  → `todo.md`, as a warn-and-confirm.
- **New Apprentice hire cost is a flat 100gc**; the book scales it `(level-6)×10+160gc`.
  Scheduled. A level-0 wizard pays 100gc either way, so warband creation is unchanged; the
  dismissal refund records and returns the price actually paid, or refunding at the current
  formula after levelling would print money.
- **"Death of the Lich Lord" campaign reward** (-5gc soldier / -10gc apprentice) —
  scheduled. It is a wizard *Reputation* (Thaw p.34, "notes on their Wizard Sheet"), not a
  base resource: it must not be stored in `base["resources"]`, which `set_base_location()`
  wipes on every move. Shown on the Home base card with a remove button, badged under the
  wizard portrait, stacks with Carrier Pigeons, and persists when the book is switched off.
- **Potion of Preservation, Construct Oil, Elixir of Life** (Core Rules) — scheduled as
  items and functions. Construct Oil's +1 Move can conflict with Fireheart's Construct
  Modification rules; an info line is enough, no cross-checks.
- **Bane Weapon Table and Orb Plinth Table** (Perilous Dark) — scheduled. All 12 Bane
  Weapon combinations (2 weapon types × 6 creature types) exist as items so they can be
  carried and printed; the Shop offers them as one entry plus a variant dropdown, like
  grimoires and the Book of the Construct. Orb Plinth is bookkeeping with an optional roll.
- **Red King "Artefact" rules** have no Lexicon explanation of the tag. → `todo.md`
- **Ragged Warbands (Red King)** — **won't do**: prose-only rules, self-documented in
  `expansion_rules.json`.
- **Construct Battery / Key / Patch** (Fireheart) — scheduled, all three as items. The
  Battery tracks its six power points (its sale price is 30gc × points remaining); the Patch
  comes as two and sells for 50gc each; the Key is an item so it prints as carried gear.
- **Underworld Favours: Intimidation and Muscle** (Spellcaster Issue 3) — scheduled with
  the rest of the Underworld rules. Marker bookkeeping is the core of both; the dice are
  optional. Muscle recruits up to two models that don't count against warband size, costing
  1-2 Markers each plus one more if they die; a failed Intimidation returns half the Markers
  spent, rounded up, minimum one kept.

## Checked and confirmed correct (called out because they looked risky)

- Underworld Debts table and its cascading "pay what you owe" logic (Spellcaster Issue 3) —
  verified against source text, matches exactly.
- Malcor's optional core-rule updates and Pentangle homerule — fully and correctly
  implemented per the six-step gating pattern (which new work no longer follows — see
  CLAUDE.md's gating rule).
- Construct Modification table (40/40), Grave Mutations table (1000/1000, spot-checked),
  Monster Hunting table (92/92), Casting Roll Criticals 2E (77/77) — all exact matches.
