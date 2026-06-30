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
"""


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
