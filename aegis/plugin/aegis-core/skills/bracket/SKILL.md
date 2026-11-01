---
name: bracket
description: "Aegis process skill — BRACKET. For a name NOT currently held (you don't bracket something you already own). Callable any time, repeated any number of times. Given a ticker, produces queue levels — entry zone, stop, TP ladder, R:R, size, sector impact. No committee guard: PM discretion is a valid reason to bracket a name on its own. Deterministic tool (tools/bracket_calc.py) does the arithmetic; this skill only gathers live inputs (Tiger primary price, FMP fallback — D-98, IBKR retired) and prints the result on screen. No verdict, no gate, no record kept."
model: sonnet
---

# PROCESS: BRACKET — queue levels, not a decision

**The decision is already made by the time this runs.** Either the committee advanced the name, or the PM picked it on discretion — both are equally valid reasons to be here (PM ruling, 29 Jul: "I will make my own decision of which ticket to trade with or without a committee"). This skill does not re-argue the idea. It answers one question: **where do I queue this.**

**Callable any time, any number of times (PM ruling, 29 Jul).** Not a one-shot morning step. Run it premarket to plan, run it again at 11am if the price moved, run it on a name nobody nominated. Nothing here is scheduled, nothing here stands anything down for tomorrow.

**No committee guard.** This skill does not check today's committee file, does not check today's plan, does not ask permission. The PM's own hand on the ticker is the authority. That authority is *recorded* (see step 6), never *checked*.

**No record kept (PM ruling, 29 Jul: "old brackets don't matter").** Nothing here writes a bracket log. If the bracket is accepted, it gets staged and the fill becomes the record via the normal journal path — that's a position, not a bracket history. If it's declined, nothing persists. Screen only.

---

## Input: `TICKER`, and nothing else required

**This skill is never run against a held name.** You don't bracket something you already own — that's the trailing-stop/exits path, a different skill. `TICKER` here is always a name outside the book.

## STEP 1 — Live price (Tiger primary, FMP fallback)
**D-98: IBKR retired.** Tiger now serves equity spot for a name outside the book. Resolve Tiger's live equity-quote tool the same portable way the broker prefix is discovered elsewhere in this kernel (never hardcode a literal connector name — it can register under a different prefix per environment). Older material in this repo (including a prior version of this file, and Tiger's own connector docs as of an earlier snapshot) claimed Tiger had no equity spot-quote tool and routed through IBKR instead — that route no longer exists. If a live Tiger equity-quote call is genuinely refused, treat it exactly like any other broker-tool absence: fall through to FMP and flag it, do not silently assume the old IBKR path.

| Call | On failure |
|---|---|
| Tiger's live equity quote (spot/last) | fall through to FMP `quote` |
| FMP `quote` | **refuse — no price, no bracket** |

FMP is ~15-min delayed — flag it plainly whenever it's the one used. Record `{"value": <price>, "source": "tiger"|"fmp"}`.

## STEP 2 — Which data tier
Check `output/aqe_daily_export.json`, `daily_list`, for `TICKER`.

| Found? | Tier | What step 3 gathers |
|---|---|---|
| Yes | **`aqe`** | that row's `bracket`, `atr_14d`, `beta_30d`, `vol_30d_ann`, `gics_sector`, `regime`, `regime_stop_pct_ceiling` — verbatim, nothing recomputed |
| No, but a fresher single-ticker AQE file exists (PM triggered AQE on this one name manually, per PM ruling 29 Jul: "I can manually run AQE in a one ticker") | **`aqe_single`** | same as above — validate against `contracts/aqe_export.schema.json` (or the single-ticker equivalent) before use, same as any AQE input |
| No, and no single-ticker file | **`20ma`** | pull ~25 trading days of daily OHLC via FMP historical, pass as `history_20d` — the tool computes the 20-day SMA and ATR-14 itself. **This is a kernel-derived level, not an AQE-scored one — say so on the line, every time.** |

## STEP 3 — Intraday tape (skip entirely premarket — there is no tape before the open)
If the market is open: fetch 5-min bars for today via FMP `chart`, pass as `intraday_bars`. The tool reads them as a **measurement only** — six components, a composite score, a state label (`tools/intraday_read.py`) — never a verdict. It shapes *where* the entry zone sits (limit / stop-breakout / now / watch), nothing more.

