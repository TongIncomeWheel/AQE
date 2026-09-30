# AQE handoff v2.3.1: watch the PMA committee's levels in the 15-minute alerts

**From:** Aegis PMA · **To:** AQE engine (build: Claude Code) · **Date:** 2026-09-30 · **Owner:** Ash (PM)
**Supersedes:** the 2026-09-29 draft. What changed: the file location is fixed, the PMA side is built and publishing, and the build is mapped onto AQE's existing alert engine rather than a new one.
**v2.1 (same day, PM ruling R20.1):** the file now carries the last **three** runs, not only today's, because committee levels often trigger a session or two late (§2A). Dedup for PMA alerts lasts the life of a trigger, not one day (§3).
**v2.2:** the existing 15-minute heartbeat email stays exactly as it is; the committee levels become one new section at the top, designed for a phone (§3A).
**v2.3:** every card shows distance in %. Held names: how far price is from **your broker stop** and from the **committee's stop**, side by side. The day's committee shortlist (ADVANCE and HOLD-FOR-CONDITIONS): how far from the **entry** line and the **first target**. Entry and target never appear on held names (§3B).
**v2.3.1 (PM, 30 Sep):** delivery is settled. The committee section piggybacks the existing AQE live-alerts feed: same mailbox (`AQE_ALERT_TO` / `AQE_ALERT_FROM`), same email, same cadence, same channel. No new sender, no separate emails, no phone push.
**Hard line:** alerts only. Nothing in this path places, changes, cancels or sizes an order. Every email is information for the PM to act on himself.

---

## 1. Where the committee's levels live

| What | Where |
|---|---|
| **The file AQE reads** | `TongIncomeWheel/AQE` · branch `main` · **`aegis/output/pma/pma_levels.json`** |
| Dated record (written from the next run on) | `aegis/output/pma/levels/<run_date>.json` |
| Schema | `pma_levels.v1` (below; producer: `aegis-core` 1.19.0 `skills/pma/tools/pma_levels.py`) |
| When it lands | Once each morning, after the PMA committee run, before the US open |
| What it covers | **The last three runs** (R20.1, from aegis-core 1.20.0); PMA does the merge, AQE reads one file |
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

### 2A. The three-session window (R20.1)

Committee levels often trigger a session or two after they are set, so each morning's file carries the last three runs. PMA does the merge, so AQE never has to reconcile three files.

- **Today wins.** A name voted today carries only today's row; any older level on it is superseded.
- **Retired, with a reason in `window.retired`:**
  - a name the committee PASSED today;
  - a carried row whose own kill or invalidation close is already broken by today's served close;
  - any HELD or WATCH row from an earlier run (your broker stops and AQE's admission rules are re-read every morning, so only today's are current);
  - anything older than three runs.
- **Carried:** every other ADVANCE or HOLD-FOR-CONDITIONS row from the last two runs. These are typically names that left today's room but whose level may still trigger. Carried rows are marked:
  - `carried: true`;
  - `origin_run` (the run that set the level);
  - `age_sessions` (1 or 2);
  - `last_session_live: true` on the final day.
- **Trigger ids are stamped with their origin run** (`2026-09-29:PK-cond`), so the same level keeps the same id every day it is carried.
- **File-level block:** `window: {sessions, runs[], carried[], retired[], rule}`, and `counts.carried`.

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

**Dedup — for the life of the trigger, not one day.** The existing `fired` set resets every morning, which would re-send a carried level each day it stays true.
- Keep PMA fires in their own Drive set, `pma_fired`, keyed by the stamped trigger id (`PMA:2026-09-29:PK-cond`).
- Keep a key while that id is still in the current file.
- Prune any key whose id has left the file (retired, superseded or aged out).
- A `daily` close trigger's WARN and its ACTION are separate keys (`…|warn`, `…|close`).
- Result: every level alerts at most once over its three-session life.

**Priority → delivery.**
- **ACTION** and **WARN**: in the next digest email of the existing feed, which already goes out on any cycle with fresh triggers. No separate email, no new channel (PM, v2.3.1).
- **INFO**: the after-close digest only.
- **WATCH rows**: the after-close digest only.

---

## 3A. Keep the heartbeat; add a committee section on top; design the email for a phone

**The heartbeat stays exactly as it is.** The existing 15-minute cycle, its rules (MOVE, BOS, NEAR_BREAKOUT, NEAR_TARGET, NEAR_STOP), its dedup, its ledger and its digest ("AQE Trade Entry", ★ HELD first, then the event sections) are unchanged. This work adds ONE new section at the very top of that same email, and nothing below it moves.

**When the email goes out:** exactly as today, on any cycle with fresh triggers. A cycle with only PMA triggers still sends; a cycle with only heartbeat triggers sends exactly as today, with no empty committee section.

**The committee section: "COMMITTEE LEVELS (PMA)".** It is built to be read in five seconds on a phone.

