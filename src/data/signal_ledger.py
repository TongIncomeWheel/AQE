"""Signal Ledger — append-only archive of daily AQE output for continuous learning.

Every pipeline run appends one row per ticker on the longlist / elder_list.
A separate backfill pass fills forward returns (T+5/10/20) from the panel
once the calendar has advanced enough. This gives the PM a concrete record:
"which names did AQE flag, at what scores, and what happened next?"

Tables live in the existing aqe.db (SQLite). The ledger is append-only;
the backfill is idempotent (UPDATE … WHERE ret_t5 IS NULL).

Usage from the daily pipeline:
    from src.data.signal_ledger import record_signals, backfill_outcomes
    record_signals(export)        # after drive_sync.export_to_drive()
    backfill_outcomes()           # uses panel_daily.parquet
"""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

from src.data.paths import DATA_DIR, PANEL_DAILY

DB_PATH = DATA_DIR / "aqe.db"

_LEDGER_SCHEMA = """
CREATE TABLE IF NOT EXISTS signal_snapshots (
    scan_date    TEXT    NOT NULL,
    ticker       TEXT    NOT NULL,
    list_source  TEXT    NOT NULL,   -- 'longlist' or 'elder_list'
    on_longlist  INTEGER DEFAULT 0,
    pe           INTEGER DEFAULT 0,
    close        REAL,
    sc_mom       REAL,
    sc_mom_raw   REAL,
    ptrs         REAL,
    elder        REAL,
    flow         REAL,
    energy       REAL,
    structure    REAL,
    mp           REAL,
    bq           REAL,
    mp_state     TEXT,
    rd_score     REAL,
    rd_state     TEXT,
    hl_score     REAL,
    hl_state     TEXT,
    gics_sector  TEXT,
    gics_gate    TEXT,
    entry        REAL,
    dsl_stop     REAL,
    dsl_risk     REAL,
    dsl_tp_1r    REAL,
    dsl_tp_2r    REAL,
    PRIMARY KEY (scan_date, ticker, list_source)
);

CREATE TABLE IF NOT EXISTS signal_outcomes (
    scan_date    TEXT    NOT NULL,
    ticker       TEXT    NOT NULL,
    close_t0     REAL,
    close_t5     REAL,
    close_t10    REAL,
    close_t20    REAL,
    ret_t5       REAL,
    ret_t10      REAL,
    ret_t20      REAL,
    high_5d      REAL,
    high_10d     REAL,
    high_20d     REAL,
    low_5d       REAL,
    low_10d      REAL,
    low_20d      REAL,
    tp1_hit      INTEGER,
    tp2_hit      INTEGER,
    sl_hit       INTEGER,
    PRIMARY KEY (scan_date, ticker)
);

CREATE INDEX IF NOT EXISTS idx_snap_date ON signal_snapshots(scan_date);
CREATE INDEX IF NOT EXISTS idx_snap_ticker ON signal_snapshots(ticker);
CREATE INDEX IF NOT EXISTS idx_outcome_date ON signal_outcomes(scan_date);

-- ── Signal Radar paper-track (M14-M18) ─────────────────────────────────────
-- Short-term memory: which names the radar tagged each day, and (once matured)
-- what price actually did afterward vs the PRE-REGISTERED pass/fail bands.
-- Append-only; reconcile is idempotent. Detection rate != win rate. NO TAG
-- INFORMS SIZING UNTIL ITS TRACK SHOWS PASS.
CREATE TABLE IF NOT EXISTS signal_tags (
    tag_date     TEXT    NOT NULL,
    ticker       TEXT    NOT NULL,
    tag          TEXT    NOT NULL,   -- 'runner_setup' or 'premove_setup'
    conviction   INTEGER,
    subtype      TEXT,
    PRIMARY KEY (tag_date, ticker, tag)
);

CREATE TABLE IF NOT EXISTS signal_track_results (
    tag_date       TEXT    NOT NULL,
    ticker         TEXT    NOT NULL,
    tag            TEXT    NOT NULL,
    matured_10d    INTEGER DEFAULT 0,
    matured_20d    INTEGER DEFAULT 0,
    fwdmax_pct_10d REAL,
    fwdmax_pct_20d REAL,
    PRIMARY KEY (tag_date, ticker, tag)
);

CREATE INDEX IF NOT EXISTS idx_tags_date ON signal_tags(tag_date);
CREATE INDEX IF NOT EXISTS idx_tags_tag ON signal_tags(tag);
CREATE INDEX IF NOT EXISTS idx_trackres_tag ON signal_track_results(tag);
"""

