"""Nick Crown Macro Layer — macro intelligence before position-taking.

Kernel v1.4, read top to bottom in the order the process demands (§4):

    Heartbeat -> (stop if unreadable) -> CTA + COT + Gamma -> Vol -> Divergence
    -> expression FAMILY -> size multiplier

STANDALONE BY DIRECTIVE (PM, 2026-08-09). This page reads nothing from SRM,
Macro Weather or the Thematic RRG, and nothing there reads this. Merging and
de-duplicating the three is a later, separate decision — keeping them apart for
now is what makes the overlap measurable instead of assumed.

The page owns no maths. Every number comes from `src.macro.crown`, and the run
is cached to `output/crown_macro.json` so a reload is free.
"""

from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

st.set_page_config(page_title="Crown Macro", page_icon=":anatomical_heart:",
                   layout="wide")

PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.ui.shared import require_login, table_with_copy  # noqa: E402

require_login()

import pandas as pd  # noqa: E402

from src.macro.crown import spec as S  # noqa: E402
from src.macro.crown.daily import load_crown, run_crown  # noqa: E402
from src.macro.scenarios import load_scenarios, run_scenarios  # noqa: E402

st.title("🫀 Nick Crown Macro Layer")
st.caption(
    "Positioning, breadth and regime **before** price. Kernel v1.4. "
    "Built standalone — it does not read SRM, Macro Weather or the Thematic RRG, "
    "and they do not read it."
)


def _pct(x, nd=1):
    return "—" if x is None else f"{float(x) * 100:.{nd}f}%"


def _num(x, nd=2):
    return "—" if x is None else f"{float(x):,.{nd}f}"


# ── run / load ────────────────────────────────────────────────────────────

left, right = st.columns([1, 3])
with left:
    go = st.button("▶️ Run Crown layer", use_container_width=True, type="primary")
    gamma_on = st.checkbox("Include gamma (slower)", value=False,
                           help="Pulls both option chains with open interest. "
                                "Needs Alpaca keys; degrades loudly without them.")
with right:
    st.caption("The run pulls RSP/SPY, 18 futures series, the VIX complex and the "
               "CFTC COT file. Cached to `output/crown_macro.json` — a reload is free.")

if go:
    with st.spinner("Running the hierarchy…"):
        try:
            crown = run_crown(with_gamma=gamma_on)
        except Exception as exc:
            st.error(f"Crown run failed: {exc}")
            crown = load_crown()
else:
    crown = load_crown()

if not crown:
    st.info("No Crown read yet. Press **Run Crown layer** above.")
    st.stop()

status = crown.get("crown_status")
banner = {"OK": st.success, "DEGRADED": st.warning,
          "EARLY_EXIT": st.warning, "UNAVAILABLE": st.error}.get(status, st.info)
banner(f"**{status}** — generated {crown.get('generated_at')}")

if crown.get("degraded"):
    with st.expander(f"⚠️ {len(crown['degraded'])} degraded input(s) — what is missing",
                     expanded=(status in ("UNAVAILABLE", "EARLY_EXIT"))):
        for d in crown["degraded"]:
            st.markdown(f"- {d}")

