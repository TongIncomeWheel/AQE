"""QS memory — the two things the engine has to remember between runs.

QS is not stateless. Two of its inputs are only knowable from history:

  `qs_persist`  how many of the PRIOR 5 sessions the name also qualified as
                QS (recipe_hits >= 3). Measured to be an independent
                conviction dimension — inside identical hits x lens buckets it
                still adds +0.06..+0.16 to the hit rate, in train AND test.

  regime cell   trend_200 / vol_60 bucketed against EXPANDING terciles fitted
                on prior days only. The boundaries move as history grows, so
                the series has to be kept, not recomputed from a window.

Both live in `aqe.db`, which `persist.py` already ships inside the daily
snapshot — so a Hugging Face container recycle restores QS's memory along with
everything else. Without that, `qs_persist` silently reads 0 for every name
after a restart, every name drops to the `0-1` persist band, and the whole
book re-prices downward with nothing in the output looking wrong.

Retention: hits are kept FOREVER, not trimmed to the 5 days persistence
needs. They are the audit trail — the record of what the engine saw on the
day it saw it — and they are what a future re-freeze would be rebuilt from.
"""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager

import pandas as pd

from src.data.paths import DATA_DIR

DB_PATH = DATA_DIR / "aqe.db"

# Fixed by the frozen calibration (`calibration.json.persist_window`). Not a
# tunable: the persist bands were measured over exactly 5 prior sessions.
PERSIST_WINDOW = 5
QS_DAY_MIN_HITS = 3


_SCHEMA = """
CREATE TABLE IF NOT EXISTS qs_daily_hits (
    date        TEXT NOT NULL,
    ticker      TEXT NOT NULL,
    recipe_hits INTEGER NOT NULL,
    lens_total  REAL,
    eligible    INTEGER NOT NULL DEFAULT 1,
    PRIMARY KEY (date, ticker)
);
CREATE INDEX IF NOT EXISTS ix_qs_hits_date ON qs_daily_hits(date);

CREATE TABLE IF NOT EXISTS qs_regime_series (
    date        TEXT PRIMARY KEY,
    trend_200   REAL,
    vol_60      REAL,
    t_tercile   INTEGER,
    v_tercile   INTEGER,
    regime_cell TEXT
);
"""


@contextmanager
def get_conn():
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


def init_qs_tables() -> None:
    with get_conn() as conn:
        conn.executescript(_SCHEMA)


def _d(v) -> str:
    return pd.Timestamp(v).strftime("%Y-%m-%d")


# ---------------------------------------------------------------- hits

def upsert_daily_hits(df: pd.DataFrame) -> int:
    """Store one run's recipe_hits. Columns: date, ticker, recipe_hits[,
    lens_total, eligible]. Idempotent — re-running a date overwrites it."""
    if df is None or df.empty:
        return 0
    init_qs_tables()
    rows = [
        (_d(r.date), str(r.ticker), int(r.recipe_hits),
         (None if pd.isna(getattr(r, "lens_total", None))
          else float(getattr(r, "lens_total"))),
         int(bool(getattr(r, "eligible", True))))
        for r in df.itertuples(index=False)
    ]
    with get_conn() as conn:
        conn.executemany(
            "INSERT INTO qs_daily_hits (date,ticker,recipe_hits,lens_total,eligible) "
            "VALUES (?,?,?,?,?) ON CONFLICT(date,ticker) DO UPDATE SET "
            "recipe_hits=excluded.recipe_hits, lens_total=excluded.lens_total, "
            "eligible=excluded.eligible", rows)
    return len(rows)


def get_qs_persist(as_of, window: int = PERSIST_WINDOW) -> dict[str, int]:
    """{ticker: count of the prior `window` sessions with recipe_hits >= 3}.

    "Prior sessions" means the last `window` DISTINCT STORED DATES strictly
    before `as_of` — not the last `window` calendar days. This matches the
    reference implementation (`daily_scan.py:152`), and it is the correct
    reading: a market holiday is not a day the name failed to qualify.

    A ticker absent on a prior date contributes 0 for that date, so a name
    that only appeared yesterday cannot inherit someone else's history.
    Returns {} when no prior dates exist — every name then lands in the `0-1`
    persist band, which is the honest reading of "no memory yet".
    """
    init_qs_tables()
    cutoff = _d(as_of)
    with get_conn() as conn:
        prior = [r[0] for r in conn.execute(
            "SELECT DISTINCT date FROM qs_daily_hits WHERE date < ? "
            "ORDER BY date DESC LIMIT ?", (cutoff, int(window))).fetchall()]
        if not prior:
            return {}
        marks = ",".join("?" * len(prior))
        rows = conn.execute(
            f"SELECT ticker, COUNT(*) FROM qs_daily_hits "
            f"WHERE date IN ({marks}) AND recipe_hits >= ? "
            f"GROUP BY ticker", (*prior, QS_DAY_MIN_HITS)).fetchall()
    return {t: int(n) for t, n in rows}


