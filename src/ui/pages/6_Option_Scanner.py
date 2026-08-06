"""AQE Universe Option Scanner — a filterable theta scanner for the income wheel.

Sweeps the whole AQE universe for cash-secured puts worth selling (data from Alpaca's
free option-chain snapshot — IV + greeks + quotes, one call per name, no throttle).
Reads the nightly sweep `output/options_scan.json`; you filter it live (annualised
yield / delta band / DTE / POP / cushion). Recommend-only — AQE computes the numbers,
the AIC decides + sizes. Can also run an on-demand sweep on a typed ticker subset.
"""

from __future__ import annotations

import os
import sys
import json
from datetime import date
from pathlib import Path

import streamlit as st

st.set_page_config(page_title="AQE Option Scanner", page_icon=":ok:", layout="wide")

PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.ui.shared import require_login, table_with_copy, OUTPUT_DIR  # noqa: E402

require_login()

import pandas as pd  # noqa: E402
from src.options import config as OC  # noqa: E402

SCAN_FILE = OUTPUT_DIR / "options_scan.json"

st.title("🎯 Universe Option Scanner — CSP theta")
st.caption("Cash-secured puts across the AQE universe · Alpaca-fed · recommend-only "
           "(AQE computes numbers; the AIC decides + sizes).")


