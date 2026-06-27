"""Thin wrapper around Financial Modeling Prep's REST API for EOD bars.

FMP Starter plan: 300 calls/min, daily EOD US equities, 5+ years history.
We cap ourselves at ~250 calls/min to leave headroom.

Used endpoints:
    /stable/historical-price-eod/full?symbol={S}  — daily OHLCV (split + dividend
        adjusted). Returns a flat list of bars in descending date order. We sort
        ascending before returning.

The legacy /api/v3/historical-price-full/ endpoint stopped accepting new keys
after August 2025 and now returns "Legacy Endpoint" errors for accounts created
after that date; the /stable/ replacement is functionally equivalent and is what
the FMP docs now point new users to.

Weekly bars are built locally by resampling daily bars (W-FRI close). This
matches Pine `request.security(sym, "W", ...)` once we shift one bar back to
avoid look-ahead.
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Iterable

import pandas as pd
import requests
from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(PROJECT_ROOT / ".env")


FMP_BASE_STABLE = "https://financialmodelingprep.com/stable"
DEFAULT_RATE_LIMIT_PER_MIN = 250  # FMP Starter is 300; leave headroom.
# When running on cloud datacenter IPs (HF/AWS, Streamlit Cloud/GCP, etc.),
# FMP can apply IP-based throttling that's tighter than per-key. A lower
# default for cloud avoids "Invalid API KEY" mid-run that's actually
# IP-rate-limit behaviour. Override via FMP_RATE_LIMIT_PER_MIN env var.
CLOUD_RATE_LIMIT_PER_MIN = 80


def _effective_rate_limit() -> int:
    """Pick a rate limit based on env override / cloud detection."""
    import os
    override = os.environ.get("FMP_RATE_LIMIT_PER_MIN")
    if override:
        try:
            v = int(override)
            return max(10, min(v, 500))
        except ValueError:
            pass
    # Cloud detection: HF Spaces sets SPACE_ID; Streamlit Cloud sets STREAMLIT_SERVER_PORT
    if os.environ.get("SPACE_ID") or os.environ.get("SPACE_HOST"):
        return CLOUD_RATE_LIMIT_PER_MIN
    return DEFAULT_RATE_LIMIT_PER_MIN


@dataclass
class FMPConfig:
    api_key: str
    rate_limit_per_min: int = DEFAULT_RATE_LIMIT_PER_MIN
    timeout_seconds: int = 30


class FMPError(RuntimeError):
    """Raised on any non-2xx response from FMP or unexpected payload shape."""


class FMPQuotaError(FMPError):
    """Raised when FMP returns 'Invalid API KEY' mid-run (daily quota hit)."""


class FMPClient:
    """Synchronous client. Single-threaded use — we don't need parallel pulls."""

    def __init__(self, config: FMPConfig | None = None) -> None:
        if config is None:
            key = os.environ.get("FMP_API_KEY")
            if not key:
                raise FMPError(
                    "FMP_API_KEY not set. Copy .env.template to .env and fill it in."
                )
            config = FMPConfig(api_key=key, rate_limit_per_min=_effective_rate_limit())
        self.config = config
        self._session = requests.Session()
        # Use a browser-ish UA -- some API providers (including FMP) treat
        # python-requests UA as a scraper signal and throttle harder.
        self._session.headers["User-Agent"] = (
            "AQE-Scanner/1.0 (+https://github.com/TongIncomeWheel/AQE)"
        )
        self._call_times: list[float] = []  # rolling 60s window
        self._ok_count: int = 0  # track successful calls (for quota detection)
        # Log the effective rate so cloud runs show clearly what they're using
        print(f"[fmp] effective rate limit: {config.rate_limit_per_min} calls/min",
              flush=True)

    # ---------- public ----------

    def get_daily_bars(
        self,
        ticker: str,
        from_date: str | date | None = None,
        to_date: str | date | None = None,
    ) -> pd.DataFrame:
        """Return OHLCV daily bars in ascending date order.

        Columns: date (Timestamp, normalized), open, high, low, close, volume.
        The OHLC values are already split + dividend adjusted by FMP.
        """
        params = {"symbol": ticker, "apikey": self.config.api_key}
        if from_date is not None:
            params["from"] = _as_iso(from_date)
        if to_date is not None:
            params["to"] = _as_iso(to_date)

        url = f"{FMP_BASE_STABLE}/historical-price-eod/full"
        payload = self._get_json(url, params=params)
        # The /stable/ endpoint returns a flat list of bars in descending date order.
        if not isinstance(payload, list) or not payload:
            return _empty_bars_frame()

        df = pd.DataFrame(payload)
        df["date"] = pd.to_datetime(df["date"]).dt.normalize()
        df = df.sort_values("date", kind="stable").reset_index(drop=True)

        for col in ("open", "high", "low", "close"):
            df[col] = df[col].astype(float)
        df["volume"] = df["volume"].fillna(0).astype("int64")
        return df[["date", "open", "high", "low", "close", "volume"]]

    def get_intraday_bars(
        self,
        ticker: str,
        interval: str = "5min",
        from_date: str | date | None = None,
        to_date: str | date | None = None,
    ) -> list[dict]:
        """Intraday OHLCV bars for one ticker (default 5-min).

        interval ∈ {1min, 5min, 15min, 30min, 1hour, 4hour}. Returns a list of
        {date, open, high, low, close, volume} dicts (FMP order; the intraday
        module sorts internally). Returns [] on any failure so callers degrade
        gracefully. Used by the Pricer (intraday momentum + bracket).
        """
        params = {"symbol": ticker, "apikey": self.config.api_key}
        if from_date is not None:
            params["from"] = _as_iso(from_date)
        if to_date is not None:
            params["to"] = _as_iso(to_date)
        url = f"{FMP_BASE_STABLE}/historical-chart/{interval}"
        try:
            payload = self._get_json(url, params=params)
        except FMPError:
            return []
        return payload if isinstance(payload, list) else []

    def get_quotes(self, tickers: list[str]) -> dict[str, dict]:
        """Fetch live (15-min-delayed on Starter) quotes for a set of tickers.

        Returns {ticker: {price, volume, avg_volume, ma_50, ma_200, day_low,
        day_high, prev_close, ts}}. Each ticker is one throttled call to
        /stable/quote. Failures on a single ticker degrade to skipping it — the
        alert engine simply won't evaluate names it has no quote for.
        """
        out: dict[str, dict] = {}
        url = f"{FMP_BASE_STABLE}/quote"
        for tk in tickers:
            try:
                payload = self._get_json(url, params={"symbol": tk,
                                                       "apikey": self.config.api_key})
            except FMPQuotaError:
                raise  # daily quota — let the caller email what it has so far
            except FMPError:
                continue  # single-name hiccup — skip it
            row = payload[0] if isinstance(payload, list) and payload else None
            if not isinstance(row, dict):
                continue
            price = row.get("price")
            if price is None:
                continue
            out[tk] = {
                "price": _f(price),
                "open": _f(row.get("open")),
                "volume": _f(row.get("volume")),
                "avg_volume": _f(row.get("avgVolume")),
                "ma_50": _f(row.get("priceAvg50")),
                "ma_200": _f(row.get("priceAvg200")),
                "day_low": _f(row.get("dayLow")),
                "day_high": _f(row.get("dayHigh")),
                "prev_close": _f(row.get("previousClose")),
                "ts": row.get("timestamp"),
            }
        return out

    def get_quotes_batch(self, tickers: list[str],
                         chunk: int = 50) -> dict[str, dict]:
        """Batch quote fetch — comma-separated symbols, `chunk` per call.

        Same return shape as get_quotes() but drastically fewer API calls
        (~1 per 50 tickers vs 1 per ticker).
        """
        out: dict[str, dict] = {}
        url = f"{FMP_BASE_STABLE}/quote"
        for i in range(0, len(tickers), chunk):
            batch = tickers[i:i + chunk]
            try:
                payload = self._get_json(
                    url, params={"symbol": ",".join(batch),
                                 "apikey": self.config.api_key})
            except FMPQuotaError:
                raise
            except FMPError:
                continue
            if not isinstance(payload, list):
                continue
            for row in payload:
                if not isinstance(row, dict):
                    continue
                tk = (row.get("symbol") or "").upper()
                price = row.get("price")
                if not tk or price is None:
                    continue
                out[tk] = {
                    "price": _f(price),
                    "open": _f(row.get("open")),
                    "volume": _f(row.get("volume")),
                    "avg_volume": _f(row.get("avgVolume")),
                    "ma_50": _f(row.get("priceAvg50")),
                    "ma_200": _f(row.get("priceAvg200")),
                    "day_low": _f(row.get("dayLow")),
                    "day_high": _f(row.get("dayHigh")),
                    "prev_close": _f(row.get("previousClose")),
                    "ts": row.get("timestamp"),
                }
        return out

    def get_screener(
        self,
        min_mcap: int = 1_000_000_000,
        min_price: float = 5.0,
        min_volume: int = 500_000,
        exchanges: list[str] | None = None,
        limit: int = 5000,
    ) -> list[dict]:
        """Pull equity screener results from FMP.

        Returns list of dicts with keys: symbol, companyName, marketCap, price, volume, exchange.
        """
        if exchanges is None:
            exchanges = ["NASDAQ", "NYSE"]

        params = {
            "apikey": self.config.api_key,
            "marketCapMoreThan": str(min_mcap),
            "priceMoreThan": str(min_price),
            "volumeMoreThan": str(min_volume),
            "exchange": ",".join(exchanges),
            "isActivelyTrading": "true",
            "isEtf": "false",
            "limit": str(limit),
        }
        url = f"{FMP_BASE_STABLE}/company-screener"
        payload = self._get_json(url, params=params)
        if not isinstance(payload, list):
            return []
        return payload

    # ---------- internals ----------

    def _get_json(self, url: str, params: dict) -> dict | list:
        self._throttle()
        resp = self._session.get(url, params=params, timeout=self.config.timeout_seconds)
        if resp.status_code == 429:
            # FMP rate-limit hit. Back off a full minute and retry once.
            time.sleep(60)
            resp = self._session.get(url, params=params, timeout=self.config.timeout_seconds)
        if resp.status_code in (401, 403):
            if self._ok_count > 0:
                # Key worked before → likely daily quota, not bad key
                raise FMPQuotaError(
                    f"FMP daily quota likely reached after {self._ok_count} successful calls. "
                    f"Run the pipeline again later to pull remaining tickers (incremental)."
                )
            raise FMPError(
                "FMP rejected the API key. Possible causes: "
                "(a) FMP_API_KEY value is wrong / has a typo, "
                "(b) free plan doesn't cover /stable/historical-price-eod/full -- needs Starter+, "
                "(c) FMP abuse detection triggered by concurrent use from multiple IPs (same key "
                "used from local PC AND cloud at the same time). Response: " + resp.text[:200]
            )
        if not resp.ok:
            raise FMPError(f"FMP HTTP {resp.status_code} for {url}: {resp.text[:200]}")
        try:
            payload = resp.json()
        except ValueError as exc:
            raise FMPError(f"FMP non-JSON response for {url}: {exc}") from exc
        # FMP sometimes returns 200 OK with an error body
        if isinstance(payload, dict) and "Error Message" in payload:
            msg = payload["Error Message"]
            if "Invalid API KEY" in msg:
                if self._ok_count > 0:
                    # Key worked before → daily quota exhausted, not bad key.
                    # Wait 30s and retry once in case it was transient.
                    time.sleep(30)
                    resp2 = self._session.get(url, params=params,
                                              timeout=self.config.timeout_seconds)
                    try:
                        p2 = resp2.json()
                    except ValueError:
                        p2 = {}
                    if isinstance(p2, list) and p2:
                        self._ok_count += 1
                        return p2  # retry succeeded
                    raise FMPQuotaError(
                        f"FMP daily quota reached after {self._ok_count} successful calls. "
                        f"Run the pipeline again later to pull remaining tickers."
                    )
                raise FMPError(
                    f"FMP 'Invalid API KEY' on first call — the key is wrong or "
                    f"the plan doesn't cover this endpoint. Message: {msg}"
                )
            raise FMPError(f"FMP error: {msg}")
        self._ok_count += 1
        return payload

    def _throttle(self) -> None:
        now = time.monotonic()
        window_start = now - 60.0
        self._call_times = [t for t in self._call_times if t >= window_start]
        if len(self._call_times) >= self.config.rate_limit_per_min:
            sleep_for = 60.0 - (now - self._call_times[0]) + 0.05
            if sleep_for > 0:
                time.sleep(sleep_for)
        self._call_times.append(time.monotonic())


