#!/usr/bin/env python3
"""bracket_calc.py — AEGIS BRACKET calculator.

AUTHORED 2026-08-25. The /bracket skill's step 5 has always named
`tools/bracket_calc.py`, but no such file existed anywhere in the repo
(checked aegis/tools/ — 50 files — and aegis/tools/calculators/ — 7 files).
The skill has therefore been unrunnable end-to-end since it was written.
This is that missing tool, built to the skill's own step-6 output contract.

Deterministic. No model in the path. Same input -> same output.

PRICE CHAIN (PM ruling 2026-08-25, supersedes D-98 — see D-99):
    1. FMP `quote-short`         — primary. Works on the Starter plan.
                                   `quote` / `batch-quote` are Premium-gated;
                                   `quote-short` is NOT. Do not confuse them.
    2. IBKR `get_price_snapshot` — on the stale/gap flag below, or on demand.
                                   Genuinely REALTIME, and covers premarket.
    3. AQE prior close           — declared last resort.
  Yahoo is not in the chain. Tiger is not in the chain: it TRADES equities
  (`place_stock_order` is live) but exposes no equity QUOTE tool — its own
  greeks/HV/roll tools reach out to yfinance and FMP for spot, which is the
  tell.

THE STALENESS FLAG is why the chain has a step 2 at all. Premarket, FMP
`quote-short` returns the PRIOR CLOSE, not a 15-minute-delayed print — there
is no session yet to be delayed behind. So an FMP price equal to the AQE
reference is stale BY CONSTRUCTION, and on a gapping name every downstream
number (risk%, R:R, stop distance) is computed against a price that no longer
exists. Measured 2026-08-25 on CRM: FMP 209.06 vs IBKR live 204.45 (-2.21%),
which flipped the ATR flag from PASS (1.00) to FAIL (0.42) on the same stop.

SIZING is an exact port of aegis/tools/calculators/sizing.py (constitution
law 4: the ONLY place sizing arithmetic lives). It is not re-derived here.

Anything this file had to DEFINE rather than inherit is tagged AUTHORED.
"""
import json, argparse, math, sys, signal

try:
    signal.signal(signal.SIGPIPE, signal.SIG_DFL)   # don't traceback under `| head`
except (AttributeError, ValueError):
    pass

R_LADDER = [0.5, 1.0, 2.0]
GAP_PCT = 1.0          # AUTHORED: |live - AQE ref| above this = flag as gapped
SAME_TOL = 0.005       # price treated as identical to the AQE reference


