# AQE RED TEAM REVIEW
## Three-Voice Independent Assessment | 18 May 2026

**Reviewers:**
- **Marcos López de Prado** — Quant/Backtesting Methodology
- **Robert Pardo** — Systematic Strategy Evaluation & Walk-Forward Analysis
- **Ernest Chan** — Quantitative PM, Solo Practitioner Scale

**Documents reviewed:** Design Committee Spec v1.0, AQE Engineering Spec v0.1, Backtest Calibration Spec v0.1

Each voice reviews independently. Synthesis and remediation plan follows.

---

# VOICE 1 — MARCOS LÓPEZ DE PRADO

## Overall Assessment

The team has built a thoughtful, well-structured indicator stack. The decision to move from TradingView to a local compute pipeline is correct. However, the backtesting and calibration framework as specified will produce **dangerously overfit results** and a **false sense of statistical confidence**. I count at least five of my Seven Sins of Quantitative Investing present in this specification.

## Critical Findings

### FINDING MLP-1: MULTIPLE TESTING BIAS (SEVERITY: HIGH)

The calibration engine proposes to test every gate threshold from 30 to 80 in steps of 5, every engine weight in a continuous optimisation space, and every scoring curve for monotonicity. This is a massive multiple-testing problem.

When you test 11 thresholds × 5 engines × 2 pipelines = 110 hypotheses, at p=0.05 you expect ~5.5 false positives by chance alone. The specification contains no correction for this.

**Remedy:** Apply the Bonferroni correction or, better, the Deflated Sharpe Ratio (DSR). For every "improvement" the calibration engine proposes, compute the probability that this result would occur by chance given the total number of trials conducted. Report the DSR alongside the raw Sharpe. If DSR < 1.0, the improvement is not statistically distinguishable from noise.

```python
def deflated_sharpe_ratio(observed_sharpe, num_trials, 
                          variance_of_sharpes, T):
    """
    López de Prado (2014). Accounts for selection bias
    when choosing the best strategy from multiple trials.
    
    observed_sharpe: Sharpe of the 'best' strategy found
    num_trials: total strategies tested (including rejected ones)
    variance_of_sharpes: variance across all trial Sharpes
    T: number of observations (bars)
    """
    from scipy.stats import norm
    
    expected_max = variance_of_sharpes * \
        ((1 - np.euler_gamma) * norm.ppf(1 - 1/num_trials) + 
         np.euler_gamma * norm.ppf(1 - 1/(num_trials * np.e)))
    
    se = np.sqrt((1 + 0.5 * observed_sharpe**2) / (T - 1))
    
    dsr = norm.cdf((observed_sharpe - expected_max) / se)
    return dsr
```

### FINDING MLP-2: BACKTEST OVERFITTING THROUGH PROFILE MATCHING (SEVERITY: HIGH)

The Backtest Confidence layer matches live candidates to historical "twins" using a profile signature with 8 dimensions. This is a form of conditional analysis that can produce arbitrarily good-looking subsets.

The problem: with enough dimensions, you can always find a subset of historical trades that looks good. "STRONG composite + BUILDING MP + GREEN regime + DEPLOY SRM + STAIR BD + SMOOTH FIP" might match 25 historical cases with 72% win rate. But that 72% is a sample artefact — the narrow filter selected for winners.

**Remedy:** Use the **Combinatorially Symmetric Cross-Validation (CSCV)** method to test whether the profile matching is genuinely predictive or just overfitting to the particular historical sample.

Additionally, compute the **Probability of Backtest Overfitting (PBO):**

```python
def probability_of_backtest_overfitting(returns_matrix, num_partitions=16):
    """
    Bailey et al. (2014). Splits the data into S subsets,
    forms all C(S, S/2) train/test combinations, checks how
    often the best in-sample model underperforms out-of-sample.
    
    PBO > 0.50 means your 'best' model is more likely to be
    overfit than not.
    """
    from itertools import combinations
    
    S = num_partitions
    subsets = np.array_split(returns_matrix, S)
    
    count_overfit = 0
    total = 0
    
    for train_idx in combinations(range(S), S // 2):
        test_idx = [i for i in range(S) if i not in train_idx]
        
        # Compute performance on train and test
        train_perf = compute_perf(subsets, train_idx)
        test_perf = compute_perf(subsets, test_idx)
        
        # Best in-sample strategy
        best_is = np.argmax(train_perf)
        
        # Does it rank below median out-of-sample?
        oos_rank = rankdata(test_perf)[best_is]
        if oos_rank <= len(test_perf) / 2:
            count_overfit += 1
        total += 1
    
    return count_overfit / total
```