# ---------- helpers ----------


def test_api_key() -> dict:
    """One-shot FMP key validation. Returns {ok, message, plan_hint}.

    Calls the cheapest possible authenticated endpoint (a 5-bar SPY pull) and
    inspects the response. Used by the cloud diagnostic so the user can verify
    the key without burning a 5-minute pipeline run on a bad key.

    Never raises -- always returns a dict with `ok` boolean and a human message.
    """
    import os
    key = os.environ.get("FMP_API_KEY")
    if not key:
        return {"ok": False, "message": "FMP_API_KEY not set in environment.",
                "plan_hint": None}
    url = f"{FMP_BASE_STABLE}/historical-price-eod/full"
    params = {"symbol": "SPY", "apikey": key}
    try:
        resp = requests.get(url, params=params, timeout=15)
    except requests.RequestException as exc:
        return {"ok": False, "message": f"Network error: {exc}", "plan_hint": None}

    if resp.status_code in (401, 403):
        return {"ok": False,
                "message": f"FMP rejected the key (HTTP {resp.status_code}). "
                           f"Body: {resp.text[:160]}",
                "plan_hint": "Verify the key at https://site.financialmodelingprep.com/dashboard"}
    if not resp.ok:
        return {"ok": False,
                "message": f"HTTP {resp.status_code} from FMP: {resp.text[:160]}",
                "plan_hint": None}

    try:
        payload = resp.json()
    except ValueError:
        return {"ok": False, "message": f"Non-JSON response from FMP",
                "plan_hint": None}

    if isinstance(payload, dict) and "Error Message" in payload:
        msg = payload["Error Message"]
        plan_hint = None
        if "Invalid API KEY" in msg:
            plan_hint = ("FMP says 'Invalid API KEY' on a SINGLE test call. "
                         "Either the key value is wrong (typo / wrong key pasted), "
                         "or the key was revoked. Visit "
                         "https://site.financialmodelingprep.com/dashboard "
                         "to verify it's listed as active.")
        elif "Plan" in msg or "Subscription" in msg.lower():
            plan_hint = ("Your plan doesn't cover this endpoint. Starter plan "
                         "($14/mo) is the minimum that includes "
                         "/stable/historical-price-eod/full.")
        return {"ok": False, "message": f"FMP error: {msg}", "plan_hint": plan_hint}

    if isinstance(payload, list) and payload:
        return {"ok": True,
                "message": f"OK -- received {len(payload)} bars for SPY (most "
                           f"recent: {payload[0].get('date', '?')})",
                "plan_hint": None}

    return {"ok": False, "message": "Unexpected empty response.", "plan_hint": None}


