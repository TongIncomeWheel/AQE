"""SQLite state store for AQE.

Single-file database at data/aqe.db. Zero config, no server.
Provides persistent storage for:
    - daily_bars: OHLCV history (append-only, incremental pulls)
    - engine_state: bar-over-bar state (BD counter, trend bars, etc.)
    - scores: daily computed scores
    - earnings: next earnings dates
    - srm_scores: sector rotation grades

The parquet pipeline remains the primary data path for bulk historical
scoring. SQLite handles incremental daily state and avoids full rebuilds.
"""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import date
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DB_PATH = PROJECT_ROOT / "data" / "aqe.db"


@contextmanager
def get_conn():
    """Context manager for SQLite connections. Auto-commits on success."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH), timeout=10)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db() -> None:
    """Create all tables if they don't exist."""
    with get_conn() as conn:
        conn.executescript(_SCHEMA)


_SCHEMA = """
CREATE TABLE IF NOT EXISTS universe (
    ticker TEXT PRIMARY KEY,
    name TEXT,
    sector TEXT,
    industry TEXT,
    market_cap REAL,
    exchange TEXT,
    last_refreshed DATE
);

CREATE TABLE IF NOT EXISTS daily_bars (
    ticker TEXT NOT NULL,
    date DATE NOT NULL,
    open REAL,
    high REAL,
    low REAL,
    close REAL,
    volume INTEGER,
    PRIMARY KEY (ticker, date)
);

CREATE TABLE IF NOT EXISTS weekly_bars (
    ticker TEXT NOT NULL,
    week_end DATE NOT NULL,
    open REAL,
    high REAL,
    low REAL,
    close REAL,
    volume INTEGER,
    PRIMARY KEY (ticker, week_end)
);

CREATE TABLE IF NOT EXISTS engine_state (
    ticker TEXT PRIMARY KEY,
    raw_base_count INTEGER DEFAULT 0,
    latched_bd INTEGER DEFAULT 0,
    bars_since_bo INTEGER DEFAULT 999,
    trend_bars INTEGER DEFAULT 0,
    bq_raw_base INTEGER DEFAULT 0,
    bq_latched_bd INTEGER DEFAULT 0,
    bq_bars_since_bo INTEGER DEFAULT 999,
    last_computed DATE
);

CREATE TABLE IF NOT EXISTS scores (
    ticker TEXT NOT NULL,
    date DATE NOT NULL,
    flow_100 REAL,
    energy_100 REAL,
    structure_100 REAL,
    mp_100 REAL,
    mp_state TEXT,
    elder_score REAL,
    bq_100 REAL,
    sc_momentum REAL,
    sc_position REAL,
    k39_value REAL,
    close REAL,
    atr14 REAL,
    pipe_rank REAL,
    earn_days INTEGER,
    PRIMARY KEY (ticker, date)
);

CREATE TABLE IF NOT EXISTS earnings (
    ticker TEXT PRIMARY KEY,
    next_earnings_date DATE,
    last_refreshed DATE
);

CREATE TABLE IF NOT EXISTS srm_scores (
    sector TEXT NOT NULL,
    date DATE NOT NULL,
    grade TEXT,
    sh REAL,
    PRIMARY KEY (sector, date)
);

CREATE INDEX IF NOT EXISTS idx_bars_ticker_date ON daily_bars(ticker, date DESC);
CREATE INDEX IF NOT EXISTS idx_scores_date ON scores(date DESC);
CREATE INDEX IF NOT EXISTS idx_scores_rank ON scores(date, pipe_rank DESC);
"""


# ---- Bar operations ----

def get_last_bar_date(ticker: str) -> date | None:
    """Return the most recent bar date for a ticker, or None if no bars."""
    with get_conn() as conn:
        row = conn.execute(
            "SELECT MAX(date) FROM daily_bars WHERE ticker = ?", (ticker,)
        ).fetchone()
        if row and row[0]:
            return date.fromisoformat(row[0])
    return None


def upsert_bars(ticker: str, df: pd.DataFrame) -> int:
    """Insert or replace daily bars for a ticker. Returns count inserted."""
    if df.empty:
        return 0
    with get_conn() as conn:
        rows = []
        for _, r in df.iterrows():
            d = r["date"]
            if isinstance(d, pd.Timestamp):
                d = d.strftime("%Y-%m-%d")
            rows.append((
                ticker, str(d),
                float(r["open"]), float(r["high"]),
                float(r["low"]), float(r["close"]),
                int(r["volume"]),
            ))
        conn.executemany(
            "INSERT OR REPLACE INTO daily_bars (ticker, date, open, high, low, close, volume) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            rows,
        )
        return len(rows)


def get_bars(ticker: str, from_date: str | None = None, to_date: str | None = None) -> pd.DataFrame:
    """Read daily bars for a ticker from SQLite."""
    with get_conn() as conn:
        query = "SELECT date, open, high, low, close, volume FROM daily_bars WHERE ticker = ?"
        params: list = [ticker]
        if from_date:
            query += " AND date >= ?"
            params.append(from_date)
        if to_date:
            query += " AND date <= ?"
            params.append(to_date)
        query += " ORDER BY date"
        df = pd.read_sql_query(query, conn, params=params)
    if not df.empty:
        df["date"] = pd.to_datetime(df["date"]).dt.normalize()
    return df


