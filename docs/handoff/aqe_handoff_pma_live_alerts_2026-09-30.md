# AQE handoff v2: watch the PMA committee's levels in the 15-minute alerts

**From:** Aegis PMA · **To:** AQE engine (build: Claude Code) · **Date:** 2026-09-30 · **Owner:** Ash (PM)
**Supersedes:** the 2026-09-29 draft. What changed: the file location is fixed, the PMA side is built and publishing, and the build is mapped onto AQE's existing alert engine rather than a new one.
**Hard line:** alerts only. Nothing in this path places, changes, cancels or sizes an order. Every email is information for the PM to act on himself.

---

## 1. Where the committee's levels live

| What | Where |
|---|---|
| **The file AQE reads** | `TongIncomeWheel/AQE` · branch `main` · **`aegis/output/pma/pma_levels.json`** |
| Dated record (written from the next run on) | `aegis/output/pma/levels/<run_date>.json` |
| Schema | `pma_levels.v1` (below; producer: `aegis-core` 1.19.0 `skills/pma/tools/pma_levels.py`) |
| When it lands | Once each morning, after the PMA committee run, before the US open |
| First file | Run 2026-09-29, pushed 2026-09-30: 36 rows, 52 triggers, verified byte-for-byte by read-back |

**Why `aegis/output/`.** `.github/workflows/deploy-hf.yml` rebuilds the HF Space on every push to `main` *except* `aegis/output/**`. A levels file written anywhere else would redeploy the Space every morning and kill the container mid-run. Keep every PMA write under `aegis/output/pma/`.

**Who sees it.**
- The GitHub Actions backstop (`alerts.yml`) checks out `main` every 15 minutes, so it always has the latest file.
- The HF Space does **not** redeploy on output commits, so its own checkout goes stale. The Space's in-app poller must fetch the file from GitHub (see §4), not read its local copy.

---

## 2. What PMA now produces (built, 1.19.0)

Each run ends with a new **LEVELS** step (ruling R20), and **PUBLISH** pushes the file and reads it back to verify it.

| Class | Meaning | Triggers carried |
|---|---|---|
| `ADVANCE` | Buy candidate today, subject to its lines | Entry (e.g. new high), chase line (do not buy above), kill (close back under pivot). Computed stop/targets in `levels` (render-only). |
| `HOLD_FOR_CONDITIONS` | Watch, don't buy yet; becomes actionable only if its condition is met | Condition (ACTION on the close), intraday touch (INFO), invalidation (INFO). `held: true` marks an ADD condition on a name the PM already owns. |
| `HELD` | A position the PM owns | His **broker stop** (read-only from Tiger: order type, stop, limit), the committee's exit line, near-stop band, and flags for a missing stop or a limit above its stop. |
| `WATCH` | AQE's admission rules liked it; no analyst nominated it (R17) | **None.** Digest only; never an intraday alert. |

PMA refuses to publish the file if any of these hold:
- a HOLD condition has no trigger and no stated `not_structured_yet` reason;
- a WATCH row carries a trigger;
- a committee exit line sits **below** the PM's broker stop (a committee line may never loosen a stop he has).

Rows with `not_structured_yet` are conditions PMA can't yet express as a number (two-legged, "pulls back and holds", Elder turns). **AQE skips them rather than guesses.** 8 of 19 on 2026-09-29.

### Row and trigger shape