def _load_scan() -> dict | None:
    """Local file first, then DRIVE — the sweep must survive a restart.

    The container's output/ is ephemeral: every deploy, sleep or crash wiped
    the sweep and the page said "no scan yet", so the PM re-ran a five-minute
    Alpaca sweep to look at numbers that already existed. The sweep has always
    been published to the CSP Drive folder; nothing was reading it back. Drive
    is the source of truth between runs here exactly as it is for the universe,
    the alert ledger and the daily export.
    """
    if SCAN_FILE.exists():
        try:
            return json.loads(SCAN_FILE.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            pass
    try:
        from src.data import gdrive_uploader
        if gdrive_uploader.is_configured():
            folder = os.environ.get("GDRIVE_CSP_FOLDER_ID", OC.GDRIVE_CSP_FOLDER_ID)
            txt = gdrive_uploader.download_text(Path(OC.UNIVERSE_SCAN_FILE).name,
                                                folder_id=folder)
            if txt:
                blob = json.loads(txt)
                # Re-seed the local copy so the next render is instant and the
                # scheduler's own date-marker read sees it.
                try:
                    SCAN_FILE.parent.mkdir(parents=True, exist_ok=True)
                    SCAN_FILE.write_text(txt, encoding="utf-8")
                except Exception:  # noqa: BLE001
                    pass
                return blob
    except Exception as exc:  # noqa: BLE001
        st.caption(f"Drive copy unreachable ({type(exc).__name__}) — local only.")
    return None


# ── Run a scan (full universe → Drive, or a local subset) ───────────────────
with st.expander("↻ Run a scan", expanded=True):
    have_keys = bool(os.environ.get(OC.ALPACA_KEY_ID_ENV) and
                     os.environ.get(OC.ALPACA_SECRET_ENV))
    if not have_keys:
        st.info(f"Set **{OC.ALPACA_KEY_ID_ENV}** + **{OC.ALPACA_SECRET_ENV}** as "
                "deploy secrets to enable live scans.")
    subset = st.text_input("Subset tickers (comma list; used by the local button)", "")
    c1, c2 = st.columns(2)
    dmin = c1.number_input("DTE min", 1, 365, OC.UNIVERSE_DTE_MIN)
    dmax = c2.number_input("DTE max", 1, 365, OC.UNIVERSE_DTE_MAX)
    b1, b2 = st.columns(2)
    run_full = b1.button("🚀 Run full scan → Drive", disabled=not have_keys,
                         use_container_width=True,
                         help="Sweep the whole AQE universe and overwrite the single "
                              "CSP file in the Drive folder.")
    run_sub = b2.button("Run subset (local only)",
                        disabled=not have_keys or not subset.strip(),
                        use_container_width=True)
    # Re-upload the EXISTING local scan to Drive — no re-scan, no Alpaca keys needed.
    if st.button("⬆️ Re-upload existing scan → Drive", use_container_width=True,
                 disabled=not SCAN_FILE.exists(),
                 help="Push the current output/options_scan.json to the Drive folder "
                      "without re-scanning. Use when you already have the JSON."):
        from src.options.universe_scan import republish_scan_to_drive
        with st.spinner("Uploading options_scan.json to Drive…"):
            _rr = republish_scan_to_drive(str(SCAN_FILE))
        if _rr.get("ok"):
            st.success(f"Uploaded **{OC.CSP_SCAN_FILENAME}** → Drive "
                       f"({'replaced' if _rr.get('replaced') else 'created'}).")
        else:
            st.warning(f"Upload: {_rr.get('reason')}")
    if run_full or run_sub:
        from src.options.universe_scan import (scan_universe, write_scan,
                                               export_scan_to_drive)
        tk = ([t.strip().upper() for t in subset.split(",") if t.strip()]
              if run_sub else None)
        with st.spinner("Scanning… full universe ≈ a few minutes"):
            blob = scan_universe(tickers=tk, dte_min=int(dmin), dte_max=int(dmax),
                                 log=lambda *_: None)
            if run_full:
                res = export_scan_to_drive(blob, str(SCAN_FILE))
                dr = res["drive"]
                if dr.get("ok"):
                    st.success(f"Scanned {blob['candidates_count']} candidates → Drive "
                               f"({'replaced' if dr.get('replaced') else 'created'} "
                               f"`{OC.CSP_SCAN_FILENAME}`).")
                else:
                    st.warning(f"Scanned {blob['candidates_count']} — saved locally; "
                               f"Drive upload failed: {dr.get('reason')}")
            else:
                write_scan(blob, str(SCAN_FILE))
                st.success(f"Scanned {blob['candidates_count']} candidates (local).")
        st.rerun()

scan = _load_scan()
if not scan:
    st.warning("No scan yet. Run one above, or wait for the nightly job to write "
               "`output/options_scan.json`.")
    st.stop()

rows = scan.get("candidates", [])
st.caption(f"Sweep for **{scan.get('generated_for')}** · DTE "
           f"{scan.get('dte_window')} · {scan.get('candidates_count')} candidates "
           f"across {len({r['ticker'] for r in rows})} names "
           f"({scan.get('priced')}/{scan.get('universe_size')} priced).")

if not rows:
    st.info("Sweep ran but no CSP cleared the filters.")
    st.stop()

df = pd.DataFrame(rows)

# ── AQE context, JOINED not recomputed ──────────────────────────────────────
# ATR14, the sector read and the thematic basket all already exist on the daily
# export, computed by the engines that own them. Recomputing ATR here would put
# a second implementation of a number the whole system trades off — the same
# duplicate-field trap this codebase has spent the day removing. So this is a
# lookup, and a ticker the export has not scored simply comes back blank.
@st.cache_data(ttl=300, show_spinner=False)
def _aqe_context() -> dict:
    try:
        from src.ui.shared import load_export
        ex = load_export(allow_drive=True) or {}
    except Exception:  # noqa: BLE001
        return {}
    out = {}
    for r in (ex.get("daily_list") or []):
        tk = r.get("ticker")
        if tk:
            out[tk] = {
                "atr_14d": r.get("atr_14d"),
                "sector": r.get("gics_sector_name"),
                "sector_state": r.get("sector_trend_state"),
                "sector_gate": r.get("gics_gate"),
                "theme": r.get("thematic_basket"),
                "theme_grade": r.get("thematic_grade"),
            }
    return out


_ctx = _aqe_context()
# THE COLUMNS ARE ALWAYS CREATED, even when the context is empty. Building them
# only `if _ctx` meant that on a fresh container — output/ wiped by a deploy, or
# the daily export mid-write — the ATR, sector and theme columns simply WERE NOT
# THERE, and a column that vanishes without a word is the silent-empty failure
# this codebase forbids. Blank cells plus a warning is the honest version.
for _col, _key in (("atr_14d", "atr_14d"), ("sector", "sector"),
                   ("sector_state", "sector_state"), ("sector_gate", "sector_gate"),
                   ("theme", "theme"), ("theme_grade", "theme_grade")):
    df[_col] = df["ticker"].map(lambda t, k=_key: (_ctx.get(t) or {}).get(k))
# ── THE SCORE CACHE — the right source, and the one I reached for last ──────
# scores_daily.parquet holds the FULL UNIVERSE scored every day (594 names on
# 2026-08-06), not the 326 the export publishes. The export is what CLEARED a
# gate; the parquet is what was MEASURED. For a CSP list the second is the
# right question — "what does AQE think of this name" applies to every name in
# the universe, whether or not it earned a place on a list.
#
# It carries atr14 AND the scores, so this single join replaces a panel
# recomputation and answers more than ATR ever did (PM: "it should pull from
# both Universe parquet score and AQE longlist ... instead of running their
# own"). Read straight off the file the pipeline writes — nothing recomputed.
@st.cache_data(ttl=900, show_spinner=False)
def _score_cache() -> dict:
    try:
        import pandas as _pd
        from src.data.paths import DATA_DIR
        pth = DATA_DIR / "scores_daily.parquet"
        if not pth.exists():
            return {}
        cols = ["date", "ticker", "atr14", "sc_momentum", "elder_score",
                "flow_100", "energy_100", "structure_100", "mp_100", "mp_state",
                "pipe_rank"]
        sc = _pd.read_parquet(pth, columns=cols)
        sc["date"] = _pd.to_datetime(sc["date"])
        sc = sc[sc["date"] == sc["date"].max()]          # LATEST day only
        return {r["ticker"]: r for r in sc.to_dict("records")}
    except Exception:  # noqa: BLE001
        return {}


_sc = _score_cache()
for _col, _key in (("atr_14d", "atr14"), ("sc_mom", "sc_momentum"),
                   ("elder", "elder_score"), ("flow", "flow_100"),
                   ("energy", "energy_100"), ("structure", "structure_100"),
                   ("mp", "mp_100"), ("mp_state", "mp_state"),
                   ("pipe_rank", "pipe_rank")):
    _vals = df["ticker"].map(lambda t, k=_key: (_sc.get(t) or {}).get(k))
    # The export wins where it has a value — it is the same number from the same
    # engines, and a row should not flip source between renders.
    df[_col] = df[_col].fillna(_vals) if _col in df.columns else _vals
if not _sc:
    st.info("**Score cache unavailable** — sc_mom / elder / mp_state are blank. "
            "scores_daily.parquet is not on this container (a fresh deploy "
            "before the first pipeline run). The ATR falls back to the panel "
            "and then FMP; the SCORES have no fallback, because they are AQE "
            "engine output rather than market data.")

# FALL BACK TO THE PANEL for anything the export and the score cache both miss.
# Uses src.engines.utils.atr — the SAME function the pipeline uses. This is one
# implementation applied to more names, NOT a second ATR living on this page.
@st.cache_data(ttl=900, show_spinner=False)
def _panel_atr(tickers: tuple) -> dict:
    try:
        import pandas as _pd
        from src.data.paths import PANEL_DAILY
        from src.engines.utils import atr as _atr
        if not PANEL_DAILY.exists():
            return {}
        pan = _pd.read_parquet(PANEL_DAILY,
                               columns=["date", "ticker", "high", "low", "close"])
        pan = pan[pan["ticker"].isin(set(tickers))].sort_values(["ticker", "date"])
        out = {}
        for tk, g in pan.groupby("ticker", sort=False):
            if len(g) < 20:
                continue
            v = _atr(g["high"].astype(float), g["low"].astype(float),
                     g["close"].astype(float), n=14).iloc[-1]
            if v == v and v > 0:                       # not NaN, not zero
                out[tk] = round(float(v), 2)
        return out
    except Exception:  # noqa: BLE001
        return {}


_need = tuple(sorted(df.loc[df["atr_14d"].isna(), "ticker"].unique()))
_from_panel = _panel_atr(_need) if len(_need) else {}
if _from_panel:
    df["atr_14d"] = df["atr_14d"].fillna(df["ticker"].map(_from_panel))


# LAST RESORT: PULL THE BARS (PM: "option scanner should query and pull if there
# is something that is NOT in the AQE Scanner universe. this helps them stay
# optimal"). A CSP candidate outside the AQE universe is still a trade, and
# refusing to price its volatility because another module never scored it is the
# module's problem, not the trade's.
#
# BOUNDED, because FMP Starter has a throttle and a page render must never be
# able to burn it: capped per render, cached for the session-day, and off by one
# click. Same client and same ATR function as the pipeline — one implementation,
# wider reach.
FMP_ATR_MAX_FETCH = 40


@st.cache_data(ttl=43200, show_spinner=False)          # 12h — ATR barely moves
def _fmp_atr(tickers: tuple) -> dict:
    from datetime import timedelta
    try:
        from src.data.fmp_client import FMPClient
        from src.engines.utils import atr as _atr
        cl = FMPClient()
    except Exception as exc:  # noqa: BLE001
        return {"_error": f"{type(exc).__name__}: {exc}"}
    out, today = {}, date.today()
    for tk in tickers:
        try:
            bars = cl.get_daily_bars(tk, from_date=today - timedelta(days=120),
                                     to_date=today)
            if bars is None or len(bars) < 20:
                continue
            v = _atr(bars["high"].astype(float), bars["low"].astype(float),
                     bars["close"].astype(float), n=14).iloc[-1]
            if v == v and v > 0:
                out[tk] = round(float(v), 2)
        except Exception:  # noqa: BLE001 — one bad symbol never stops the rest
            continue
    return out


_still = sorted(df.loc[df["atr_14d"].isna(), "ticker"].unique())
if _still:
    _do_fetch = st.checkbox(
        f"Fetch ATR from FMP for {len(_still)} name(s) outside the AQE universe",
        value=True, key="opt_fmp_atr",
        help=f"One daily-bars call each, capped at {FMP_ATR_MAX_FETCH} per "
             "render and cached 12h, so this cannot burn the FMP throttle.")
    if _do_fetch:
        _pulled = _fmp_atr(tuple(_still[:FMP_ATR_MAX_FETCH]))
        _err = _pulled.pop("_error", None)
        if _err:
            st.warning(f"FMP unavailable ({_err}) — those rows stay blank.")
        elif _pulled:
            df["atr_14d"] = df["atr_14d"].fillna(df["ticker"].map(_pulled))
            st.caption(f"Pulled ATR14 from FMP for {len(_pulled)} name(s) not in "
                       "the AQE daily list or the local panel.")
        if len(_still) > FMP_ATR_MAX_FETCH:
            st.caption(f"{len(_still) - FMP_ATR_MAX_FETCH} more still blank — the "
                       f"per-render cap is {FMP_ATR_MAX_FETCH}. Re-render to "
                       "continue; results are cached.")

if not _ctx:
    st.warning(
        "**AQE context unavailable** — atr_14d, dist_ATRs, sector and theme are "
        "blank on every row. The columns are still here; the daily export they "
        "join from could not be read locally or from Drive (a fresh container "
        "before the first pipeline run, or a run in progress). Re-check after "
        "the AQE Scanner's daily pipeline completes.")

# ── Market cap, joined from the universe build ──────────────────────────────
# Harvested from the SAME FMP screener response that decides membership, so it
# costs nothing. Unknown stays UNKNOWN — a missing size must never sort as a
# small company.
try:
    from src.data.universe import load_universe_mcap
    _mcap = load_universe_mcap()
except Exception:  # noqa: BLE001
    _mcap = {}
df["mcap_b"] = df["ticker"].map(lambda t: ((_mcap.get(t) or 0) / 1e9) or None)
if not _mcap:
    st.info("**Market cap not yet available** — the column is present but empty. "
            "It is harvested during the universe build (06:00 SGT) and first "
            "populates on the next one.")

# Distance to the strike measured in ATRs. THE point of this column: a 6% gap
# on a quiet $600 name and a 6% gap on a $20 mover are not the same trade, and
# a percentage cannot tell them apart. One ATR = roughly a normal day's range,
# so ">= 1 ATR away" reads as "the strike is beyond a typical day's move".
if "spot" in df.columns:
    _gap = pd.to_numeric(df["spot"], errors="coerce") - pd.to_numeric(df["strike"],
                                                                     errors="coerce")
    df["atr_strikes"] = (_gap / pd.to_numeric(df.get("atr_14d"),
                                              errors="coerce")).round(2)

# ── Filters (sidebar — TYPED, so an exact number can be given) ──────────────
# Kept in the sidebar where the PM expects them; the sliders became number
# inputs because a slider cannot be handed an exact value. One widget per
# filter: two driving the same cut is how a screen starts lying about what it
# is showing.
_dte_w = scan.get("dte_window", [20, 50])
sb = st.sidebar
sb.header("Filters")
d_lo = sb.number_input("Delta ≥", 0.0, 1.0, float(OC.CSP_DELTA_MIN), 0.01,
                       help="Short-put |Δ|. Lower = further OTM.")
d_hi = sb.number_input("Delta ≤", 0.0, 1.0, float(OC.CSP_DELTA_MAX), 0.01)
pop_min = sb.number_input("POP % ≥", 0.0, 100.0, 70.0, 1.0,
                          help="P(finish above breakeven).") / 100.0
dist_min = sb.number_input("Distance to strike % ≥", 0.0, 40.0, 0.0, 0.5) / 100.0
atr_min = sb.number_input(
    "Distance ≥ N × ATR14  (dist_ATRs)", 0.0, 10.0, 0.0, 0.25,
    help="Set 1.0 for 'the strike is at least one 14-day ATR below spot'. "
         "0 = off. Rows with no ATR (ticker not scored today) are EXCLUDED "
         "when this is on — an unknown is not a pass.")
ay_min = sb.number_input("Annualised yield % ≥", 0.0, 500.0, 20.0, 5.0) / 100.0
cush_min = sb.number_input("Downside cushion % ≥", 0.0, 50.0, 0.0, 0.5) / 100.0
sc_min = sb.number_input("AQE SC_MOM ≥", 0.0, 100.0, 0.0, 5.0,
                         help="From the full-universe score cache, so it "
                              "applies to names that are not on any AQE list. "
                              "Rows with no score are EXCLUDED when this is on.")
eld_min = sb.number_input("AQE Elder ≥", 0.0, 10.0, 0.0, 0.5,
                          help="Same source. 0 = off.")
mcap_min = sb.number_input("Market cap $B ≥", 0.0, 5000.0, 0.0, 5.0,
                           help="Blank/0 = no floor. Needs a universe build "
                                "since 2026-08-06 to be populated.")
mcap_max = sb.number_input("Market cap $B ≤ (0 = none)", 0.0, 5000.0, 0.0, 50.0)
_slot = int(OC.CAPITAL / OC.MAX_POSITIONS)
cap_max = sb.number_input(
    "Max collateral $ (0 = none)", 0, 500_000, 0, step=500,
    help=f"Cash-secured = strike x 100. One of {OC.MAX_POSITIONS} slots ~ ${_slot:,}.")
dte_lo = sb.number_input("DTE ≥", 0, 365, int(_dte_w[0]))
dte_hi = sb.number_input("DTE ≤", 0, 365, int(_dte_w[1]))
names = sorted(df["ticker"].unique())
pick = sb.multiselect("Tickers (blank = all)", names, [])
sect_pick = sb.multiselect(
    "Sector (blank = all)",
    sorted({v for v in df.get("sector", pd.Series(dtype=str)).dropna()}), [])
theme_pick = sb.multiselect(
    "Theme (blank = all)",
    sorted({v for v in df.get("theme", pd.Series(dtype=str)).dropna()}), [])

f = df.copy()
f = f[(f["annual_yield"].fillna(0) >= ay_min) &
      (f["abs_delta"].fillna(0).between(d_lo, d_hi)) &
      (f.get("pop", pd.Series(0, index=f.index)).fillna(0) >= pop_min) &
      (f.get("distance_to_strike_pct", pd.Series(0, index=f.index)).fillna(0) >= dist_min) &
      (f["downside_cushion"].fillna(-9) >= cush_min) &
      (f["dte"].between(dte_lo, dte_hi))]
if cap_max:
    f = f[f["collateral"].fillna(0) <= cap_max]
if pick:
    f = f[f["ticker"].isin(pick)]
if sect_pick and "sector" in f.columns:
    f = f[f["sector"].isin(sect_pick)]
if theme_pick and "theme" in f.columns:
    f = f[f["theme"].isin(theme_pick)]
if atr_min > 0:
    # fillna(-1) so a row with no ATR fails the test rather than passing it.
    f = f[f.get("atr_strikes", pd.Series(dtype=float)).reindex(f.index).fillna(-1)
          >= atr_min]
# fillna(-1) so an unscored row FAILS the test rather than passing it — the
# same rule as the ATR filter: an unknown is not a pass.
if sc_min > 0 and "sc_mom" in f.columns:
    f = f[pd.to_numeric(f["sc_mom"], errors="coerce").fillna(-1) >= sc_min]
if eld_min > 0 and "elder" in f.columns:
    f = f[pd.to_numeric(f["elder"], errors="coerce").fillna(-1) >= eld_min]
if mcap_min > 0 and "mcap_b" in f.columns:
    f = f[f["mcap_b"].fillna(-1) >= mcap_min]
if mcap_max > 0 and "mcap_b" in f.columns:
    f = f[f["mcap_b"].fillna(1e9) <= mcap_max]
f = f.sort_values("annual_yield", ascending=False)

st.subheader(f"{len(f)} matches")
# Build a display frame with percentages as numeric %-scaled columns (sortable).
disp = pd.DataFrame({"ticker": f["ticker"], "strike": f["strike"], "dte": f["dte"]})
# The distance block, READ ACROSS IN ONE LINE (PM ruling): spot, the gap in
# DOLLARS, the name's ATR in dollars, then the gap expressed in ATRs. Same unit
# side by side is the whole point — "$12 away, ATR is $4, so three ATRs" is a
# glance; the same thing as a percentage next to a dollar ATR is arithmetic.
if "spot" in f.columns:
    disp["spot"] = pd.to_numeric(f["spot"], errors="coerce").round(2)
    disp["dist_$"] = (pd.to_numeric(f["spot"], errors="coerce")
                      - pd.to_numeric(f["strike"], errors="coerce")).round(2)
if "atr_14d" in f.columns:
    disp["atr_14d"] = pd.to_numeric(f["atr_14d"], errors="coerce").round(2)
if "atr_strikes" in f.columns:
    # Named for the QUESTION it answers, not for the maths behind it.
    # "atr_strikes" made the reader work out what was being divided by what;
    # dist_ATRs sits next to dist_$ and atr_14d and completes the sentence.
    disp["dist_ATRs"] = f["atr_strikes"]
if "abs_delta" in f.columns:
    disp["delta"] = f["abs_delta"].round(3)
for label, src in [("dist_to_strike_%", "distance_to_strike_pct"), ("POP_%", "pop"),
                   ("not_assigned_%", "pop_not_assigned"), ("ann_yield_%", "annual_yield"),
                   ("cushion_%", "downside_cushion"), ("iv_%", "iv")]:
    if src in f.columns:
        disp[label] = (f[src] * 100).round(1)
for label, src in [("credit$", "credit_per_contract"), ("breakeven", "breakeven"),
                   ("theta/day", "theta_credit_day"), ("collateral", "collateral")]:
    if src in f.columns:
        disp[label] = f[src]
# AQE context. atr_strikes answers the question the raw ATR cannot: is this
# strike a normal week's move away, or three of them? That is the number that
# makes a CSP distance readable across a $20 name and a $600 one.
if "mcap_b" in f.columns:
    disp["mcap_$b"] = pd.to_numeric(f["mcap_b"], errors="coerce").round(1)
# AQE's own read on the name, for EVERY universe name rather than only the
# published ones. Rounded here, not in the join, so the source stays raw.
for _label, _src in (("sc_mom", "sc_mom"), ("elder", "elder"),
                     ("mp_state", "mp_state"), ("pipe_rank", "pipe_rank")):
    if _src in f.columns:
        _v = f[_src]
        disp[_label] = (pd.to_numeric(_v, errors="coerce").round(1)
                        if _src != "mp_state" else _v)
for _label, _src in (("sector", "sector"), ("sector_state", "sector_state"),
                     ("theme", "theme"), ("theme_grade", "theme_grade")):
    if _src in f.columns:
        disp[_label] = f[_src]
# A BLANK MUST SAY WHY, WHERE IT CAN BE SEEN. This used to be an st.caption
# under the table — grey, small, and below the thing it explains, so a blank
# ATR read as an unexplained gap (PM: "why is SNDK atr_14d blank? no error was
# provided"). It is an st.info above the table now, and it NAMES the tickers.
if "atr_14d" in disp.columns:
    _blank_atr = sorted(disp.loc[disp["atr_14d"].isna(), "ticker"].unique())
    if _blank_atr:
        _eg = ", ".join(_blank_atr[:8]) + (" …" if len(_blank_atr) > 8 else "")
        st.info(
            f"**No ATR for {len(_blank_atr)} of {disp['ticker'].nunique()} names** "
            f"({_eg}). They are in the options universe but not in today's AQE "
            "daily list, are absent from the local panel, and could not be "
            "pulled from FMP either — so atr_14d and dist_ATRs are blank on "
            "those rows. Blank, never guessed; the ATR-distance filter excludes "
            "them rather than letting an unknown pass. (sector and theme stay "
            "blank regardless: those are AQE ENGINE reads, not market data, so "
            "there is nothing to fetch for a name AQE never scored.)")
table_with_copy(disp, key="universe_csp")

if len(f):
    b = f.iloc[0]
    st.success(f"Top: **SELL {b['ticker']} {b['strike']:.0f}P {int(b['dte'])}DTE** — "
               f"${b['credit_per_contract']:.0f} credit, {b['annual_yield']*100:.0f}% "
               f"annualised, {b['pop_not_assigned']*100:.0f}% not-assigned, breakeven "
               f"{b['breakeven']:.2f}. Numbers only — the AIC sizes/decides.")
