# D-99 — PRICE CHAIN CORRECTION (supersedes D-98)

**Date:** 2026-08-25
**Status:** ADOPTED — PM signed in session
**Supersedes:** D-98 (IBKR retirement)
**Owner:** Aegis / bracket skill STEP 1

---

## 1. What D-98 got wrong

D-98 retired the IBKR connector from the equity price chain on the stated
premise that **Tiger MCP now served equity spot prices**.

That premise is false, and was false when D-98 was written.

**Evidence, from the Tiger MCP v7 tool surface itself:**

| Observation | Implication |
|---|---|
| `get_option_chain`, `get_option_greeks`, `get_option_briefs`, `get_option_bars`, `get_option_depth`, `get_option_trade_ticks` all exist | Tiger's market-data entitlement is **US Option L1**, not equity |
| There is **no** `get_stock_quote` / `get_price_snapshot` / equity spot tool anywhere in the surface | Tiger cannot be asked for an equity price |
| Tiger's own `compute_hv` and `compute_portfolio_greeks` source underlying prices from **yfinance** | Tiger internally goes outside itself for equity spot |
| Tiger's `get_roll_candidates` sources underlying prices from **FMP** | Same |
| The server's own instruction block states: *"For EQUITY (stock/ETF) spot prices use the IBKR connector's get_price_snapshot — Tiger MCP intentionally does not expose a spot-prices tool."* | Explicit, in writing, from the server |

**What Tiger DOES do for equities:** it *trades* them — `place_stock_order`
is live and has been used for recent AEGIS equity fills, and
`get_stock_positions` reports the book. Trading equities and quoting
equities are separate entitlements. D-98 conflated them.

**Consequence:** with IBKR retired and Tiger unable to quote, the bracket
skill's STEP 1 had no reachable price source. Bracketing has been
structurally unavailable since D-98, not because of any data-vendor plan.

---

## 2. Second, independent root cause

`aegis/tools/bracket_calc.py` — referenced by the bracket skill at STEP 6 —
**never existed in the repository**. Every bracket run that got past STEP 1
would have failed at STEP 6 regardless.

Both faults are fixed by this decision: the chain below restores STEP 1, and
`bracket_calc.py` is committed alongside this note.

---

## 3. The corrected chain (STEP 1)

```
1. FMP  quote-short          ← PRIMARY
2. IBKR get_price_snapshot   ← on STALE or GAP flag, or on FMP failure
3. AQE  export ref_price     ← last resort (prior close), always declared
```

### Why FMP primary
PM ruling, 2026-08-25: *"FMP is a better source than yahoo though its 15mins
lag — if this is a fallback then yes use FMP."* FMP is already a paid,
authenticated dependency of this book. It requires no brokerage session to
be alive.

### Why IBKR is the escalation, not the primary
PM: *"IBKR does give me live prices actually — my brokerage account is still
live so if you want to use the connector it is doable but i think easier to
just stick to FMP."* IBKR is live and authoritative but depends on an active
brokerage session; it is called when FMP's answer is flagged unusable, not
by default.

---

## 4. FMP plan reality (Starter) — tested, not assumed

**PM standing constraint: "Fmp is what it is, I won't upgrade."** No part of
this decision assumes or requests an upgrade.

| Endpoint | Starter | Note |
|---|---|---|
| `quote-short` | **WORKS** | The price source. Returns symbol/price/volume. |
| `historical-price-eod-light` | **WORKS** | Used for ATR/MA context. |
| `quote` | GATED (Premium) | 403 |
| `batch-quote` | GATED (Premium) | 403 |
| `economics-calendar` | GATED | 403 |
| `intraday-5-min` | GATED | 403 |

**Correction of my own error, logged deliberately:** on first test I hit
`batch-quote`, received ACCESS DENIED with the vendor's "do not attempt
sibling tools" message, and concluded FMP price was entirely dead. It is
not. `quote-short` is ungated on Starter and works. The generalisation from
one gated sibling to the whole family was wrong and cost a full diagnostic
cycle.

---

## 5. Staleness by construction — MANDATORY FLAG

Premarket, `quote-short` returns the **prior close**, not a 15-minute-delayed
print. There is no delayed premarket tape on this plan. Therefore:

- When FMP price **equals** the AQE export `ref_price` (both are the prior
  close), `bracket_calc.py` prints
  `*** STALE BY CONSTRUCTION — FMP = AQE ref, prior close, no live premarket tape ***`
- When `|FMP − AQE ref| ≥ 1%`, it prints `*** GAPPED n% ***`

Either flag is the trigger to escalate to IBKR `get_price_snapshot` before
arming anything. Measured on CRM this session: FMP `quote-short` returned
exactly the AQE `ref_price` — the flag fired correctly.

**A bracket computed off a stale price is a bracket computed off yesterday.**
The flag is not advisory; nothing is staged while it is up without an IBKR
confirmation.

---

## 6. What is NOT changed

- **Alpaca** stays a read-only options/Greeks data feed. It is not in the
  equity price chain.
- **yfinance** is not adopted. PM prefers FMP over Yahoo explicitly.
- Sizing law is untouched: two-step R-size then vol-cap, smaller wins
  (`aegis/tools/calculators/sizing.py`, constitution law 4).
- dynCap remains AEGIS-book-only (D-41). Tiger and IBKR are shared with
  Income Wheel and Protege9; **co-mingled broker totals are never used.**

---

## 7. Action taken

1. `aegis/tools/bracket_calc.py` — committed (new file, was missing).
2. This note — committed as the D-98 correction of record.
3. `skills/bracket/SKILL.md` STEP 1 — **cannot be edited from a Cowork
   session**: the `aegis-core` plugin on disk is a synced read-only cache.
   The skill text must be updated at source in the plugin repo. Until then,
   this note is the operative instruction and overrides STEP 1 as written.