**Practically:** Run PBO on the profile matching system. If PBO > 0.40, the confidence layer is overfit and should use broader profile tiers only.

### FINDING MLP-3: FORWARD-LOOKING BIAS IN OUTCOME TAGGING (SEVERITY: MEDIUM)

The forward outcome tagging computes `mfe_10d`, `mae_10d`, and `trail_exit_r` using future bars from the scoring date. This is correct for building the outcome database. However, the specification does not address the **embargo period** between train and test sets in walk-forward analysis.

If a stock is scored on day T, and you're testing a calibration change, the training set must exclude days T-5 through T+40 (the forward outcome window) to prevent information leakage.

**Remedy:** Implement a **purge + embargo** protocol:

```python
def purged_kfold(dates, n_splits, embargo_pct=0.01):
    """
    Purged K-Fold CV (López de Prado, 2018).
    
    Purges: removes from training any observation whose 
    forward-outcome period overlaps with test observations.
    
    Embargoes: additionally removes a buffer of observations
    immediately after the test set to prevent serial correlation
    leakage.
    """
    embargo_size = int(len(dates) * embargo_pct)
    
    for train_idx, test_idx in KFold(n_splits).split(dates):
        # Purge: remove training obs that overlap test forward window
        test_start = dates[test_idx[0]]
        test_end = dates[test_idx[-1]]
        
        train_idx = [i for i in train_idx 
                     if not overlaps_forward_window(dates[i], 
                                                     test_start, test_end)]
        
        # Embargo: remove post-test buffer
        embargo_start = test_idx[-1] + 1
        embargo_end = min(embargo_start + embargo_size, len(dates))
        train_idx = [i for i in train_idx 
                     if i < test_idx[0] or i >= embargo_end]
        
        yield train_idx, test_idx
```

### FINDING MLP-4: TRIPLE BARRIER METHOD MISSING (SEVERITY: MEDIUM)

The outcome classification uses a simple trail exit R-multiple. This conflates TIME and PRICE. A stock that reaches +2R in 3 days is fundamentally different from one that reaches +2R in 25 days.

**Remedy:** Adopt the **triple barrier method** for labelling outcomes:

```
Three barriers define the outcome:
  1. UPPER BARRIER: Take-profit hit (e.g., +2R)     → label = +1
  2. LOWER BARRIER: Stop-loss hit (e.g., -1R)        → label = -1
  3. VERTICAL BARRIER: Time expiry (e.g., 20 bars)   → label = sign(return)
  
Whichever barrier is hit FIRST defines the outcome.
```

This produces a much richer outcome distribution because it captures the PATH, not just the final price. A stock that hits +2R on day 3 and then reverses to -1R on day 18 is correctly labelled as a +1 (upper barrier hit first), not as a loser.

```python
def triple_barrier_label(bars, entry_price, upper_mult, lower_mult, 
                         max_bars, risk_per_share):
    """
    Label a trade using the triple barrier method.
    
    Returns: (label, barrier_hit, bars_to_hit)
    """
    upper = entry_price + (risk_per_share * upper_mult)
    lower = entry_price - (risk_per_share * lower_mult)
    
    for i, bar in enumerate(bars[:max_bars]):
        if bar['high'] >= upper:
            return (+1, 'UPPER', i)
        if bar['low'] <= lower:
            return (-1, 'LOWER', i)
    
    # Vertical barrier: time expiry
    final_return = bars[min(max_bars-1, len(bars)-1)]['close'] - entry_price
    label = 1 if final_return > 0 else (-1 if final_return < 0 else 0)
    return (label, 'VERTICAL', max_bars)
```

### FINDING MLP-5: SAMPLE WEIGHT BY UNIQUENESS (SEVERITY: LOW-MEDIUM)