# ── freshness: as-of per source, against today ───────────────────────────
# The legs come from four publishers on four clocks. A single "generated at"
# would hide a source that quietly stopped updating, which is exactly how a
# stale panel once made the Heartbeat read two months behind everything else.
fresh = crown.get("freshness") or {}
if fresh:
    lag = fresh.get("oldest_leg_days")
    f1, f2, f3 = st.columns(3)
    f1.metric("Today", fresh.get("today", "—"))
    f2.metric("Oldest leg", fresh.get("oldest_leg") or "—",
              delta=(f"{lag}d behind" if lag else "current"),
              delta_color=("inverse" if (lag or 0) > S.MAX_BAR_STALENESS_DAYS else "off"))
    f3.metric("Newest leg", fresh.get("newest_leg") or "—")
    if (lag or 0) > S.MAX_BAR_STALENESS_DAYS:
        st.error(f"**This read is only as current as {fresh.get('oldest_leg')}.** "
                 "Every number below inherits that date, whatever the run "
                 "timestamp says.")

    with st.expander("Freshness by source — last bar vs today"):
        frows = []
        for name, s in (fresh.get("heartbeat") or {}).items():
            frows.append({"Source": f"Heartbeat · {name}", "As of": s.get("as_of"),
                          "Days behind": s.get("days_stale"), "Via": "panel/FMP"})
        for k, s in (fresh.get("cta_markets") or {}).items():
            frows.append({"Source": f"CTA · {k}", "As of": s.get("as_of"),
                          "Days behind": s.get("days_stale"),
                          "Via": f"{s.get('symbol')} ({s.get('via')})"
                                 + (" ⚠️STALE" if s.get("stale") else "")})
        v = fresh.get("volatility") or {}
        frows.append({"Source": "Volatility complex", "As of": v.get("as_of"),
                      "Days behind": None, "Via": v.get("source")})
        c_ = fresh.get("cot") or {}
        frows.append({"Source": "CFTC COT", "As of": c_.get("as_of"),
                      "Days behind": (c_.get("weeks_stale") or 0) * 7,
                      "Via": "cftc.gov (weekly)"})
        table_with_copy(pd.DataFrame(frows), key="crown_freshness",
                        label="📋 Copy freshness table")
        st.caption(
            "An ETF `via` means the futures symbol was unavailable or stale on "
            "our FMP plan and the tracking ETF stood in — trend direction holds, "
            "absolute levels are not the contract's. Markets are proxied rather "
            "than dropped because `flip_risk` is extremes ÷ markets, and a "
            "shrinking denominator silently re-rates every reading."
        )

# ── the decision, first, because it is what the hierarchy is FOR ─────────

dec = crown.get("decision") or {}
expr = dec.get("expression") or {}
fam = expr.get("family", "NONE")

st.header("The call")
c1, c2, c3, c4 = st.columns(4)
c1.metric("Expression family", fam.replace("_", " ").title(),
          help=(expr.get("playbook") or {}).get("context"))
c2.metric("Match", str(expr.get("match", "—")).upper())
c3.metric("Size multiplier", f"×{dec.get('size_multiplier', 0):.2f}",
          help="A multiplier on the PM's OWN risk budget. AQE does not size.")
c4.metric("Checklist", "PASSED" if dec.get("checklist_pass") else "FAILED")

if dec.get("early_exit"):
    st.error(
        "**Early exit.** Heartbeat confidence is below the "
        f"{S.HB_CONFIDENCE_GATE:.2f} gate, so §5 stopped the process and nothing "
        "downstream was computed. A market you cannot read is not one you take a "
        "smaller position in.\n\n"
        "Sections 2–4 below are therefore **empty because they were never run**, "
        "not because the readings came back quiet."
    )

pb = expr.get("playbook") or {}
if fam != "NONE":
    st.markdown(f"**Context** — {pb.get('context', '')}")
    pc1, pc2, pc3 = st.columns(3)
    pc1.markdown(f"**Equity**\n\n{pb.get('equity', '—')}")
    pc2.markdown(f"**Pair**\n\n{pb.get('pair', '—')}")
    pc3.markdown(f"**Options**\n\n{pb.get('options', '—')}")
    st.caption(
        "The regime dictates the allowed **family**. The individual setup — VWAP "
        "pullback, Donchian break, divergence confirmation — comes after, and is "
        "not this layer's job."
    )

with st.expander("Why this family — every condition, met and unmet"):
    met, unmet = expr.get("conditions_met") or [], expr.get("conditions_unmet") or []
    st.markdown("**Met:** " + (", ".join(f"`{m}`" for m in met) or "_none_"))
    st.markdown("**Unmet:** " + (", ".join(f"`{u}`" for u in unmet) or "_none_"))
    cands = expr.get("candidates") or []
    if cands:
        st.dataframe(pd.DataFrame([
            {"Family": c["family"], "Score": f"{c['score']:.0%}",
             "Met": ", ".join(c["met"]), "Unmet": ", ".join(c["unmet"])}
            for c in cands]), use_container_width=True, hide_index=True)
    st.caption(f"Size derivation: {dec.get('size_derivation', '—')}")