# ── PRE-REGISTERED paper-track bands (frozen 2026-07-06 — do NOT move after the
# fact; this is the pre-registration discipline the whole program held to). ──
TRACK_REGISTERED_ON = "2026-07-06"
RUNNER_MIN_EPISODES = 60
RUNNER_MIN_CAL_DAYS = 92
RUNNER_PASS_FLOOR = 35.0        # % forward +20%/20d detection
RUNNER_PASS_MULT = 1.5          # x concurrent QUAL-pond base
RUNNER_FAIL_BELOW = 25.0
# premove bands live in signal_engine_params.json (premove_track_bands), read live.


@contextmanager
def _conn():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH), timeout=10)
    conn.execute("PRAGMA journal_mode=WAL")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_ledger() -> None:
    with _conn() as conn:
        conn.executescript(_LEDGER_SCHEMA)


def _n(v):
    try:
        return round(float(v), 4) if v is not None else None
    except (TypeError, ValueError):
        return None


def record_signals(export: dict) -> int:
    """Append today's longlist + elder_list to the ledger. Returns row count."""
    init_ledger()

    scan_date = (export.get("date") or "")[:10]
    if not scan_date:
        return 0

    rows: list[tuple] = []
    seen: set[tuple[str, str]] = set()

    for source_key in ("longlist", "elder_list"):
        for rec in export.get(source_key) or []:
            tk = rec.get("ticker")
            if not tk:
                continue
            key = (tk, source_key)
            if key in seen:
                continue
            seen.add(key)

            rows.append((
                scan_date, tk, source_key,
                int(bool(rec.get("on_longlist"))),
                int(bool(rec.get("pe"))),
                _n(rec.get("close")),
                _n(rec.get("sc_momentum")),
                _n(rec.get("sc_momentum_raw")),
                _n(rec.get("ptrs")),
                _n(rec.get("elder")),
                _n(rec.get("flow")),
                _n(rec.get("energy")),
                _n(rec.get("structure")),
                _n(rec.get("mp")),
                _n(rec.get("bq")),
                str(rec.get("mp_state", "")),
                _n(rec.get("rd_score")),
                str(rec.get("rd_state") or ""),
                _n(rec.get("hl_score")),
                str(rec.get("hl_state") or ""),
                str(rec.get("gics_sector") or ""),
                str(rec.get("gics_gate") or ""),
                _n(rec.get("entry")),
                _n(rec.get("dsl_stop")),
                _n(rec.get("dsl_risk")),
                _n(rec.get("dsl_tp_1r")),
                _n(rec.get("dsl_tp_2r")),
            ))

    if not rows:
        return 0

    with _conn() as conn:
        conn.executemany(
            "INSERT OR REPLACE INTO signal_snapshots "
            "(scan_date, ticker, list_source, on_longlist, pe, close, "
            "sc_mom, sc_mom_raw, ptrs, elder, flow, energy, structure, mp, bq, "
            "mp_state, rd_score, rd_state, hl_score, hl_state, "
            "gics_sector, gics_gate, entry, dsl_stop, dsl_risk, dsl_tp_1r, dsl_tp_2r) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            rows,
        )

    # Seed outcome rows (close_t0 only) so backfill has something to UPDATE.
    outcome_rows = []
    seen_tk: set[str] = set()
    for r in rows:
        tk = r[1]
        if tk not in seen_tk:
            seen_tk.add(tk)
            outcome_rows.append((scan_date, tk, r[5]))  # close_t0 = close

    with _conn() as conn:
        conn.executemany(
            "INSERT OR IGNORE INTO signal_outcomes (scan_date, ticker, close_t0) "
            "VALUES (?,?,?)",
            outcome_rows,
        )

    return len(rows)


