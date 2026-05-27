"""Tests for backtest modules — costs, sizing, triple barrier, portfolio sim."""

import numpy as np
import pandas as pd
import pytest

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


class TestCosts:
    def test_entry_fill_slips_up(self):
        from src.backtest.costs import entry_fill
        fill, comm = entry_fill(100.0, 100)
        assert fill == pytest.approx(100.10, abs=0.01)
        assert comm == pytest.approx(0.50, abs=0.01)

    def test_exit_fill_slips_down(self):
        from src.backtest.costs import exit_fill
        fill, comm = exit_fill(100.0, 100)
        assert fill == pytest.approx(99.90, abs=0.01)
        assert comm == pytest.approx(0.50, abs=0.01)

    def test_round_trip_cost(self):
        from src.backtest.costs import round_trip_cost
        cost = round_trip_cost(100.0, 105.0, 100)
        assert cost > 0
        # Slippage both sides + commission both sides
        # Entry: 100*0.001*100=10 + 0.50, Exit: 105*0.001*100=10.5 + 0.50 = ~21.5
        assert cost == pytest.approx(21.50, abs=0.5)


class TestSizing:
    def test_full_position(self):
        from src.backtest.sizing import compute_position_size
        result = compute_position_size(
            equity=100_000, entry_price=50.0,
            risk_per_share=2.0, disposition="FULL"
        )
        # 3% of $100K = $3000 risk / $2 per share = 1500 shares
        assert result["shares"] == 1500
        assert result["dollar_risk"] == pytest.approx(3000.0)

    def test_half_position(self):
        from src.backtest.sizing import compute_position_size
        result = compute_position_size(
            equity=100_000, entry_price=50.0,
            risk_per_share=2.0, disposition="HALF"
        )
        # 3% * 0.5 = 1.5% of $100K = $1500 / $2 = 750 shares
        assert result["shares"] == 750

    def test_quarter_position(self):
        from src.backtest.sizing import compute_position_size
        result = compute_position_size(
            equity=100_000, entry_price=50.0,
            risk_per_share=2.0, disposition="QUARTER"
        )
        # 3% * 0.25 = 0.75% of $100K = $750 / $2 = 375 shares
        assert result["shares"] == 375

    def test_reject_gives_zero(self):
        from src.backtest.sizing import compute_position_size
        result = compute_position_size(
            equity=100_000, entry_price=50.0,
            risk_per_share=2.0, disposition="REJECT"
        )
        assert result["shares"] == 0

    def test_zero_risk_per_share(self):
        from src.backtest.sizing import compute_position_size
        result = compute_position_size(
            equity=100_000, entry_price=50.0,
            risk_per_share=0.0, disposition="FULL"
        )
        assert result["shares"] == 0


class TestTripleBarrier:
    def test_upper_barrier_hit(self):
        from src.backtest.portfolio_sim import triple_barrier_label
        # Price gaps up immediately
        highs = np.array([110.0, 115.0])
        lows = np.array([99.0, 100.0])
        closes = np.array([105.0, 110.0])
        result = triple_barrier_label(highs, lows, closes, 100.0, 3.0, upper_mult=3.0)
        # Upper barrier = 100 + 3*3 = 109. First bar high=110 → hit
        assert result["label"] == 1
        assert result["barrier"] == "UPPER"
        assert result["bars"] == 1

    def test_lower_barrier_hit(self):
        from src.backtest.portfolio_sim import triple_barrier_label
        # Price drops
        highs = np.array([101.0, 100.0])
        lows = np.array([96.0, 95.0])
        closes = np.array([97.0, 96.0])
        result = triple_barrier_label(highs, lows, closes, 100.0, 3.0, lower_mult=1.0)
        # Lower = 100 - 1*3 = 97. First bar low=96 → hit
        assert result["label"] == -1
        assert result["barrier"] == "LOWER"
        assert result["bars"] == 1

    def test_vertical_barrier(self):
        from src.backtest.portfolio_sim import triple_barrier_label
        # Price stays flat
        highs = np.array([101.0] * 25)
        lows = np.array([99.0] * 25)
        closes = np.array([100.5] * 25)
        result = triple_barrier_label(highs, lows, closes, 100.0, 3.0, max_bars=5)
        # Upper=109, Lower=97 — neither hit in 5 bars
        assert result["barrier"] == "VERTICAL"
        assert result["bars"] == 5
        assert result["label"] == 1  # close > entry


class TestMonteCarlo:
    def test_basic_distribution(self):
        from src.backtest.portfolio_sim import monte_carlo_equity
        np.random.seed(42)
        pnls = [100.0] * 10 + [-50.0] * 5  # 10 wins, 5 losses
        result = monte_carlo_equity(pnls, 100_000, n_simulations=500)
        assert result["median_return_pct"] > 0
        assert result["p95_max_dd_pct"] > 0
        assert result["p5_return_pct"] <= result["median_return_pct"]

    def test_empty_trades(self):
        from src.backtest.portfolio_sim import monte_carlo_equity
        result = monte_carlo_equity([], 100_000)
        assert result["median_return_pct"] == 0.0
