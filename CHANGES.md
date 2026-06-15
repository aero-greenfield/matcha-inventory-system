# Botaniks design-system foundation pass

System-level only. No page layouts were redesigned and no per-page inline `style="..."`
was removed. Three files touched: `static/css/style.css`, `templates/base.html`, `app.py`.

## Fonts (base.html)
Single Google Fonts link now loads **Inter** (body/labels/table text), **Syne** (page
titles + section headers only), and **DM Mono** (all numerals/IDs/units/costs/dates).

## Tokens (style.css `:root`)
All existing token **names kept** (renaming would break templates app-wide); re-valued to
the approved palette and extended:
- Surfaces: `--content-bg #F7F8F8`, `--card-bg #fff`, `--border #E7E8EA`.
- Text: `--text #1A1B1E`, `--text-muted #6E7177`, **new** `--text-faint #9AA0A6`.
- Accent: `--accent #2AB08E` (reserved for primary button + active nav only).
- Sidebar: `--sidebar-bg #17181A`, muted `#9CA0A6`, active bg `rgba(42,176,142,.12)`,
  **new** `--sidebar-section-label #5A5E63`; width 240px.
- Status badges re-valued to the semantic palette (in-stock `#E7F3EC`/`#1F7A4D`,
  low `#FBF1DF`/`#8A5A12`, out `#FBEAEA`/`#A12D2D`).
- **New:** `--border-input #D3D6D9`, `--border-tag #D8DADD`, `--tag-text #5F6368`,
  `--focus-ring`, 4px spacing scale `--sp-1…--sp-8`, `--content-max 1280px`,
  font-role faces `--font` / `--font-display` / `--font-mono`.

## Font-role rules
- `h1` / `.page-header h1`, `.section-card h2` → Syne (`--font-display`).
- `.mono` / `.num` / `td.num` utilities + `.stat-value` → DM Mono with tabular numerals.
- Everything else stays Inter.

## Components updated
- **App shell:** `.app-layout` is `height:100vh; overflow:hidden`; sidebar + `.main-content`
  scroll internally; main content capped at `--content-max` and centered.
- **Sidebar:** muted nav items; active item = tinted bg + **2px green left border** +
  light text + green icon; 11px tracked section labels.
- **Buttons:** primary = solid green; secondary = white + neutral border; danger = white +
  red border/text (outline, was pink fill); **new** `.btn-ghost`; 40px min target + focus ring.
- **Inputs:** visible `--border-input` border, 42px min height, radius 8px, green focus ring.
- **Tables:** tighter row height; **new** right-aligned mono numeric cell class (`.num`).
- **Badges/tags:** status badges bind to re-valued tokens; `.badge-organic` re-valued to a
  **neutral outline attribute tag** (no longer green), plus shared `.tag` / `.badge-attr`.
- **Density:** base font 13px so a table page fits at 100% zoom on a 1366px laptop.
- **A11y:** global `:focus-visible` ring on all interactive elements.

## Jinja filters (app.py — defined, not yet applied in templates)
- `fmt_num` — `{{ qty | fmt_num }}` → strips float noise / trailing zeros (`48.98`, `5`).
- `dash` — `{{ value | dash }}` → empty/None/nan/blank renders `—`.
- `humanize` — `{{ action | humanize }}` → `material_updated` → `Material updated`.
- `fmt_date` — `{{ row.received_date | fmt_date }}` → consistent `YYYY-MM-DD`; handles
  datetime / ISO string / None.
All are defensive (never raise) and registered via `@app.template_filter`.

## DEFERRED per-page work (NOT done here)
- Removing/rewriting per-page inline `style="..."`.
- Applying `.mono` / `.num` to numeric table cells in each template.
- Applying `fmt_num` / `dash` / `humanize` / `fmt_date` across templates.
- Layout/redesign of Dashboard, New Batch, and other pages (incl. per-viewport fitting).
- Re-evaluating batch-type badges (`.badge-standard/.badge-mix/.badge-finished`), tab-bar
  accent usage, and other page-local helper classes.