- **Subject line:** committee items lead, e.g. `[AQE] PMA: PK buy line hit · NTRA stop order check · +12 names moving`. The existing subject bits follow unchanged.
- **One card per alert, three lines** (plus one levels line on ACTION cards only, below):
  1. **Headline in plain words**, ticker first, verb second: `PK — closed above its buy line`, `A — through the chase line: don't buy here`, `MRVL — near your stop`, `WEAT — no stop order`.
  2. **The number line: at most three labelled items, each with its % distance in brackets.** The items depend on the class (§3B):
     - held name: `Now 238.00 · Your stop 233.85 (1.7% away) · Committee stop 234.65 (1.4% away)`
     - shortlisted name: `Now 175.40 · Entry 176.02 (0.4% to go) · Target 185.48 (5.7% away)`
  3. **What the committee said**, one sentence, taken from the trigger's `action` text and cut to about 90 characters. For a carried row, add a small grey tag: `set 29 Sep · day 2 of 3`.
- **Colour means one thing each:** red = your money (HELD); green = a buy condition met (ADVANCE / HOLD condition); amber = a warning (chase line, near stop, intraday touch not yet confirmed). A coloured left bar and a small badge; no emoji walls.
- **Order:** ACTION cards first (red, then green), then WARN. INFO never appears intraday.
- **Plain words, not codes.** Write `buy line`, `idea is dead below`, `your stop`, `don't buy above`. Never show `trade_above`, `close_below`, trigger ids, JSON keys, lens tags, SC scores, β or R:R in the committee section. The existing AIC monospace prompt line does NOT appear on committee cards.
- **Levels are secondary:** the computed stop and targets sit behind a single collapsed line (`Levels: stop 15.23 · targets 16.72 / 17.39 — information only, not sized`), shown only on ACTION cards.
- **Layout that survives email clients:** table-based layout, inline CSS, max width 600px, body text at least 14px, tap targets at least 44px, readable in dark mode (no light-grey text on white), and a plain-text part that mirrors the cards line for line.
- **Footer once per email, not per card:** DRAFT — PM approval required. Nothing is staged, nothing is armed.

**Worked cards (HTML intent, plain-text mirror):**

```
PK — closed above its entry line                      [BUY CONDITION MET]
Now 16.30 · Entry 16.20 (through by 0.6%) · Target 16.72 (2.6% away)
Committee: hold turned actionable — the range top gave way on the close.
Levels: stop 15.23 · targets 16.72 / 17.39 — information only, not sized

MRVL — near your stops                                          [HELD · WARN]
Now 238.00 · Your stop 233.85 (1.7% away) · Committee stop 234.65 (1.4% away)
Committee: exit on a close below 234.65. Your broker stop is the order in force.
```

**Test the look, not just the logic.** Render the email from the §4.8 replay to an HTML file and a plain-text file, and attach both to the PR. Screenshot at 390px and 600px widths.

---

## 3B. Distance in %: held book vs the day's shortlist

**Every % is measured from the current price:** `abs(level − price) / price × 100`, one decimal. Words carry the direction, never a sign alone: `1.7% away`, `0.4% to go`, `through by 0.6%`, `below by 0.8%`.

**Held names (class `HELD`): stops only. No entry, no target.**
- **Your stop** = `broker_stop.stop` (read from Tiger that morning). Label it "Your stop". If the row has no broker stop, show `Your stop — none` in red.
- **Committee stop** = `committee_exit` (a daily-close line). PMA guarantees it is never below your broker stop, so it is always the nearer of the two.
- **New alert: near your stops (WARN).** Fires when price is within `HELD_NEAR_PCT` (default **3.0%**) of *either* stop, or inside the existing `within_atr_of` band, whichever comes first. One key per held trigger id (`…|near`), so at most once per session; held rows are re-issued each morning, so it re-arms daily while the position is exposed.
- The existing held alerts (committee close below, no stop order, stop-limit set above its stop) use the same number line.