```json
{ "ticker": "A", "class": "ADVANCE", "lane": "MOMENTUM", "conviction": 3, "held": false, "mark": "STANDING",
  "levels": { "ref_close": 175.21, "stop": 170.2, "stop_type": "aqe_atr_fallback", "stop_pct": 2.86,
              "tp": [176.02, 185.48, 197.51], "rr_to_tp2": 2.05, "gates_clear": true, "sized": false },
  "triggers": [
    { "id": "A-entry", "kind": "trade_above", "level": 176.02, "basis": "15m",   "priority": "ACTION", "action": "..." },
    { "id": "A-chase", "kind": "trade_above", "level": 178.78, "basis": "15m",   "priority": "WARN",   "action": "..." },
    { "id": "A-kill",  "kind": "close_below", "level": 163.75, "basis": "daily", "priority": "ACTION", "action": "..." } ] }

{ "ticker": "NTRA", "class": "HELD", "qty": 17,
  "broker_stop": { "order": "STP_LMT", "stop": 350.5, "limit": 350.58, "note": "limit sits ABOVE the stop ..." },
  "committee_exit": 354.62, "committee_exit_range": [354.62, 398.78], "atr_14d": 12.99,
  "triggers": [
    { "id": "NTRA-stopnear",  "kind": "within_atr_of", "level": 350.5, "atr": 12.99, "atr_mult": 0.5, "basis": "15m", "priority": "WARN" },
    { "id": "NTRA-ordertype", "kind": "order_config",  "level": 350.5, "basis": "open",  "priority": "ACTION" },
    { "id": "NTRA-committee", "kind": "close_below",   "level": 354.62, "basis": "daily", "priority": "ACTION" } ] }
```

File header: `schema`, `run_date`, `session`, `generated_at`, `valid_until`, `render_only: true`, `guardrails[]`, `counts{}`, `rows[]`.

---

## 3. How each trigger maps onto AQE's live quote

AQE's poller uses FMP `/stable/quote`, which is 15 minutes delayed on the Starter plan. It returns `price, day_high, day_low, volume, avg_volume, prev_close, ts`. There are no 15-minute bars, so evaluate against the quote as follows.

| `kind` | `basis` | Fires when | Notes |
|---|---|---|---|
| `trade_above` | 15m | `day_high >= level` | A touch at any point today |
| `trade_below` | 15m | `day_low <= level` | |
| `close_above` / `close_below` | daily | **Final cycle only** (first poll at or after 16:00 ET, inside the existing 16:15 ET window): `price` beyond `level` | Before that cycle, a `price` beyond the level sends a one-time **WARN**: "beyond the line intraday; confirms only on the close". The next morning's digest confirms against the official `prev_close`. |
| `within_atr_of` | 15m | `level < price <= level + atr_mult × atr` | Replaces the held-name `NEAR_STOP`, which reads `held_sl` (null on every row, so it has never fired) |
| `no_stop_order` | open | First cycle of the session | Repeat once every session until the row disappears |
| `order_config` | open | First cycle of the session | |
| `volume_min_x` (optional field) | any | Projected full-day volume ≥ `volume_min_x × avg_volume` | Use the pace in `src/alerts/intraday.py` (linear accumulation, a stated approximation). If it can't be computed, send the alert marked **"volume unconfirmed"**; never drop it silently. |

**Freshness gate.** Act on the file only if `session` equals today's New York date. Otherwise send one email at the first cycle ("PMA levels are stale: run X, today Y; not being watched") and nothing else from it.

**Dedup.** Use the existing Drive state: key `PMA:{trigger id}` in `fired`, once per trading day. A `daily` close trigger's WARN and its ACTION are separate keys (`…|warn`, `…|close`).

**Priority → delivery.**
- **ACTION** and **WARN**: in the next digest email, which already goes out each cycle there are fresh triggers.
- **INFO**: the after-close digest only.
- **WATCH rows**: the after-close digest only.

---

## 4. Build brief for Claude Code (AQE repo)

Work on branch `pma-levels-alerts`; the handoff and example file are already there. Open a PR to `main`. Merging will redeploy the Space once, which is expected.

