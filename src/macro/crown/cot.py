"""§2.3 / §2.5 Positioning — CFTC Commitment of Traders, straight from the source.

FMP gates COT behind Premium. That is not a reason to skip it: the CFTC is the
publisher, and it puts the whole thing on cftc.gov for free — the current week as
a flat file, and every prior year as a zipped annual with a header row. So we
take it from the publisher and owe nobody a subscription for it.

  weekly   https://www.cftc.gov/dea/newcot/deafut.txt      (headerless, positional)
  annual   https://www.cftc.gov/files/dea/history/deacot<YYYY>.zip  (annual.txt, headed)

**What COT is and is not.** It reports Tuesday's book and publishes Friday 15:30
ET, so every reading is at least three days stale by the time you see it, and up
to ten by the following Thursday. It cannot time anything. Crown uses it for one
job only (§2.5): *positioning vs price divergence* — price making new highs while
large specs are already at an extreme. That is a slow context dial, and this
module is deliberately built to answer that question and no other.

Markets are keyed on the **CFTC contract market code**, not the market name.
Names get re-spelled between years ("CRUDE OIL, LIGHT SWEET" vs "WTI ..."); the
code does not, and a join on names silently drops a market for a whole year.
"""

from __future__ import annotations

import csv
import io
import zipfile
from datetime import date

import numpy as np
import pandas as pd
import requests

from src.data.paths import DATA_DIR
from . import spec as S
from .cta import MARKETS

COT_WEEKLY_URL = "https://www.cftc.gov/dea/newcot/deafut.txt"
COT_ANNUAL_URL = "https://www.cftc.gov/files/dea/history/deacot{year}.zip"
COT_CACHE = DATA_DIR / "crown_cot.parquet"

HTTP_TIMEOUT = 90
DEFAULT_YEARS = 3
PERCENTILE_WINDOW_WEEKS = 156       # 3 years — enough for "extreme" to mean something
MIN_WEEKS_FOR_PERCENTILE = 52

# Positional layout of the "All" block, identical in the weekly flat file and in
# the annual (whose header row we skip rather than trust, so one parser serves
# both). Verified against the 2026 annual header, 2026-08-09.
_COL = {
    "name": 0, "as_of_yymmdd": 1, "report_date": 2, "code": 3,
    "exchange": 4, "region": 5, "commodity": 6,
    "open_interest": 7,
    "nc_long": 8, "nc_short": 9, "nc_spread": 10,
    "comm_long": 11, "comm_short": 12,
    "tot_rept_long": 13, "tot_rept_short": 14,
    "nonrept_long": 15, "nonrept_short": 16,
}
_MAX_COL = max(_COL.values())

# Reverse of cta.MARKETS — code -> our market key.
CODE_TO_MARKET = {m["cot"]: k for k, m in MARKETS.items() if m.get("cot")}


# ── parsing (pure — unit-testable with no network) ────────────────────────

def _num(x) -> float:
    try:
        v = float(str(x).strip().replace(",", ""))
        return v if np.isfinite(v) else np.nan
    except (TypeError, ValueError):
        return np.nan


def parse_cot(text: str, *, codes: set[str] | None = None) -> pd.DataFrame:
    """CFTC futures-only CSV text -> tidy frame. Header rows are detected and
    dropped rather than assumed present, so this handles both file shapes.

    Returns columns: date, code, name, open_interest, nc_long, nc_short,
    nc_spread, comm_long, comm_short, net_spec, net_spec_pct_oi.
    """
    rows: list[dict] = []
    for r in csv.reader(io.StringIO(text)):
        if len(r) <= _MAX_COL:
            continue
        code = r[_COL["code"]].strip()
        if not code or code.lower().startswith("cftc"):
            continue                     # header row
        if codes is not None and code not in codes:
            continue
        d = pd.to_datetime(r[_COL["report_date"]].strip(), errors="coerce")
        if pd.isna(d):
            continue
        oi = _num(r[_COL["open_interest"]])
        nl, ns = _num(r[_COL["nc_long"]]), _num(r[_COL["nc_short"]])
        rows.append({
            "date": d.normalize(),
            "code": code,
            "name": r[_COL["name"]].strip(),
            "open_interest": oi,
            "nc_long": nl, "nc_short": ns,
            "nc_spread": _num(r[_COL["nc_spread"]]),
            "comm_long": _num(r[_COL["comm_long"]]),
            "comm_short": _num(r[_COL["comm_short"]]),
        })

    df = pd.DataFrame(rows)
    if df.empty:
        return df
    df["net_spec"] = df["nc_long"] - df["nc_short"]
    # Normalising by open interest is what makes a 2019 reading comparable to a
    # 2026 one — contract sizes, participation and OI all drift over years, and
    # a raw contract count quietly stops meaning the same thing.
    df["net_spec_pct_oi"] = np.where(
        df["open_interest"] > 0, df["net_spec"] / df["open_interest"], np.nan)
    return df.sort_values(["code", "date"]).reset_index(drop=True)