def resample_to_weekly(daily: pd.DataFrame) -> pd.DataFrame:
    """Build weekly Friday-aligned bars from a daily frame.

    Each weekly bar is dated by its Friday close. To use a weekly value safely
    on daily date `t` (no look-ahead), join on the most recent weekly bar whose
    date is < `t`. The score runner handles that join.
    """
    if daily.empty:
        return _empty_bars_frame()
    idx = daily.set_index("date")
    weekly = pd.DataFrame({
        "open": idx["open"].resample("W-FRI").first(),
        "high": idx["high"].resample("W-FRI").max(),
        "low": idx["low"].resample("W-FRI").min(),
        "close": idx["close"].resample("W-FRI").last(),
        "volume": idx["volume"].resample("W-FRI").sum(),
    })
    weekly = weekly.dropna(subset=["close"]).reset_index()
    return weekly[["date", "open", "high", "low", "close", "volume"]]


def _f(v) -> float | None:
    """Best-effort float coercion — None/blank/non-numeric → None."""
    try:
        if v is None or v == "":
            return None
        return float(v)
    except (TypeError, ValueError):
        return None


def _as_iso(d: str | date) -> str:
    if isinstance(d, (date, datetime)):
        return d.strftime("%Y-%m-%d")
    return str(d)


def _empty_bars_frame() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "date": pd.Series(dtype="datetime64[ns]"),
            "open": pd.Series(dtype="float64"),
            "high": pd.Series(dtype="float64"),
            "low": pd.Series(dtype="float64"),
            "close": pd.Series(dtype="float64"),
            "volume": pd.Series(dtype="int64"),
        }
    )


def iter_with_progress(items: Iterable[str], label: str = "") -> Iterable[str]:
    """Tiny progress logger so build_panel.bat shows life on the console."""
    items = list(items)
    n = len(items)
    for i, item in enumerate(items, 1):
        prefix = f"[{label}] " if label else ""
        print(f"{prefix}{i}/{n} {item}", flush=True)
        yield item
