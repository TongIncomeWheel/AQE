#!/usr/bin/env python3
"""BRACKET — queue levels for a committee-approved or PM-discretion name.
Never run against a name already held (that's the exits/trailing-stop path).

Deterministic (law 4): no network, no model. The orchestrator (skills/bracket)
gathers live prices (Tiger primary, FMP fallback — D-98, IBKR retired), the AQE record if one exists, the journal
(dynCap, current held book for the sector simulation), and optional intraday
bars — assembles them into the input shape below — and this module does the
arithmetic.

INPUT (JSON, passed via --input or stdin):
{
  "ticker": "AAPL",
  "date": "2026-07-29",
  "price": {"value": 231.40, "source": "tiger|fmp"},
  "authority": "COMMITTEE_ADVANCE" | "PM_DISCRETION",
  "tier": "aqe" | "aqe_single" | "20ma",
  "aqe_record": { ... daily_list row, or null ...},           # tier aqe/aqe_single
  "history_20d": [{"date":..,"open":..,"high":..,"low":..,"close":..}, ...] | null,  # tier 20ma
  "intraday_bars": [ ...5-min OHLCV... ] | null,               # null pre-open
  "regime": {"level": "YELLOW", ...} | null,
  "regime_stop_pct_ceiling": 8.0 | null,
  "dyncap": {"value": 65761.65, "one_r": 986.42},
  "r_multiple": 1.0,                                            # from parameters.yaml sizes, PM picks tier
  "vol_30d_ann": 0.42 | null,
  "sector": "XLK" | null,
  "sector_tone": "TAILWIND|NEUTRAL|HEADWIND" | null,
  "open_positions": [{"ticker","sector","exposure_usd","beta","risk_usd"}, ...],
  "stop_override": null | number
}

OUTPUT: see build_bracket() docstring.
"""
from __future__ import annotations

import json
import os
import sys

import numpy as np
import yaml

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))

from calculators import sizing, book_sim  # noqa: E402
import intraday_read  # noqa: E402

MIN_ATR_RATIO = 1.0
MIN_RR_TP2 = 2.0


def load_params(dyncap=None):
    """Sizing parameters. ONE RISK FIGURE (BUILD_PLAN Phase 1, 2026-11-01): when config/aegis_fund.md carries
    one_r_usd (PM 2026-10-27: $620 fixed), the R budget is that dollar figure, expressed here as the percent of
    dynCap that reproduces it exactly so sizing.size() needs no second code path. Otherwise the legacy
    parameters.yaml percent rule applies. `one_r_source` says which was used -- never silent."""
    p = yaml.safe_load(open(os.path.join(ROOT, "charter", "parameters.yaml")))
    cap = p.get("capital", {})
    out = {
        "one_r_pct": cap.get("one_r_pct_of_dyncap", 1.5),
        "one_r_source": "parameters.yaml capital.one_r_pct_of_dyncap",
        "one_r_usd": None,
        "sizes": cap.get("sizes", {"standard_r": 1.0, "high_conviction_r": 2.0}),
        "vol_cap_pct": cap.get("vol_cap_pct_of_dyncap", {}),
    }
    try:
        import fund_config
        fixed = fund_config.one_r_usd()
    except Exception as e:                       # a missing/broken fund file is reported, not hidden
        out["one_r_source"] += f" (fund config unreadable: {e.__class__.__name__})"
        fixed = None
    if fixed is not None:
        out["one_r_usd"] = fixed
        out["one_r_source"] = "config/aegis_fund.md one_r_usd (PM 2026-10-27, fixed $)"
        if dyncap:
            out["one_r_pct"] = fund_config.one_r_pct_equivalent(dyncap)
    return out


def _num(v):
    return v if isinstance(v, (int, float)) and not isinstance(v, bool) else None