def backfill_outcomes(panel_path: Path | None = None) -> int:
    """Fill forward returns for outcomes where ret_t5 is still NULL.

    Uses panel_daily.parquet as the price source. Only fills rows where
    enough calendar time has passed (20 trading days ≈ 28 calendar days
    for the full fill; 5d partial fills happen earlier).

    Returns the number of rows updated.
    """
    init_ledger()
    panel_path = panel_path or PANEL_DAILY
    if not panel_path.exists():
        return 0

    with _conn() as conn:
        pending = conn.execute(
            "SELECT scan_date, ticker, close_t0 FROM signal_outcomes "
            "WHERE ret_t20 IS NULL"
        ).fetchall()

    if not pending:
        return 0

    panel = pd.read_parquet(panel_path, columns=["date", "ticker", "close", "high", "low"])
    panel["date"] = pd.to_datetime(panel["date"]).dt.normalize()

    updated = 0
    with _conn() as conn:
        for scan_date_str, ticker, close_t0 in pending:
            scan_date = pd.Timestamp(scan_date_str)
            tk_bars = panel[
                (panel["ticker"] == ticker) & (panel["date"] > scan_date)
            ].sort_values("date").reset_index(drop=True)

            if tk_bars.empty:
                continue

            if close_t0 is None or close_t0 <= 0:
                bar_on_date = panel[
                    (panel["ticker"] == ticker) & (panel["date"] == scan_date)
                ]
                if not bar_on_date.empty:
                    close_t0 = float(bar_on_date["close"].iloc[0])
                else:
                    continue

            updates = {"close_t0": close_t0}

            for horizon, label in [(5, "t5"), (10, "t10"), (20, "t20")]:
                if len(tk_bars) >= horizon:
                    close_h = float(tk_bars["close"].iloc[horizon - 1])
                    high_h = float(tk_bars["high"].iloc[:horizon].max())
                    low_h = float(tk_bars["low"].iloc[:horizon].min())
                    updates[f"close_{label}"] = close_h
                    updates[f"ret_{label}"] = round((close_h / close_t0 - 1) * 100, 4)
                    updates[f"high_{horizon}d"] = high_h
                    updates[f"low_{horizon}d"] = low_h

            # TP/SL hit detection — need the snapshot's DSL levels
            snap = conn.execute(
                "SELECT entry, dsl_stop, dsl_tp_1r, dsl_tp_2r FROM signal_snapshots "
                "WHERE scan_date = ? AND ticker = ? LIMIT 1",
                (scan_date_str, ticker),
            ).fetchone()

            if snap and len(tk_bars) >= 20:
                entry, dsl_stop, tp1, tp2 = snap
                h20 = updates.get("high_20d")
                l20 = updates.get("low_20d")
                if tp1 and h20:
                    updates["tp1_hit"] = 1 if h20 >= tp1 else 0
                if tp2 and h20:
                    updates["tp2_hit"] = 1 if h20 >= tp2 else 0
                if dsl_stop and l20:
                    updates["sl_hit"] = 1 if l20 <= dsl_stop else 0

            if len(updates) <= 1:
                continue

            set_clause = ", ".join(f"{k} = ?" for k in updates)
            vals = list(updates.values()) + [scan_date_str, ticker]
            conn.execute(
                f"UPDATE signal_outcomes SET {set_clause} "
                "WHERE scan_date = ? AND ticker = ?",
                vals,
            )
            updated += 1

    return updated