with st.expander("Audit trail (§4 rhythm, step by step)"):
    for m in dec.get("messages", []):
        st.text(m)

st.divider()

# ── 1. Heartbeat ──────────────────────────────────────────────────────────

hb = crown.get("heartbeat") or {}
st.header("1 · Heartbeat — what kind of market is this?")
st.caption("RSP / SPY. Rising = the average stock is winning. Falling = the "
           "leaders carry everything. Range position says when the wave is tired.")

h1, h2, h3, h4, h5 = st.columns(5)
h1.metric("Regime", str(hb.get("regime", "—")).upper())
h2.metric("Range position", str(hb.get("range_position", "—")).upper(),
          help="Where RSP/SPY sits in its own 252-day range.")
h3.metric("Ratio", _num(hb.get("ratio"), 4))
h4.metric("20d slope", f"{hb.get('slope_20d'):.6f}" if hb.get("slope_20d") is not None else "—",
          help=f"|slope| must exceed {S.HB_SLOPE_EPS} to count as a regime.")
h5.metric("Confidence", _num(hb.get("confidence")),
          help=f"Gate is {S.HB_CONFIDENCE_GATE}. Below it, the process stops.")
st.info(f"**{hb.get('bias', '—')}**")
st.caption(hb.get("rationale", ""))

# ── 2. Positioning ────────────────────────────────────────────────────────

st.header("2 · Positioning — who is in, and how crowded?")

cta = crown.get("cta") or {}
mkts = crown.get("cta_markets") or {}
cot = crown.get("cot") or {}
gam = crown.get("gamma") or {}

t1, t2, t3, t4 = st.columns(4)
t1.metric("CTA bias", str(cta.get("overall_bias", "—")).replace("_", " ").upper())
t2.metric("Flip risk", _pct(cta.get("flip_risk")),
          help="Share of markets at a trend extreme. Crowded trends are fragile.")
t3.metric("CTA size dial", f"×{cta.get('size_adjustment', 1.0):.2f}")
t4.metric("Markets scored", str(cta.get("n_markets", 0)))

if cta.get("sector_bias"):
    st.caption("Sector bias — " + " · ".join(
        f"**{k}** {v:+.2f}" for k, v in cta["sector_bias"].items()))

rows = []
for key, r in sorted(mkts.items()):
    if r.get("signal") is None:
        rows.append({"Market": key, "Name": r.get("label"), "Sector": r.get("sector"),
                     "Signal": None, "Price": None, "Vol ann": None,
                     "Flip 1d": None, "Flip 1d %": None, "Flip 20d": None,
                     "COT %ile": None, "COT extreme": r.get("reason")})
        continue
    flips = {f["horizon"]: f for f in (r.get("flips") or [])}
    cot_m = (cot.get("markets") or {}).get(key) or {}
    rows.append({
        "Market": key, "Name": r.get("label"), "Sector": r.get("sector"),
        "Signal": r.get("signal"), "Price": r.get("price"),
        "Vol ann": r.get("vol_ann"),
        "Flip 1d": (flips.get(1) or {}).get("level"),
        "Flip 1d %": (flips.get(1) or {}).get("distance_pct"),
        "Flip 20d": (flips.get(20) or {}).get("level"),
        "COT %ile": cot_m.get("percentile"),
        "COT extreme": cot_m.get("extreme"),
    })

if rows:
    st.subheader("CTA trend model — and the levels where it flips")
    st.caption(
        "Replicated from the public method (Moskowitz-Ooi-Pedersen time-series "
        "momentum at 2/6/12 months + Faber's 10-month average), vol-normalised. "
        "**The flip level is the useful column** — it is arithmetic, not anyone's "
        "book. Our positioning estimate will NOT match Goldman's; the flip levels "
        "will be close."
    )
    table_with_copy(pd.DataFrame(rows), key="crown_cta", label="📋 Copy CTA table")