# ── STOP: AQE structural is the default. Everything else is a labelled
# suggestion, never a competitor (PM ruling 29 Jul — no invented default). ──
def pick_stop(entry: float, aqe_record: dict | None, intraday_bars: list | None,
              history_20d: list | None, atr14: float | None, tp2: float | None,
              ceiling_pct: float | None, stop_override: float | None) -> dict:
    ceiling_pct = ceiling_pct if ceiling_pct is not None else 8.0

    def _score(price, typ):
        risk = entry - price
        if risk <= 0:
            return None
        atr_ratio = (risk / atr14) if atr14 else None
        rr_tp2 = ((tp2 - entry) / risk) if tp2 else None
        stop_pct = risk / entry * 100.0
        return {
            "type": typ, "price": round(price, 2), "risk": round(risk, 2),
            "atr_ratio": round(atr_ratio, 2) if atr_ratio is not None else None,
            "rr_tp2": round(rr_tp2, 2) if rr_tp2 is not None else None,
            "stop_pct": round(stop_pct, 2),
            "flags": {
                "atr_ok": bool(atr_ratio is not None and atr_ratio >= MIN_ATR_RATIO),
                "rr_ok": bool(rr_tp2 is not None and rr_tp2 >= MIN_RR_TP2),
                "ceiling_ok": bool(stop_pct <= ceiling_pct),
            },
        }

    default = None
    default_source = None
    bracket = (aqe_record or {}).get("bracket") or {}
    struct_stop = _num(bracket.get("stop"))
    fallback_stop = _num(bracket.get("atr_fallback_stop"))
    if struct_stop is not None and struct_stop < entry:
        default = _score(struct_stop, "aqe_structural")
        default_source = "aqe_structural"
    elif fallback_stop is not None and fallback_stop < entry:
        default = _score(fallback_stop, "aqe_atr_fallback")
        default_source = "aqe_atr_fallback"

    if stop_override is not None:
        default = _score(stop_override, "pm_override")
        default_source = "pm_override"

    suggestions = []
    if intraday_bars:
        bars = intraday_read.normalize_bars(intraday_bars)
        if bars:
            comp_price = bars[-1]["c"]
            vwaps = intraday_read._vwap_series(bars)
            vwap = vwaps[-1] if vwaps else None
            iatr = intraday_read._intraday_atr(bars)
            # intraday swing low (fractal, k=3)
            k = 3
            lows = [b["l"] for b in bars]
            if len(lows) >= 2 * k + 1:
                for i in range(len(lows) - k - 1, k - 1, -1):
                    seg = lows[i - k:i + k + 1]
                    if lows[i] <= min(seg) and lows[i] < entry:
                        s = _score(round(lows[i], 2), "intraday_swing_low")
                        if s:
                            suggestions.append(s)
                        break
            if vwap is not None and iatr:
                s = _score(vwap - 0.5 * iatr, "vwap_buffer")
                if s:
                    suggestions.append(s)
            by_day = {}
            for b in bars:
                by_day.setdefault(b["dt"].date(), []).append(b)
            days = sorted(by_day)
            if len(days) >= 2:
                s = _score(min(x["l"] for x in by_day[days[-2]]), "prior_day_low")
                if s:
                    suggestions.append(s)

    if history_20d and default is None:
        # 20MA fallback path — only reachable when AQE gave nothing at all.
        closes = [float(b["close"]) for b in history_20d[-20:] if b.get("close") is not None]
        if closes:
            sma20 = float(np.mean(closes))
            if sma20 < entry:
                default = _score(sma20, "20ma_fallback")
                default_source = "20ma_fallback"

    return {"default": default, "default_source": default_source, "suggestions": suggestions}


def twenty_ma_atr(history_20d: list) -> tuple:
    """Returns (sma20, atr14) from ~20-25 daily OHLC bars. Pure math, no network."""
    if not history_20d:
        return None, None
    bars = sorted(history_20d, key=lambda b: b.get("date", ""))
    closes = [float(b["close"]) for b in bars if b.get("close") is not None]
    sma20 = float(np.mean(closes[-20:])) if len(closes) >= 1 else None
    trs = []
    for i in range(1, len(bars)):
        h, l, pc = float(bars[i]["high"]), float(bars[i]["low"]), float(bars[i - 1]["close"])
        trs.append(max(h - l, abs(h - pc), abs(l - pc)))
    atr14 = float(np.mean(trs[-14:])) if len(trs) >= 1 else None
    return (round(sma20, 2) if sma20 else None, round(atr14, 3) if atr14 else None)


