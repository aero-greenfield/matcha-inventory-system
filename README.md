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
- [Getting Started](#getting-started)
- [Known Limitations & Next Steps](#known-limitations--next-steps)

## Overview

<!-- What it is, who uses it, and status — e.g. "In production since ___, used daily by warehouse staff." This is the section recruiters read first. -->
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

### 1. The double-deduction race and the conditional UPDATE fix

**Problem:**
**What went wrong:**
**Fix:**
**Why this over the alternative:**

### 2. The float/Decimal bug and the units layer

**Problem:**
**What went wrong:**
**Fix:**
**Why this over the alternative:**

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

## Tech Stack

| Layer | Technology |
|---|---|
| Backend | |
| Database | |
| Hosting | |
| Testing | |
| CI/CD | |

## Getting Started

<details>
<summary>Setup & running locally/tests</summary>

```bash

```

</details>

## Known Limitations & Next Steps

<!-- Be honest: lazy promotion trigger, SQLite-vs-Postgres test fidelity, shared auth. -->

- 
- 
- 
</content>
</invoke>