with st.expander("CFTC Commitment of Traders — large-spec positioning"):
    if not cot:
        st.info("Not computed — the process stopped at the Heartbeat gate.")
    elif cot.get("status") != "OK":
        st.warning(f"COT unavailable: {cot.get('reason') or cot.get('status')}")
    else:
        st.caption(
            f"As of **{cot.get('as_of')}** ({cot.get('weeks_stale')} weeks stale). "
            "Straight from cftc.gov — FMP gates COT behind Premium, the CFTC "
            "publishes it free. Reports Tuesday's book on Friday, so it can time "
            "nothing; it is a slow context dial for §2.5's positioning divergence."
        )
        cl, cs = cot.get("crowded_long") or [], cot.get("crowded_short") or []
        cc1, cc2 = st.columns(2)
        cc1.markdown("**Crowded long:** " + (", ".join(cl) or "_none_"))
        cc2.markdown("**Crowded short:** " + (", ".join(cs) or "_none_"))
        crows = [{"Market": k, "Contract": v.get("name"),
                  "Net spec": v.get("net_spec"), "% of OI": v.get("net_spec_pct_oi"),
                  "Percentile": v.get("percentile"), "WoW Δ%OI": v.get("wow_change_pct_oi"),
                  "Weeks": v.get("weeks_of_history"), "Extreme": v.get("extreme")}
                 for k, v in sorted((cot.get("markets") or {}).items())]
        if crows:
            table_with_copy(pd.DataFrame(crows), key="crown_cot", label="📋 Copy COT table")

st.subheader("Gamma — the short-term structural force")
if not gam:
    st.info("Not computed — the process stopped at the Heartbeat gate.")
elif gam.get("status") != "OK":
    st.warning(f"Gamma unavailable — {gam.get('reason')}")
    st.caption(
        "A gamma map needs **open interest** and **both** rights. The CSP adapter "
        "fetches puts only and skips OI by design, so this is a separate call. "
        "An unavailable map is reported as unavailable: a zeroed profile would "
        "read as 'dealers are neutral', which is a different claim entirely."
    )
else:
    for sym, prof in (gam.get("underlyings") or {}).items():
        g1, g2, g3, g4 = st.columns(4)
        g1.metric(f"{sym} gamma regime", prof.get("regime"))
        g2.metric("Gamma flip", _num(prof.get("gamma_flip")),
                  delta=(f"{prof.get('flip_distance_pct'):+.2f}%"
                         if prof.get("flip_distance_pct") is not None else None))
        cw, pw = prof.get("call_wall") or {}, prof.get("put_wall") or {}
        g3.metric("Call wall", _num(cw.get("strike")))
        g4.metric("Put wall", _num(pw.get("strike")))
        st.caption(f"**{sym}** — {prof.get('interpretation')}")
        if prof.get("profile"):
            st.bar_chart(pd.DataFrame(prof["profile"]).set_index("strike")["gex"],
                         height=200)
    st.caption("⚠️ " + (next(iter((gam.get("underlyings") or {}).values()), {})
                        .get("assumption", "")))

st.divider()

# ── 3. Volatility ─────────────────────────────────────────────────────────

vol = crown.get("volatility") or {}
disp = vol.get("dispersion") or {}
st.header("3 · Volatility — the true risk regime")
st.caption("VIX is **not** a fear gauge here. It is the price of 30-day SPX vol. "
           "The tool Crown trades is single-stock vol minus index vol.")

if not vol:
    st.info("Not computed — the process stopped at the Heartbeat gate.")

v1, v2, v3, v4, v5 = st.columns(5)
v1.metric("VIX", _num(vol.get("vix")))
v2.metric("VIXEQ (single-stock)", _num(disp.get("single_stock_vol")))
v3.metric("Spread", _num(disp.get("spread")),
          delta=(f"{disp.get('spread_20d_change'):+.2f} (20d)"
                 if disp.get("spread_20d_change") is not None else None))