# ---- Score operations ----

def upsert_scores(df: pd.DataFrame) -> int:
    """Insert or replace daily scores. DataFrame must have ticker+date columns."""
    if df.empty:
        return 0
    cols = ["ticker", "date", "flow_100", "energy_100", "structure_100",
            "mp_100", "mp_state", "elder_score", "bq_100", "sc_momentum",
            "sc_position", "k39_value", "close", "atr14"]
    present = [c for c in cols if c in df.columns]
    placeholders = ", ".join(["?"] * len(present))
    col_names = ", ".join(present)
    with get_conn() as conn:
        rows = []
        for _, r in df.iterrows():
            vals = []
            for c in present:
                v = r[c]
                if c == "date" and isinstance(v, pd.Timestamp):
                    v = v.strftime("%Y-%m-%d")
                elif isinstance(v, float) and pd.isna(v):
                    v = None
                vals.append(v)
            rows.append(tuple(vals))
        conn.executemany(
            f"INSERT OR REPLACE INTO scores ({col_names}) VALUES ({placeholders})",
            rows,
        )
        return len(rows)


def get_latest_scores(as_of: str | None = None, limit: int = 1000) -> pd.DataFrame:
    """Read the most recent scores for all tickers."""
    with get_conn() as conn:
        if as_of:
            query = ("SELECT * FROM scores WHERE date = ? ORDER BY sc_momentum DESC LIMIT ?")
            df = pd.read_sql_query(query, conn, params=[as_of, limit])
        else:
            query = ("SELECT * FROM scores WHERE date = "
                     "(SELECT MAX(date) FROM scores) ORDER BY sc_momentum DESC LIMIT ?")
            df = pd.read_sql_query(query, conn, params=[limit])
    if not df.empty and "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"]).dt.normalize()
    return df


# ---- Engine state operations ----

def get_engine_state(ticker: str) -> dict | None:
    """Read persisted engine state for a ticker."""
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM engine_state WHERE ticker = ?", (ticker,)
        ).fetchone()
        if row:
            cols = [d[0] for d in conn.execute("SELECT * FROM engine_state WHERE 1=0").description]
            return dict(zip(cols, row))
    return None


def save_engine_state(ticker: str, state: dict) -> None:
    """Persist engine state for a ticker."""
    with get_conn() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO engine_state "
            "(ticker, raw_base_count, latched_bd, bars_since_bo, trend_bars, "
            "bq_raw_base, bq_latched_bd, bq_bars_since_bo, last_computed) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                ticker,
                state.get("raw_base_count", 0),
                state.get("latched_bd", 0),
                state.get("bars_since_bo", 999),
                state.get("trend_bars", 0),
                state.get("bq_raw_base", 0),
                state.get("bq_latched_bd", 0),
                state.get("bq_bars_since_bo", 999),
                state.get("last_computed"),
            ),
        )


# ---- Earnings operations ----

def upsert_earnings(cal: dict[str, str]) -> int:
    """Bulk insert/replace earnings dates. {ticker: "YYYY-MM-DD"}."""
    if not cal:
        return 0
    today = date.today().isoformat()
    with get_conn() as conn:
        rows = [(t, d, today) for t, d in cal.items()]
        conn.executemany(
            "INSERT OR REPLACE INTO earnings (ticker, next_earnings_date, last_refreshed) "
            "VALUES (?, ?, ?)",
            rows,
        )
        return len(rows)


def get_earnings() -> dict[str, str]:
    """Read all earnings dates. Returns {ticker: "YYYY-MM-DD"}."""
    with get_conn() as conn:
        rows = conn.execute("SELECT ticker, next_earnings_date FROM earnings").fetchall()
    return {t: d for t, d in rows if d}


# ---- SRM operations ----

def upsert_srm(sector: str, run_date: date, grade: str, sh: float) -> None:
    """Save SRM grade for a sector."""
    with get_conn() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO srm_scores (sector, date, grade, sh) VALUES (?, ?, ?, ?)",
            (sector, run_date.isoformat(), grade, sh),
        )


def get_srm_latest() -> dict[str, dict]:
    """Read the latest SRM grades. Returns {sector: {grade, sh}}."""
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT sector, grade, sh FROM srm_scores "
            "WHERE date = (SELECT MAX(date) FROM srm_scores)"
        ).fetchall()
    return {r[0]: {"grade": r[1], "sh": r[2]} for r in rows}


# ---- Utilities ----

def table_counts() -> dict[str, int]:
    """Return row counts for all tables. Useful for diagnostics."""
    tables = ["universe", "daily_bars", "weekly_bars", "engine_state", "scores", "earnings", "srm_scores"]
    counts = {}
    with get_conn() as conn:
        for t in tables:
            try:
                row = conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()
                counts[t] = row[0] if row else 0
            except sqlite3.OperationalError:
                counts[t] = -1
    return counts


if __name__ == "__main__":
    init_db()
    print(f"Database initialized at {DB_PATH}")
    counts = table_counts()
    for table, n in counts.items():
        print(f"  {table}: {n:,} rows")
