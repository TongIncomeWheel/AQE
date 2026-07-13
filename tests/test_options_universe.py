"""Tests for the Alpaca adapter + universe theta scanner — pure, no network."""

from __future__ import annotations

from datetime import date

import pytest

from src.options.providers import alpaca
from src.options import universe_scan as U
from src.options import config as C


TODAY = date(2026, 7, 13)


# ── OCC symbol parsing ──────────────────────────────────────────────────────
def test_parse_occ_symbol():
    root, exp, right, strike = alpaca.parse_occ_symbol("MRVL260821P00195000")
    assert root == "MRVL"
    assert exp == date(2026, 8, 21)
    assert right == "PUT"
    assert strike == 195.0


def test_parse_occ_variable_root_and_call():
    root, exp, right, strike = alpaca.parse_occ_symbol("F260918C00012500")
    assert root == "F" and right == "CALL" and strike == 12.5


# ── Chain snapshot → contract dicts ─────────────────────────────────────────
def _snap_resp():
    # Real Alpaca shape: camelCase containers, short quote keys, decimal IV.
    return {"snapshots": {
        "MRVL260821P00195000": {
            "latestQuote": {"bp": 11.5, "ap": 11.9, "bs": 5, "as": 7},
            "impliedVolatility": 0.92,
            "greeks": {"delta": -0.24, "gamma": 0.01, "theta": -0.3, "vega": 0.2},
        },
        "MRVL260821P00192500": {                         # non-round strike → dropped
            "latestQuote": {"bp": 10.0, "ap": 10.4},
            "impliedVolatility": 0.93, "greeks": {"delta": -0.22},
        },
        "MRVL260717P00195000": {                         # 4 DTE → outside window
            "latestQuote": {"bp": 3.0, "ap": 3.2},
            "impliedVolatility": 0.95, "greeks": {"delta": -0.15},
        },
        "MRVL260821C00250000": {                         # a call → dropped (puts only)
            "latestQuote": {"bp": 1.0, "ap": 1.2},
            "impliedVolatility": 0.80, "greeks": {"delta": 0.10},
        },
    }}


def test_parse_chain_filters_and_maps():
    rows = alpaca.parse_chain(_snap_resp(), "MRVL", spot=228.5, today=TODAY,
                              dte_min=20, dte_max=50, strike_step=5.0)
    # Only the round-strike, in-window put survives.
    assert len(rows) == 1
    c = rows[0]
    assert c["ticker"] == "MRVL" and c["strike"] == 195.0 and c["dte"] == 39
    assert c["iv"] == 0.92 and c["bid"] == 11.5 and c["ask"] == 11.9
    assert c["right"] == "PUT" and c["alpaca_delta"] == -0.24


def test_parse_chain_handles_snake_case_and_missing_iv():
    resp = {"snapshots": {"AAPL260821P00300000": {
        "latest_quote": {"bid_price": 4.8, "ask_price": 5.0},  # snake variant
    }}}
    rows = alpaca.parse_chain(resp, "AAPL", spot=315.0, today=TODAY,
                              dte_min=20, dte_max=50, strike_step=5.0)
    assert len(rows) == 1
    assert rows[0]["bid"] == 4.8 and rows[0]["ask"] == 5.0 and rows[0]["iv"] is None


def test_parse_spots():
    resp = {"snapshots": {
        "MRVL": {"latestTrade": {"p": 228.5}},
        "AAPL": {"dailyBar": {"c": 315.26}},              # falls back to daily close
    }}
    spots = alpaca.parse_spots(resp)
    assert spots == {"MRVL": 228.5, "AAPL": 315.26}


# ── fetch_put_chain with an injected http_get (no network) ───────────────────
def test_fetch_put_chain_injected():
    calls = []

    def fake_get(path, params):
        calls.append((path, params))
        return _snap_resp()                               # single page

    rows = alpaca.fetch_put_chain("MRVL", 228.5, today=TODAY, dte_min=20,
                                  dte_max=50, http_get=fake_get)
    assert len(rows) == 1
    assert calls[0][1]["type"] == "put" and calls[0][1]["feed"] == C.ALPACA_FEED


# ── Universe orchestration with stub provider ───────────────────────────────
def test_scan_universe_aggregates_and_ranks():
    tickers = ["AAA", "BBB", "NOSPOT"]

    def fake_spots(syms):
        return {"AAA": 100.0, "BBB": 200.0}               # NOSPOT missing → skipped

    def fake_chain(tk, spot, today, dte_min, dte_max):
        # One in-band CSP per name; BBB richer (higher IV → higher yield).
        iv = 0.35 if tk == "AAA" else 0.55
        strike = round(spot * 0.92 / 5) * 5               # ~8% OTM, round to 5
        return [{"ticker": tk, "spot": spot, "strike": strike, "dte": 35,
                 "iv": iv, "bid": None, "ask": None, "right": "PUT"}]

    blob = U.scan_universe(tickers=tickers, today=TODAY,
                           fetch_spots=fake_spots, fetch_put_chain=fake_chain,
                           filters={"min_annual_yield": 0.0, "min_pop": 0.0,
                                    "delta_min": 0.0, "delta_max": 1.0},
                           log=lambda *_: None)
    assert blob["priced"] == 2
    assert blob["names_no_spot"] == ["NOSPOT"]
    ys = [c["annual_yield"] for c in blob["candidates"]]
    assert ys == sorted(ys, reverse=True)                 # ranked desc
    assert blob["candidates"][0]["ticker"] == "BBB"       # richer IV wins


def test_scan_universe_survives_bad_name():
    def fake_spots(syms):
        return {"OK": 100.0, "BOOM": 100.0}

    def fake_chain(tk, spot, today, dte_min, dte_max):
        if tk == "BOOM":
            raise RuntimeError("chain 500")
        return [{"ticker": tk, "spot": spot, "strike": 90, "dte": 35,
                 "iv": 0.4, "bid": None, "ask": None, "right": "PUT"}]

    blob = U.scan_universe(tickers=["OK", "BOOM"], today=TODAY,
                           fetch_spots=fake_spots, fetch_put_chain=fake_chain,
                           filters={"min_annual_yield": 0.0, "min_pop": 0.0,
                                    "delta_min": 0.0, "delta_max": 1.0},
                           log=lambda *_: None)
    assert "BOOM" in blob["names_errored"]
    assert blob["candidates_count"] >= 1                   # OK still scanned


def test_export_scan_to_drive_writes_local_and_keeps_one(monkeypatch, tmp_path):
    from src.data import gdrive_uploader
    kept = {}
    monkeypatch.setattr(gdrive_uploader, "upload_or_replace",
                        lambda fn, content, folder_id=None: {
                            "ok": True, "file_id": "F1", "replaced": True,
                            "filename": fn, "folder_id": folder_id})
    monkeypatch.setattr(gdrive_uploader, "keep_only_file",
                        lambda folder, fid: kept.update(folder=folder, fid=fid))
    out = U.export_scan_to_drive({"candidates": [], "candidates_count": 0},
                                 str(tmp_path / "options_scan.json"))
    assert out["drive"]["ok"] and out["drive"]["file_id"] == "F1"
    assert (tmp_path / "options_scan.json").exists()       # local copy always written
    assert kept["fid"] == "F1"                             # trims to a single Drive file
    assert kept["folder"] == C.GDRIVE_CSP_FOLDER_ID