When building the outcome database, overlapping trades from the same sector during the same regime will produce correlated outcomes. 50 "DEPLOY Nuclear" trades during a uranium bull run are not 50 independent observations — they are ~5-10 independent observations repeated with correlation.

**Remedy:** Weight samples by **average uniqueness** — the fraction of the return period during which a trade is the only active trade in its sector:

```python
def compute_sample_uniqueness(trades):
    """
    For each trade, what fraction of its holding period 
    was it the only trade in its sector?
    Lower uniqueness = higher correlation with other trades.
    """
    for trade in trades:
        overlap_count = count_concurrent_same_sector(trade, trades)
        trade.uniqueness = 1.0 / overlap_count
    
    # Normalise weights
    total = sum(t.uniqueness for t in trades)
    for trade in trades:
        trade.sample_weight = trade.uniqueness / total
```

Use these weights in all statistical computations (win rate, expectancy, etc.).

---

# VOICE 2 — ROBERT PARDO

## Overall Assessment

The walk-forward framework in the specification is correctly conceived in principle — train on 12 months, test on 3, step by 1. This is sound. However, the implementation details contain several gaps that would produce unreliable optimisation results. The specification also confuses two distinct activities: **evaluation** (is this strategy any good?) and **optimisation** (what parameters make it best?). These must be kept separate.

## Critical Findings

### FINDING RP-1: WALK-FORWARD EFFICIENCY RATIO MISSING (SEVERITY: HIGH)

The walk-forward analysis measures out-of-sample performance but does not compute the **Walk-Forward Efficiency Ratio (WFER)** — the ratio of out-of-sample performance to in-sample performance. This is the single most important metric in strategy evaluation.

```
WFER = (OOS annualised return) / (IS annualised return)
```

| WFER | Interpretation |
|------|---------------|
| >0.50 | Robust. Parameter set generalises well. |
| 0.30-0.50 | Acceptable. Some degradation but viable. |
| <0.30 | Fragile. Strategy is curve-fit to training period. |
| <0 | Broken. Strategy loses money out of sample. |

**Every walk-forward window must report WFER.** If average WFER across all windows is below 0.30, the strategy is not tradeable regardless of how good the in-sample results look.

```python
def walk_forward_efficiency(is_returns, oos_returns):
    """
    Pardo Walk-Forward Efficiency Ratio.
    The gold standard for strategy robustness.
    """
    is_annual = annualise(is_returns)
    oos_annual = annualise(oos_returns)
    
    if is_annual <= 0:
        return 0  # Strategy doesn't work in-sample either
    
    return oos_annual / is_annual
```

### FINDING RP-2: PARAMETER SPACE NOT DEFINED (SEVERITY: HIGH)

The calibration engine optimises weights using `scipy.minimize` with continuous bounds. This is dangerous for two reasons:

1. **Continuous optimisation on noisy data finds noise, not signal.** Financial returns are noisy. An optimiser that can adjust weights to 4 decimal places will find the exact weight that exploits a specific sequence of returns.

2. **No parameter granularity constraint.** If the optimal Flow weight is 0.2847 and you're currently at 0.30, is that a real improvement or noise? You cannot tell without defining a minimum meaningful step.

**Remedy:** Define a **parameter grid** with meaningful step sizes:

```python
WEIGHT_GRID = [0.10, 0.15, 0.20, 0.25, 0.30, 0.35, 0.40]  # 7 values
GATE_GRID = [40, 45, 50, 55, 60, 65, 70]                     # 7 values
TRAIL_MULT_GRID = [0.75, 1.0, 1.25, 1.5, 1.75, 2.0, 2.5]   # 7 values
```

Use **exhaustive grid search** on this coarse grid, not continuous optimisation. The total search space for 4 engine weights at 7 levels = 7^4 = 2,401 combinations. This is computationally trivial and eliminates precision-overfitting.

Then apply the Deflated Sharpe Ratio (from López de Prado above) to account for the 2,401 trials.

### FINDING RP-3: IN-SAMPLE MINIMUM NOT SPECIFIED (SEVERITY: MEDIUM)

