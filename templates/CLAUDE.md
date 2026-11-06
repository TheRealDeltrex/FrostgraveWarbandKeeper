# UI: templates, style.css, tab script

**Forms never nest — use `form=""`.** The homerules panel, wizard/apprentice card, captain
card and every soldier row each wrap a large `data-autosave` form with its own hidden
`action`. A control there needing its own action points at a standalone hidden
`<form id="...">` declared *before* the card, via `form="..."` on the hidden input, the
button and every field it submits. Browsers silently mis-submit nested forms. Verify by
rendering, never by reading the template: `tests/test_form_nesting.py` does this (docstring
has the mechanism); extend its parametrised list when a card gains a new state.

**`{% set %}` inside `{% if %}` leaks in this Jinja version** into every later sibling block.
Wrap any per-figure narrowing of a shared variable (`vault_names`, `standard_items` in
`warband_view.html`'s item-slot blocks) in `{% with %}...{% endwith %}`, or it compounds
wizard → apprentice → captain → every soldier row.

**Two layouts, one template.** Tab layout (default) and classic render the same cards;
`<html data-layout>`, set from `localStorage` `fgLayout` in `base.html`'s `<head>`, picks the
CSS. Tab-only CSS is scoped to `html[data-layout="tabs"]`, and to `.container:has(.wb-layout)`
where a selector could hit another page's `.hero`. The rail (`.tv-rail`) is server-rendered;
`_tab_view.html` (shared by warband page and creation) only switches classes and exposes
`window.fgTabView`.
- **A new card needs a rail button** (`data-tab="<card id>"`) or it's unreachable in tab view;
  `tests/test_tab_layout.py` catches it.
- Wizard-card sub-tabs come from `data-subtab-label`; a new sub-section only needs that.
- Creation's spell list is one tab per school (`fgInitSchoolTabs()`), rebuilt after each
  `fgNewReload()` swap via `fgAfterSwap()`. Browser tests filling the creation form pin classic.
- Saves redirect to the bare URL, so tab/sub-tab/scroll state lives in `sessionStorage`;
  `base.html`'s details-state key includes the layout.
- Check UI changes in both layouts.

**Roster table info cells.** `#roster-table`'s "Show actions" toggle hides the Actions
column by default; wrap read-only info there in `<details class="actions-cell-persistent">`.

**UI copy.** State the fact and stop — no trailing self-justifying clause about what the app
doesn't automate ("— tracked at the table"). Prefer a short positive instruction to an
apology. Check new copy and trim copy you touch, even off-task. Not a ban on explanation:
where two controls differ in a way the player would miss, one line earns its space.

**Headings are title case** — every `<h*>`, card title and section `<summary>` (minor words
lower-case unless first or after a dash/colon). Data-driven headings use the `heading_case`
filter (`app.py`), not edits to `data/`.

**Font and logo are base64 inside `static/style.css`**, since `bundle.json` is text-only.
Regenerate with `scripts/build_display_font.py` / `build_logo_asset.py` (stdout only); read
their docstrings first.