def get_signal_history(
    ticker: str | None = None,
    from_date: str | None = None,
    to_date: str | None = None,
    list_source: str | None = None,
) -> pd.DataFrame:
    """Query the ledger — joined snapshots + outcomes."""
    init_ledger()
    query = (
        "SELECT s.*, o.close_t5, o.close_t10, o.close_t20, "
        "o.ret_t5, o.ret_t10, o.ret_t20, "
        "o.high_5d, o.high_10d, o.high_20d, "
        "o.low_5d, o.low_10d, o.low_20d, "
        "o.tp1_hit, o.tp2_hit, o.sl_hit "
        "FROM signal_snapshots s "
        "LEFT JOIN signal_outcomes o ON s.scan_date = o.scan_date AND s.ticker = o.ticker "
        "WHERE 1=1"
    )
    params: list = []
    if ticker:
        query += " AND s.ticker = ?"
        params.append(ticker)
    if from_date:
        query += " AND s.scan_date >= ?"
        params.append(from_date)
    if to_date:
        query += " AND s.scan_date <= ?"
        params.append(to_date)
    if list_source:
        query += " AND s.list_source = ?"
        params.append(list_source)
    query += " ORDER BY s.scan_date DESC, s.ticker"

    with _conn() as conn:
        return pd.read_sql_query(query, conn, params=params)


def get_hit_rates(
    from_date: str | None = None,
    to_date: str | None = None,
    min_sc: float | None = None,
    min_ptrs: float | None = None,
    list_source: str | None = None,
) -> dict:
    """Compute aggregate hit rates for filled outcomes, optionally filtered."""
    init_ledger()

    query = (
        "SELECT s.sc_mom, s.ptrs, s.elder, s.rd_score, s.hl_score, s.list_source, "
        "o.ret_t5, o.ret_t10, o.ret_t20, o.tp1_hit, o.tp2_hit, o.sl_hit "
        "FROM signal_snapshots s "
        "JOIN signal_outcomes o ON s.scan_date = o.scan_date AND s.ticker = o.ticker "
        "WHERE o.ret_t20 IS NOT NULL"
    )
    params: list = []
    if from_date:
        query += " AND s.scan_date >= ?"
        params.append(from_date)
    if to_date:
        query += " AND s.scan_date <= ?"
        params.append(to_date)
    if min_sc is not None:
        query += " AND s.sc_mom >= ?"
        params.append(min_sc)
    if min_ptrs is not None:
        query += " AND s.ptrs >= ?"
        params.append(min_ptrs)
    if list_source:
        query += " AND s.list_source = ?"
        params.append(list_source)

    with _conn() as conn:
        df = pd.read_sql_query(query, conn, params=params)

    if df.empty:
        return {"n": 0, "message": "No filled outcomes yet — need ~4 weeks of data"}

    n = len(df)
    return {
        "n": n,
        "avg_ret_t5": round(df["ret_t5"].mean(), 2),
        "avg_ret_t10": round(df["ret_t10"].mean(), 2),
        "avg_ret_t20": round(df["ret_t20"].mean(), 2),
        "tp1_hit_rate": round(df["tp1_hit"].mean() * 100, 1) if df["tp1_hit"].notna().any() else None,
        "tp2_hit_rate": round(df["tp2_hit"].mean() * 100, 1) if df["tp2_hit"].notna().any() else None,
        "sl_hit_rate": round(df["sl_hit"].mean() * 100, 1) if df["sl_hit"].notna().any() else None,
        "pct_positive_t10": round((df["ret_t10"] > 0).mean() * 100, 1),
        "pct_positive_t20": round((df["ret_t20"] > 0).mean() * 100, 1),
    }