The specification states "minimum 60 trades in the test dataset." This is the out-of-sample minimum. But there is no in-sample minimum specified.

**Rule of thumb:** The training window must contain **at least 10× the number of parameters being optimised.** For 4 engine weights, that's 40 trades minimum in training. For the full parameter set (4 weights + 5 gates + trail multipliers = ~15 parameters), you need 150 trades in training.

With ~120 trades per year at current frequency, a 12-month training window gives ~120 trades. This supports optimising ~12 parameters simultaneously. If you want to optimise more, you need a longer training window or higher trading frequency.

**Remedy:** Add explicit in-sample minimums:

```python
MIN_IS_TRADES = max(10 * num_parameters, 50)
MIN_OOS_TRADES = 30  # reduced from 60 — 60 is too conservative
                      # for a strategy trading ~10x/month
```

### FINDING RP-4: ANCHORED VS ROLLING WALK-FORWARD (SEVERITY: MEDIUM)

The specification uses a rolling 12-month window. This discards old data. For a strategy with limited trade frequency (~10/month), discarding older data is wasteful.

**Remedy:** Offer both modes:

- **Rolling** (current): 12-month sliding window. Best when market regime changes make old data irrelevant.
- **Anchored**: Training window starts at a fixed point and GROWS. All historical data is always included. Best when you want maximum sample size.

```python
def walk_forward(mode="anchored", anchor_date=None, ...):
    if mode == "anchored":
        train_start = anchor_date  # fixed
        train_end = current_window_start
    elif mode == "rolling":
        train_start = current_window_start - train_period
        train_end = current_window_start
```

Run BOTH. If anchored produces higher WFER than rolling, the strategy benefits from more data. If rolling produces higher WFER, regime sensitivity dominates.

### FINDING RP-5: NO MONTE CARLO STRESS TEST (SEVERITY: MEDIUM)

The backtest runs on the actual historical sequence. This is ONE path through history. The strategy might look good because it happened to avoid the worst drawdowns by timing luck.

**Remedy:** Run **Monte Carlo permutation** on the trade sequence:

```python
def monte_carlo_equity_curves(closed_trades, num_simulations=2000):
    """
    Shuffle the order of trades randomly and rebuild the equity
    curve for each permutation. This shows the DISTRIBUTION of
    possible outcomes from the same set of trades.
    
    If the original equity curve is near the median, the result
    is robust. If it's in the top 10%, sequence luck is a factor.
    """
    results = []
    pnl_sequence = [t.pnl for t in closed_trades]
    
    for _ in range(num_simulations):
        shuffled = np.random.permutation(pnl_sequence)
        equity = np.cumsum(shuffled) + initial_capital
        max_dd = compute_max_drawdown(equity)
        final_return = (equity[-1] - initial_capital) / initial_capital
        results.append({
            "final_return": final_return,
            "max_drawdown": max_dd,
            "sharpe": compute_sharpe(np.diff(equity))
        })
    
    return {
        "median_return": np.median([r["final_return"] for r in results]),
        "p5_return": np.percentile([r["final_return"] for r in results], 5),
        "p95_drawdown": np.percentile([r["max_drawdown"] for r in results], 95),
        "median_sharpe": np.median([r["sharpe"] for r in results]),
        "risk_of_ruin_pct": mean(1 for r in results 
                                  if r["max_drawdown"] > 0.25) * 100
    }
```

This answers: "What is the worst drawdown I should expect from this strategy, accounting for the fact that trade order is random?"

---

# VOICE 3 — ERNEST CHAN

## Overall Assessment

The system architecture is impressive for a solo operation. The staged approach — Claude as AI layer now, standalone app later — is pragmatic. However, I see several issues that specifically affect a single-operator, limited-capital systematic strategy. The specification over-engineers some areas and under-engineers others.

## Critical Findings

### FINDING EC-1: SURVIVORSHIP BIAS IN UNIVERSE (SEVERITY: HIGH)

The FMP screener filters for `isActivelyTrading=true` and `marketCapMoreThan=1B`. When you backtest historically, you will only include stocks that SURVIVED to the present day. Companies that were in the universe 2 years ago but have since been delisted, acquired, or fallen below $1B are invisible.

