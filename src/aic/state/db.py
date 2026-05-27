"""SQLite session-state store for the AIC layer.

Schema per spec §12. Single-file SQLite at `src/aic/state/aic.db` (gitignored).
Separate from the AQE SQLite (`data/aqe.db`) -- the AIC layer does not write
into AQE's state store.

Tables:
  sessions         -- one row per trading-day session
  position_state   -- current open positions (cached locally; canonical = PTJ)
  pipeline_state   -- the 5-10 name pipeline (WATCH/BRACKET/KILLED)
  cost_log         -- every LLM call's tokens + cost
  deliberations   -- record of each completed Deliberation Cell run
  inversions       -- record of 8/8 unanimous inversion arguments
"""

from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import date, datetime
from pathlib import Path
from typing import Any, Iterator


PROJECT_ROOT = Path(__file__).resolve().parents[3]
DB_PATH = PROJECT_ROOT / "src" / "aic" / "state" / "aic.db"


_SCHEMA = """
CREATE TABLE IF NOT EXISTS sessions (
    session_id    TEXT PRIMARY KEY,
    date          TEXT NOT NULL,
    open_sgt      TEXT,
    close_sgt     TEXT,
    regime        TEXT,
    vix           REAL,
    session_pnl   REAL,
    realised_pnl  REAL,
    api_cost_usd  REAL,
    status        TEXT
);

CREATE TABLE IF NOT EXISTS position_state (
    ticker        TEXT PRIMARY KEY,
    qty           INTEGER,
    entry         REAL,
    sl            REAL,
    tp1           REAL,
    tp2           REAL,
    dsg10_tier    INTEGER,
    sector        TEXT,
    srm_grade     TEXT,
    trade_date    TEXT,
    last_updated  TEXT
);

CREATE TABLE IF NOT EXISTS pipeline_state (
    ticker        TEXT NOT NULL,
    date_added    TEXT NOT NULL,
    status        TEXT NOT NULL,        -- BRACKET / WATCH / KILLED
    sc_momentum   REAL,
    ptrs          REAL,
    bracket_entry REAL,
    bracket_stop  REAL,
    session_notes TEXT,
    PRIMARY KEY (ticker, date_added)
);

CREATE TABLE IF NOT EXISTS cost_log (
    call_id       TEXT PRIMARY KEY,
    session_id    TEXT,
    model         TEXT,
    voice         TEXT,
    input_tokens  INTEGER,
    output_tokens INTEGER,
    cache_tokens  INTEGER,
    cost_usd      REAL,
    timestamp     TEXT
);

CREATE TABLE IF NOT EXISTS deliberations (
    deliberation_id TEXT PRIMARY KEY,
    session_id      TEXT,
    ticker          TEXT,
    decision        TEXT,
    approvals       INTEGER,
    rejections      INTEGER,
    abstentions     INTEGER,
    avg_conviction  REAL,
    inversion_required INTEGER,
    sizing          TEXT,
    cost_usd        REAL,
    payload_json    TEXT,
    created_at      TEXT
);

CREATE TABLE IF NOT EXISTS inversions (
    inversion_id    TEXT PRIMARY KEY,
    deliberation_id TEXT,
    counter_argument TEXT,
    cost_usd        REAL,
    pm_acknowledged INTEGER DEFAULT 0,
    created_at      TEXT
);

CREATE INDEX IF NOT EXISTS idx_pipeline_status   ON pipeline_state(status);
CREATE INDEX IF NOT EXISTS idx_cost_session      ON cost_log(session_id);
CREATE INDEX IF NOT EXISTS idx_delib_session     ON deliberations(session_id);
"""


@contextmanager
def _conn() -> Iterator[sqlite3.Connection]:
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
    with _conn() as c:
        c.executescript(_SCHEMA)


# ---------------------------------------------------------------------------
# Thin CRUD wrapper -- enough for the orchestrator + protocols.
# ---------------------------------------------------------------------------