def get_hits_history(ticker: str | None = None,
                     limit: int | None = None) -> pd.DataFrame:
    """The stored hits trail, newest first. The audit record."""
    init_qs_tables()
    q = "SELECT date,ticker,recipe_hits,lens_total,eligible FROM qs_daily_hits"
    params: list = []
    if ticker:
        q += " WHERE ticker = ?"
        params.append(ticker)
    q += " ORDER BY date DESC, ticker"
    if limit:
        q += f" LIMIT {int(limit)}"
    with get_conn() as conn:
        return pd.read_sql_query(q, conn, params=params)


# -------------------------------------------------------------- regime

def upsert_regime_series(df: pd.DataFrame) -> int:
    """Store the regime series. Index or column `date`, plus trend_200,
    vol_60, t_tercile, v_tercile, regime_cell."""
    if df is None or len(df) == 0:
        return 0
    init_qs_tables()
    d = df.reset_index() if df.index.name else df.copy()
    if "date" not in d.columns:
        d = d.rename(columns={d.columns[0]: "date"})
    rows = []
    for r in d.itertuples(index=False):
        nz = lambda v: None if pd.isna(v) else float(v)
        ni = lambda v: None if pd.isna(v) else int(v)
        rows.append((_d(r.date), nz(getattr(r, "trend_200", None)),
                     nz(getattr(r, "vol_60", None)),
                     ni(getattr(r, "t_tercile", None)),
                     ni(getattr(r, "v_tercile", None)),
                     str(getattr(r, "regime_cell", "unclassified"))))
    with get_conn() as conn:
        conn.executemany(
            "INSERT INTO qs_regime_series "
            "(date,trend_200,vol_60,t_tercile,v_tercile,regime_cell) "
            "VALUES (?,?,?,?,?,?) ON CONFLICT(date) DO UPDATE SET "
            "trend_200=excluded.trend_200, vol_60=excluded.vol_60, "
            "t_tercile=excluded.t_tercile, v_tercile=excluded.v_tercile, "
            "regime_cell=excluded.regime_cell", rows)
    return len(rows)


def get_regime_series() -> pd.DataFrame:
    init_qs_tables()
    with get_conn() as conn:
        df = pd.read_sql_query(
            "SELECT date,trend_200,vol_60,t_tercile,v_tercile,regime_cell "
            "FROM qs_regime_series ORDER BY date", conn)
    if not df.empty:
        df["date"] = pd.to_datetime(df["date"])
    return df


def get_regime_cell(as_of) -> str:
    """The stored cell for a date. 'unclassified' when absent — never a guess."""
    init_qs_tables()
    with get_conn() as conn:
        row = conn.execute(
            "SELECT regime_cell FROM qs_regime_series WHERE date = ?",
            (_d(as_of),)).fetchone()
    return (row[0] if row and row[0] else "unclassified")


def store_status() -> dict:
    """Row counts + date coverage, for the pipeline log and the UI status bar.

    `persist_ready` answers the question that actually matters after a
    container recycle: are there enough prior sessions for qs_persist to mean
    anything, or is every name about to read 0 through no fault of its own?
    """
    init_qs_tables()
    with get_conn() as conn:
        hits = conn.execute(
            "SELECT COUNT(*), COUNT(DISTINCT date), MIN(date), MAX(date) "
            "FROM qs_daily_hits").fetchone()
        reg = conn.execute(
            "SELECT COUNT(*), MIN(date), MAX(date) FROM qs_regime_series").fetchone()
    n_dates = hits[1] or 0
    return {
        "hits_rows": hits[0] or 0, "hits_dates": n_dates,
        "hits_from": hits[2], "hits_to": hits[3],
        "regime_rows": reg[0] or 0, "regime_from": reg[1], "regime_to": reg[2],
        "persist_ready": n_dates >= PERSIST_WINDOW,
    }