This inflates backtest returns by 1-3% annually (documented extensively in the literature). Your win rate will look better in backtest than in live trading.

**Remedy:**

1. **Point-in-time universe reconstruction.** For each historical date, use the universe that EXISTED on that date, not today's universe. FMP's `historical-price-eod-full` will return data for delisted tickers if you know the symbol. The challenge is KNOWING which tickers were in the universe historically.

2. **Practical fallback:** If point-in-time reconstruction is infeasible (FMP Starter may not support delisted tickers), apply a **survivorship bias haircut** to all backtest results:

```python
SURVIVORSHIP_BIAS_HAIRCUT = 0.02  # 2% annual return reduction
# Apply to annualised return before reporting
adjusted_return = backtest_annual_return - SURVIVORSHIP_BIAS_HAIRCUT
```

3. **Best available approach:** Use FMP's `symbol-changes-list` endpoint to identify tickers that changed symbols. Pull their historical data under old symbols. This partially addresses the problem.

### FINDING EC-2: TRANSACTION COSTS NOT MODELLED (SEVERITY: HIGH)

The backtest engine computes entries at `bar['close']` and exits at `exit_price`. There is zero slippage model, zero commission model, and no consideration of bid-ask spread.

For a $70K account trading ~10 positions per month with $5K-$12K per position, transaction costs are material:

```
IBKR tiered: ~$0.0035/share × 100 shares = $0.35 per trade
Slippage (momentum stocks, market hours): ~0.05-0.15% per side
Round-trip cost: ~0.10-0.30% of position value

On $8K avg position: $8-$24 per round trip
× 10 trades/month: $80-$240/month
× 12 months: $960-$2,880/year
On $70K capital: 1.4%-4.1% annual drag
```

**This is NOT negligible.** At your capital scale and trade frequency, a 2-3% annual transaction cost drag can turn a 12% gross return into a 9% net return.

**Remedy:**

```python
# In backtest engine
COMMISSION_PER_SHARE = 0.005   # IBKR tiered (conservative)
SLIPPAGE_PCT = 0.0010          # 10bps per side (momentum stocks)

def execute_entry(price, shares):
    slippage = price * SLIPPAGE_PCT
    fill_price = price + slippage  # buy at worse price
    commission = shares * COMMISSION_PER_SHARE
    return fill_price, commission

def execute_exit(price, shares):
    slippage = price * SLIPPAGE_PCT
    fill_price = price - slippage  # sell at worse price
    commission = shares * COMMISSION_PER_SHARE
    return fill_price, commission
```

Also model the **entry timing gap**: you place bracket orders pre-market (before 10:30 PM SGT). The market opens at 9:30 AM ET. Your limit price may not fill, or may fill at a different price. Model this as additional slippage on entry.

### FINDING EC-3: KELLY CRITERION AND POSITION SIZING (SEVERITY: MEDIUM)

The specification uses a fixed 1% risk budget per full position. This is the Van Tharp approach and it works, but it ignores information the system already has.

Once the backtest confidence layer produces win rates and payoff ratios per profile type, you can compute the **Kelly-optimal position size** for each trade:

```python
def kelly_fraction(win_rate, avg_win_r, avg_loss_r):
    """
    Kelly Criterion: optimal fraction of capital to risk.
    
    f* = (p × b - q) / b
    
    where:
      p = probability of win
      q = probability of loss = 1 - p
      b = ratio of win size to loss size (avg_win / avg_loss)
    """
    b = abs(avg_win_r / avg_loss_r)
    f = (win_rate * b - (1 - win_rate)) / b
    return max(f, 0)  # never negative

def practical_kelly(win_rate, avg_win_r, avg_loss_r, 
                    fraction=0.25):
    """
    Use QUARTER Kelly (fraction=0.25) for real trading.
    Full Kelly is theoretically optimal but assumes perfect
    knowledge of the distribution — we don't have that.
    Quarter Kelly sacrifices ~50% of growth rate but reduces
    drawdown by ~75%.
    """
    full_kelly = kelly_fraction(win_rate, avg_win_r, avg_loss_r)
    return full_kelly * fraction
```

