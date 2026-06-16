# UI Review — Botaniks Inventory

A prioritized critique against the three lenses you named:

1. **Target** — the instrument-panel design direction in [CLAUDE.md](CLAUDE.md) (color/type/component/formatting rules).
2. **Warehouse** — fast, hands-busy, low-literacy operators + a boss who glances at stock. Legibility, contrast, large targets, unambiguous states win over cleverness.
3. **Portfolio** — reads as intentional to a technical reviewer. Bar: Linear / Vercel / Raycast.

Each item says which lens(es) it fails, why it matters and to whom, and a proposed direction. Nothing here is built — these are directions for you to approve one at a time. The recommended sequence is at the end.

A note on method: the CLAUDE.md audit already catalogs the *known* divergences (DM Mono opt-in, unused filters, color sprawl, inline styling). I've tried not to just re-list those. The P0 items below are mostly things the audit did **not** catch — actual broken CSS — plus the usability traps that hit your two real audiences hardest.

**A constraint that shapes the formatting work:** the boss needs to *enter and keep* extreme-precision values (10–15 decimal places). That rules out blind rounding. So the formatting goal is **not** "round everything" — it's "preserve every digit the user actually entered, but never show floating-point *arithmetic* noise." Those are two different problems; P1-1 below is rewritten around that distinction.

---

## P0 — Broken or actively misleading

### [DONE] P0-1. Error and info alerts render with **no styling at all** (CSS class doesn't exist)
**Fails: Warehouse, Portfolio, Target.**

