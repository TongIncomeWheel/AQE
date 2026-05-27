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


@dataclass
class FMPConfig:
    api_key: str
    rate_limit_per_min: int = DEFAULT_RATE_LIMIT_PER_MIN
    timeout_seconds: int = 30


class FMPError(RuntimeError):
    """Raised on any non-2xx response from FMP or unexpected payload shape."""


class FMPClient:
    """Synchronous client. Single-threaded use — we don't need parallel pulls."""

    def __init__(self, config: FMPConfig | None = None) -> None:
        if config is None:
            key = os.environ.get("FMP_API_KEY")
            if not key:
                raise FMPError(
                    "FMP_API_KEY not set. Copy .env.template to .env and fill it in."
                )
            config = FMPConfig(api_key=key)
        self.config = config
        self._session = requests.Session()
        self._call_times: list[float] = []  # rolling 60s window

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
            raise FMPError(
                "FMP rejected the API key. Open .env and confirm FMP_API_KEY is set correctly, "
                "and that your plan covers /historical-price-full. Response: " + resp.text[:200]
            )
        if not resp.ok:
            raise FMPError(f"FMP HTTP {resp.status_code} for {url}: {resp.text[:200]}")
        try:
            payload = resp.json()
        except ValueError as exc:
            raise FMPError(f"FMP non-JSON response for {url}: {exc}") from exc
        # FMP sometimes returns 200 OK with an error body for invalid tickers or plan limits.
        if isinstance(payload, dict) and "Error Message" in payload:
            raise FMPError(f"FMP error: {payload['Error Message']}")
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