def backfill_historical(
    scores_path: Path | None = None,
    panel_path: Path | None = None,
    min_sc_raw: float = 65.0,
    min_elder: float = 7.0,
    elder_list_min: float = 8.0,
) -> dict:
    """Replay the longlist/elder_list filter on every historical date in
    scores_daily.parquet and record them as signal snapshots, then backfill
    forward returns from panel_daily.parquet.

    This gives ~360 days of signal history with outcomes instantly — no FMP
    calls needed since the data is already in the parquets.

    PTRS is approximated as SC_MOM (SH ranges -8 to +3 and we don't have
    historical SRM grades per date). DSL levels are approximated from
    close and ATR14 using the naive formula.
    """
    from src.data.paths import SCORES_DAILY, PANEL_DAILY

    scores_path = scores_path or SCORES_DAILY
    panel_path = panel_path or PANEL_DAILY

    if not scores_path.exists():
        return {"ok": False, "reason": "scores_daily.parquet not found"}

    init_ledger()

    scores = pd.read_parquet(scores_path)
    scores["date"] = pd.to_datetime(scores["date"]).dt.normalize()

    all_dates = sorted(scores["date"].unique())
    print(f"  Backfill: {len(all_dates)} dates, "
          f"{scores['ticker'].nunique()} tickers in scores_daily")

    total_snaps = 0

    for scan_dt in all_dates:
        scan_date = scan_dt.strftime("%Y-%m-%d")
        day_scores = scores[scores["date"] == scan_dt]

        rows: list[tuple] = []
        outcome_rows: list[tuple] = []
        seen_tk: set[str] = set()

        for _, r in day_scores.iterrows():
            tk = r["ticker"]
            sc_raw = float(r.get("sc_momentum_raw") or r.get("sc_momentum") or 0)
            elder = float(r.get("elder_score") or 0)
            close = float(r.get("close") or 0)
            atr14 = float(r.get("atr14") or 0)

            is_longlist = sc_raw >= min_sc_raw and elder >= min_elder
            is_elder = elder >= elder_list_min

            if not is_longlist and not is_elder:
                continue

            sources = []
            if is_longlist:
                sources.append("longlist")
            if is_elder:
                sources.append("elder_list")

            # Approximate DSL levels from close + ATR
            entry = close
            dsl_risk = max(atr14 * 1.5, 0.01) if atr14 > 0 else None
            dsl_stop = (close - dsl_risk) if dsl_risk else None
            dsl_tp_1r = (entry + dsl_risk) if dsl_risk else None
            dsl_tp_2r = (entry + 2 * dsl_risk) if dsl_risk else None

            # Approximate PTRS as SC_MOM (no historical SRM)
            ptrs_approx = sc_raw

            rd_score = float(r["rd_score"]) if "rd_score" in r.index and pd.notna(r.get("rd_score")) else None
            rd_state = str(r["rd_state"]) if "rd_state" in r.index and pd.notna(r.get("rd_state")) else ""
            hl_score = float(r["hl_score"]) if "hl_score" in r.index and pd.notna(r.get("hl_score")) else None
            hl_state = str(r["hl_state"]) if "hl_state" in r.index and pd.notna(r.get("hl_state")) else ""

            for src in sources:
                rows.append((
                    scan_date, tk, src,
                    1 if is_longlist else 0,
                    0,  # pe — can't reconstruct historically
                    _n(close),
                    _n(sc_raw),
                    _n(sc_raw),
                    _n(ptrs_approx),
                    _n(elder),
                    _n(r.get("flow_100")),
                    _n(r.get("energy_100")),
                    _n(r.get("structure_100")),
                    _n(r.get("mp_100")),
                    _n(r.get("bq_100")),
                    str(r.get("mp_state") or ""),
                    _n(rd_score),
                    rd_state,
                    _n(hl_score),
                    hl_state,
                    "",  # gics_sector — not in scores_daily
                    "",  # gics_gate
                    _n(entry),
                    _n(dsl_stop),
                    _n(dsl_risk),
                    _n(dsl_tp_1r),
                    _n(dsl_tp_2r),
                ))

            if tk not in seen_tk:
                seen_tk.add(tk)
                outcome_rows.append((scan_date, tk, _n(close)))

        if rows:
            with _conn() as conn:
                conn.executemany(
                    "INSERT OR IGNORE INTO signal_snapshots "
                    "(scan_date, ticker, list_source, on_longlist, pe, close, "
                    "sc_mom, sc_mom_raw, ptrs, elder, flow, energy, structure, mp, bq, "
                    "mp_state, rd_score, rd_state, hl_score, hl_state, "
                    "gics_sector, gics_gate, entry, dsl_stop, dsl_risk, dsl_tp_1r, dsl_tp_2r) "
                    "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    rows,
                )
            with _conn() as conn:
                conn.executemany(
                    "INSERT OR IGNORE INTO signal_outcomes (scan_date, ticker, close_t0) "
                    "VALUES (?,?,?)",
                    outcome_rows,
                )
            total_snaps += len(rows)

    print(f"  Backfill: {total_snaps} historical signals recorded across {len(all_dates)} dates")

    # Now backfill all forward returns
    n_filled = backfill_outcomes(panel_path)
    print(f"  Backfill: {n_filled} outcomes filled with forward returns")

    stats = ledger_stats()
    return {"ok": True, "signals": total_snaps, "outcomes_filled": n_filled, "stats": stats}


