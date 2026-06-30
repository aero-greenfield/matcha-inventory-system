# Pre-Departure Manual Test Checklist  ☑️

Run this end-to-end **in the live (or a staging) app** before you leave. For each step confirm two
things: (a) the result is **correct** (matches the **Expected** value), and (b) the **on-screen
feedback is clear** to a non-technical user. Write what you actually saw in the **Actual** blank and
tick the box when both pass. Where a step says "force a failure," you're deliberately testing that
the app fails *safely and understandably*.

> **How to use this fast:** do the **Setup** once, then run sections 1→9 **in order** (the expected
> numbers assume that order, because stock carries over). All expected values are exactly what the
> screen should show after the app's rounding (2 decimal places, trailing zeros trimmed).
>
> Reference conversions (the app stores mass in grams): **1 lb = 453.59237 g**, **1 kg = 1000 g**,
> **1 oz = 28.349523125 g**. Counts (each/tin) never convert.
>
> **General finding to watch for:** if any inventory or lot screen shows a raw gram number for a
> material whose unit is lb/kg (e.g. "907.18" instead of "2 lb"), note it — the unit display should
> be applied everywhere.

---

## SETUP — create this fixture first (≈10 min)

### Materials (create each, then receive the lot(s) listed)
| Material | Unit | Organic? | Edible? | Lots to receive (received date) |
|---|---|---|---|---|
| Matcha Powder | lb | yes | yes | **M1 = 2 lb** (2026-06-01), then **M2 = 0.5 lb** (2026-06-10) |
| Citric Acid | g | no | yes | 100 g |
| Cane Sugar | kg | yes | yes | 1 kg |
| Organic Vanilla | g | yes | yes | 100 g |
| Tin | each (count) | no | no | 50 |
| Mint Extract | lb | no | yes | (receive in section 1's noise test) |

### Recipes (create after materials exist)
| Recipe | Type | Product unit | Ingredients (enter exactly these units) |
|---|---|---|---|
| **Matcha Latte** | finished | bottle | Matcha Powder **100 g**  +  Citric Acid **5 g** |
| **Organic Sweet Base** | mix / component | g | Cane Sugar **0.5 g**  +  Organic Vanilla **0.1 g** *(per 1 g of base)* |
| **Organic Matcha Tin** | finished | tin | Organic Sweet Base **50 g**  +  Tin **1 each** |

> Note the deliberate trick in **Matcha Latte**: the Matcha line is entered in **grams** even though
> the material is stored in **lb**. That's the cross-unit case we most want to verify.

---

## 1. Receiving raw material lots  (unit conversion + no float spew)
- [ ] After receiving **M1 = 2 lb** Matcha, the Matcha stock reads exactly **`2 lb`** (not `2.00`, not `1.9999…`).
      Actual: __________
- [ ] After also receiving **M2 = 0.5 lb**, total Matcha stock reads **`2.5 lb`**.  Actual: __________
- [ ] Receive **Mint Extract 0.1 lb**, then **0.2 lb** → Mint stock reads exactly **`0.3 lb`** (the float-noise check — must NOT show `0.30000000004`).  Actual: __________
- [ ] Receive a lot **with** a cost-per-unit and one **without** → both save; cost shows where entered, dash/blank where not.  Actual: __________
- [ ] Enter a **bad date** (e.g. `2026-13-99`) → clear error page, not a blank/broken page.  Actual: __________

## 2. Recipes
- [ ] Create **Matcha Latte** (finished) → saved and listed.  Actual: __________
- [ ] Create **Organic Sweet Base** (mix/component) → saved and listed.  Actual: __________
- [ ] Try to create a recipe with **no unit / dimension** → blocked with a clear message.  Actual: __________

## 3. Standard batch  (cross-unit deduction, FIFO, manual lots, hard block)
- [ ] **FIFO:** make a **standard Matcha Latte, qty 2** (no manual lot pick). Needs 200 g matcha + 10 g citric.
  - [ ] Oldest lot **M1** drops first → M1 reads **`1.56 lb`** (707.18 g); **M2 unchanged at `0.5 lb`**.  Actual: __________
  - [ ] Total Matcha stock reads **`2.06 lb`**; Citric Acid reads **`90 g`**.  Actual: __________
  - [ ] Open the batch → ingredient/lot breakdown shows Matcha 100 g ×2 and Citric 5 g ×2, from the right lots.  Actual: __________
- [ ] **Manual lot selection:** make a **standard Matcha Latte, qty 1**, and manually pick **lot M2** for the matcha.
  - [ ] **M2** drops to **`0.28 lb`** (126.80 g); **M1 unchanged at `1.56 lb`**.  Actual: __________
  - [ ] Total Matcha reads **`1.84 lb`**; Citric Acid reads **`85 g`**.  Actual: __________
- [ ] **Force insufficient stock:** try a **standard Matcha Latte, qty 100** (needs 10,000 g ≈ 22 lb matcha).
      → Shortfall table appears listing **Matcha Powder**, batch is **blocked**, stock stays as above (no negative).  Actual: __________

## 4. Mix batch + organic propagation  (the recently-fixed organic logic)
- [ ] Make an **immediate Organic Sweet Base mix, qty 100 (g)**.
  - [ ] A housemade material **"Organic Sweet Base"** now exists with a lot reading **`100`**.  Actual: __________
  - [ ] It is flagged **Organic** (both inputs were organic+edible).  Actual: __________
  - [ ] Cane Sugar dropped by 50 g → reads **`0.95 kg`**; Organic Vanilla dropped by 10 g → reads **`90 g`**.  Actual: __________
- [ ] Make a finished **Organic Matcha Tin, qty 1** (consumes 50 g of the base + 1 Tin).
  - [ ] The batch shows the **Organic** tag (its only edible input, the base, is organic; the Tin is non-edible so it doesn't break organic).  Actual: __________
  - [ ] Base stock drops to **`50`**; Tin drops to **`49`**.  Actual: __________
- [ ] **Organic negative check:** open one of the **Matcha Latte** batches from section 3 → it shows **NO Organic tag** (Citric Acid is edible but not organic).  Actual: __________
- [ ] Make a **Planned** Organic Sweet Base mix (give it a completion date) → it sits as **Planned** (no housemade lot yet until it promotes).  Actual: __________

## 5. Planned finished batch + promotion  ⭐ (the key new visibility fix)
- [ ] **Success case:** create a **Planned Matcha Latte, qty 2**, completion date = today or earlier.
      Open the **Batches** page → it auto-promotes to **Ready** and 200 g matcha deducts.  Actual: __________
- [ ] **Stuck case:** create a **Planned Matcha Latte, qty 10** (needs 1000 g matcha — more than you have left), date = today/earlier. Open the **Batches** page, then go to **Manage Batches**.
  - [ ] The row shows the red **"⚠ Needs attention"** tag next to **Planned**.  Actual: __________
  - [ ] Expanding the row shows **"Couldn't complete yet"** with a reason (insufficient matcha).  Actual: __________
- [ ] **Recovery:** receive more Matcha (e.g. 5 lb), reopen **Batches** → the stuck batch now promotes automatically and the warning clears.  Actual: __________

## 6. Shipments
- [ ] Create a **full** shipment of a Ready batch → batch marked **Shipped**; manifest quantities/units match the batch.  Actual: __________
- [ ] Create a **partial** shipment (ship fewer than the batch made) → remaining quantity is correct; units display in the product's unit.  Actual: __________

## 7. Destructive-action guards
- [ ] Try to **delete a lot used by a batch** (e.g. Matcha M1) → **blocked**, message names how many batches use it.  Actual: __________
- [ ] Try to **delete a Shipped batch** → **blocked**.  Actual: __________
- [ ] **Delete a recipe that's in use** (e.g. Matcha Latte) → allowed; confirm existing Latte batches still exist, then try to create a *new* Matcha Latte batch → clear **"no recipe"** message. (Recreate the recipe afterward.)  Actual: __________

## 8. Health & error pages
- [ ] Visit **`/health`** directly → returns **`{"status":"ok"}`** (HTTP 200), even when not logged in.  Actual: __________
- [ ] Visit a made-up URL (e.g. **`/nope`**) → friendly **"Page Not Found"** page with a Home link, not a raw 404.  Actual: __________

## 9. Backups
- [ ] GitHub → **Actions → Daily Database Backup → Run workflow** → run completes green.  Actual: __________
- [ ] A fresh **`prod_backup_*.sql`** appears in the Supabase **`db-backups`** bucket.  Actual: __________
- [ ] (Recommended) Do a **test restore** into a scratch DB per `backup_instructions.txt`, so you know recovery actually works.  Actual: __________

---

## Deployment sign-off (do last)
- [ ] All changes pushed to the **branch Render auto-deploys** — confirm which branch in Render first (it currently deploys `units-conversion-layer`, not `main`).
- [ ] Render redeployed successfully (check the deploy log).
- [ ] **`/health` on the live URL** returns `{"status":"ok"}`.
- [ ] **Render health check** set: dashboard → service → **Settings → Health Checks** → path **`/health`**.
- [ ] **Email alerts on:** Render → **Settings → Notifications** (or Account → Notifications) → enable **deploy failed** + **health check failed**. *(Optional redundancy: a free UptimeRobot monitor hitting `/health` every 5 min — it alerts even when Render itself is down.)*
- [ ] **`RUNBOOK.md` contact details filled in** and its contents shared somewhere staff actually use (printed by the workstation / pinned Google Doc), not just in GitHub.