def _f(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def pick_stop(inp):
    """PM override -> AQE structural -> AQE ATR fallback -> 20MA (skill step 6.2)."""
    if _f(inp.get("stop_override")) is not None:
        return _f(inp["stop_override"]), "PM override", "pm"
    b = (inp.get("aqe") or {}).get("bracket") or {}
    if b.get("valid") and _f(b.get("stop")) is not None:
        return _f(b["stop"]), f"AQE structural [{b.get('stop_type')}]", "aqe_structural"
    if _f(b.get("atr_fallback_stop")) is not None:
        return _f(b["atr_fallback_stop"]), "AQE ATR fallback [FB]", "aqe_fallback"
    ma20 = _f((inp.get("aqe") or {}).get("ma_20"))
    if ma20 is not None:
        return ma20, "20MA (kernel-derived, NOT AQE-scored)", "ma20"
    return None, None, None


def price_quality(inp, price):
    """Label the price. Never rewrite it. Returns (lines, stale_bool)."""
    src = (inp.get("price") or {}).get("source")
    aqe = inp.get("aqe") or {}
    b = aqe.get("bracket") or {}
    ref = _f(b.get("price")) or _f(aqe.get("entry"))
    premarket = not inp.get("intraday_bars")
    lines, stale = [], False
    if ref is None:
        return ["no AQE reference to compare against"], False
    delta = price - ref
    pct = delta / ref * 100
    if src == "fmp":
        if abs(delta) < SAME_TOL:
            stale = True
            lines.append(f"FMP quote-short {price} == AQE reference {ref}")
            lines.append("*** STALE BY CONSTRUCTION — premarket, this IS the prior close, not a "
                         "delayed print. PULL IBKR BEFORE QUEUEING THIS NAME. ***" if premarket else
                         "*** price has not moved off the prior close — verify against IBKR. ***")
        else:
            lines.append(f"FMP quote-short {price} vs AQE reference {ref}: {delta:+.2f} ({pct:+.2f}%) "
                         "— a real intraday print, ~15min delayed")
    elif src == "ibkr":
        pc = _f(inp.get("prior_close"))
        if pc is not None:
            ok = "RECONCILES" if abs(pc - ref) < SAME_TOL else f"MISMATCH vs AQE ref {ref}"
            lines.append(f"IBKR prior_close {pc} vs AQE reference {ref} — {ok}")
        lines.append(f"IBKR live {price} vs AQE reference {ref}: {delta:+.2f} ({pct:+.2f}%)")
    else:
        lines.append(f"{src} {price} vs AQE reference {ref}: {delta:+.2f} ({pct:+.2f}%)")
    if abs(pct) >= GAP_PCT and not stale:
        lines.append(f"*** GAPPED {pct:+.2f}% off the AQE reference — every level below is measured "
                     "from the LIVE price, not the export's. ***")
    return lines, stale


def flags(price, stop, atr, rr, ceiling):
    """LABELS ONLY — a failed flag never withholds a line (PM ruling 29 Jul, D-38)."""
    out = []
    atr_dist = (price - stop) / atr if (atr and stop is not None) else None
    out.append(("ATR", atr_dist is not None and atr_dist >= 1.0,
                f"stop is {atr_dist:.2f} ATR from price" if atr_dist is not None else "no ATR served"))
    out.append(("R:R", rr is not None and rr >= 2.0,
                f"rr {rr:.2f}" if rr is not None else "rr not computable (no validated target)"))
    risk_pct = (price - stop) / price * 100 if stop else None
    out.append(("CEILING", risk_pct is not None and ceiling is not None and risk_pct <= ceiling,
                f"risk {risk_pct:.2f}% vs regime ceiling {ceiling}%" if risk_pct is not None else "n/a"))
    return out, atr_dist, risk_pct


def ladder(inp, price, stop):
    b = (inp.get("aqe") or {}).get("bracket") or {}
    risk = price - stop if stop is not None else None
    rows = []
    for t in (b.get("targets") or []):
        p = _f(t.get("price"))
        if p is None or risk in (None, 0):
            continue
        rows.append({"type": t.get("type"), "price": p, "tp": t.get("tp"),
                     "r": (p - price) / risk, "atr_dist": t.get("atr_dist"),
                     "vol_ratio": t.get("vol_ratio"), "vol_validated": t.get("vol_validated"),
                     "date": t.get("date")})
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True)
    a = ap.parse_args()
    inp = json.load(open(a.input)) if a.input != "-" else json.load(sys.stdin)

    tk = inp["ticker"]
    price = _f((inp.get("price") or {}).get("value"))
    src = (inp.get("price") or {}).get("source")
    tier = inp.get("tier")
    aqe = inp.get("aqe") or {}
    b = aqe.get("bracket") or {}
    atr = _f(aqe.get("atr_14d"))
    ceiling = _f(inp.get("regime_stop_pct_ceiling"))
    r_mult = _f(inp.get("r_multiple")) or 1.0

    print("=" * 96)
    print(f"BRACKET · {tk} · authority {inp.get('authority','PM_DISCRETION')} · r_multiple {r_mult}")
    print("=" * 96)
    if price is None:
        print("REFUSED — no price from FMP, IBKR or the export. No price, no bracket.")
        return

    tierlabel = {"aqe": "AQE-scored", "aqe_single": "AQE single-ticker",
                 "20ma": "20MA fallback — NOT AQE-scored"}.get(tier, tier)
    print(f"1 · TIER + PRICE   {tierlabel} · price {price} from {src}")
    q, stale = price_quality(inp, price)
    for line in q:
        print(f"                   {line}")

    stop, label, basis = pick_stop(inp)
    if stop is None:
        print("2 · STOP           REFUSED — no stop from AQE, 20MA or override. Cannot size.")
        return
    rr_served = _f(b.get("rr")) if basis == "aqe_structural" else None
    fl, atr_dist, risk_pct = flags(price, stop, atr, rr_served, ceiling)
    print(f"2 · STOP           {stop}  [{label}]")
    for name, passed, why in fl:
        print(f"                     {'PASS' if passed else 'FLAG'}  {name:8s} {why}")
    if basis != "aqe_structural" and b.get("invalid_reason"):
        print(f"                     note: {b['invalid_reason']}")
    rps = price - stop
    print(f"                   risk/share ${rps:.2f} · {risk_pct:.2f}% of price")
    if stale:
        print("                   ^ computed off a STALE price — re-run with IBKR before acting.")

    alts = []
    for k, nm in (("ma_20", "ma20"), ("ma_50", "ma50"), ("ma_100", "ma100"), ("ma_200", "ma200")):
        v = _f(aqe.get(k))
        if v is not None and v < price:
            alts.append((nm, v, (price - v) / price * 100, (price - v) / atr if atr else None))
    fb = _f(b.get("atr_fallback_stop"))
    if fb is not None and basis != "aqe_fallback" and fb < price:
        alts.append(("atr_fallback", fb, (price - fb) / price * 100, (price - fb) / atr if atr else None))
    if alts:
        print("3 · ALTERNATIVES   (PM may pick instead — never auto-selected)")
        for nm, v, pct, ad in sorted(alts, key=lambda x: -x[1]):
            print(f"                     {nm:14s} {v:>10.2f}   {pct:5.2f}% away" + (f"   {ad:.2f} ATR" if ad else ""))

    if not inp.get("intraday_bars"):
        print("4 · ENTRY ZONE     kind=levels_only")
        print("                     No intraday tape — premarket. Levels only.")
    else:
        print("4 · ENTRY ZONE     kind=watch — intraday_bars supplied but intraday_read.py is not wired in")

    rows = ladder(inp, price, stop)
    if rows:
        print(f"5 · TP LADDER      (source: {'aqe' if tier in ('aqe','aqe_single') else '20ma'})")
        for r in rows:
            v = "vol-VALIDATED" if r["vol_validated"] else ("not validated" if r["vol_ratio"] is not None else "no vol data")
            tp = f"[{r['tp']}] " if r.get("tp") else ""
            d = f" dated {r['date']}" if r.get("date") else ""
            print(f"                     {tp}{r['type']:14s} {r['price']:>10.2f}  {r['r']:>6.2f}R  {r['atr_dist']}atr  {v}{d}")
    else:
        print("5 · TP LADDER      none served")

    tp2 = next((r for r in rows if r.get("tp") == "TP2"), None)
    if tp2:
        print(f"6 · R:R to TP2     {tp2['r']:.2f}R  (target {tp2['price']})")
    else:
        cands = [r for r in rows if r["r"] and r["r"] > 0]
        if cands:
            best = max(cands, key=lambda r: r["r"])
            print(f"6 · R:R to TP2     no TP2 tagged. Best served level: {best['type']} {best['price']} = {best['r']:.2f}R")
        else:
            print("6 · R:R to TP2     not computable — no served level above price")

    dyncap = _f(inp.get("dyncap"))
    one_r_pct = _f(inp.get("one_r_pct"))
    vol_cap_pct = _f(inp.get("vol_cap_pct"))
    vol30 = _f(aqe.get("vol_30d_ann"))
    sized = None
    if dyncap is None or dyncap <= 0 or one_r_pct is None:
        print("7 · SIZE           NOT COMPUTED — dynCap unavailable "
              "(config/aegis_fund.md dyncap_usd, refreshed each premarket from the Aegis PTJ).")
    else:
        # EXACT port of aegis/tools/calculators/sizing.py
        r_budget = dyncap * one_r_pct / 100.0 * r_mult
        s_r = math.floor(r_budget / rps)
        if vol30 and 0 < vol30 < 3 and vol_cap_pct:
            daily_vol = vol30 / math.sqrt(252)
            s_v = math.floor((vol_cap_pct / 100.0 * dyncap) / (price * daily_vol))
        else:
            s_v = None
        if s_v is None:
            shares, who = s_r, "R-size (vol_30d_ann not served — vol-cap step SKIPPED)"
        else:
            shares = min(s_r, s_v)
            who = "vol-cap" if s_v < s_r else "R-size"
        sized = {"shares": shares, "risk_usd": shares * rps, "expo": shares * price}
        print(f"7 · SIZE           R-budget ${r_budget:,.2f} ({one_r_pct}% of dynCap x {r_mult}R)")
        print(f"                     R-size    {s_r:>6} sh")
        print(f"                     vol-cap   {(str(s_v) if s_v is not None else 'n/a'):>6} sh"
              + (f"   ({vol_cap_pct}% of dynCap / (px x daily_vol {vol30/math.sqrt(252)*100:.2f}%))" if s_v is not None else ""))
        print(f"                     >>> TAKE  {shares:>6} sh   ${shares*price:,.0f} exposure   "
              f"${shares*rps:,.0f} at risk   capped by {who}")

    print("8 · R LADDER       shares and $risk at each conviction step")
    if dyncap and one_r_pct:
        for m in R_LADDER:
            rb = dyncap * one_r_pct / 100.0 * m
            sh = math.floor(rb / rps)
            print(f"                     {m:>4}R   {sh:>6} sh   ${sh*rps:>9,.0f} at risk   ${sh*price:>10,.0f} exposure")
    else:
        print("                     dynCap unavailable — expressed per $1,000 of R:")
        for m in R_LADDER:
            sh = math.floor((1000 * m) / rps)
            print(f"                     {m:>4}R   {sh:>6} sh per $1,000 R   (risk/share ${rps:.2f})")

    bk = inp.get("book") or {}
    if not sized or not bk or not dyncap:
        print("9 · SECTOR BLOCK   OMITTED — needs dynCap, a sized position and the book state.")
        print()
        return
    sec = aqe.get("gics_sector") or "NONE"
    add_expo, add_risk = sized["expo"], sized["risk_usd"]
    beta = _f(aqe.get("beta_30d")) or 0.0
    se = dict(bk.get("sector_exposure") or {})
    e0 = bk.get("book_exposure", 0.0); r0 = bk.get("book_stop_risk", 0.0); b0 = bk.get("book_beta_exp", 0.0)
    s0 = se.get(sec, 0.0); s1 = s0 + add_expo
    top0 = max(se.values()) if se else 0.0
    se2 = dict(se); se2[sec] = s1
    top1 = max(se2.values()) if se2 else 0.0
    print(f"9 · SECTOR BLOCK   sector {sec} ({aqe.get('gics_sector_name')}) · tone {inp.get('sector_tone')}")
    print(f"                   {'metric':28s} {'before':>12} {'after':>12}   gate")

    def row(nm, x, y, g):
        print(f"                   {nm:28s} {x:>12} {y:>12}   {g}")
    row("this sector % of dynCap", f"{s0/dyncap*100:.2f}%", f"{s1/dyncap*100:.2f}%", "soft 25 / hard 35")
    row("top-sector % of dynCap", f"{top0/dyncap*100:.2f}%", f"{top1/dyncap*100:.2f}%", "soft 25 / hard 35")
    row("leverage x dynCap", f"{e0/dyncap:.2f}x", f"{(e0+add_expo)/dyncap:.2f}x", "soft 2.5 / hard 3.0")
    row("portfolio beta", f"{b0/dyncap:.4f}", f"{(b0+add_expo*beta)/dyncap:.4f}", "soft 2.0 / hard 2.5")
    row("combined stop risk %", f"{r0/dyncap*100:.2f}%", f"{(r0+add_risk)/dyncap*100:.2f}%", "max 12%")
    breaches = []
    if s1 / dyncap * 100 > 35: breaches.append(f"{sec} sector {s1/dyncap*100:.1f}% > hard 35%")
    if top1 / dyncap * 100 > 35: breaches.append(f"top-sector {top1/dyncap*100:.1f}% > hard 35%")
    if (e0 + add_expo) / dyncap > 3.0: breaches.append("leverage > hard 3.0x")
    if (r0 + add_risk) / dyncap * 100 > 12: breaches.append("combined stop risk > 12%")
    print("                   *** HARD GATE BREACH ON THE POST-ADD BOOK: " + "; ".join(breaches) + " ***"
          if breaches else "                   no hard gate breached on the post-add book")
    # max size that keeps THIS sector inside the hard gate
    head = dyncap * 0.35 - s0
    if head > 0:
        cap_sh = min(math.floor(head / price), sized["shares"])
        rb = dyncap * one_r_pct / 100.0
        print(f"                   GATE-CONSTRAINED MAX: {cap_sh} sh "
              f"(= {cap_sh*rps/rb:.2f}R, ${cap_sh*rps:,.0f} at risk) keeps {sec} under hard 35%")
    else:
        print(f"                   GATE-CONSTRAINED MAX: 0 sh — {sec} is ALREADY at or over the hard 35% gate")
    print()


if __name__ == "__main__":
    main()