def ledger_stats() -> dict:
    """Quick diagnostic: row counts, date range, fill status."""
    init_ledger()
    with _conn() as conn:
        snap_count = conn.execute("SELECT COUNT(*) FROM signal_snapshots").fetchone()[0]
        out_count = conn.execute("SELECT COUNT(*) FROM signal_outcomes").fetchone()[0]
        filled = conn.execute(
            "SELECT COUNT(*) FROM signal_outcomes WHERE ret_t20 IS NOT NULL"
        ).fetchone()[0]
        dates = conn.execute(
            "SELECT MIN(scan_date), MAX(scan_date) FROM signal_snapshots"
        ).fetchone()
        unique_tickers = conn.execute(
            "SELECT COUNT(DISTINCT ticker) FROM signal_snapshots"
        ).fetchone()[0]
        unique_dates = conn.execute(
            "SELECT COUNT(DISTINCT scan_date) FROM signal_snapshots"
        ).fetchone()[0]

    return {
        "snapshots": snap_count,
        "outcomes": out_count,
        "filled": filled,
        "pending": out_count - filled,
        "date_range": (dates[0], dates[1]) if dates[0] else None,
        "unique_tickers": unique_tickers,
        "unique_dates": unique_dates,
    }


# ═══════════════════════════════════════════════════════════════════════════
# Signal Radar paper-track — the forward proof, and the gate to ALL sizing.
# Every run: (1) LOG today's runner_setup / premove_setup names; (2) RECONCILE
# every logged name old enough against what price actually did (next open,
# price-path only) vs the PRE-REGISTERED bands. Detection rate != win rate.
# ═══════════════════════════════════════════════════════════════════════════
def record_signal_tags(export: dict | None = None) -> int:
    """Log today's runner_setup / premove_setup names to the append-only tracker.

    Reads the already-computed `signal_radar` block off the export (both lists cover
    the FULL scored universe) — NO recomputation, so this adds ~no time to the
    nightly run. Dedupes on (tag_date, ticker, tag). Returns the number of tags
    logged. Never raises past the caller's guard; a missing block degrades to 0 tags.
    """
    init_ledger()
    block = (export or {}).get("signal_radar") or {}
    scan_date = (block.get("scan_date") or (export or {}).get("date") or "")[:10]
    if not scan_date:
        return 0

    rows: list[tuple] = []
    for e in block.get("runner_setup", []):
        if e.get("ticker"):
            rows.append((scan_date, e["ticker"], "runner_setup",
                         int(e.get("conviction") or 0), e.get("subtype")))
    for e in block.get("premove_setup", []):
        if e.get("ticker"):
            rows.append((scan_date, e["ticker"], "premove_setup",
                         int(e.get("conviction") or 0), None))

    if not rows:
        return 0
    with _conn() as conn:
        conn.executemany(
            "INSERT OR REPLACE INTO signal_tags "
            "(tag_date, ticker, tag, conviction, subtype) VALUES (?,?,?,?,?)",
            rows,
        )
    return len(rows)