v4.metric("Percentile (2y)", _pct(disp.get("percentile")),
          help=f"Full history: {_pct(disp.get('percentile_full_history'))}")
v5.metric("State", str(disp.get("state", "—")).replace("_", " "))

if disp.get("state") == "ELEVATED_EASING":
    st.info(
        "**Elevated but easing.** The spread sits in the top band, yet it has "
        f"*fallen* {abs(disp.get('spread_20d_change') or 0):.2f} points over 20 "
        "sessions. §2.4's practical rule is directional — a **rising** spread is "
        "hidden stress. An elevated spread that is unwinding is stress *leaving* "
        "the market, and buying downside into it buys the end of the move. Level "
        "and direction are shown separately because they routinely disagree."
    )

if disp.get("basis") == "realised":
    st.warning(
        "**This is the REALISED proxy, not the implied VIXEQ − VIX spread.** "
        "The Cboe VIXEQ series could not be fetched, so this is the mean 30-day "
        "realised vol across the universe minus SPY's. It asks the same question "
        "of bars we hold, but it lags and carries none of the forward-looking "
        "volatility risk premium that makes the implied version tradeable."
    )
elif vol.get("source") == "cboe":
    st.caption("Source: **cboe.com** direct — Cboe computes these indices and "
               "publishes the full history free. FMP gates VIXEQ, VIX3M and "
               "VIX9D above our plan.")

corr = vol.get("corroboration") or {}
if corr.get("dspx") is not None:
    cc1, cc2, cc3 = st.columns(3)
    cc1.metric("DSPX (Cboe dispersion)", _num(corr.get("dspx")),
               help="Cboe's purpose-built S&P 500 Dispersion Index — the same "
                    "question, built by the people who define the inputs.")
    cc2.metric("DSPX percentile", _pct(corr.get("dspx_percentile")))
    cc3.metric("Implied correlation", _num(corr.get("implied_correlation")),
               delta=_pct(corr.get("correlation_percentile")) + " pctl",
               delta_color="off",
               help="Index variance is constituent variance × correlation, so a "
                    "collapsing correlation IS a widening spread. It must move "
                    "opposite — if it stops, the spread is wrong.")
    if corr.get("agrees") is False:
        st.warning(f"⚠️ {corr.get('note')}")
    else:
        st.caption(corr.get("note") or "")

rules = vol.get("rules") or {}
r1, r2, r3 = st.columns(3)
r1.metric("Hidden stress", "YES" if rules.get("hidden_stress") else "no",
          help="Dispersion elevated AND rising → favour defined-risk downside "
               "or reduce risk. Level alone is not the rule.")
r2.metric("Very low VIX", "YES" if rules.get("very_low_vix") else "no",
          help=f"VIX < {S.VIX_VERY_LOW}. With positive gamma → premium-selling.")
r3.metric("Already priced", "YES" if rules.get("already_priced") else "no",
          help=f"VIX ≥ {S.VIX_ELEVATED}. Protection is already expensive — not a "
               "fresh sell signal.")

ts = vol.get("term_structure") or {}
if ts.get("available"):
    st.caption(f"Term structure — VIX9D {_num(ts.get('vix9d'))} · "
               f"VIX {_num(ts.get('vix'))} · VIX3M {_num(ts.get('vix3m'))} → "
               f"**{ts.get('shape')}**")

st.divider()

# ── 4. Divergence ─────────────────────────────────────────────────────────

div = crown.get("divergence") or {}
st.header("4 · Divergence — where momentum is failing behind price")
st.caption(div.get("note", ""))

if not div:
    st.info("Not computed — the process stopped at the Heartbeat gate.")
