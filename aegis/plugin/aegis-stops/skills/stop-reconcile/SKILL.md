---
name: stop-reconcile
description: "Aegis process skill — STOP RECONCILE. Compares the working stop orders at Tiger with the committee's stop levels for Aegis cash equities, proposes raises only, and after the PM approves specific levels in chat writes amend requests for the staging-gatekeeper (or a manual Tiger checklist), then verifies. Triggers: /stops, stop reconcile, reconcile my stops, stop check, stop loss adjustment, committee stops vs Tiger, amend stops, tighten stops. Read and compute only: never cancels, places or amends an order."
---

# PROCESS: STOP RECONCILE — Tiger stops vs committee stops

**What this is.** One loop: pull what Tiger is actually holding as stops, set it beside what the committee says the stop should be, show every gap, and — only on the PM's explicit approval of specific levels — produce the amend request. **The PM decides every level.** This skill computes and proposes; it never moves a stop.

**What this is not.** It does not cancel, place or amend any order. Order entry belongs to the staging-gatekeeper (constitution law 1). If the gatekeeper is unavailable or not armed, the output is a checklist the PM keys in at Tiger. Never call `place_stock_order`, `cancel_order` or `execute_roll` from this skill, with or without `confirm`.

The engine is `scripts/stop_reconcile.py` (relative to this skill). It holds the arithmetic and the guards. Do not recompute classifications, deltas or ratchet checks by hand, and do not soften what it returns.

---

## Step 0 — Stamp the clock

Run `date` for SGT and US Eastern. Say which world the prices are in: session open ("live"), closed ("at the close"), or shut ("last close, market shut"). Stops cannot trigger while the market is shut, which makes it the safe window to amend. Pass the SGT date to the script as `--today`.

## Step 1 — Fix the scope

In scope: **Aegis cash equities, long-only.** Out of scope, never reconcile or propose against them:

- Income Wheel equity (shares held from assigned puts or against covered calls; the Core and Active pots)
- Ryan Pot holdings
- Protege9 and any option position

Decide membership from the Aegis journal's confirmed held book where it is available. A held equity with a protective stop at Tiger and no pot assignment is almost always Aegis: include it, **name it to the PM as an inference**, and ask. Never guess silently in either direction.

## Step 2 — Fresh Tiger pull

Resolve the live Tiger connector prefix first; never hardcode it. Run in this order and stop if any call fails (retry once):

1. `get_account_summary`
2. `get_stock_positions`
3. `get_open_orders`

Build two files in a working folder (`stop_work/`):

- `positions.json` — `{"positions": [{"symbol", "qty", "mark"}]}` for in-scope names only
- `tiger_orders.json` — `{"orders": [{"id", "symbol", "type", "qty", "limit_price", "stop_price", "status"}]}` for SELL `STP` / `STP_LMT` orders only

**Data trap: Tiger does not return the stop trigger.** `get_open_orders` returns `limit_price` for a stop-limit and nothing for a plain stop; `stop_price` is always null and `get_order_transactions` is empty for working orders. Save `stop_price: null`. The script treats a stop-limit's limit as a floor on the trigger (the true trigger is at or above it) and reports plain stops as `TIGER_TRIGGER_HIDDEN`. Say this every run; it is why some rows cannot be reconciled.

Other traps: `get_account_summary` is one segment only (never quote it as NAV); `market_price` on a position can be a cached mark, so for any name where the decision turns on a few percent, say the mark's age.

## Step 3 — Committee levels

Build `committee_stops.json`:

```json
{"as_of": "YYYY-MM-DD", "source": "<doc and section>",
 "stops": {"TICKER": {"level": 0.0, "basis": "close|intraday", "action": "HOLD|STOP-TIGHTEN|EXIT", "note": ""}}}
```

Source order, newest dated wins: (1) the latest PMA brief's held-book section ("Stop today" / "Level that ends it"); (2) the stop references carried in the latest journal; (3) the mechanical floor from `trailing_stop.py`, which ratchets and is the authority on that number. Record the source on the file. Where both a committee level and a mechanical floor exist, show both to the PM; the committee level drives the proposal.

Record `basis` honestly. Most committee rules are **close-basis** ("a close below the 20-day"), while a Tiger stop is **intraday**. Flag the mismatch; do not hide it.

A committee `EXIT` with no level gets `"level": null`. A name the committee does not list is simply absent.

**Freshness.** Report the age of the committee levels in days. Levels older than 3 days block ticket generation. Do not rationalise a stale level into a proposal; ask the PM for a fresh `/pma` run, or for an explicit override.