def reconcile_signal_tags(panel_path: Path | None = None) -> int:
    """Score every logged tag old enough (>=10/20 bars forward) against price.

    Entry = next bar's open; outcome = max favourable % within the horizon
    (price path only, no stop, no R). Idempotent UPDATE-on-mature. Returns the
    number of track rows written/updated.
    """
    init_ledger()
    panel_path = panel_path or PANEL_DAILY
    if not panel_path.exists():
        return 0

    with _conn() as conn:
        tags = conn.execute(
            "SELECT tag_date, ticker, tag FROM signal_tags"
        ).fetchall()
    if not tags:
        return 0

    panel = pd.read_parquet(panel_path, columns=["date", "ticker", "open", "high"])
    panel["date"] = pd.to_datetime(panel["date"]).dt.normalize()
    # PERF: tags mature within 20 trading days, so only recent history can reconcile
    # a still-open tag. Keep a generous tail (covers any tag < ~6 months old) to cut
    # the groupby cost — older tags are already matured/scored.
    _oldest = min((pd.Timestamp(t[0]) for t in tags), default=None)
    _cut = panel["date"].max() - pd.Timedelta(days=200)
    if _oldest is not None:
        _cut = min(_cut, _oldest - pd.Timedelta(days=5))
    panel = panel[panel["date"] >= _cut]
    groups = {t: g.sort_values("date").reset_index(drop=True)
              for t, g in panel.groupby("ticker")}

    written = 0
    with _conn() as conn:
        for tag_date_str, ticker, tag in tags:
            g = groups.get(ticker)
            if g is None:
                continue
            tag_dt = pd.Timestamp(tag_date_str)
            loc = g.index[g["date"] == tag_dt]
            if not len(loc):
                continue
            i = int(loc[0])
            if i + 1 >= len(g) or not (g["open"].iloc[i + 1] > 0):
                continue
            e = float(g["open"].iloc[i + 1])

            rec = {"matured_10d": 0, "matured_20d": 0,
                   "fwdmax_pct_10d": None, "fwdmax_pct_20d": None}
            for hz, lbl in [(10, "10d"), (20, "20d")]:
                if i + 1 + hz <= len(g):
                    hi = float(g["high"].iloc[i + 1:i + 1 + hz].max())
                    rec[f"fwdmax_pct_{lbl}"] = round((hi / e - 1) * 100, 4)
                    rec[f"matured_{lbl}"] = 1
            if not rec["matured_10d"]:
                continue
            conn.execute(
                "INSERT OR REPLACE INTO signal_track_results "
                "(tag_date, ticker, tag, matured_10d, matured_20d, "
                "fwdmax_pct_10d, fwdmax_pct_20d) VALUES (?,?,?,?,?,?,?)",
                (tag_date_str, ticker, tag, rec["matured_10d"], rec["matured_20d"],
                 rec["fwdmax_pct_10d"], rec["fwdmax_pct_20d"]),
            )
            written += 1
    return written