def tp_ladder(aqe_record: dict | None, history_20d: list | None, entry: float) -> tuple:
    """Returns (ladder, source). AQE targets first; 20MA path uses the recent swing high
    or a fixed 2R objective, clearly sourced."""
    bracket = (aqe_record or {}).get("bracket") or {}
    tgts = bracket.get("targets") or []
    above = sorted(
        [{"type": t.get("type"), "price": t["price"]} for t in tgts
         if isinstance(t, dict) and _num(t.get("price")) and t["price"] > entry],
        key=lambda x: x["price"])
    if above:
        return above[:3], "aqe"
    if history_20d:
        highs = [float(b["high"]) for b in history_20d if b.get("high") is not None]
        swing_high = max(highs) if highs else None
        if swing_high and swing_high > entry:
            return [{"type": "20d_swing_high", "price": round(swing_high, 2)}], "20ma"
        return [{"type": "fixed_2r", "price": round(entry * 1.04, 2)}], "20ma"
    return [], "none"


def build_bracket(inp: dict) -> dict:
    params = load_params(dyncap=(inp.get("dyncap") or {}).get("value"))
    ticker = inp["ticker"]
    entry = inp["price"]["value"]
    price_source = inp["price"].get("source")
    tier = inp.get("tier", "aqe")
    aqe_record = inp.get("aqe_record")
    history_20d = inp.get("history_20d")
    intraday_bars = inp.get("intraday_bars")
    regime = inp.get("regime") or {}
    ceiling_pct = inp.get("regime_stop_pct_ceiling")
    dyncap = (inp.get("dyncap") or {}).get("value")
    one_r = (inp.get("dyncap") or {}).get("one_r")
    r_multiple = inp.get("r_multiple", params["sizes"].get("standard_r", 1.0))
    vol_30d_ann = inp.get("vol_30d_ann")
    sector = inp.get("sector")
    sector_tone = inp.get("sector_tone", "NEUTRAL-UNKNOWN")
    open_positions = inp.get("open_positions") or []
    stop_override = inp.get("stop_override")
    authority = inp.get("authority", "PM_DISCRETION")

    atr14 = _num((aqe_record or {}).get("atr_14d"))
    ladder, ladder_source = tp_ladder(aqe_record, history_20d, entry)
    tp2 = ladder[1]["price"] if len(ladder) >= 2 else (ladder[0]["price"] if ladder else None)

    if atr14 is None and history_20d:
        _, atr14 = twenty_ma_atr(history_20d)

    stop_block = pick_stop(entry, aqe_record, intraday_bars, history_20d, atr14, tp2,
                            ceiling_pct, stop_override)
    default_stop = stop_block["default"]

    # Entry zone: intraday tape if present (a live queue shape), else levels-only.
    tape_read = None
    if intraday_bars:
        tape_read = intraday_read.intraday_read(intraday_bars, aqe_record or {})
        zone = intraday_read.entry_zone_from_state(tape_read, aqe_record.get("entry") if aqe_record else None)
    else:
        zone = {"kind": "levels_only", "low": None, "high": None,
                "note": "No intraday tape (premarket or bars unavailable) — queue off AQE/20MA structure."}

    out = {
        "ticker": ticker, "date": inp.get("date"), "authority": authority,
        "tier": tier, "price": {"value": entry, "source": price_source},
        "regime": regime.get("level"), "regime_stop_pct_ceiling": ceiling_pct,
        "tape_read": tape_read, "entry_zone": zone,
        "stop": default_stop, "stop_suggestions": stop_block["suggestions"],
        "tp_ladder": ladder, "tp_ladder_source": ladder_source,
    }

    if default_stop is None:
        out["warning"] = "NO STOP DEFINABLE — refusing to size. AQE gave nothing, 20MA fallback failed, no PM override."
        out["size"] = None
        out["sector"] = None
        return out

    risk_per_share = default_stop["risk"]
    rr = round((tp2 - entry) / risk_per_share, 2) if (tp2 and risk_per_share) else None
    out["rr_to_tp2"] = rr

    if dyncap is None or dyncap <= 0:
        out["warning"] = f"dynCap unavailable or non-positive ({dyncap}) — refusing to size."
        out["size"] = None
    else:
        vol_cap_pct = params["vol_cap_pct"].get(regime.get("level"), 1.5) if isinstance(params["vol_cap_pct"], dict) else params["vol_cap_pct"]
        try:
            sz = sizing.size(dyncap=dyncap, one_r_pct=params["one_r_pct"], r_multiple=r_multiple,
                              entry=entry, stop=default_stop["price"],
                              vol_30d_ann=vol_30d_ann if vol_30d_ann else 0.30,
                              vol_cap_pct=vol_cap_pct)
            sz["vol_30d_ann_used"] = vol_30d_ann if vol_30d_ann else "0.30 (default — vol_30d_ann unavailable, flagged)"
            sz["one_r_source"] = params["one_r_source"]      # which risk figure sized this -- never silent
            out["size"] = sz
            out["r_ladder"] = book_sim.size_scenarios(entry=entry, stop=default_stop["price"],
                                                        dyncap=dyncap, one_r_pct=params["one_r_pct"])
        except ValueError as e:
            out["warning"] = f"sizing refused: {e}"
            out["size"] = None

    # Sector block — mandatory (PM ruling). Feeds both this printout and the
    # gatekeeper's post-add check 5, same book_sim call, same numbers.
    if dyncap and dyncap > 0 and out.get("size") and sector:
        shares = out["size"]["shares"]
        exposure_usd = round(shares * entry, 2)
        beta = _num((aqe_record or {}).get("beta_30d")) or 0.0
        risk_usd = out["size"]["risk_usd"]
        try:
            sim = book_sim.simulate(open_positions, [{"op": "ADD", "ticker": ticker, "sector": sector,
                                                        "exposure_usd": exposure_usd, "beta": beta,
                                                        "risk_usd": risk_usd}], dyncap)
            out["sector"] = {
                "gics_sector": sector, "live_tone": sector_tone,
                "exposure_pct_before": sim["before"]["sector_exposure_pct"].get(sector, 0.0),
                "exposure_pct_after": sim["after"]["sector_exposure_pct"].get(sector, 0.0),
                "top_sector_pct_before": sim["before"]["top_sector_pct"],
                "top_sector_pct_after": sim["after"]["top_sector_pct"],
                "portfolio_beta_before": sim["before"]["portfolio_beta"],
                "portfolio_beta_after": sim["after"]["portfolio_beta"],
                "combined_stop_risk_pct_before": sim["before"]["combined_stop_risk_pct"],
                "combined_stop_risk_pct_after": sim["after"]["combined_stop_risk_pct"],
            }
        except (ValueError, ZeroDivisionError) as e:
            out["sector"] = {"error": f"sector simulation failed: {e}"}
    else:
        out["sector"] = None

    # Quality flags — soft, never a rejection (PM ruling 29 Jul: no structural
    # stop and a failed R:R gate are both explicitly NOT grounds to refuse).
    out["flags"] = default_stop.get("flags")

    return out


def main(argv=None):
    import argparse
    ap = argparse.ArgumentParser(description="Bracket calculator — queue levels, no verdict")
    ap.add_argument("--input", default=None, help="path to input JSON; omit to read stdin")
    ap.add_argument("--out", default=None, help="path to write output JSON; omit to print")
    a = ap.parse_args(argv)
    raw = open(a.input).read() if a.input else sys.stdin.read()
    inp = json.loads(raw)
    result = build_bracket(inp)
    text = json.dumps(result, indent=1)
    if a.out:
        open(a.out, "w").write(text)
        print(f"bracket written to {a.out}")
    else:
        print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
