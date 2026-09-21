# Rules Coverage Audit — Frostgrave Warband Keeper

Audited 2026-09-08 against Core Rules + all 13 `SOURCE_BOOKS` supplements + all 7 Spellcaster
Magazine issues. Closed 2026-09-21: every accepted finding has shipped.

What remains here is the record of what was **ruled out**, so it is not re-audited and not
re-opened. Deferred work lives in `todo.md`.

## Ruled out — not to be "fixed"

- **Leaving a Pact via the state dropdown skips the pact-break penalty.** Deliberate escape
  hatch: a player who tried a Pact to see what it did needs a free way out that doesn't cost
  them their warband. `break_wizard_pact()` is the genuine mechanic.
- **Weapons Rack (Folio p.61, 50gc) is correctly absent.** It grants "non-magic weapons may be
  bought or replaced for free" — a 1st-edition rule, a no-op in 2e where ordinary gear is
  already free (see `buy_standard_item()`).
- **Base casting bonuses are not applied to Casting Numbers.** They are bonuses to the *roll*;
  CNs stay as printed. `BASE_CASTING_BONUSES` (`expansions.py`) is therefore consulted only
  where the app itself rolls — Write Scroll, Brew Potion, Alchemical Workshop — and the figure
  is shown beside the result.
- **Soldier/Spellcaster Survival Tables (Core Rules p.73-80).** Not the app's job. The
  After-the-game card's "Gold lost" field covers the 150gc fee and anything else.
- **Out of Game spells generically** — table play. Brew Potion and Write Scroll shipped as the
  exceptions, because the app rolls them.
- **The Perilous Dark's dungeon-generation toolkit** — scenario generation, not warband state.
- **Level-up spending has no per-game cap** — the app tracks no games, so there is no "per
  game" to enforce.

## False findings — verified against source and code, do not rebuild

The 2026-09-08 pass produced these by grepping for a feature's name rather than its mechanism.

- "No promote-apprentice-to-wizard function exists anywhere" — `apprentice_takes_over()` is
  complete and wired; the grep only hit the Folio's soldier→captain `promote_*` code.
- "Nothing lets a wizard add a Book of the Construct construct" — all nine types exist in
  `SOLDIERS`, gated through `expansions.VAULT_ITEM_SOLDIERS`.
- The proposed Beastcrafter-surcharge fix (exempting `KENNEL_ELIGIBLE_TYPE_KEYS`) was wrong:
  that set is a roster-slot concept, not a war-hound equivalence. Shipped instead as
  `war_hound` always exempt, `dire_hound` behind the `dire_hound_counts_as_hound` homerule.
- The proposed base-resource fix was wrong — folding the bonuses into `recompute_spell_cns()`
  would print a wrong CN on the wizard sheet and in the PDF. See above.

## Confirmed correct — recorded because they looked risky

Underworld Debts and its cascading "pay what you owe" logic (Spellcaster Issue 3); Malcor's
optional core-rule updates and the Pentangle homerule; Construct Modification (40/40), Grave
Mutations (1000/1000, spot-checked), Monster Hunting (92/92) and Casting Roll Criticals 2E
(77/77), all exact matches against source.