**Resolution (2026-06-16):** Renamed the two `alert-danger` → `alert-error` ([receive_lot.html:16](templates/receive_lot.html#L16), [add_material.html:22](templates/add_material.html#L22)) — canonical class, matches the edit_* pages, no new CSS. For the genuinely-informational add-material hand-off banner ([add_material.html:17](templates/add_material.html#L17)), kept `alert-info` and **added a real `.alert-info` rule** (Option A) using neutral tokens (`--content-bg` / `--text-muted` / `--border`) — a fourth distinct alert state, not a synonym for error. Rationale: forcing it into green "success" would mislead a hurried operator; neutral grey reads as "context." Flash-category audit: every `flash(...)` in app.py uses only `success`/`error`/`warning`, all mapping to real classes, so base.html's `alert-{{ category }}` rendering was already safe — the bug was confined to the two hand-written templates. Files: receive_lot.html, add_material.html, [style.css](static/css/style.css#L577-L587).

[receive_lot.html:16](templates/receive_lot.html#L16) and [add_material.html:22](templates/add_material.html#L22) emit `class="alert alert-danger"`, and [add_material.html:17](templates/add_material.html#L17) emits `class="alert alert-info"`. The stylesheet only defines `.alert-success`, `.alert-error`, and `.alert-warning` ([style.css:565-581](static/css/style.css#L565-L581)). There is **no `.alert-danger` and no `.alert-info`.** So these messages get only the base `.alert` rule (padding + radius, [style.css:557](static/css/style.css#L557)) with no background or color — they appear as plain text in a borderless box.

Why it matters, and to whom: these two pages are where a warehouse user is *most* likely to hit an error — "Material not found," a bad quantity, a duplicate lot. The one moment the system needs to shout, it whispers. A hurried operator can easily miss an unstyled line and assume the submit worked. This is the single highest-impact defect in the app, and it's invisible in a screenshot review — which is exactly why it also quietly undermines portfolio polish.

Proposed direction: pick the smaller fix now, the systematic fix later.
- **Now (P0):** either change the three occurrences to the classes that exist (`alert-error` for the danger cases, and either `alert-success`-styled or a new info treatment for the receive-lot hand-off notice), **or** add `.alert-danger`/`.alert-info` rules. I lean toward *renaming the template classes to the canonical `error`/`success`* rather than adding more class names — fewer synonyms is more in keeping with the "one system" goal.
- **Later (rolls into P1-2):** the flash categories in [base.html:119](templates/base.html#L119) are `success`/`error`/`warning`, but Flask's default category is `message` and some code may flash other names — worth confirming every `flash(...)` category maps to a defined class so a flashed message never renders naked.

### [DONE] P0-2. Inventory "Lots" toggle button uses **non-existent CSS variables** → invisible styling
**Fails: Portfolio, Warehouse (minor), Target.**

**Resolution (2026-06-16):** Corrected the reversed-word token typos in inventory.html's inline `<style>` — 3 occurrences: `var(--bg-card)`→`var(--card-bg)` (`.lot-toggle` bg, line 26), and `var(--bg-content)`→`var(--content-bg)` (`.lot-toggle:hover` line 29 + `.expired-toggle:hover` line 41). Effect: the "Lots" expander button now actually shows its intended light-grey background + hover, so it reads as a button instead of bare text. Minimal token-name fix only; the larger structural move (delete this inline block, extract a shared `.detail-row`/`.detail-panel` component — duplicated in batches.html) is deferred to **P1-4** per the sequence, to keep this to one concern/one file.

In [inventory.html:26-29](templates/inventory.html#L26-L29) and [:41](templates/inventory.html#L41), the inline `<style>` references `var(--bg-card)` and `var(--bg-content)`. Those tokens **do not exist** — the real tokens are `--card-bg` and `--content-bg` ([style.css:24-25](static/css/style.css#L24-L25)). With no fallback value, the background simply doesn't apply (transparent), so the `.lot-toggle` button and its hover state are unstyled relative to intent.

Why it matters, and to whom: Raw Materials is the boss's main glance-page and a daily warehouse page. The "Lots" expander is the primary interaction on it, and it currently looks half-finished. To a technical reviewer, a typo'd CSS variable name is a tell that the system isn't actually a system. Low user harm, high credibility cost — cheap to fix.

Proposed direction: correct the four token names. Better, **delete the inline `<style>` and promote `.lot-toggle` / the inner lot-table styles into the stylesheet** as a real "expandable detail row" component (see P1-4) — the same pattern recurs in [batches.html](templates/batches.html#L7-L54) for the Materials expander, so it wants to be one shared component, not two copies with different colors.

### [DONE] P0-3. Red "out of stock" pill is reused to mean "No" / "Not organic" — alarm color for a non-alarm state
**Fails: Target, Warehouse.**

**Resolution (2026-06-16):** Added a neutral two-state toggle pair `.badge-on` / `.badge-off` to [style.css](static/css/style.css) (after the attribute-tag block) and repointed both toggles in [manage_materials.html:74,80](templates/manage_materials.html#L74). ON = filled neutral chip (`--content-bg` fill + `--text` + `--border-tag`); OFF = transparent ghost (`--text-muted` + `--border`). **Fixed both sides, not just the red:** the ON state was also misusing a status color (`badge-in-stock` green) — both now use the neutral pair, so neither status color (green in-stock / red out) leaks onto boolean attributes. Also removed the inline `border:none` so the new badge borders render. Decisions made & named: (1) OFF uses `--text-muted` (#6E7177, ~5.6:1, passes AA) instead of the review-suggested `--text-faint` (#9AA0A6, ~2.6:1, fails) — usability-over-polish call, "No" must stay legible for warehouse staff; (2) filled-vs-empty chosen as the glance signal over a subtler border-style difference. `badge-organic` left intact for the read-only Organic tags elsewhere (batches/inventory/shipments) — those were already correct; only the interactive toggle changed. Scope confirmed by grep: these two lines were the *only* misuse of `badge-out` for non-stock state; all other `badge-out`/`badge-in-stock` usages are legitimate status (Out of Stock, inactive lot, Shipped).

On [manage_materials.html:74](templates/manage_materials.html#L74) and [:80](templates/manage_materials.html#L80), the Edible/Organic toggles render the *off* state with `class="badge badge-out"` — the **red out-of-stock pill** — showing "No". So a perfectly fine non-organic material (most of them) lights up the same red the system uses for "you are out of this material."

Why it matters, and to whom: this is a direct violation of the Target rule that the out red (`--badge-out-text #A12D2D`) is the semantic *stock-out* color and status colors must mean one thing. For the warehouse user it's a false alarm: a screen full of red dots that mean nothing urgent trains people to ignore red — which is dangerous when red *also* means a real stock-out elsewhere. The boss glancing at this page would reasonably think half the inventory is in trouble.

Proposed direction: an on/off attribute toggle is not a status pill. Use a **neutral two-state control**: "on" = the neutral attribute-tag look (`--border-tag` outline, or for Organic specifically the existing `.badge-organic` neutral tag), "off" = a muted/ghost pill (faint text, no fill). Reserve the red pill exclusively for stock-out. This also reads as more deliberate in a portfolio.

---

## P1 — Clear wins

### [IN PROGRESS] P1-1. Numbers render raw — arithmetic float spew on the most-looked-at values, *without* destroying entered precision
**Fails: Target, Warehouse, Portfolio.**

**PRECISION CONTRACT — settled 2026-06-16 (decision made with the developer):**
1. **Preserve up to 15 decimal places.** Never round display below 15. The boss enters extreme-precision values; truncating them is a data-presentation failure worse than the noise it would hide.
2. **Display = strip arithmetic noise + trailing zeros**, show full significant digits: `48.980000000000004 → 48.98`, `0.123456789012 → 0.123456789012`, `5.0 → 5`.
3. **Implementation:** the existing `fmt_num` filter ([app.py:136](app.py#L136)) already strips trailing zeros; its default was widened `places=11 → 15` (the old 11 would have silently chopped the 12th–15th entered digits). **Applied 2026-06-16** — filter still unused in templates, so nothing changed on screen yet; this just makes it correct for the step-4 wiring.
4. **Known residual (named honestly):** a Python `float`/IEEE-754 double carries only ~15–17 significant decimal digits. Noise at the 16th–17th digit (e.g. `0.1+0.2 → 0.300…04`) is stripped by rounding to 15; rare noise at the ~15th place (e.g. some `48.98` subtractions) **cannot** be stripped without truncating a real 15th-place digit, so it may still show. Accepted: preserving entered precision outranks the rare artifact.
5. **Durable fix (out of scope, flagged for separate decision):** migrate quantity/cost columns to `Decimal`(Python)/`NUMERIC`(Postgres) so the noise never arises and the display layer has nothing to paper over. This is the real fix; the display filter is a mitigation.
6. **Knock-on:** Empty/missing → `dash` (`—`); dates → `fmt_date` (`YYYY-MM-DD`). The Create Batch `toFixed(2)` allocation math ([create_batch.html](templates/create_batch.html)) is revisited against this contract in **P1-5**.

**Remaining work:** wire `fmt_num`/`dash` into templates, one page at a time (step 4: Raw Materials → Low Stock first), bundled with P1-3 (`.num`/mono + right-align) and P1-2 (`fmt_date`). Not yet done — each page is its own decision-first edit.

Stock levels, quantities, and reorder levels print straight from the row: `{{ row.stock_level }}` ([inventory.html:114](templates/inventory.html#L114), [low_stock.html:37](templates/low_stock.html#L37), repeated on batches/manage pages). Costs are hand-formatted with `'%.2f'|format(...)` inline in some places ([inventory.html:118](templates/inventory.html#L118), [batches.html:124](templates/batches.html#L124)) and *not at all* in others.

The trap here, and why this is **not** a "round everything" fix: your boss legitimately enters values to 10–15 decimal places, so a blunt round-to-2 would silently corrupt real data — that's worse than the disease. But a *stock level* that reads `48.980000000000004` is not precision; it's IEEE-754 binary float error introduced by the deduction arithmetic (`50 - 1.02`). The job is to **distinguish entered precision from arithmetic artifacts** and only kill the latter.

Why it matters, and to whom: an artifact like `48.980000000000004` is the most common way this class of app embarrasses itself — the boss sees garbage and distrusts the whole system; the warehouse user can't read it at a glance; a data-engineering reviewer reads it as "no presentation layer." But over-correcting and dropping a digit the boss typed is a *data-integrity* failure, which is worse.

Proposed direction (two layers — the storage layer is the real fix):
- **Display layer (the quick win):** route numeric cells through a formatter that normalizes *representation* without lowering precision — e.g. format the value to a high but bounded number of significant places and strip trailing zeros, so `48.980000000000004` → `48.98` while `0.123456789012` is shown in full. The existing [`fmt_num`](app.py#L136) filter is the hook; **before reusing it, confirm its current rounding doesn't truncate below the boss's needed precision** — if it rounds to 2–3 dp it must be widened or replaced, not blindly applied. This is the one filter where I would *not* wire it in unchanged.
- **Storage/compute layer (the durable fix, flagged for a separate decision):** the artifacts come from doing float math on quantities. Storing/most-computing these as `Decimal` (Python) / `NUMERIC` (Postgres) eliminates the noise at the source, so the display layer has nothing to paper over and entered precision round-trips exactly. This is a backend change beyond this UI review's scope — flagging it because the cleanest fix to a "UI" symptom is actually in the data layer, which is worth saying out loud to a data-engineering audience.

Pair the display change with DM Mono + right-alignment (P1-3) so it lands as one change per table. Start with Raw Materials and Low Stock — highest visibility, simplest tables. **Decision needed from you before I touch any number:** the exact precision contract (max significant digits to preserve), since it governs both layers.

### P1-2. Three+ date formats and four empty-value conventions across pages
**Fails: Target, Portfolio, Warehouse (minor).**

Dates appear as bare DB strings (`{{ row.received_date or '' }}`), full timestamps with time component ([audit_log.html:27](templates/audit_log.html#L27)), and JS "2 h ago" strings ([index.html:286](templates/index.html#L286)). Empty values are handled four ways: `or '—'`, `or ''` (blank cell), and brittle string-compares `!= 'nan'` ([shipments.html:35-36](templates/shipments.html#L35-L36)) and `!= 'None'` elsewhere. The `dash`/`fmt_date` filters exist and are unused.

Why it matters, and to whom: inconsistency is the thing a technical reviewer notices first and a stressed warehouse user feels without naming — "why is this cell blank and that one a dash?" The `!= 'nan'` checks are also a latent correctness bug: they only catch the literal *string* "nan", not a real `None`/`NaN`, so they'll still leak blanks.

Proposed direction: adopt one date format everywhere via `fmt_date` (I'd keep the dashboard's relative "2 h ago" only in the activity feed, where recency is the point, and use absolute dates everywhere else). Route every "missing value" through `dash` so empty is *always* "—", never blank, never "nan". This is a find-and-replace-grade change but should be done **one page at a time** so each table can be eyeballed.

> Tension to name: the dashboard activity feed's relative timestamps are genuinely better UX there (a boss wants "just now," not a timestamp), even though it breaks the "one date format" rule. I'd treat relative time as an intentional exception scoped to the activity feed, and say so in a comment — not silently. Don't let the consistency rule delete a real usability win.

### P1-3. DM Mono / right-alignment is opt-in, so numeric columns don't line up
**Fails: Target, Portfolio, Warehouse.**

Per the audit, almost no numeric `<td>` carries `.num`/`.mono`, so stock levels, costs, and dates render in Inter, left-aligned. The `.data-table td.num` right-align rule ([style.css:316](static/css/style.css#L316)) exists but is barely used.

Why it matters, and to whom: right-aligned tabular figures are *the* thing that makes an inventory table scannable — you compare magnitudes by digit position. Left-aligned proportional numbers force the eye to read each value. This is the cheapest single upgrade to both warehouse scannability and portfolio polish ("they understand tables"). It also pairs naturally with the high-precision values from P1-1: mono + tabular-nums is what keeps a 12-decimal number from looking like a ransom note.

Proposed direction: add `class="num"` to numeric headers and cells on the core tables (stock, reorder, qty, cost, counts). Keep IDs/lot numbers left-aligned (they're labels, not magnitudes) but still mono. Do this in the same pass as P1-1 per table.

### P1-4. Two near-identical "expandable detail row" implementations, both as inline per-page CSS
**Fails: Target, Portfolio.**

The lot expander ([inventory.html:23-61](templates/inventory.html#L23-L61)) and the batch-materials expander ([batches.html:6-54](templates/batches.html#L6-L54)) are the same component — a nested table revealed under a row — implemented twice, with different tints (`#f9fafb` / `#f3f4f6` vs `#f0faf6` / `#e2f2ec`) and different broken/ad-hoc variables.

Why it matters, and to whom: duplicated, slightly-divergent components are the clearest "templated, not systematized" signal to a reviewer. It's also a maintenance trap — a fix to one won't reach the other.

Proposed direction: extract one `.detail-row` / `.detail-panel` + `.inner-table` component into the stylesheet, neutral surfaces from the tokens, and delete both inline blocks. This is the natural home for fixing P0-2 too. Defer until after the data-formatting passes — it's polish, not a user-facing defect.

### P1-5. Create Batch — the lot-selection UI is built entirely from inline-styled JS-generated divs
**Fails: Portfolio, Warehouse, Target.**

[create_batch.html](templates/create_batch.html) is your most important warehouse screen and your best portfolio set-piece (real-time lot allocation with running "remaining / over by" math — genuinely good). But the batch-type buttons ([:35-37](templates/create_batch.html#L35-L37)) and every dynamically built lot card/row/select carry hand-written inline `style="..."` and hardcoded hexes (`#dc2626`, `#16a34a`, `#fefce8`/`#fde68a`/`#92400e`). The styling logic lives in the JS string templates ([:121-167](templates/create_batch.html#L121-L167)).

Why it matters, and to whom: warehouse — the custom batch-type "buttons" are `<button>`s styled by hand, ~`7px 18px` padding, smaller than the 40px `.btn` tap target the rest of the app guarantees ([style.css:338](static/css/style.css#L338)); on this hands-busy page the *primary* control is the *smallest* one. Portfolio — a reviewer who opens this page (the most impressive one) finds the least systematic code. Target — these are exactly the hardcoded status colors the system says to tokenize. Note: the running-total inputs here are also where the P1-1 precision contract matters most — the "remaining / over by" math (`required.toFixed(2)`, [:129](templates/create_batch.html#L129)) currently hard-rounds to 2 dp in the *display*, which may not match the precision the boss expects to allocate at.

Proposed direction: a focused refactor *after* the table pages are clean. (a) Replace the batch-type buttons with a proper segmented control or radio-group meeting the 40px target. (b) Move the lot-card/lot-row CSS out of the JS strings into stylesheet classes (`.lot-card`, `.lot-row`, `.lot-remaining.is-over`, `.is-covered`) so the JS toggles classes, not inline colors — and the "covered / over by" states use the badge tokens. (c) Revisit the `toFixed(2)` calls against the agreed precision contract. This is the highest-value *single page* in the app; treat it as its own milestone.

> Flagging my own suggestion as a risk: a "segmented control" can get clever and lose contrast. For warehouse use, keep the three options as large, clearly-bordered, clearly-labeled targets with an obvious filled selected state. Do **not** trade the current unambiguous green-fill-selected for a subtle underline or tint that's hard to read across a warehouse. Usability first here.

### P1-6. Audit log shows raw machine slugs and full timestamps
**Fails: Target, Portfolio, Warehouse.**

[audit_log.html:28](templates/audit_log.html#L28) prints `{{ row['action'] }}` raw — `material_updated`, `batch_created`. The `humanize` filter built for exactly this is unused. Timestamps are raw full datetimes ([:27](templates/audit_log.html#L27)).

Why it matters, and to whom: the audit log is pitched to the boss as the "if something looks off" safety net ([index.html:447](templates/index.html#L447)) — so it must be *readable by a non-technical person*, and `batch_created` / a 26-char timestamp aren't. For portfolio, raw enum slugs in the UI read as unfinished.

Proposed direction: apply `humanize` to the action column ("Material updated") and `fmt_date` to the timestamp. Consider a small monospace/neutral pill for the action type so the column scans. Low effort, and it makes a page you already sell as a feature actually deliver.

### P1-7. Sort control is a `.btn`-styled `<select>` — looks like a button, behaves like a menu
**Fails: Portfolio, Warehouse (minor).**

The `sort_box` macro ([inventory.html:10-21](templates/inventory.html#L10-L21), duplicated in [manage_materials.html](templates/manage_materials.html#L10-L21)) puts `class="btn btn-secondary"` on a native `<select>` with `padding:5px 10px` — overriding the 40px button height and mixing two component metaphors. It also navigates on `onchange`, which is fine, but the styling makes it ambiguous.

Why it matters, and to whom: portfolio — borrowing button classes for a dropdown is a "no real component model" tell. Warehouse — sub-40px target, and a control that looks like a button but opens a menu is a small hesitation cost repeated all day.

Proposed direction: give sort/filter selects their own `.select-control` class (proper height, the input border token, a caret), distinct from `.btn`. Minor, but it removes a recurring inconsistency that appears on two high-traffic pages.

---

## P2 — Polish

### P2-1. Color sprawl cleanup (already in the audit, restated as a task)
**Fails: Target, Portfolio.** Two unrelated reds (`#dc3545` error-box, `#dc2626` deletes/warnings) plus the tokenized `--badge-out-text #A12D2D`; three greens; `.alert-*` and `.badge-standard` hardcode the badge palette instead of reusing tokens; delete buttons on the five `manage_*` pages override `.btn-secondary` with inline `#dc2626` instead of using `.btn-danger` ([manage_materials.html:89](templates/manage_materials.html#L89), [manage_batches.html:76](templates/manage_batches.html#L76)); `.badge-planned` is defined inline in [manage_batches.html:7](templates/manage_batches.html#L7) only. Direction: converge each role on one token, switch deletes to `.btn-danger`, promote `.badge-planned` to the stylesheet. Do it as one "color convergence" sweep once the per-page formatting work is done, so you're not editing the same files twice.

### P2-2. Spacing/size drift
**Fails: Target, Portfolio.** The `--sp-*` scale is defined and never used; paddings/radii/font-sizes are raw px with half-pixel values (`11.5`, `13.5`) and one-off radii (`3/4/5/6/8/10/20px`). Direction: don't chase this globally — adopt the scale opportunistically *as you touch each component* in the passes above, rather than a dedicated sweep. Lowest user impact.

### P2-3. Empty/loading/error states are inconsistent and mostly text-only
**Fails: Warehouse, Portfolio.** Empty states are a centered sentence in a bordered box (fine, consistent-ish). But the expander panels show a bare `Loading...` ([batches.html:131](templates/batches.html#L131), [inventory.html:147](templates/inventory.html#L147)) and a bare "Failed to load" on fetch error — no spinner, no retry. Direction: a small shared "loading" and "couldn't load — retry" treatment for the async panels. The fetches in [inventory.html](templates/inventory.html#L316) and [batches.html](templates/batches.html#L324) have `.catch` handlers already, so the hook exists. Low priority but it's the kind of unambiguous-state detail the Target a11y section calls non-negotiable.

### P2-4. Dashboard "How to Use" is a large amount of bespoke CSS for a help block
**Fails: Portfolio (mild).** [index.html:6-198](templates/index.html#L6-L198) is ~190 lines of one-off styles (htu-workflow, htu-cards, htu-pills) for a collapsed help section. It's well-built and genuinely useful for low-literacy users (Warehouse: keep it), but it's a lot of single-use CSS. No action needed soon; if you ever consolidate, this is a candidate to slim. Noting it so it's a conscious keep, not an oversight.

---

## Tensions worth holding in view

- **Precision vs float spew (P1-1).** The boss enters 10–15 dp; the arithmetic emits `48.98000…004`. "Round all numbers" (Target) collides head-on with "keep every entered digit" (a data-integrity requirement). Resolution: never lower precision — normalize *representation* (strip arithmetic noise / trailing zeros at high significant-digit bound), and ideally fix it at the source with `Decimal`/`NUMERIC` storage. You owe me one decision — the precision contract — before any number is touched.
- **Relative vs absolute dates (P1-2).** "One date format everywhere" (Target/Portfolio) vs "the boss wants 'just now'" (Warehouse). Resolution: relative time is an *intentional, commented* exception scoped to the activity feed; everything else is one absolute format.
- **Segmented control on Create Batch (P1-5).** Polish wants something sleek; warehouse needs big, high-contrast, unambiguous targets. Resolution: systematize the *code* (classes, tokens, tap-target) without making the control subtler. Keep the obvious filled-selected state.
- **Help block on the dashboard (P2-4).** Portfolio minimalism would trim it; warehouse low-literacy users benefit from it. Resolution: keep it, it serves the primary audience — that's the CLAUDE.md priority order working as intended.

---

## Recommended sequence

Move one concern or one page at a time. Order chosen so each step is independently shippable and the early steps are low-risk, high-trust-per-effort.

1. **P0-1 (broken alerts).** Tiny change, removes a real "errors are invisible" failure on two warehouse forms. Do this first — it's a correctness bug, not styling.
2. **P0-2 (broken `--bg-*` vars) + P0-3 (red "No" pills).** Both small, both on the boss's main pages, both make the app look unfinished. Quick credibility recovery.
3. **Agree the precision contract (P1-1 decision).** Before any number formatting, settle the max significant digits to preserve. This is a conversation, not code, but it gates step 4 and the Create Batch work — so do it now while the easy fixes are landing.
4. **Formatting pass, one table page at a time — start with Raw Materials, then Low Stock.** Bundle P1-1 (precision-safe number formatting), P1-3 (`.num`/mono + right-align), and P1-2 (`fmt_date`/`dash`) into a single edit per page so each table is verified once. These two pages are the highest-traffic and simplest, so they prove the pattern before you apply it to batches/shipments/audit.
5. **Roll the same formatting pass through Batches, Shipments, Manage pages, then Audit Log (P1-6).** Audit log adds `humanize`.
6. **Create Batch (P1-5).** Its own milestone — most important page, biggest payoff, but riskiest (and it depends on the precision contract from step 3), so do it after the formatting pattern is settled and you've built confidence on the simpler pages.
7. **Component extraction (P1-4) + color convergence (P2-1) + sort control (P1-7).** Consolidation sweeps once the per-page work has surfaced every place the duplicated patterns live. Doing these last means you touch each file once for content, once for consolidation — not repeatedly.
8. **P2 polish (spacing scale, loading/error states)** opportunistically, as you're already in each file.

Rationale for leading with the P0s and *then* the simplest pages rather than the flashiest: the broken CSS is cheap to fix and currently undercuts every other lens at once, and proving the precision-safe formatting pattern on Raw Materials/Low Stock de-risks the bigger Create Batch refactor. Save the impressive page for when the system underneath it is actually a system.
