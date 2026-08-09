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

v1, v2, v3, v4 = st.columns(4)
v1.metric("VIX", _num(vol.get("vix")))
v2.metric("Dispersion spread", _num(disp.get("spread")),
          delta=(f"{disp.get('spread_20d_change'):+.2f} (20d)"
                 if disp.get("spread_20d_change") is not None else None))
v3.metric("Spread percentile", _pct(disp.get("percentile")))
v4.metric("Band", str(disp.get("band", "—")))

if disp.get("basis") == "realised":
    st.warning(
        "**This is the REALISED proxy, not the implied VIXEQ − VIX spread.** "
        "`^VIXEQ` is not available on our FMP Starter plan, so this is the mean "
        "30-day realised vol across the universe minus SPY's. It asks the same "
        "question of the data we hold, but it lags and carries none of the "
        "forward-looking volatility risk premium that makes the implied version "
        "tradeable. Do not read it as the number §2.4 describes."
    )

rules = vol.get("rules") or {}
r1, r2, r3 = st.columns(3)
r1.metric("Hidden stress", "YES" if rules.get("hidden_stress") else "no",
          help="Elevated dispersion → favour defined-risk downside or reduce risk.")
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

d1, d2, d3 = st.columns(3)
d1.metric("RSI", (div.get("rsi") or {}).get("state", "—"))
d2.metric("Cross-asset", (div.get("cross_asset") or {}).get("state", "—"))
d3.metric("Positioning", (div.get("positioning") or {}).get("state", "—"))

for label, block in (("RSI", div.get("rsi")), ("Cross-asset", div.get("cross_asset")),
                     ("Positioning", div.get("positioning"))):
    b = block or {}
    detail = b.get("why") or b.get("reason")
    if detail:
        st.markdown(f"- **{label}** — {detail}")

st.divider()
st.caption(
    f"Kernel v{crown.get('kernel_version')} · {crown.get('standalone_note')}"
)