## Step 4 — Reconcile

```
python3 scripts/stop_reconcile.py reconcile --positions stop_work/positions.json \
  --orders stop_work/tiger_orders.json --committee stop_work/committee_stops.json \
  --today <SGT date> --out-dir stop_work/out
```

Print `reconcile.md` verbatim as a table. Then, in this order, name what needs a decision:

1. **Committee EXIT or `BREACHED`** — the mark is already through the committee line. A stop cannot be proposed above price; this is an exit-or-override call for the PM.
2. **`NO_TIGER_STOP`** — an unprotected position. Say so in the first line.
3. **`TIGER_LOOSER`** — the proposals. State level, distance under the mark, and the dollars at risk at the proposed level.
4. **Unreconcilable** — `TIGER_TRIGGER_HIDDEN`, `NO_COMMITTEE_LEVEL`. Say what is missing and what would fix it.
5. **`TIGER_TIGHTER` / `ALIGNED`** — one line, no action. Stops only ratchet up: a Tiger stop tighter than the committee's stays.

## Step 5 — Approval (the PM's step, not yours)

Ask the PM which proposals to approve. **Approval means the PM names the symbol and the level in chat.** "Looks good" or "go ahead" over a table is not approval of any specific level: restate the exact levels and ask again.

Write `approvals.json` from `approvals_template.json`, setting `approved: true` and `approved_level` to exactly the figure the PM stated, only for the rows they approved. Never infer, round or improve a level. One approval covers one set of levels: if any level, quantity or the committee data changes, re-run Step 4 and ask again.

Lowering a stop is never proposed. If the PM explicitly wants one, set `allow_lower: true` on that row only, and say it back to them.

## Step 6 — Amend requests

```
python3 scripts/stop_reconcile.py ticket --approvals stop_work/approvals.json \
  --recon stop_work/out/reconcile.json --out-dir stop_work/out
```

The script refuses a level at or above the mark, a lowered stop, a quantity that differs from the held position, and stale committee levels. Print every refusal verbatim.

Each ticket is: re-pull open orders → **cancel** the old order → **place** the new `STP_LMT` sell (GTC) → verify. Tiger has no amend call, so an amend is always cancel then place. Never place first: if both orders trigger, the position oversells and goes short. Default limit buffer is 0.5% below the trigger; the PM may change it with `--limit-buffer-pct`.

Hand `amend_requests.json` to the **staging-gatekeeper**. If it is absent, not armed, or the session cannot submit orders, give the PM `amend_checklist.md` for manual entry at Tiger. Say plainly which route applies. This skill never submits.

## Step 7 — Verify

When the PM says the amends are done, pull fresh `get_open_orders` and `get_stock_positions`, rebuild the two JSON files, and run:

```
python3 scripts/stop_reconcile.py verify --positions stop_work/positions.json \
  --orders stop_work/tiger_orders.json --requests stop_work/out/amend_requests.json \
  --out-dir stop_work/out
```

Report each row's status verbatim: `OK`, `NOT_REPLACED`, `UNPROTECTED`, `DOUBLE_SELL_RISK`, `MISMATCH`. Anything but `OK` is reported first and plainly, without softening. `UNPROTECTED` and `DOUBLE_SELL_RISK` are urgent. Because the trigger price is hidden, verification rests on limit, quantity and order identity; say so.

## Step 8 — Close

One closing line: how many stops are protected, how many are not, and what the PM still has to decide.

---

## What this skill must not do

Cancel, place, amend or preview an order · call any Tiger write tool · treat vague agreement as approval of a level · propose a stop at or above the mark · propose lowering a stop · present stale committee levels as current · reconcile a name that is outside Aegis scope · fill in a missing trigger price by assumption · decide EXIT or HOLD on a position (that is the committee's read and the PM's call) · recompute what the script returns.

## Known gaps (state them, never paper over them)

1. Tiger's MCP returns no stop trigger. The permanent fix is on the Tiger MCP server: return the order's `aux_price` as `stop_price` in `get_open_orders`. Until then, reconciliation of plain stops is impossible and stop-limits are bounded only.
2. Tiger's MCP has no amend call. Amending is cancel + place, with a short unprotected window; do it while the US market is shut where possible.
3. Committee rules are mostly close-basis; Tiger stops are intraday. A wick can trigger a stop the committee would not act on. The alternative is a price alert at the committee level.
4. Committee levels come from briefs and journals, which can be days old. The age is always reported.

See `references/contract-and-rules.md` for the file contracts, status table and the ratchet rationale.
