# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

Inventory management web app for Botaniks, a small matcha manufacturer. Tracks raw materials, production batches, recipes, and shipments. Runs in production on Render (PostgreSQL/Supabase) and locally on SQLite. Flask + Gunicorn backend, server-rendered Jinja templates, no frontend framework.

## Commands

```bash
# Setup
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# Run locally (SQLite — leave DATABASE_URL blank in .env). Serves on :8000
python app.py

# Production server (also how the Dockerfile/Procfile launch it)
gunicorn app:app --bind 0.0.0.0:8000 --workers 2

# Tests — pytest suite in test_scripts/. Runs against an isolated throwaway SQLite DB
# (SQLITE_PATH temp file, built per session, wiped per test) — never touches data/inventory.db.
python -m pytest test_scripts -q
# With coverage:
python -m pytest test_scripts --cov=services --cov=routes --cov-report=term-missing

# One-time setup: enable the local pre-push pipeline (pytest + app-boot smoke test).
# Render auto-deploys on push with no gate in between, so this blocks `git push` locally
# if the suite or the smoke test fails — catching breakage before it reaches prod, not
# just after (the tests.yml GitHub Actions workflow is async and doesn't block deploy).
git config core.hooksPath hooks
```

Required env vars (`.env` locally): `SECRET_KEY`, `AUTH_USERNAME`, `AUTH_PASSWORD`, and `DATABASE_URL` (blank → SQLite at `data/inventory.db`; set → PostgreSQL). The app refuses to start without `SECRET_KEY` (raises) or auth vars (asserts in [auth.py](auth.py)).

## Architecture

Three layers, kept deliberately separate:

- **[app.py](app.py)** — all web page routes, form parsing, input validation, auth decorators, and the redirect flows between pages. ~2400 lines; this is where HTTP request handling lives. Also defines Jinja display filters (`fmt_num`, `dash`, `humanize`, `fmt_date`) and rate limiting.
- **[services/](services/)** — all business logic and DB operations, split by domain: `materials.py`, `lots.py`, `recipes.py`, `batches.py`, `shipments.py`, `audit.py`, `setup.py`. Routes call into these; services never import Flask.
- **[routes/api.py](routes/api.py)** — a Flask Blueprint (`/api/...`) returning JSON, used by the autocomplete/lot-selection JavaScript ([static/js/autocomplete.js](static/js/autocomplete.js)). Registered in app.py.

### Database abstraction — read this before writing any query

[database.py](database.py) makes SQLite and PostgreSQL interchangeable with **zero per-environment code changes**. Always go through it:

- Use `get_db_connection()` to get a `DatabaseConnection` wrapper (not the raw `get_connection()`).
- Write all SQL with `%s` placeholders. Call `db.execute(cursor, sql, params)` — it rewrites `%s` to `?` for SQLite automatically.
- Get insert IDs with `db.get_last_insert_id(cursor)` (handles `LASTVAL()` vs `lastrowid`).
- `db.close()` returns PostgreSQL connections to a module-level pool (kept warm for the process); for SQLite it closes the file handle. Don't bypass it.

### Schema and the lot-number model

Schema for fresh SQLite DBs is created by `create_database()` in [services/setup.py](services/setup.py); fresh **PostgreSQL** deploys use [init_db.py](init_db.py) instead. `create_database()` also does additive SQLite migrations (PRAGMA-checked `ALTER TABLE`) for existing local DBs — follow that pattern when adding columns.

Core tables: `raw_materials`, `raw_material_lots`, `recipes` + `recipe_materials`, `batches` + `batch_materials`, `shipments`, `audit_log`. Material stock is tracked per-**lot** in `raw_material_lots` (each receipt is a lot with its own quantity/expiry/cost); a material's available stock is the SUM over its active lots, not a single column. Batch creation deducts from specific lots (FIFO by received_date, or user-selected via the lot-selection UI) and records each deduction in `batch_materials`.