def parse_annual_zip(blob: bytes, *, codes: set[str] | None = None) -> pd.DataFrame:
    with zipfile.ZipFile(io.BytesIO(blob)) as z:
        names = [n for n in z.namelist() if n.lower().endswith(".txt")]
        if not names:
            return pd.DataFrame()
        return parse_cot(z.read(names[0]).decode("latin-1"), codes=codes)


# ── fetching ──────────────────────────────────────────────────────────────

def _get(url: str) -> bytes | None:
    try:
        r = requests.get(url, timeout=HTTP_TIMEOUT,
                         headers={"User-Agent": "AQE/1.0 (research)"})
        r.raise_for_status()
        return r.content
    except requests.RequestException as exc:
        print(f"[crown.cot] fetch failed {url}: {exc}", flush=True)
        return None


def fetch_weekly(codes: set[str] | None = None) -> pd.DataFrame:
    """This week's report. Empty frame (not an exception) if the fetch fails."""
    blob = _get(COT_WEEKLY_URL)
    if blob is None:
        return pd.DataFrame()
    return parse_cot(blob.decode("latin-1"), codes=codes)


def fetch_year(year: int, codes: set[str] | None = None) -> pd.DataFrame:
    blob = _get(COT_ANNUAL_URL.format(year=year))
    if blob is None:
        return pd.DataFrame()
    return parse_annual_zip(blob, codes=codes)


def refresh(years: int = DEFAULT_YEARS, *, codes: set[str] | None = None,
            cache: "object" = None) -> dict:
    """Bring the local COT history up to date and return a status dict.

    Backfills the annual archives once (they never change for a closed year),
    then appends the current week on every subsequent call. Cached as a parquet
    beside the panels so Daily Persist carries it across a container recycle —
    without that the percentile window would reset to one row on every restart
    and every market would read "no history" instead of "extreme".
    """
    codes = codes or set(CODE_TO_MARKET)
    path = DATA_DIR / "crown_cot.parquet" if cache is None else cache

    have = pd.DataFrame()
    if path.exists():
        try:
            have = pd.read_parquet(path)
        except Exception as exc:            # a corrupt cache must not kill the run
            print(f"[crown.cot] cache unreadable, rebuilding: {exc}", flush=True)

    this_year = date.today().year
    wanted = list(range(this_year - years + 1, this_year + 1))
    present = set()
    if not have.empty:
        present = set(pd.to_datetime(have["date"]).dt.year.unique().tolist())

    frames = [have] if not have.empty else []
    fetched_years: list[int] = []
    for y in wanted:
        # Always re-pull the current year (it grows weekly); prior years once.
        if y in present and y != this_year:
            continue
        f = fetch_year(y, codes=codes)
        if not f.empty:
            frames.append(f)
            fetched_years.append(y)

    wk = fetch_weekly(codes=codes)
    if not wk.empty:
        frames.append(wk)

    if not frames:
        return {"ok": False, "reason": "no COT data fetched and no cache",
                "rows": 0, "as_of": None}

    df = (pd.concat(frames, ignore_index=True)
            .drop_duplicates(subset=["code", "date"], keep="last")
            .sort_values(["code", "date"])
            .reset_index(drop=True))
    try:
        df.to_parquet(path, index=False)
    except Exception as exc:
        print(f"[crown.cot] cache write failed: {exc}", flush=True)

    as_of = pd.to_datetime(df["date"]).max()
    return {
        "ok": True,
        "rows": int(len(df)),
        "codes": int(df["code"].nunique()),
        "as_of": as_of.date().isoformat() if pd.notna(as_of) else None,
        "years_fetched": fetched_years,
        "weekly_ok": not wk.empty,
    }