def _concurrent_pond_base(lo: str, hi: str, panel_path: Path | None = None) -> float | None:
    """QUAL-pond +20%/20d base detection over [lo, hi] — the 1.5x reference band."""
    from src.data.paths import SCORES_DAILY
    panel_path = panel_path or PANEL_DAILY
    if not SCORES_DAILY.exists() or not panel_path.exists():
        return None
    sc = pd.read_parquet(SCORES_DAILY, columns=["date", "ticker", "sc_momentum", "elder_score"])
    sc["date"] = pd.to_datetime(sc["date"]).dt.normalize()
    qual = sc[(sc["date"] >= pd.Timestamp(lo)) & (sc["date"] <= pd.Timestamp(hi))
              & (sc["sc_momentum"] >= 75) & (sc["elder_score"] >= 6.5)]
    if qual.empty:
        return None
    panel = pd.read_parquet(panel_path, columns=["date", "ticker", "open", "high"])
    panel["date"] = pd.to_datetime(panel["date"]).dt.normalize()
    groups = {t: g.sort_values("date").reset_index(drop=True)
              for t, g in panel.groupby("ticker")}
    outc = []
    for _, q in qual.iterrows():
        g = groups.get(q["ticker"])
        if g is None:
            continue
        loc = g.index[g["date"] == q["date"]]
        if len(loc):
            i = int(loc[0])
            if i + 21 <= len(g) and g["open"].iloc[i + 1] > 0:
                e = float(g["open"].iloc[i + 1])
                outc.append((g["high"].iloc[i + 1:i + 21].max() / e - 1) * 100 >= 20)
    return round(float(np.mean(outc)) * 100, 1) if outc else None


def signal_track_scoreboard() -> dict:
    """Per-tag paper-track scoreboard vs the pre-registered bands — reused verbatim
    by the Scanner UI (do not recompute differently there). Every % is a DETECTION
    rate (price path only), not a win rate."""
    init_ledger()
    from src.engines.signal_radar import load_params
    params = load_params() or {}

    with _conn() as conn:
        logged = dict(conn.execute(
            "SELECT tag, COUNT(*) FROM signal_tags GROUP BY tag").fetchall())
        dates = conn.execute("SELECT MIN(tag_date), MAX(tag_date) FROM signal_tags").fetchone()
        res = pd.read_sql_query("SELECT * FROM signal_track_results", conn)

    lo, hi = (dates[0], dates[1]) if dates and dates[0] else (None, None)
    days_elapsed = ((pd.Timestamp.now().normalize() - pd.Timestamp(lo)).days
                    if lo else 0)
    pond_base = _concurrent_pond_base(lo, hi) if lo else None

    out = {"registered_on": TRACK_REGISTERED_ON, "days_elapsed": days_elapsed,
           "pond_base_det20": pond_base, "tags": {}}
    for tag in ("runner_setup", "premove_setup"):
        sub = res[(res["tag"] == tag) & (res["matured_20d"] == 1)] if not res.empty else res
        n = len(sub)
        entry = {"logged": int(logged.get(tag, 0)), "matured": n,
                 "det20": None, "det10": None, "verdict": "RUNNING (nothing matured yet)"}
        if n:
            entry["det20"] = round(float((sub["fwdmax_pct_20d"] >= 20).mean()) * 100, 1)
            entry["det10"] = round(float((sub["fwdmax_pct_10d"] >= 10).mean()) * 100, 1)
            if tag == "runner_setup":
                floor, mult, fail_below = RUNNER_PASS_FLOOR, RUNNER_PASS_MULT, RUNNER_FAIL_BELOW
                window_met = n >= RUNNER_MIN_EPISODES and days_elapsed >= RUNNER_MIN_CAL_DAYS
            else:
                b = params.get("premove_track_bands") or {}
                floor = b.get("pass_floor"); mult = b.get("pass_mult"); fail_below = b.get("fail_below")
                window_met = n >= RUNNER_MIN_EPISODES and days_elapsed >= RUNNER_MIN_CAL_DAYS
            det = entry["det20"]
            if not window_met:
                entry["verdict"] = "RUNNING (window not met)"
            elif floor is not None and det >= floor and (pond_base is None or det >= mult * pond_base):
                entry["verdict"] = "PASS — edge holding; sizing discussion may open"
            elif fail_below is not None and det < fail_below:
                entry["verdict"] = "FAIL — below pre-registered floor; do not size"
            else:
                entry["verdict"] = "INCONCLUSIVE — between bands; keep tracking"
        out["tags"][tag] = entry
    return out