### Batch types (in [services/batches.py](services/batches.py))

- `standard` — deducts material lots immediately on creation.
- `mix` — an intermediate house-made product; creates/updates a pseudo-material in `raw_materials` with `is_housemade=True` so finished batches can consume it.
- `finished` with a `planned_completion_date` — **defers** material deduction; the batch sits in `Planned` status until promoted (when overdue, if stock suffices) into `Ready`, otherwise records a `promotion_failure_reason`. Deductions roll back atomically on insufficient stock.

Every mutating action calls `log_action(...)` ([services/audit.py](services/audit.py)) to write the audit log.

## Conventions

- Validation lives in the route (app.py): parse/strip form fields, validate, then render `error.html` with `back_link*` kwargs on bad input. Keep services free of HTTP concerns.
- User-facing messages after a redirect use Flask `flash()` (session-backed), not URL query params.
- Don't surface raw exception text to users — log it server-side and show a generic message (see the `create_batch` ValueError handling for the pattern).
- Excel exports go through `export_to_excel()` in [helper_functions.py](helper_functions.py) and land in `exports/`.

## Tests

`test_scripts/` is a pytest suite (`conftest.py` + `test_*.py`), one file per domain
(units, materials, lots, recipes, batches, shipments) plus `test_routes.py` for HTTP/API
integration through the Flask test client. `conftest.py` sets the env vars the app needs at
import, points the DB at an isolated temp SQLite file via `SQLITE_PATH`, builds the schema
once per session, and wipes every table between tests. Factory fixtures (`make_material`,
`make_lot`, `make_recipe`) seed data through the services layer; the `client`/`auth` fixtures
give an authenticated test client with CSRF + rate limiting disabled. Quantities in tests are
in base units (grams for mass) since that's how the services store them.

**Known gap:** tests run on SQLite; production is PostgreSQL. The suite verifies app logic, not
Postgres-specific behavior (Decimal return types, `LASTVAL()`, the connection pool). There is
no CI — run the suite locally before deploying.

## Caveat

The [README.md](README.md) references an `inventory_app.py` and a root `cli.py` that no longer
exist — that code was refactored into `services/`. Trust the `services/` modules over those
references.

## Current design state (audit)

Baseline inventory of what the UI code actually does as of this audit. There is exactly **one stylesheet**, [static/css/style.css](static/css/style.css); all other styling is inline `<style>` blocks or `style="..."` attributes inside the Jinja templates. There are **282 `style="..."` occurrences across all 25 templates** — inline styling is the norm, not the exception.

### 1. Fonts