def load_cached() -> pd.DataFrame:
    if not COT_CACHE.exists():
        return pd.DataFrame()
    try:
        return pd.read_parquet(COT_CACHE)
    except Exception:
        return pd.DataFrame()


# ── the reading ───────────────────────────────────────────────────────────

def positioning(df: pd.DataFrame, code: str,
                window_weeks: int = PERCENTILE_WINDOW_WEEKS) -> dict | None:
    """Large-spec positioning for one contract: level, percentile, extreme flag.

    The percentile is over `net_spec_pct_oi`, and it is the number that carries
    the meaning — "+180k contracts" says nothing without knowing whether that is
    the biggest long in three years or a Tuesday.
    """
    if df is None or df.empty:
        return None
    sub = df[df["code"] == code].sort_values("date")
    if sub.empty:
        return None
    tail = sub.tail(window_weeks)
    series = pd.to_numeric(tail["net_spec_pct_oi"], errors="coerce").dropna()
    if series.empty:
        return None

    latest = float(series.iloc[-1])
    n = len(series)
    pctl = float((series <= latest).sum() - 1) / max(n - 1, 1) if n > 1 else None
    prev = float(series.iloc[-2]) if n > 1 else None

    extreme = None
    if pctl is not None:
        if pctl >= S.DIV_COT_EXTREME_PCTL:
            extreme = "CROWDED_LONG"
        elif pctl <= (1.0 - S.DIV_COT_EXTREME_PCTL):
            extreme = "CROWDED_SHORT"

    row = tail.iloc[-1]
    return {
        "code": code,
        "market": CODE_TO_MARKET.get(code),
        "name": str(row["name"]),
        "as_of": pd.to_datetime(row["date"]).date().isoformat(),
        "net_spec": int(row["net_spec"]) if pd.notna(row["net_spec"]) else None,
        "net_spec_pct_oi": round(latest, 4),
        "open_interest": int(row["open_interest"]) if pd.notna(row["open_interest"]) else None,
        "percentile": round(pctl, 4) if pctl is not None else None,
        "weeks_of_history": int(n),
        "percentile_reliable": bool(n >= MIN_WEEKS_FOR_PERCENTILE),
        "wow_change_pct_oi": round(latest - prev, 4) if prev is not None else None,
        "extreme": extreme,
    }


def analyse(df: pd.DataFrame | None = None) -> dict:
    """Positioning across the whole replicated CTA universe."""
    if df is None:
        df = load_cached()
    if df is None or df.empty:
        return {"status": "UNAVAILABLE", "as_of": None, "markets": {},
                "crowded_long": [], "crowded_short": [],
                "reason": "no COT history — run crown.cot.refresh()"}

    out: dict[str, dict] = {}
    for code, key in CODE_TO_MARKET.items():
        p = positioning(df, code)
        if p is not None:
            out[key] = p

    as_of = pd.to_datetime(df["date"]).max()
    stale_weeks = None
    if pd.notna(as_of):
        stale_weeks = int((pd.Timestamp.today().normalize() - as_of).days // 7)

    return {
        "status": "OK" if out else "EMPTY",
        "as_of": as_of.date().isoformat() if pd.notna(as_of) else None,
        "weeks_stale": stale_weeks,
        "markets": out,
        "crowded_long": sorted(k for k, v in out.items() if v["extreme"] == "CROWDED_LONG"),
        "crowded_short": sorted(k for k, v in out.items() if v["extreme"] == "CROWDED_SHORT"),
        "reason": None if out else "no tracked contract codes found in the file",
    }
