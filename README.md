# Botaniks Inventory Managment System 


<!-- One-line tagline under the title, e.g. "Lot-based inventory & production tracking for a matcha manufacturer." -->

<!-- Badge/tag row — e.g. shields.io badges or plain text: Flask · PostgreSQL · SQLite · Supply Chain · Render -->

## Table of Contents

- [Overview](#overview)
- [Demo](#demo)
- [Features](#features)
- [Architecture](#architecture)
- [Engineering Decisions](#engineering-decisions)
- [Testing & Reliability](#testing--reliability)
- [Known Limitations & Next Steps](#known-limitations--next-steps)

## Overview


### What it is:

Botaniks is an inventory management system for a Santa Cruz matcha and tea wholesaler (Botaniks Herbs & Tea). It tracks raw materials by lot, plans and records production batches deducted from user-selected lots or automatic FIFO, and logs shipments, giving warehouse and management staff exact stock levels, recipes, and batch and shipment history. It has been in production since June 2026 and is used daily by six staff.

**Stack:**

| Layer | Tools |
|---|---|
| Backend | Python, Flask, Gunicorn |
| Data | PostgreSQL (prod), SQLite (dev/test), pandas, openpyxl (Excel export) |
| Frontend | Jinja2 templates, HTML/CSS, JavaScript |
| Testing | pytest, Hypothesis |
| Infra | Docker, GitHub Actions, Render, Supabase, Cloudflare R2 |


### Background:

I started as a warehouse employee at Botaniks, where inventory was tracked in spreadsheets and by intuition. That caused daily slowdowns: unexpected material shortages, manual physical counts of batches ready to ship, and batch details that had to be checked by hand.

I built a demo database system and pitched it to the owner. After a positive response I kept building it on the side, and eventually the company moved me off warehouse work to build it during paid hours.

## Demo
 
<!-- GIF or 3-4 screenshots: receiving a lot, FIFO batch creation, shipping. Use scrubbed data. -->

## Features

<!-- 5-6 core actions in plain language -->

- 
- 
- 
- 
- 

## Architecture

<!-- Mermaid diagram of the overall system/flow -->

```mermaid
graph LR

```

### Schema

<!-- Small ER diagram of raw_material_lots, batches, batch_materials, shipment_batches -->

```mermaid
erDiagram

```

## Engineering Decisions

<!-- 4-5 entries, each: Problem → What went wrong → Fix → Why this over the alternative -->

### 1. The double-deduction race and the conditional UPDATE fix (NEEDS REVIEW BEFORE FINISH CIRCLING BACK!!!!!!!!)

**Problem:** Planned batches auto-promote from `Planned` to `Ready` lazily, on page load, once their planned completion date has passed — there's no background worker, `get_batches()` and `get_all_batches_with_id()` both just call `promote_planned_batches()` on every request. That function fetches every overdue batch, deducts its materials lot-by-lot, and flips its status. Two requests that both land on that path at (near) the same time — two different pages, two Gunicorn workers, doesn't matter which — can both end up acting on the same overdue batch.



**Problem:** Planned batches are promoted to `Ready` lazily: `get_batches()` calls `promote_planned_batches()` on page load once a batch's planned date has passed. Postgres rows were already locked with `FOR UPDATE SKIP LOCKED`, but SQLite has no equivalent, so there the read-deduct-write sequence was unprotected. Two requests could both read a batch as `Planned` and both deduct it, leaving lots deducted twice and, for mix batches, a duplicate output lot (phantom stock). [One sentence on whether production data was affected.] I wrote `scripts/repair_double_promotion.py` to find and fix the duplicates (dry-run by default).


**What went wrong:** The app runs SQLite locally/in tests and Postgres in production. The Postgres path already locked the overdue rows with `SELECT ... FOR UPDATE SKIP LOCKED`, so a second concurrent transaction would just skip a row already being processed. SQLite has no `FOR UPDATE` at all, though, and that gap was previously left unaddressed on purpose — SQLite was treated as "single-writer, local-only" and not worth locking. That left the read-then-deduct-then-write sequence unprotected on the one engine every test actually runs against: a request could read a batch as `Planned`, start deducting its lots, and a second request could read the same row as `Planned` before the first had written anything back — producing duplicate `batch_materials` rows (lots deducted twice) and, for mix batches, a duplicate house-made output lot (phantom stock). I wrote `scripts/repair_double_promotion.py` to find and repair both kinds of duplicate, run as a dry-run report by default.

**Fix:** The UPDATE that flips a batch to `Ready` now carries `WHERE batch_id = %s AND status = 'Planned'` (`_claim_batch` in `services/batches.py`), and it's the *first* statement of that batch's own transaction — every other write for that batch happens after it, so a later rollback (e.g. insufficient stock) also releases the claim. The predicate is re-checked against whatever is actually committed at write time: whichever request's UPDATE lands first flips the row and wins; the second request's UPDATE, once it runs, finds `status` already `'Ready'` and matches zero rows, so it does nothing. That guarantee holds under SQLite's whole-database write lock exactly the same way it holds under a Postgres row lock — the correctness doesn't depend on which engine is underneath.

**Why this over the alternative:** The obvious alternative was to just add `FOR UPDATE` support for SQLite too — but SQLite doesn't have it, so that path doesn't exist. The next obvious alternative was leaving Postgres on its existing lock and writing a SQLite-only guard, but that means carrying two different concurrency mechanisms for the same function and trusting that they're equivalent — exactly the kind of asymmetry that's easy to get subtly wrong. A conditional UPDATE needs no engine-specific locking clause, so one line of logic is correct everywhere, including in the SQLite-backed test suite, which can now actually exercise and assert the race is closed instead of only reasoning about it for the engine tests don't run against.

### 2. The float/Decimal bug and the units layer

**Problem:** Quantities are entered in what ever unit of measument is natural for the receipt (pounds, ounces, kilograms, etc) but need to be stored, summed and compared against the recipes required quantity consistently. Doing this using plain floats meant converting through binary floating point, which cant represent most of these conversions exactly. 

**What went wrong:** A house-made mix lot holding exactly 176 lb was rejected as insufficient for a batch needing exactly 176 lb. The lot's produced quantity had been rounded to 4 decimal places (in grams) when saved, which shifted it about 0.00002 g from the exact value. The "is there enough stock" check used a 1e-6 g tolerance, smaller than that gap, so identical quantities failed the comparison.

**Fix:**  Four pieces working together:
- **One base unit per dimension** (grams for mass). Conversion happens only at the edges, form input and display, so each quantity is converted once instead of bouncing between units.
- **Decimal for conversion math**, built via `Decimal(str(x))` with exact conversion factors, so the conversion step adds no error.
- **No rounding on save.** Produced quantities are stored at full precision.
- **One shared tolerance.** Every coverage check goes through two helpers (`_covers`, `_quantities_match`) using a 1 mg epsilon, above storage noise and far below any quantity that matters. Previously, call sites had no tolerance or a too-tight one.


**Why this over the alternative:** Threading `Decimal` end-to-end and dropping the tolerance is the principled fix, and I scoped it out deliberately. Values are still cast to `float` on write to SQLite (`REAL` has no fixed-precision decimal type), so a tolerance would still be needed on that path. On PostgreSQL, quantity columns are `NUMERIC`, which closes most of that gap. The 1 mg tolerance bounds the remaining risk without a rewrite of every service function.

### 3. Lot-based stock as a derived SUM

**Problem:**
**What went wrong:**
**Fix:**
**Why this over the alternative:**

### 4. Verified backups with an off-site copy

**Problem:**
**What went wrong:**
**Fix:**
**Why this over the alternative:**

### 5. N+1 elimination

**Problem:**
**What went wrong:**
**Fix (before/after query count):**
**Why this over the alternative:**

## Testing & Reliability

<!-- Hypothesis property tests, deterministic race reproduction, pre-push hook + CI, backup integrity checks. Use real counts only. -->




## Known Limitations & Next Steps

<!-- Be honest: lazy promotion trigger, SQLite-vs-Postgres test fidelity, shared auth. -->

- 
- 
- 
</content>
</invoke>