Three Google Fonts loaded in [base.html](templates/base.html#L9) (`Inter:400,500,600`, `Syne:600,700`, `DM Mono:400,500`), exposed as three role tokens in `:root` ([style.css:65-67](static/css/style.css#L65-L67)):

- `--font` (**Inter**) — body, labels, table text, buttons, inputs. Set on `body` and reused throughout.
- `--font-display` (**Syne**) — applied only to `.page-header h1` ([style.css:261](static/css/style.css#L261)) and `.section-card h2` ([style.css:596](static/css/style.css#L596)).
- `--font-mono` (**DM Mono**) — intended for "ALL numerals, IDs, units, costs, dates." Actually applied only via `.mono/.num/td.num` ([style.css:90-96](static/css/style.css#L90-L96)) and `.stat-card .stat-value` ([style.css:523](static/css/style.css#L523)).

**Inconsistencies / gaps:** The mono "all numerals" rule is aspirational — most numeric table cells (e.g. `{{ row.stock_level }}` at [inventory.html:114](templates/inventory.html#L114), all `${{ '%.2f'... }}` cost cells, dates) carry no `.num`/`.mono` class, so they render in Inter, not DM Mono. Tabular alignment only happens on the few cells that opt in.

### 2. Colors

Colors are split between `:root` tokens and a large number of hardcoded literals (both in style.css and inline per-template). Distinct **six-digit** hex values and their roles:

**Tokenized in `:root`** ([style.css:7-67](static/css/style.css#L7-L67)): `#17181A` sidebar bg, `#232427` sidebar border, `#9CA0A6` sidebar muted text, `#C8CDD4` sidebar text, `#E9F6F1` sidebar active text, `#5A5E63` section label, `#2AB08E` accent (green), `#1e8a6e` accent-dark, `#F7F8F8` content bg, `#ffffff` card bg, `#E7E8EA` border, `#1A1B1E` text, `#6E7177` muted text, `#9AA0A6` faint text, `#E7F3EC`/`#1F7A4D` in-stock badge, `#FBF1DF`/`#8A5A12` low badge, `#FBEAEA`/`#A12D2D` out badge, `#D3D6D9` input border, `#D8DADD` tag border, `#5F6368` tag text.

**Hardcoded literals in style.css** (bypass the tokens): `#fafafa` table-row hover, `#F2F3F4` secondary-btn hover, `#E7B9B9` danger-btn border, `#f3f4f6`/`#f6f...` collapse-btn hover, alert palettes `#d1fae5`/`#065f46`/`#a7f3d0` (success), `#fee2e2`/`#991b1b`/`#fecaca` (error), `#fef3c7`/`#92400e`/`#fde68a` (warning), `#fff8f8` danger-card bg, `#dc3545` error-box accent, `#f8f9fa` code bg, batch-type badges `#d1fae5`/`#065f46` (standard), `#dbeafe`/`#1e40af` (mix), `#ede9fe`/`#5b21b6` (finished).

**Hardcoded literals inline in templates:** `#f0faf6`/`#e2f2ec` ([batches.html](templates/batches.html#L27), [shipped_batches.html](templates/shipped_batches.html#L26)), `#fef2f2`/`#991b1b`/`#dc2626` (batches failed-promotion rows), `#f9fafb`/`#f3f4f6`/`#f0f0f0`/`#9ca3af` (inventory lot rows), `#fefce8`/`#fde68a`/`#92400e`/`#dc2626`/`#16a34a` ([create_batch.html](templates/create_batch.html#L41)), `#dbeafe`/`#1d4ed8` badge-planned ([manage_batches.html:7](templates/manage_batches.html#L7)), and `#dc2626` on every Delete button across the five `manage_*` pages. Three-digit hexes also appear (`#888` on "(optional)" hints in [create_batch.html:24](templates/create_batch.html#L24) and [edit_batch.html:40](templates/edit_batch.html#L40)).

**Inconsistencies / gaps:**
- **Two unrelated reds, and one red overloaded.** `#dc3545` (Bootstrap red) is the error-box accent, but `#dc2626` (a different red) is used for delete buttons, negative-stock text, promotion-failure notes, and the create-batch over-allocation warning — one literal spanning several unrelated roles, none of it the tokenized out-of-stock red `#A12D2D`.
- **At least three greens.** `#2AB08E` (accent), `#065f46`/`#16a34a` (alert/JS success text), `#1F7A4D` (in-stock badge) — visually similar, semantically different, not unified.
- **Alerts and batch-type badges ignore the badge tokens.** `.alert-success` and `.badge-standard` both hardcode `#d1fae5`/`#065f46` instead of reusing `--badge-in-stock-*`; the status palette is effectively duplicated.
- **`badge-planned` ≠ `badge-mix`.** Both use `#dbeafe` bg but different text (`#1d4ed8` vs `#1e40af`) — near-duplicate, defined in two places (inline vs stylesheet).

### 3. CSS tokens / variables

All custom properties live in a single `:root` block ([style.css:7-67](static/css/style.css#L7-L67)): layout (`--sidebar-width`, `--content-max`), sidebar palette (6 vars), `--accent`/`--accent-dark`, surfaces (`--content-bg`, `--card-bg`, `--border`), text (`--text`, `--text-muted`, `--text-faint`), badge palette (6 vars), `--border-input`/`--border-tag`/`--tag-text`, `--focus-ring`, `--btn-radius`, spacing scale (`--sp-1..--sp-8`), and the three font roles.

**Inconsistencies / gaps:**
- The spacing scale `--sp-*` is **defined but never referenced** — every padding/margin in the file is a raw px literal.
- Many surface/hover colors that logically belong in tokens (`#fafafa`, `#F2F3F4`, `#f3f4f6`, all alert and batch-badge colors) are hardcoded instead.
- No colliding `--card-bg`/`--bg-card`-style duplicates exist; the token names are clean. The collisions are between **tokens and literals**, not between token names.

### 4. Spacing & sizing

A 4px scale is declared (`--sp-1:4 … --sp-8:32`) but unused (see above). In practice spacing is hand-set px throughout and mostly — but not strictly — multiples of 2/4: card padding ranges across `20px 22px`, `24px 28px`, `28px 32px`, `30px`; radii are a mix of `6px`, `8px`, `10px`, `20px` (and `3px`/`4px`/`5px` inline). Font sizes hover around a 13px base but include `11px`, `11.5px`, `12px`, `13.5px`, `14px`, `15px`, `22px`, `24px`, `28px` — several half-px values (`11.5`, `13.5`). Responsive gutters use `clamp()` ([style.css:234](static/css/style.css#L234)).

**Inconsistencies / gaps:** No enforced scale — the token scale is bypassed; half-pixel font sizes and one-off radii/paddings (especially in inline styles like `padding:5px 12px`, `padding:4px 8px`) drift from any system.

### 5. Components

- **Buttons** — `.btn` base + `.btn-primary` (solid accent), `.btn-secondary` (white/neutral border), `.btn-danger` (white/red), `.btn-ghost` ([style.css:333-397](static/css/style.css#L333-L397)). But Delete buttons on the `manage_*` pages do **not** use `.btn-danger`; they're `.btn-secondary` with inline `color:#dc2626;border-color:#dc2626` overrides (e.g. [manage_materials.html:89](templates/manage_materials.html#L89)).
- **Inputs** — styled via `.form-group input/select/textarea` with a visible `--border-input` and green focus ring ([style.css:462-487](static/css/style.css#L462-L487)). Consistent where `.form-group` wraps them.
- **Tables** — `.table-container` + `.data-table` ([style.css:280-327](static/css/style.css#L280-L327)); `.num` opt-in for right-aligned mono cells. Per-page tables add inline `<style>` blocks for row tinting (lot detail rows, failed-promotion rows, shipped-batch grouping).
- **Sidebar / nav** — fixed two-panel grid; `.nav-item.active` gets the accent left-border + tinted bg ([style.css:209-214](static/css/style.css#L209-L214)). Off-canvas with a `.topbar` toggle under 900px. This is the most systematized component.
- **Status indicators** — `.badge-in-stock/-low/-out` are tokenized and computed in-template from `stock_level` vs `reorder_level` ([inventory.html:127-132](templates/inventory.html#L127-L132)). Batch-type badges (`.badge-standard/-mix/-finished`) are stylesheet classes with hardcoded colors; `.badge-planned` is defined **inline** in [manage_batches.html:7](templates/manage_batches.html#L7) only.

**Inconsistencies / gaps:** Status/destructive colors are hardcoded inline per-template in many places rather than via the existing classes — Delete buttons (5 templates) and `badge-planned` (1 template) are the clearest cases. Row-tint colors live in scattered per-page `<style>` blocks.

### 6. Value formatting

**Critical finding: the four display filters in [app.py](app.py#L136-L185) — `fmt_num`, `dash`, `humanize`, `fmt_date` — are defined but used ZERO times in any template** (verified by grepping `| fmt_num`, `| dash`, etc.: 0 matches each). Templates instead hand-roll formatting:

- **Numbers** — rendered raw, e.g. `{{ row.stock_level }}` ([inventory.html:114](templates/inventory.html#L114)) with no rounding filter. Float noise like `48.980000000000004` is **not** guarded at the template layer; it's only avoided if the service/DB already rounded. Costs use `'%.2f'|format(...)` inline ([inventory.html:118](templates/inventory.html#L118), [batches.html:124](templates/batches.html#L124)).
- **Dates** — rendered raw straight from the DB with **no single format**: bare date strings via `{{ row.received_date or '' }}` / `or '—'`, full timestamps with time component in [audit_log.html:27](templates/audit_log.html#L27), and JS-relativized "2 h ago" strings in [index.html:286](templates/index.html#L286). The `fmt_date` filter that would normalize all of these is unused.
- **Empty / missing values** — handled at least four different ways: `or '—'`, `or ''` (blank, e.g. [manage_lots.html:37](templates/manage_lots.html#L37)), `!= 'nan'` string-compare ([shipments.html:35](templates/shipments.html#L35), [shipped_batches.html](templates/shipped_batches.html#L104)), and `!= 'None'` string-compare ([shipment_detail.html:57](templates/shipment_detail.html#L57)). The centralized `dash`/`_is_empty` logic (which correctly handles real `None`/`NaN`/blank) is bypassed; the `!= 'nan'`/`!= 'None'` checks only catch the literal *strings* "nan"/"None".
- **Labels** — audit-log `action` slugs are rendered raw: `{{ row['action'] }}` ([audit_log.html:28](templates/audit_log.html#L28)) shows DB values like `material_updated`, not humanized "Material updated" — the `humanize` filter built for exactly this is unused.

**Inconsistencies / gaps:** A complete, tested formatting layer exists in app.py but is entirely disconnected from the templates. The result is inconsistent number rounding, 3+ date presentations, 4 empty-value conventions (including blank cells and brittle string-compares against `'nan'`/`'None'`), and raw machine slugs in the audit log.

## Approved design system (build toward this)

This is the agreed target. The audit above is the current state; where they conflict, the audit names the work left to do (see Known gaps). The `:root` tokens in [style.css](static/css/style.css#L7-L67) already encode most of this — use them, don't add new literals.

### Who this is for

Two first-class audiences: (1) **warehouse staff** entering production batches fast, hands-busy, low technical literacy; (2) a **boss** with low technical comfort who glances at stock and low-stock alerts. It is also a **portfolio piece** for data-engineering internship applications. **Where warehouse usability and portfolio polish conflict, NAME the tension in your response — never sacrifice usability for polish.**

### Design voice

"Instrument panel, not website." Understated, credible, direct. Quality bar: Linear, Vercel dashboard, Raycast. No flashy, trendy, or promotional styling.

### Typography (fonts already loaded in [base.html](templates/base.html#L9))

- **Syne** (`--font-display`) — page titles + section headers ONLY.
- **DM Mono** (`--font-mono`) — ALL numerals, IDs, units, quantities, costs, dates. Apply via `.num`/`.mono` (opt-in today — most numeric cells still render in Inter; see gaps).
- **Inter** (`--font`) — body, labels, table text.

### Color (tokenized — never hardcode status colors inline)

- **Accent matcha green `#2AB08E`** (`--accent`): primary button + active nav item ONLY. Never status, never attribute tags.
- **Status pills:** In stock `--badge-in-stock-bg #E7F3EC` / `-text #1F7A4D`; Low `--badge-low-bg #FBF1DF` / `-text #8A5A12`; Out `--badge-out-bg #FBEAEA` / `-text #A12D2D`. Use the `.badge-in-stock/-low/-out` classes — one status-pill system everywhere.
- **Attribute tags** (Organic, Housemade): neutral outline only — border `--border-tag #D8DADD`, text `--tag-text #5F6368`. Never green.
- **Surfaces:** page bg `--content-bg #F7F8F8`; cards `--card-bg #fff`, 1px `--border #E7E8EA`, radius 10–12px.
- **Text:** primary `--text #1A1B1E`; muted `--text-muted #6E7177`; faint `--text-faint #9AA0A6`.
- **Spacing on a 4px scale** (`--sp-1..--sp-8` exist — prefer them over raw px).

### Components

- **Sidebar:** dark `#17181A`; nav items muted `#9CA0A6` with icon; active = `rgba(42,176,142,.12)` bg + 2px green left border + light/green text+icon; section labels 11px uppercase tracked `#5A5E63`. (Already implemented — the most systematized component.)
- **Buttons:** primary solid green/white; secondary white + 1px `#D8DADD` border; destructive white + red border/text (`.btn-danger`); ghost transparent.
- **Inputs:** visible 1px `#D3D6D9` border (warehouse contrast matters); 42–44px tall; radius 8px; green focus ring.
- **Tables:** small uppercase muted headers; text left-aligned; numbers right-aligned in DM Mono; comfortable row height; single status-pill system; support grouped/nested rows.
- **Icons:** Tabler outline set.

### Formatting contract (apply everywhere — ideally via the existing Jinja filters)

The `fmt_num`, `dash`, `humanize`, `fmt_date` filters already exist in [app.py](app.py#L136-L185) but are unused. Wire them in:

- **Round all numbers** — never float spew (e.g. `48.980000000000004`).
- **Empty/missing → always "—"** (em dash). Never None, nan, or blank.
- **Humanize all labels** — never raw DB slugs (e.g. `material_updated`).
- **One consistent date format** across all templates.

### Layout / scroll

- App shell: `height:100vh; overflow:hidden` — sidebar + main scroll internally only (already in place).
- Dashboard and New batch must fit one viewport with no page scroll.

### Accessibility non-negotiables

Sufficient contrast, generous click targets, unambiguous states (loading, empty, error), sensible fallbacks (no raw NaN or blank cells — use "—").

## Working norms (for every Claude Code session on this UI)

- **Move one page or one concern at a time.** Don't rewrite all templates at once.
- **Decision-first:** critique and propose before producing finished UI; wait for approval before treating anything as final.
- **Explain reasoning** — the developer is learning front-end design.

## Known gaps (approved spec vs. current code)

Where the code diverges from the system above. Flagged, not silently fixed — fix one at a time, decision-first.

- **DM Mono is opt-in, not universal.** Most numeric table cells (stock levels, cost cells, dates) carry no `.num`/`.mono` class and render in Inter. The "all numerals in DM Mono" rule is aspirational.
- **Formatting filters are wired up nowhere.** `fmt_num`/`dash`/`humanize`/`fmt_date` exist but are used zero times; templates hand-roll formatting → inconsistent rounding, 3+ date presentations, 4 empty-value conventions, raw audit-log slugs.
- **Hardcoded status/destructive colors inline per-template.** Delete buttons on the five `manage_*` pages use `.btn-secondary` + inline `#dc2626` overrides instead of `.btn-danger`; `badge-planned` is defined inline in [manage_batches.html](templates/manage_batches.html#L7) only. Status palette is duplicated in `.alert-*` and `.badge-standard` rather than reusing the badge tokens.
- **Color sprawl:** two unrelated reds (`#dc3545`, `#dc2626`) plus the tokenized out red `#A12D2D`; three greens (`#2AB08E`, `#065f46`/`#16a34a`, `#1F7A4D`). Not unified.
- **`--sp-*` spacing scale is defined but never referenced** — every padding/margin is a raw px literal; half-px font sizes (`11.5`, `13.5`) and one-off radii drift from the 4px scale.
- **Inline styling is the norm:** 282 `style="..."` occurrences across 25 templates, plus scattered per-page `<style>` blocks for row tinting. The single stylesheet is the exception, not the rule.