The backtest confidence layer's win rate and average R per profile type feed directly into Kelly sizing. A trade with 65% win rate and 2.5:1 payoff ratio gets a larger Kelly fraction than a 52% / 1.8:1 trade. This is information-theoretically optimal capital allocation.

**Practical implementation:** Use quarter-Kelly as a CEILING on the 1% risk budget. Never exceed the charter's FULL/HALF/QUARTER disposition. Kelly provides a principled way to choose between HALF and FULL when PTRS says FULL.

### FINDING EC-4: REGIME CHANGE DETECTION (SEVERITY: MEDIUM)

The system classifies regime by VIX level (GREEN/YELLOW/ORANGE/RED). This is static. The system should also detect **regime transitions** — the moment when market character is changing.

A strategy calibrated in a trending regime will underperform in a mean-reverting regime, and vice versa. The calibration engine should segment its outcome database BY regime and report separate metrics.

**Remedy:** Add a simple regime change detector:

```python
def detect_regime_change(vix_series, spy_returns, lookback=60):
    """
    Detect whether the market is in a trending or 
    mean-reverting regime using the Hurst exponent.
    
    H > 0.55: trending (momentum strategies favoured)
    H ≈ 0.50: random walk
    H < 0.45: mean-reverting (momentum strategies suffer)
    """
    # Hurst exponent via rescaled range
    from hurst import compute_Hc
    H, c, data = compute_Hc(spy_returns[-lookback:], 
                             kind='price', simplified=True)
    
    regime_type = "TRENDING" if H > 0.55 else \
                  "MEAN_REVERT" if H < 0.45 else "RANDOM"
    
    return {
        "hurst": H,
        "regime_type": regime_type,
        "implication": "Momentum strategies favoured" if H > 0.55 
                       else "Caution: momentum may underperform"
    }
```

Segment the outcome database: "In TRENDING regimes, SC_MOMENTUM ≥ 65 produced 62% win rate. In MEAN_REVERT regimes, same score produced 41% win rate." This is actionable intelligence for the PM.

### FINDING EC-5: CAPACITY AND MARKET IMPACT (SEVERITY: LOW)

At $70K capital with $5K-$12K positions, market impact is negligible for large-caps. But several of your thematic baskets include small-cap names (IONQ, RGTI, QBTS, JOBY) where your order could represent a meaningful fraction of daily volume.

**Remedy:** Add a **capacity check** to the scoring pipeline:

```python
def capacity_check(ticker, position_value, avg_daily_volume, 
                   avg_price):
    """
    Ensure position doesn't represent too large a fraction
    of daily volume.
    """
    daily_dollar_volume = avg_daily_volume * avg_price
    participation_rate = position_value / daily_dollar_volume
    
    if participation_rate > 0.01:  # >1% of daily volume
        return "CAPACITY_WARNING"
    return "OK"
```

This matters more if/when capital grows. Build the check now so it's there when needed.

---

# SYNTHESIS — PRIORITISED REMEDIATION PLAN

## Tier 1: Must Fix Before Any Backtest Results Are Trusted

| # | Finding | Remediation | Effort |
|---|---------|-------------|--------|
| 1 | **EC-2: Transaction costs** | Add slippage + commission model to backtest engine. 10bps + $0.005/share baseline. | 2 hours |
| 2 | **EC-1: Survivorship bias** | Apply 2% annual haircut to backtest returns. Attempt point-in-time universe via FMP symbol changes. | 4 hours |
| 3 | **MLP-1: Multiple testing** | Implement Deflated Sharpe Ratio. Report alongside all calibration results. Reject improvements with DSR < 1.0. | 4 hours |
| 4 | **RP-1: Walk-forward efficiency** | Add WFER computation to every walk-forward window. Reject strategies with avg WFER < 0.30. | 2 hours |

## Tier 2: Required Before Calibration Engine Goes Live