**Shortlisted names (`ADVANCE` and `HOLD_FOR_CONDITIONS`, today's run and carried rows): entry and target only. No stops on this line.**
- **Entry** = the row's ACTION trigger level (the ADVANCE entry, or the HOLD condition line).
- **Target** = the first value in `levels.tp` that sits above the entry. (For A on 29 Sep, `tp[0]` equals the entry 176.02, so the target shown is 185.48.) No `levels.tp` → drop the item.
- **New alert: approaching entry (WARN).** Fires when price is below the entry and within `SHORTLIST_NEAR_PCT` (default **1.5%**) of it. Key `…|nearentry`, once in the trigger's life.
- **New alert: approaching target (WARN).** Fires only after that name's entry has triggered, when price is within `SHORTLIST_NEAR_PCT` of the target. Key `…|neartp`, once in the trigger's life. This replaces the TP1-reached INFO.
- The computed stop stays on the collapsed Levels line of ACTION cards, labelled information only.

**After-close digest: two small tables at the top.**
- *Held book vs stops:* one row per held name, nearest first: `Ticker · Close · Your stop (%) · Committee stop (%)`.
- *Shortlist vs entry:* one row per shortlisted name, nearest entry first: `Ticker · Class · Close · Entry (%) · Target (%) · set on / day n of 3`.

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
3. **`src/alerts/emailer.py`:** add the committee section in §3A at the top of the existing digest, above ★ HELD. Leave every existing section, its order and its cards unchanged. The committee cards follow §3A and §3B exactly: three lines plus a levels line on ACTION cards, at most three labelled items on the number line (each with its % in brackets), plain words, colour by meaning, no AIC line. Held cards show your stop and the committee stop; shortlist cards show entry and target; never the other way round. The subject leads with committee items, then the existing subject bits.
4. **After-close digest:** the last cycle of the session (first poll at or after 16:00 ET) carries a short committee summary at the top of its email: confirmed closes, HOLD invalidations, and the WATCH list (doors, mp, distance from pivot).
5. **Config (`src/alerts/config.py`):** `PMA_LEVELS_ENABLED` (default true), `PMA_LEVELS_PATH` (default `aegis/output/pma/pma_levels.json`), `HELD_NEAR_PCT` (default 3.0) and `SHORTLIST_NEAR_PCT` (default 1.5).
6. **Workflow:** for the Space's fallback fetch, reuse whatever GitHub read credential AQE already holds; add an `AQE_GH_TOKEN` secret only if none exists, and say so in the PR. No schedule change is needed: the cron already covers 13:00–21:00 UTC, and the engine's New York market-hours gate handles daylight saving (the SGT window moves to 22:30–05:00 after 1 November).
7. **Tests (`tests/test_alert_pma_levels.py`):**
   - one test per trigger kind, including the final-cycle close logic and the WARN-then-ACTION pair;
   - stale file → no triggers plus the stale notice;
   - a WATCH row never triggers;
   - a `not_structured_yet` row never triggers;
   - `NEAR_STOP` suppressed when a broker stop is present;
   - a carried trigger that already fired is not re-sent the next day, and its key is pruned once the row leaves the file;
   - a `volume_min_x` shortfall → no ACTION;
   - volume missing → "volume unconfirmed";
   - **heartbeat unchanged:** a cycle with no PMA triggers renders subject, plain and HTML byte-identical to `main` today (golden test captured before any edit);
   - **% distances (§3B):** a held card carries "Your stop" and "Committee stop" with their %, and never "Entry" or "Target"; a shortlist card carries "Entry" and "Target" with their %, and never "Your stop"; a held row with no broker stop shows `Your stop — none`; the near-stops, approaching-entry and approaching-target WARNs fire at their thresholds and not one tick outside;
   - **committee card UX:** each card's number line carries at most three labelled items, and none of `trade_above`, `close_below`, a trigger id, `SC`, `β`, `R:R` or the AIC line appears in the committee section.
8. **Acceptance replay:** run `evaluate_pma` over `aegis/output/pma/pma_levels.json` (run 2026-09-29) with synthetic quotes. That first file predates run-stamping, so its ids read `A-entry`; from the next run they read `2026-09-30:A-entry`. It must produce:
   - at the first cycle: `WEAT-nostop` (ACTION) and `NTRA-ordertype` (ACTION);
   - A at `day_high` 176.10 → `A-entry` ACTION; at 178.90 → also `A-chase` WARN;
   - PK at `day_high` 16.25 → `PK-near` INFO; price 16.30 on the final cycle → `PK-cond` ACTION;
   - MRVL at 238.00 → near-stops WARN, card reads `Your stop 233.85 (1.7% away) · Committee stop 234.65 (1.4% away)`;
   - A at 175.40 → approaching-entry WARN, card reads `Entry 176.02 (0.4% to go) · Target 185.48 (5.7% away)`;
   - no trigger for any WATCH row, or for TMO/DT/ASX/VEEV/NTAP/CNK/TEAM conditions;
   - **window:** replay a second day with the same file plus one new run. A trigger that fired on day 1 must not fire again on day 2. A carried row must show "set 2026-09-29, day 2 of 3". A row absent from the new file must have its `pma_fired` key pruned.

**Guardrails to keep in the code:**
- no broker write scope anywhere in AQE;
- nothing AQE observes feeds back into PMA's votes (the alert ledger is for later grading only);
- the PM's broker stop is always the stop that email text calls "your stop".

---

## 5. What's still open

| Item | Owner |
|---|---|
| PMA: express the two-legged and "holds" conditions as structured pairs, so the 8 skipped rows become watchable | PMA (next build) |
| PMA: publish needs a byte-exact git push. Today the push goes through the GitHub connector as inline text; the first push had a one-digit slip that the read-back caught. Adding `TongIncomeWheel/AQE` to the session's authorised repositories lets `git_sync.py` push files directly. | **PM action, deferred (on mobile). Not blocking the AQE build.** |
| ~~Mailbox, WARN routing, phone push~~ **Settled (v2.3.1):** piggyback the existing AQE live-alerts feed; no change to mailbox, sender, cadence or channel. | Closed |
| GitHub read credential for the Space's fetch, if AQE doesn't already hold one | Claude Code flags it in the PR |

DRAFT — PM approval required. Nothing is staged, nothing is armed.