else:
    dm1, dm2 = st.columns([1, 3])
    dm1.metric("Warnings lit", div.get("weight", 0),
               help="Independent non-confirmations currently firing. §2.5: "
                    "divergence is most powerful when several agree.")
    cov = div.get("coverage") or {}
    dm2.caption(
        f"Coverage — RSI across **{cov.get('rsi_series', 0)}** series · "
        f"**{cov.get('confirmers', 0)}** cross-asset confirmers · "
        f"**{cov.get('cot_contracts', 0)}** COT contracts · "
        f"VIX {'✅' if cov.get('vix') else '—'} · "
        f"breadth {'✅' if cov.get('breadth') else '—'} · "
        f"dispersion {'✅' if cov.get('dispersion') else '—'}. "
        "A skipped check is never shown as a passed one."
    )

    # ── the everyday read: price direction vs RSI direction, 5d and 20d ──
    slope = div.get("rsi_slope") or {}
    hbma = div.get("breadth_ma") or {}
    if slope.get("windows"):
        st.subheader("Price vs RSI — 5d and 20d")
        srow = []
        for w in sorted(slope["windows"], key=lambda x: int(x)):
            v = slope["windows"][w]
            srow.append({"Window": f"{w}d",
                         "Price Δ%": v.get("price_change_pct"),
                         "RSI Δ pts": v.get("rsi_change_pts"),
                         "RSI then": v.get("rsi_then"), "RSI now": v.get("rsi_now"),
                         "Read": v.get("state", "").replace("_", " ")})
        sc1, sc2 = st.columns([2, 3])
        with sc1:
            st.dataframe(pd.DataFrame(srow), use_container_width=True, hide_index=True)
            verdict = slope.get("state", "NONE")
            if verdict == "BEARISH_DIVERGENCE":
                st.error(f"⚠️ **Both windows agree** — {slope.get('why')}")
            elif verdict == "BULLISH_DIVERGENCE":
                st.success(f"**Both windows agree (bullish)** — {slope.get('why')}")
            elif verdict == "MIXED":
                st.info(f"**One horizon only** — {slope.get('why')}")
            else:
                st.caption("Price and RSI are not pulling apart at either horizon.")
        with sc2:
            ser = slope.get("series") or {}
            if ser.get("dates"):
                chart = pd.DataFrame({"date": pd.to_datetime(ser["dates"]),
                                      "close": ser["close"], "rsi": ser["rsi"]}
                                     ).set_index("date")
                st.caption("Index (rebased to 100) vs RSI-14")
                rebased = chart["close"] / chart["close"].iloc[0] * 100
                st.line_chart(pd.DataFrame({"index (rebased)": rebased,
                                            "RSI-14": chart["rsi"]}), height=220)
        st.caption(
            "Shown at both horizons because that is the thing worth looking at — "
            "but a **single** window is a readout, not a warning. Measured on "
            "trending random walks with no divergence structure, the 20d window "
            "alone fires on **14.1%** of days (a bounded oscillator drifting off "
            "its plateau is what a healthy trend looks like); both windows "
            "agreeing fires on **0.6%**. For the strict form — a higher swing "
            "high on a lower RSI high — see *RSI (index)* below, which compares "
            "confirmed pivots over 120 sessions, because a 20-day window cannot "
            "hold two comparable highs."
        )

    if hbma.get("windows"):
        st.subheader(f"Breadth vs its own {hbma.get('ma_window', 20)}d average")
        hc1, hc2 = st.columns([2, 3])
        with hc1:
            hrow = [{"Window": f"{w}d",
                     "Index Δ%": v.get("price_change_pct"),
                     "RSP/SPY Δ%": v.get("breadth_ratio_change_pct"),
                     "Read": v.get("state", "").replace("_", " ")}
                    for w, v in sorted(hbma["windows"].items(), key=lambda x: int(x[0]))]
            st.dataframe(pd.DataFrame(hrow), use_container_width=True, hide_index=True)
            st.metric(f"Distance to {hbma.get('ma_window', 20)}d MA",
                      f"{hbma.get('distance_to_ma_pct'):+.2f}%"
                      if hbma.get("distance_to_ma_pct") is not None else "—",
                      delta="below" if hbma.get("below_ma") else "above",
                      delta_color="inverse" if hbma.get("below_ma") else "normal")
            if hbma.get("state") == "BREADTH_MA_DIVERGENCE":
                st.error(f"⚠️ {hbma.get('why')}")
            else:
                st.caption(hbma.get("why") or "")
        with hc2:
            hs = hbma.get("series") or {}
            if hs.get("dates"):
                st.caption("RSP/SPY against its own moving average")
                st.line_chart(pd.DataFrame(
                    {"RSP/SPY": hs["ratio"], f"{hbma.get('ma_window', 20)}d MA": hs["ma"]},
                    index=pd.to_datetime(hs["dates"])), height=220)
        st.caption(
            "This one fires on the RATIO's own move, not on the change in its "
            "distance to the average — that gap is self-damping, because the "
            "average chases the ratio and stabilises even while breadth "
            "deteriorates outright. The gap level is shown as context."
        )

    st.subheader("All checks")
    checks = [
        ("RSI (pivots)", div.get("rsi")),
        ("RSI (5d/20d)", div.get("rsi_slope")),
        ("Cross-asset", div.get("cross_asset")),
        ("VIX", div.get("vix")),
        ("Breadth regime", div.get("breadth")),
        ("Breadth vs MA", div.get("breadth_ma")),
        ("Dispersion", div.get("dispersion")),
        ("Positioning", div.get("positioning")),
    ]
    cols = st.columns(len(checks))
    for col, (label, block) in zip(cols, checks):
        state = (block or {}).get("state", "—")
        col.metric(label, "—" if state in (None, "NONE") else state.replace("_", " "))

    for label, block in checks:
        b = block or {}
        detail = b.get("why") or b.get("reason")
        if detail:
            fired = b.get("state") not in (None, "NONE", "CONFIRMED")
            st.markdown(f"- {'⚠️' if fired else '·'} **{label}** — {detail}")

    smat = div.get("slope_matrix") or {}
    if smat.get("scanned"):
        with st.expander(f"5d/20d read across {smat['scanned']} series"):
            st.markdown("**Both windows bearish:** " +
                        (", ".join(f"`{s}`" for s in smat.get("bearish") or []) or "_none_"))
            st.markdown("**Both windows bullish:** " +
                        (", ".join(f"`{s}`" for s in smat.get("bullish") or []) or "_none_"))
            rows = []
            for k, v in sorted((smat.get("by_series") or {}).items()):
                w = v.get("windows") or {}
                rows.append({
                    "Series": k,
                    "5d price Δ%": (w.get("5") or {}).get("price_change_pct"),
                    "5d RSI Δ": (w.get("5") or {}).get("rsi_change_pts"),
                    "20d price Δ%": (w.get("20") or {}).get("price_change_pct"),
                    "20d RSI Δ": (w.get("20") or {}).get("rsi_change_pts"),
                    "RSI now": v.get("rsi_now"),
                    "Read": str(v.get("state", "")).replace("_", " "),
                })
            if rows:
                table_with_copy(pd.DataFrame(rows), key="crown_slope_matrix",
                                label="📋 Copy 5d/20d read")

    mat = div.get("rsi_matrix") or {}
    if mat.get("scanned"):
        with st.expander(f"RSI divergence matrix (pivots) — {mat['scanned']} series scanned"):
            if mat.get("bearish"):
                st.markdown("**Bearish:** " + ", ".join(f"`{s}`" for s in mat["bearish"]))
            if mat.get("bullish"):
                st.markdown("**Bullish:** " + ", ".join(f"`{s}`" for s in mat["bullish"]))
            if not mat.get("bearish") and not mat.get("bullish"):
                st.caption("No divergence on any scanned series.")
            rows = [{"Series": k, "State": v.get("state"),
                     "Prior": (v.get("prior") or {}).get("price"),
                     "Prior RSI": (v.get("prior") or {}).get("rsi"),
                     "Latest": (v.get("latest") or {}).get("price"),
                     "Latest RSI": (v.get("latest") or {}).get("rsi"),
                     "Why": v.get("why") or v.get("reason")}
                    for k, v in sorted((mat.get("by_series") or {}).items())]
            if rows:
                table_with_copy(pd.DataFrame(rows), key="crown_rsi_matrix",
                                label="📋 Copy RSI matrix")

    pm = div.get("positioning_matrix") or {}
    if pm.get("scanned"):
        with st.expander(f"Positioning sweep — {pm['scanned']} COT contracts"):
            st.markdown("**Diverging:** " +
                        (", ".join(f"`{s}`" for s in pm.get("diverging") or []) or "_none_"))
            rows = [{"Market": k, "State": v.get("state"),
                     "Price rising": v.get("price_rising"),
                     "COT %ile": v.get("cot_percentile"),
                     "Extreme": v.get("cot_extreme"), "Why": v.get("why")}
                    for k, v in sorted((pm.get("by_market") or {}).items())]
            if rows:
                table_with_copy(pd.DataFrame(rows), key="crown_pos_matrix",
                                label="📋 Copy positioning sweep")