| # | Finding | Remediation | Effort |
|---|---------|-------------|--------|
| 5 | **MLP-2: Profile overfitting** | Compute PBO on the confidence layer. Use BROAD tier matching until PBO < 0.40 at tighter tiers. | 8 hours |
| 6 | **RP-2: Parameter grid** | Replace continuous optimisation with coarse grid search. 7 levels per parameter. | 3 hours |
| 7 | **MLP-3: Purge + embargo** | Add purged K-fold CV with embargo period = forward outcome window. | 4 hours |
| 8 | **MLP-4: Triple barrier** | Implement triple barrier labelling alongside trail-based labelling. Report both. | 4 hours |
| 9 | **RP-3: IS/OOS minimums** | Define explicit sample size requirements: IS ≥ 10× parameters, OOS ≥ 30. | 1 hour |

## Tier 3: Enhance Once Foundation Is Solid

| # | Finding | Remediation | Effort |
|---|---------|-------------|--------|
| 10 | **RP-5: Monte Carlo** | Implement 2000-iteration permutation test on trade sequence. Report p5 drawdown and risk of ruin. | 3 hours |
| 11 | **RP-4: Anchored WF** | Add anchored walk-forward mode alongside rolling. Compare WFER. | 2 hours |
| 12 | **EC-3: Kelly sizing** | Compute quarter-Kelly from BC layer. Use as ceiling on 1% risk budget. | 3 hours |
| 13 | **EC-4: Regime detection** | Add Hurst exponent regime classifier. Segment outcome database by trending/reverting. | 4 hours |
| 14 | **MLP-5: Sample uniqueness** | Weight overlapping same-sector trades by uniqueness in all statistics. | 3 hours |
| 15 | **EC-5: Capacity check** | Add participation rate check to scoring pipeline. Warn at >1% of daily volume. | 1 hour |

## Total Estimated Effort: ~48 hours

---

# KEY TERMINOLOGY FOR THE PM

Since the PM noted unfamiliarity with backtesting techniques, here are the critical concepts referenced above in plain language:

**Deflated Sharpe Ratio (DSR):** When you test 100 parameter combinations and pick the best one, you're probably picking luck, not skill. DSR adjusts the score downward based on how many combinations you tested. If your "best" strategy still looks good after this adjustment, it's probably real.

**Walk-Forward Efficiency Ratio (WFER):** You train the system on 12 months of data and it produces a 40% return in-sample. Then you test it on the NEXT 3 months and it produces a 15% return. WFER = 15/40 = 0.375. Anything above 0.30 is acceptable. Below 0.30 means the "learning" was mostly memorisation, not generalisation.

**Probability of Backtest Overfitting (PBO):** You split your data into 16 chunks and test every possible way of dividing them into "train" and "test" halves. If the best training result also performs well in testing more than 50% of the time, PBO is low (good). If it underperforms in testing more than 50% of the time, PBO is high — your backtest is lying to you.

**Triple Barrier Method:** Instead of just asking "did this trade make money?", ask "which of three things happened FIRST: hit the profit target, hit the stop loss, or ran out of time?" This captures the quality of the trade, not just the final result.

**Survivorship Bias:** Your historical database only contains stocks that still exist today. The ones that went bankrupt, got acquired at fire-sale prices, or collapsed to penny-stock status are invisible. This makes your backtest look 1-3% better per year than reality.

**Monte Carlo Permutation:** Shuffle your trade results into random order 2,000 times and rebuild the equity curve each time. This shows you the RANGE of possible outcomes. If your real equity curve is near the middle of this range, the result is robust. If it's in the top 10%, you got lucky with sequencing.

**Kelly Criterion:** A mathematical formula that tells you the optimal bet size given your win rate and average payoff. Full Kelly maximises long-term growth but has brutal drawdowns. Quarter Kelly (betting 25% of the Kelly amount) gives up about half the growth rate but cuts maximum drawdown by 75%. For a solo PM, quarter Kelly is the practical choice.

**Hurst Exponent:** A number between 0 and 1 that tells you whether recent prices are trending (H > 0.55, momentum works well) or reverting to the mean (H < 0.45, momentum strategies get chopped up). If H is near 0.50, the market is a random walk and no strategy has an edge.

---

*Red Team Review completed by: López de Prado, Pardo, Chan*
*Reviewed documents: Design Committee Spec v1.0, AQE Engineering Spec v0.1, Backtest Calibration Spec v0.1*
*All findings independent. Synthesis by Alfred.*