class AICStateDB:
    """High-level state operations the protocols use."""

    def __init__(self) -> None:
        init_db()

    # --- sessions

    def start_session(
        self,
        session_id: str,
        regime: str | None = None,
        vix: float | None = None,
    ) -> None:
        today = date.today().isoformat()
        now = datetime.now().isoformat(timespec="seconds")
        with _conn() as c:
            c.execute(
                "INSERT OR REPLACE INTO sessions "
                "(session_id, date, open_sgt, regime, vix, status) "
                "VALUES (?, ?, ?, ?, ?, 'OPEN')",
                (session_id, today, now, regime, vix),
            )

    def close_session(
        self,
        session_id: str,
        session_pnl: float | None,
        realised_pnl: float | None,
        api_cost_usd: float | None,
    ) -> None:
        now = datetime.now().isoformat(timespec="seconds")
        with _conn() as c:
            c.execute(
                "UPDATE sessions SET close_sgt=?, session_pnl=?, realised_pnl=?, "
                "api_cost_usd=?, status='CLOSED' WHERE session_id=?",
                (now, session_pnl, realised_pnl, api_cost_usd, session_id),
            )

    # --- pipeline

    def upsert_pipeline(
        self,
        ticker: str,
        status: str,
        date_added: str | None = None,
        sc_momentum: float | None = None,
        ptrs: float | None = None,
        bracket_entry: float | None = None,
        bracket_stop: float | None = None,
        session_notes: str | None = None,
    ) -> None:
        date_added = date_added or date.today().isoformat()
        with _conn() as c:
            c.execute(
                "INSERT OR REPLACE INTO pipeline_state "
                "(ticker, date_added, status, sc_momentum, ptrs, "
                "bracket_entry, bracket_stop, session_notes) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (ticker, date_added, status, sc_momentum, ptrs,
                 bracket_entry, bracket_stop, session_notes),
            )

    def active_pipeline_count(self) -> int:
        with _conn() as c:
            row = c.execute(
                "SELECT COUNT(*) FROM pipeline_state "
                "WHERE status IN ('BRACKET', 'WATCH')"
            ).fetchone()
        return int(row[0]) if row else 0

    # --- cost log

    def log_cost(
        self,
        call_id: str,
        session_id: str,
        model: str,
        voice: str,
        input_tokens: int,
        output_tokens: int,
        cache_tokens: int,
        cost_usd: float,
    ) -> None:
        with _conn() as c:
            c.execute(
                "INSERT OR REPLACE INTO cost_log "
                "(call_id, session_id, model, voice, input_tokens, "
                "output_tokens, cache_tokens, cost_usd, timestamp) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (call_id, session_id, model, voice, input_tokens,
                 output_tokens, cache_tokens, cost_usd,
                 datetime.now().isoformat(timespec="seconds")),
            )

    def session_cost_usd(self, session_id: str) -> float:
        with _conn() as c:
            row = c.execute(
                "SELECT COALESCE(SUM(cost_usd), 0) FROM cost_log WHERE session_id=?",
                (session_id,),
            ).fetchone()
        return float(row[0]) if row else 0.0

    # --- deliberations + inversions

    def record_deliberation(
        self,
        deliberation_id: str,
        session_id: str,
        ticker: str,
        decision: str,
        approvals: int,
        rejections: int,
        abstentions: int,
        avg_conviction: float,
        inversion_required: bool,
        sizing: str | None,
        cost_usd: float,
        payload: dict[str, Any],
    ) -> None:
        with _conn() as c:
            c.execute(
                "INSERT OR REPLACE INTO deliberations VALUES "
                "(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (deliberation_id, session_id, ticker, decision, approvals,
                 rejections, abstentions, avg_conviction,
                 int(bool(inversion_required)), sizing, cost_usd,
                 json.dumps(payload, default=str),
                 datetime.now().isoformat(timespec="seconds")),
            )

    def record_inversion(
        self,
        inversion_id: str,
        deliberation_id: str,
        counter_argument: str,
        cost_usd: float,
    ) -> None:
        with _conn() as c:
            c.execute(
                "INSERT OR REPLACE INTO inversions VALUES (?, ?, ?, ?, 0, ?)",
                (inversion_id, deliberation_id, counter_argument, cost_usd,
                 datetime.now().isoformat(timespec="seconds")),
            )

    def acknowledge_inversion(self, inversion_id: str) -> None:
        with _conn() as c:
            c.execute(
                "UPDATE inversions SET pm_acknowledged=1 WHERE inversion_id=?",
                (inversion_id,),
            )

    # --- read helpers

    def list_pipeline(self) -> list[dict[str, Any]]:
        with _conn() as c:
            rows = c.execute(
                "SELECT ticker, date_added, status, sc_momentum, ptrs, "
                "bracket_entry, bracket_stop, session_notes "
                "FROM pipeline_state ORDER BY date_added DESC"
            ).fetchall()
        return [
            {
                "ticker": r[0], "date_added": r[1], "status": r[2],
                "sc_momentum": r[3], "ptrs": r[4],
                "bracket_entry": r[5], "bracket_stop": r[6],
                "session_notes": r[7],
            }
            for r in rows
        ]


if __name__ == "__main__":
    init_db()
    print(f"Initialised AIC state DB at {DB_PATH}")
    db = AICStateDB()
    print(f"Active pipeline names: {db.active_pipeline_count()}")