If premarket, or bars are unavailable: pass `intraday_bars: null`. The bracket prints `entry_zone.kind = "levels_only"` and says plainly there is no tape yet — never fabricates one.

## STEP 4 — dynCap, sector book, sector tone
- `dyncap` and `one_r`: read straight from today's journal (refreshed each premarket from the PTJ mark-to-market). Never recomputed here.
- `open_positions`: today's journal `open_positions`, reshaped to `{ticker, sector, exposure_usd, beta, risk_usd}` — `exposure_usd = qty × entry`, `risk_usd = qty × (entry − stop)`, `beta` from that name's own last AQE record if available, else 0. `TICKER` itself is never in this list (step 1's whole premise).
- `sector_tone`: read `data/intraday/<DATE>/sector_pulse.json` if it exists (from `srm_live.py`, run separately); else pass `"NEUTRAL-UNKNOWN"` and say so.

## STEP 5 — Run the calculator
```
python3 tools/bracket_calc.py --input <assembled JSON>
```
Set `"authority": "PM_DISCRETION"` unless today's committee file genuinely carries an ADVANCE for this ticker, in which case `"authority": "COMMITTEE_ADVANCE"`. This is a record of where the idea came from, carried on the output — nothing here checks it, nothing here gates on it.

`r_multiple` — default `1.0` (`1.0 [RB:capital.sizes.standard_r]`). If the PM states high conviction, use `2.0` (`sizes.high_conviction_r`) instead; say which was used.

## STEP 6 — Print on screen, tabular, nothing filed
Required, in this order:

1. **Tier + price source line** — e.g. "AQE-scored · price from Tiger" or "20MA fallback — not AQE · price from FMP, ~15min delayed."
2. **Stop** — the default (AQE structural, else AQE ATR fallback, else 20MA, else PM override) with its three flags (ATR / R:R / ceiling) shown as **labels, never a rejection** — a failed flag never removes the line, per PM ruling 29 Jul that neither a missing structural stop nor a failed R:R gate is grounds to refuse.
3. **Stop suggestions**, if any (intraday swing low / VWAP buffer / prior-day low) — clearly marked as alternatives the PM may pick instead, never auto-selected.
4. **Entry zone** — kind, low/high, the one-line reason.
5. **TP ladder** with source (`aqe` or `20ma`).
6. **R:R to TP2.**
7. **Size** — R-size, vol-cap size, the smaller one chosen, which one capped it. If dynCap is unavailable or non-positive, **no share count** — say why, in plain words, and still show everything above it.
8. **R ladder** — 0.5R / 1R / 2R shares and dollar risk, so the PM picks conviction rather than being handed one number.
9. **Sector block** — sector, live tone, exposure % before/after this add, portfolio beta before/after, combined stop-risk % before/after, top-sector % before/after. If dynCap or sizing failed upstream, this block is omitted and it says why.

Nothing here is written to disk. If the PM wants it staged, that is a separate, explicit next step — this skill does not offer to stage it.

## ON FAILURE
- No price from Tiger or FMP → refuse outright. Nothing prints.
- No stop definable from any tier and no override given → refuse to size; the calculator's own refusal message is shown verbatim.
- dynCap missing or ≤ 0 → levels and R:R still print; size and sector block do not; the reason is shown verbatim, not swallowed.
- AQE export missing or stale for tier `aqe` → fall through to tier `aqe_single` or `20ma`, say which, never silently use yesterday's file.

## WHAT THIS SKILL MUST NOT DO
- Must not run against a held name — that's a different skill (exits/trailing-stop).
- Must not fall back to IBKR for price — that connector is retired (D-98); Tiger is primary, FMP is the only fallback.
- Must not check today's committee file or today's plan as a precondition to running.
- Must not emit ENTER / CAUTION / STAND_DOWN or any other verdict.
- Must not treat a failed ATR/R:R/ceiling flag as a reason to withhold levels.
- Must not invent a stop when AQE, the 20MA fallback, and the PM override are all absent — refuse instead.
- Must not write a bracket log, a file, or a phone notification. Screen only.
- Must not mention or route through the staging gatekeeper — bracket's job ends at printing levels.