st.divider()

# ── 5. Macro scenarios — the first merge point ───────────────────────────

st.header("5 · Macro scenarios")
st.caption(
    "Macro Weather's seven instruments (TLT · UUP · HYG · IWM · GLD · CPER · USO) "
    "read together with Crown's dispersion, implied correlation, CTA bias and "
    "breadth. **This is the first merge point** — Crown itself stays standalone."
)

if st.button("🔄 Re-run scenario read", key="crown_scenarios"):
    with st.spinner("Pulling macro instruments…"):
        try:
            st.session_state["crown_scen"] = run_scenarios(crown=crown)
        except Exception as exc:
            st.error(f"Scenario read failed: {exc}")

# The daily pipeline writes this at step 6g; the button only refreshes it.
scen = st.session_state.get("crown_scen") or load_scenarios()
if not scen:
    st.info("No scenario read yet — the daily pipeline writes one at step 6g, "
            "or press **Re-run scenario read**.")
elif scen.get("status") != "OK":
    st.warning(f"Scenarios unavailable: {scen.get('reason')}")
else:
    for d in scen.get("degraded", []):
        st.warning(f"⚠️ {d}")
    s1, s2, s3 = st.columns(3)
    s1.metric("Leading", str(scen.get("leading") or "NONE").replace("_", " ").title())
    s2.metric("Score", _pct(scen.get("leading_score")) if scen.get("leading_score")
              is not None else "—", help="Share of conditions met — NOT a probability.")
    s3.metric("Contested", "YES" if scen.get("contested") else "no")
    st.info(scen.get("reading", ""))

    for s in scen.get("scenarios", []):
        lead = s["scenario"] == scen.get("leading")
        head = (f"{'🏁 ' if lead else ''}{s['scenario'].replace('_', ' ').title()} — "
                f"{s['score']:.0%} of conditions · {s['coverage']:.0%} coverage")
        with st.expander(head, expanded=lead):
            st.markdown(f"_{s['story']}_")
            if s.get("caveat"):
                st.warning(s["caveat"])
            e1, e2 = st.columns(2)
            with e1:
                st.markdown("**Evidence for**")
                for e in s["evidence"] or ["_none_"]:
                    st.markdown(f"- {e}")
            with e2:
                st.markdown("**What is missing** (the falsifiers)")
                for e in s["missing_conditions"] or ["_nothing — all met_"]:
                    st.markdown(f"- {e}")
            if s.get("unavailable"):
                st.caption("Not evaluable: " + " · ".join(s["unavailable"]))
            st.markdown(f"**Expression family** — {s['expression']}")

    st.caption(scen.get("note", ""))

st.divider()
st.caption(
    f"Kernel v{crown.get('kernel_version')} · {crown.get('standalone_note')}"
)