1. **`src/alerts/pma_levels.py` (new):**
   - `load_pma_levels()` returns the parsed file or `None`. Order:
     1. The local checkout `aegis/output/pma/pma_levels.json`, when its `session` is today (the fresh case in Actions).
     2. Otherwise the GitHub contents API for `TongIncomeWheel/AQE@main` with an `AQE_GH_TOKEN` read-only secret (the Space's case).
     3. Otherwise `None`, with a reason string.
   - `is_fresh(doc, now_et)` implements the freshness gate above.
   - `evaluate_pma(row, quote, now_et, is_final_cycle, is_first_cycle) -> list[trigger]` is a pure function implementing §3. It returns trigger dicts in the engine's existing shape: `ticker, source="pma", is_held, level=<trigger id>, label, level_price, live_px, chg_pct, prev_close, intraday, note`, plus `pma_class, priority, action`.
2. **`src/alerts/engine.py`:**
   - In `run_alert_cycle`, after `monitored(export)`, load the levels file.
   - Add every ticker from rows with `class != "WATCH"` to the quote fetch; they bypass `in_alert_universe`, because the committee picked them.
   - Evaluate with `evaluate_pma`, dedupe with the `PMA:` keys, write to the same history and ledger, and pass to `send_digest`.
   - **Do not** remove or change the existing MOVE/BOS/NEAR_* rules. PMA triggers are an additional source.
   - Suppress the legacy held-name `NEAR_STOP` for a ticker when the levels file carries a `broker_stop` for it, so the PM never gets two stop alerts with different stops.
3. **`src/alerts/emailer.py`:** render PMA triggers as their own block at the top of the digest, ordered ACTION → WARN, each showing:
   - subject tag `[AEGIS {priority}] {ticker} {class}`;
   - the event (level, price, time in ET and SGT);
   - the committee's `action` text, verbatim;
   - class context: conviction/lane/mark, or for HELD, qty, broker stop and committee line;
   - `levels` labelled "information only, not sized";
   - the footer **DRAFT — PM approval required. Nothing is staged, nothing is armed.**
4. **After-close digest:** extend the existing final-cycle email with confirmed closes, HOLD invalidations, and the WATCH list (doors, mp, distance from pivot).
5. **Config (`src/alerts/config.py`):** `PMA_LEVELS_ENABLED` (default true) and `PMA_LEVELS_PATH` (default `aegis/output/pma/pma_levels.json`).
6. **Workflow:** add `AQE_GH_TOKEN` to `alerts.yml` env for the fallback fetch. No schedule change is needed: the cron already covers 13:00–21:00 UTC, and the engine's New York market-hours gate handles daylight saving (the SGT window moves to 22:30–05:00 after 1 November).
7. **Tests (`tests/test_alert_pma_levels.py`):**
   - one test per trigger kind, including the final-cycle close logic and the WARN-then-ACTION pair;
   - stale file → no triggers plus the stale notice;
   - a WATCH row never triggers;
   - a `not_structured_yet` row never triggers;
   - `NEAR_STOP` suppressed when a broker stop is present;
   - a `volume_min_x` shortfall → no ACTION;
   - volume missing → "volume unconfirmed".
8. **Acceptance replay:** run `evaluate_pma` over `aegis/output/pma/pma_levels.json` (run 2026-09-29) with synthetic quotes. It must produce:
   - at the first cycle: `WEAT-nostop` (ACTION) and `NTRA-ordertype` (ACTION);
   - A at `day_high` 176.10 → `A-entry` ACTION; at 178.90 → also `A-chase` WARN;
   - PK at `day_high` 16.25 → `PK-near` INFO; price 16.30 on the final cycle → `PK-cond` ACTION;
   - MRVL at 238.00 → `MRVL-stopnear` WARN (233.85 + 0.5 × 13.53 = 240.62);
   - no trigger for any WATCH row, or for TMO/DT/ASX/VEEV/NTAP/CNK/TEAM conditions.

**Guardrails to keep in the code:**
- no broker write scope anywhere in AQE;
- nothing AQE observes feeds back into PMA's votes (the alert ledger is for later grading only);
- the PM's broker stop is always the stop that email text calls "your stop".

---

## 5. What's still open

| Item | Owner |
|---|---|
| PMA: express the two-legged and "holds" conditions as structured pairs, so the 8 skipped rows become watchable | PMA (next build) |
| PMA: publish needs a byte-exact git push. Today the push goes through the GitHub connector as inline text; the first push had a one-digit slip that the read-back caught. Adding `TongIncomeWheel/AQE` to the session's authorised repositories lets `git_sync.py` push files directly. | **PM action** |
| Mailbox and sender: AQE already emails via `AQE_ALERT_TO` / `AQE_ALERT_FROM`. Confirm that is the mailbox you want. | PM |
| WARN emails to the inbox or the digest only? Default above: inbox, in the next cycle's digest. | PM |
| Phone notification for HELD-name ACTIONs | PM |

DRAFT — PM approval required. Nothing is staged, nothing is armed.
