# AQE BACKTEST ENGINE — SCORING LAYER & CALIBRATION FRAMEWORK
## Enhancement Specification v0.1 | 18 May 2026

**Extends:** AQE Engineering Specification v0.1
**Core premise:** The backtester is not a one-time validation tool. It is a **permanent scoring layer** that converts historical outcomes into live confidence signals, and a **calibration engine** that iteratively improves every parameter in the system.

---

# 1 — THE FEEDBACK LOOP

```
                    ┌──────────────────────────┐
                    │    LIVE SCORING (AQE)     │
                    │                          │
                    │  Flow + Energy + Struct   │
                    │  + MP + Elder + BQ        │
                    │  = SC_MOMENTUM / POSITION │
                    │  + CM = PTRS             │
                    └────────────┬─────────────┘
                                 │
                    ┌────────────▼─────────────┐
              ┌────▶│  BACKTEST CONFIDENCE      │◀────┐
              │     │  LAYER (NEW)              │     │
              │     │                          │     │
              │     │  "Given this exact score │     │
              │     │   profile, what happened │     │
              │     │   historically?"         │     │
              │     │                          │     │
              │     │  Empirical win rate,     │     │
              │     │  avg R, max adverse,     │     │
              │     │  holding period, decay   │     │
              │     └────────────┬─────────────┘     │
              │                  │                    │
              │     ┌────────────▼─────────────┐     │
              │     │  ENHANCED PTRS            │     │
              │     │                          │     │
              │     │  PTRS_E = PTRS + BC      │     │
              │     │  (Backtest Confidence)    │     │
              │     └────────────┬─────────────┘     │
              │                  │                    │
              │     ┌────────────▼─────────────┐     │
              │     │  TRADE EXECUTION          │     │
              │     │  → outcome recorded       │     │
              │     └────────────┬─────────────┘     │
              │                  │                    │
              │     ┌────────────▼─────────────┐     │
              │     │  OUTCOME DATABASE         │     │
              │     │  (grows every trade)      │     │
              └─────┤                          ├─────┘
                    │  Feeds back into both:   │
                    │  • Confidence layer       │
                    │  • Calibration engine     │
                    └──────────────────────────┘
```

The system is a closed loop. Every trade outcome enriches the database that informs the next trade's confidence score. The more trades executed, the sharper the confidence signal becomes. Nothing is static because the input data is always growing.

---

# 2 — BACKTEST CONFIDENCE LAYER (BC)

## 2.1 What It Answers

For any candidate the AQE scores today, the backtest layer answers:

> "Over the last N years, when a stock had this score profile at entry, what was the empirical outcome distribution?"

This is not a theoretical model. It is a **frequentist lookup** against the historical record of the AQE's own scoring output.

## 2.2 Score Profile Signature

Every scored candidate produces a **profile signature** — a vector of key dimensions that defines its "type":

```python
@dataclass
class ScoreProfile:
    """Signature for backtest lookup."""
    # Composite tier
    sc_momentum_band: str    # "STRONG" (≥65), "QUAL" (55-64), "WEAK" (<55)
    
    # Dominant engine
    dominant_engine: str     # Which engine contributed most to composite
    
    # Gate health
    weakest_gate: str        # Which engine is closest to its floor
    gate_margin: float       # How far above the floor (tightest gate)
    
    # Structural state
    bd_mode: int             # 0/1/2/3/4 — base pattern type
    mp_state: int            # 1=BUILDING, 2=STRONG, 3=FADING
    
    # Context
    regime: str              # GREEN/YELLOW/ORANGE
    srm_grade: str           # DEPLOY/HOLD/TURNING/WATCH/AVOID
    
    # Risk character
    atr_pct: float           # ATR as % of price (volatility character)
    fip_class: str           # SMOOTH/MODERATE/JUMPY
```

## 2.3 Historical Outcome Record

Every bar in the historical database where the AQE produces a qualifying score gets tagged with the **forward outcome**:

```python
@dataclass
class ForwardOutcome:
    """What happened after this score was generated."""
    ticker: str
    entry_date: date
    entry_price: float
    score_profile: ScoreProfile
    
    # Forward returns at fixed intervals
    fwd_5d_return: float     # 5-day forward return %
    fwd_10d_return: float    # 10-day (1-2 week momentum holding)
    fwd_20d_return: float    # 20-day
    fwd_40d_return: float    # ~2 months (position holding)
    
    # Max favourable / adverse excursion
    mfe_10d: float           # Max Favourable Excursion in 10 days (%)
    mae_10d: float           # Max Adverse Excursion in 10 days (%)
    mfe_20d: float
    mae_20d: float
    
    # R-multiple outcome (using DSL initial stop)
    peak_r: float            # Best R-multiple achieved
    r_at_10d: float          # R-multiple at day 10
    r_at_20d: float          # R-multiple at day 20
    
    # Trail outcome (simulated DSG-10)
    trail_exit_date: date    # When DSG-10 trail would have stopped out
    trail_exit_r: float      # R-multiple at trail exit
    highest_tier: int        # Highest DSG-10 tier reached
    
    # Classification
    outcome_class: str       # WIN_BIG (>3R), WIN (1-3R), SCRATCH (0-1R), 
                             # LOSS_SMALL (<-0.5R), LOSS_FULL (stopped at -1R)
```

## 2.4 Confidence Score Computation

Given a live candidate's score profile, query the outcome database for historical matches:

```python
def compute_backtest_confidence(profile: ScoreProfile, 
                                 outcome_db: OutcomeDB) -> BacktestConfidence:
    """
    Empirical confidence score from historical outcomes.
    
    Uses tiered matching:
      Tier 1: Exact profile match (all dimensions)
      Tier 2: Core match (composite band + regime + mp_state)
      Tier 3: Broad match (composite band only)
    
    Reports from tightest tier with N ≥ 20 samples.
    """
    
    # Tier 1: Exact match
    exact = outcome_db.query(
        sc_band=profile.sc_momentum_band,
        mp_state=profile.mp_state,
        regime=profile.regime,
        srm_grade=profile.srm_grade,
        bd_mode=profile.bd_mode,
        fip_class=profile.fip_class
    )
    
    # Tier 2: Core match (relax SRM and BD mode)
    core = outcome_db.query(
        sc_band=profile.sc_momentum_band,
        mp_state=profile.mp_state,
        regime=profile.regime
    )
    
    # Tier 3: Broad match (composite band only)
    broad = outcome_db.query(
        sc_band=profile.sc_momentum_band
    )
    
    # Use tightest tier with sufficient samples
    matches = exact if len(exact) >= 20 else (core if len(core) >= 20 else broad)
    tier_used = "EXACT" if matches is exact else ("CORE" if matches is core else "BROAD")
    
    # Compute empirical statistics
    win_rate = mean(1 for m in matches if m.trail_exit_r > 0) / len(matches)
    avg_r = mean(m.trail_exit_r for m in matches)
    median_r = median(m.trail_exit_r for m in matches)
    avg_mfe = mean(m.mfe_20d for m in matches)
    avg_mae = mean(m.mae_10d for m in matches)
    pct_big_wins = mean(1 for m in matches if m.outcome_class == "WIN_BIG") / len(matches)
    avg_hold_days = mean((m.trail_exit_date - m.entry_date).days for m in matches)
    
    # Expectancy
    avg_win = mean(m.trail_exit_r for m in matches if m.trail_exit_r > 0) or 0
    avg_loss = mean(m.trail_exit_r for m in matches if m.trail_exit_r <= 0) or -1
    expectancy = (win_rate * avg_win) + ((1 - win_rate) * avg_loss)
    
    # Confidence score: 0-100 scale
    # Weights: win_rate (40%), expectancy (30%), sample_size (15%), consistency (15%)
    wr_score = min(win_rate / 0.65 * 100, 100)    # 65% win rate = 100
    exp_score = min(max(expectancy / 1.5 * 100, 0), 100)  # 1.5R expectancy = 100
    n_score = min(len(matches) / 100 * 100, 100)  # 100 samples = full confidence
    
    # Consistency: low stdev of R-multiples = more predictable
    r_stdev = stdev(m.trail_exit_r for m in matches)
    consistency = min(max((2.0 - r_stdev) / 2.0 * 100, 0), 100)
    
    bc_raw = (wr_score * 0.40 + exp_score * 0.30 + 
              n_score * 0.15 + consistency * 0.15)
    
    return BacktestConfidence(
        bc_score=bc_raw,
        tier=tier_used,
        sample_size=len(matches),
        win_rate=win_rate,
        avg_r=avg_r,
        median_r=median_r,
        expectancy=expectancy,
        avg_mfe=avg_mfe,
        avg_mae=avg_mae,
        pct_big_wins=pct_big_wins,
        avg_hold_days=avg_hold_days,
        r_distribution=build_r_histogram(matches)
    )
```

## 2.5 Enhanced PTRS

The backtest confidence layer modifies PTRS without replacing it:

```
PTRS_E = PTRS + BC_modifier

Where:
  BC_modifier = (BC_score - 50) × 0.15
  
  Range: -7.5 (BC=0, terrible history) to +7.5 (BC=100, excellent history)
```

**Design philosophy:** BC is an ADJUSTMENT, not a replacement. The engines remain the primary signal. BC tilts the disposition when historical evidence is strong.

| BC Score | Interpretation | PTRS Effect |
|----------|----------------|-------------|
| 80-100 | Strong empirical support | +4.5 to +7.5 |
| 60-79 | Favourable history | +1.5 to +4.4 |
| 40-59 | Neutral / insufficient data | -1.5 to +1.4 |
| 20-39 | Unfavourable history | -4.5 to -1.6 |
| 0-19 | Historically poor performer | -7.5 to -4.6 |

**Guardrail:** BC_modifier NEVER overrides a REJECT (PTRS < 45 stays rejected regardless of BC). BC can promote HALF → FULL or demote FULL → HALF, but cannot resurrect a dead trade.

**Minimum sample clause:** If sample_size < 20 (any tier), BC_modifier = 0. Insufficient data means no adjustment. The system defaults to indicator-only scoring until the database matures.

---

# 3 — THE BACKTEST EVENT ENGINE

## 3.1 Architecture

```python
class BacktestEngine:
    """
    Event-loop backtester that simulates the full AQE pipeline
    against historical data.
    
    NOT a simple "buy when score > X" backtest. Simulates:
    - Daily AQE scoring pipeline
    - Gate enforcement
    - PTRS computation with context modifier
    - DSG-10 trail system with tier transitions
    - Position sizing per disposition
    - Portfolio-level constraints (beta, concentration)
    """
    
    def __init__(self, start_date, end_date, initial_capital=70000):
        self.start = start_date
        self.end = end_date
        self.capital = initial_capital
        self.positions = {}          # ticker → Position
        self.closed_trades = []      # completed trade records
        self.daily_scores = {}       # date → {ticker: ScoringResult}
        self.equity_curve = []
        self.max_positions = 6       # charter constraint
        self.max_sector_exposure = 0.35  # DSG-09
        
    def run(self):
        """Main event loop."""
        for date in trading_days(self.start, self.end):
            
            # 1. Score universe for this date
            scores = self.score_universe(date)
            self.daily_scores[date] = scores
            
            # 2. Manage existing positions
            for ticker, position in list(self.positions.items()):
                self.manage_position(ticker, position, date, scores)
            
            # 3. Evaluate new entries
            candidates = self.get_qualified_candidates(scores, date)
            for ticker, score in candidates:
                if self.can_enter(ticker, score, date):
                    self.enter_position(ticker, score, date)
            
            # 4. Record daily state
            self.record_daily_state(date)
    
    def manage_position(self, ticker, position, date, scores):
        """
        DSG-10 trail management + exit detection.
        This is where the trail tiers, R-multiples, and exit
        signals are simulated bar-by-bar.
        """
        bar = self.get_bar(ticker, date)
        
        # Update R-multiple
        position.update_r(bar['close'])
        
        # Update trail tier (ratchet)
        position.update_tier()
        
        # Compute trail stop for current tier
        trail = position.compute_trail(bar, self.get_weekly_low(ticker, date))
        
        # Check exit conditions
        if bar['close'] < trail:
            self.exit_position(ticker, date, "TRAIL_EXIT", bar['close'])
        elif position.tier <= 1 and self.elder_red(ticker, date):
            self.exit_position(ticker, date, "IMPULSE_EXIT", bar['close'])
        elif self.earnings_within_5(ticker, date):
            self.exit_position(ticker, date, "EARNINGS_EXIT", bar['close'])
    
    def enter_position(self, ticker, score, date):
        """
        Full entry simulation: sizing per PTRS disposition,
        initial stop per DSL, risk per share computation.
        """
        bar = self.get_bar(ticker, date)
        
        # Compute initial stop (tactical profile)
        sl = self.compute_initial_stop(ticker, date)
        risk_per_share = bar['close'] - sl
        
        # Position size from PTRS disposition
        disposition = score.disposition
        size_mult = {"FULL": 1.0, "HALF": 0.5, "QUARTER": 0.25}[disposition]
        
        # Risk budget: 1% of capital per full position
        risk_budget = self.capital * 0.01 * size_mult
        shares = int(risk_budget / risk_per_share) if risk_per_share > 0 else 0
        
        if shares == 0:
            return
        
        position = Position(
            ticker=ticker,
            entry_date=date,
            entry_price=bar['close'],
            shares=shares,
            initial_stop=sl,
            risk_per_share=risk_per_share,
            disposition=disposition,
            score_at_entry=score
        )
        self.positions[ticker] = position
    
    def exit_position(self, ticker, date, reason, exit_price):
        """Record completed trade with full outcome data."""
        position = self.positions.pop(ticker)
        
        trade = CompletedTrade(
            ticker=ticker,
            entry_date=position.entry_date,
            exit_date=date,
            entry_price=position.entry_price,
            exit_price=exit_price,
            shares=position.shares,
            risk_per_share=position.risk_per_share,
            r_multiple=(exit_price - position.entry_price) / position.risk_per_share,
            peak_r=position.peak_r,
            highest_tier=position.highest_tier,
            exit_reason=reason,
            hold_days=(date - position.entry_date).days,
            score_at_entry=position.score_at_entry,
            pnl=(exit_price - position.entry_price) * position.shares
        )
        self.closed_trades.append(trade)
```

## 3.2 Forward Outcome Tagging

The key output of the backtester isn't the equity curve — it's the **outcome-tagged score database**:

```python
def build_outcome_database(self):
    """
    After backtest completes, tag every qualifying score event
    with its forward outcome. This IS the confidence layer's
    training data.
    """
    outcomes = []
    
    for date, scores in self.daily_scores.items():
        for ticker, score in scores.items():
            if not score.sc_m_gates:
                continue  # only tag qualifying scores
            
            # Get forward bars
            fwd_bars = self.get_forward_bars(ticker, date, days=40)
            if len(fwd_bars) < 20:
                continue
            
            entry_price = fwd_bars[0]['close']
            
            # Forward returns
            fwd_5d = (fwd_bars[4]['close'] - entry_price) / entry_price * 100
            fwd_10d = (fwd_bars[9]['close'] - entry_price) / entry_price * 100
            fwd_20d = (fwd_bars[19]['close'] - entry_price) / entry_price * 100
            
            # MFE / MAE
            highs_10 = [b['high'] for b in fwd_bars[:10]]
            lows_10 = [b['low'] for b in fwd_bars[:10]]
            mfe_10d = (max(highs_10) - entry_price) / entry_price * 100
            mae_10d = (min(lows_10) - entry_price) / entry_price * 100
            
            # Simulate DSG-10 trail
            trail_result = self.simulate_trail(ticker, date, fwd_bars)
            
            outcomes.append(ForwardOutcome(
                ticker=ticker,
                entry_date=date,
                entry_price=entry_price,
                score_profile=score.to_profile(),
                fwd_5d_return=fwd_5d,
                fwd_10d_return=fwd_10d,
                fwd_20d_return=fwd_20d,
                mfe_10d=mfe_10d,
                mae_10d=mae_10d,
                peak_r=trail_result.peak_r,
                trail_exit_r=trail_result.exit_r,
                highest_tier=trail_result.highest_tier,
                trail_exit_date=trail_result.exit_date,
                # ... classify outcome
            ))
    
    return outcomes
```

**Every qualifying score event in the historical record gets tagged with what actually happened.** This is the data that powers the confidence layer.

---

# 4 — CALIBRATION ENGINE

## 4.1 What Gets Calibrated

Nothing in the system is sacred. Everything has an empirical basis that should be verified and refined:

| Parameter | Current Value | Calibration Method |
|-----------|---------------|-------------------|
| **Engine weights** (SC_M) | Flow 30/Energy 30/Struct 20/MP 20 | Regression against R-outcomes |
| **Engine weights** (SC_P) | Flow 10/Energy 30/Struct 20/MP 5/BQ 35 | Same |
| **Gate thresholds** | Elder ≥6.5, Flow ≥60, etc. | Conditional win rate analysis |
| **Scoring curves** | e.g. RS >10%=15pts, >5%=12pts | Monotonicity check + optimal bin boundaries |
| **PTRS bands** | ≥60 FULL, 50-59 HALF, etc. | Outcome distribution by PTRS band |
| **CM weights** | SH/RA/RL contributions | Marginal improvement analysis |
| **DSG-10 tier thresholds** | 1R/2R/4R tier transitions | Trail efficiency vs early exit rate |
| **DSG-10 ATR multiples** | T1: 1.0×, T2: 1.5×, T3: 2.0×, T4: 2.5× | Shakeout rate vs profit capture |
| **Base duration sweet spot** | 10-25 days optimal | Outcome by BD range |
| **Exhaustion trend minimum** | 15 bars | Exhaustion signal accuracy by threshold |
| **VP proxy vs real VP** | Range position proxy | Delta analysis vs outcome |

## 4.2 Calibration Methods

### Weight Optimisation (Engine Weights)

```python
def calibrate_weights(outcome_db: OutcomeDB, pipeline: str = "momentum"):
    """
    Find optimal engine weights that maximise expected R-multiple.
    
    Method: Constrained optimisation.
    Constraints: weights sum to 1.0, each weight ∈ [0.05, 0.50].
    Objective: maximise correlation between composite score and forward R.
    
    CRITICAL: Use walk-forward validation, not in-sample fit.
    """
    from scipy.optimize import minimize
    
    # Get all scored outcomes
    outcomes = outcome_db.get_all(pipeline=pipeline)
    
    def objective(weights):
        """Negative correlation (we minimise)."""
        flow_w, energy_w, struct_w, mp_w = weights
        composites = [
            o.flow * flow_w + o.energy * energy_w + 
            o.struct * struct_w + o.mp * mp_w
            for o in outcomes
        ]
        r_multiples = [o.trail_exit_r for o in outcomes]
        return -np.corrcoef(composites, r_multiples)[0, 1]
    
    constraints = [
        {"type": "eq", "fun": lambda w: sum(w) - 1.0}  # sum to 1
    ]
    bounds = [(0.05, 0.50)] * 4  # each weight 5-50%
    
    result = minimize(objective, 
                      x0=[0.30, 0.30, 0.20, 0.20],  # current weights
                      method="SLSQP",
                      bounds=bounds, 
                      constraints=constraints)
    
    return {
        "optimal_weights": result.x,
        "current_corr": -objective([0.30, 0.30, 0.20, 0.20]),
        "optimal_corr": -result.fun,
        "improvement": (-result.fun) - (-objective([0.30, 0.30, 0.20, 0.20]))
    }
```

### Gate Threshold Analysis

```python
def analyse_gate_thresholds(outcome_db: OutcomeDB, engine: str, 
                             current_threshold: float):
    """
    For a given engine gate (e.g. Flow ≥ 60), compute win rate 
    and expectancy at every threshold from 30 to 80 in steps of 5.
    
    Answers: "Is 60 the right floor? Would 55 or 65 produce 
    better outcomes?"
    """
    results = []
    for threshold in range(30, 85, 5):
        # Filter outcomes where this engine was above threshold
        passing = [o for o in outcome_db.get_all() 
                   if getattr(o, f"{engine}_score") >= threshold]
        
        if len(passing) < 20:
            continue
        
        win_rate = mean(1 for o in passing if o.trail_exit_r > 0) / len(passing)
        avg_r = mean(o.trail_exit_r for o in passing)
        expectancy = compute_expectancy(passing)
        
        results.append({
            "threshold": threshold,
            "n": len(passing),
            "win_rate": win_rate,
            "avg_r": avg_r,
            "expectancy": expectancy,
            "is_current": threshold == current_threshold
        })
    
    # Find optimal: highest expectancy with N ≥ 30
    viable = [r for r in results if r["n"] >= 30]
    optimal = max(viable, key=lambda r: r["expectancy"])
    
    return {
        "current": current_threshold,
        "optimal": optimal["threshold"],
        "improvement": optimal["expectancy"] - next(
            r["expectancy"] for r in results if r["is_current"]
        ),
        "full_analysis": results
    }
```

### Scoring Curve Validation

```python
def validate_scoring_curve(outcome_db: OutcomeDB, engine: str, 
                           component: str):
    """
    Check that higher scores in a component actually predict 
    better outcomes. If they don't, the scoring curve is wrong.
    
    Example: Structure RS vs SPY component awards 15 pts for >10%.
    But if stocks with RS 5-10% actually produce better R-multiples
    than stocks with RS >10%, the curve is mispriced.
    """
    # Bucket outcomes by component score
    buckets = defaultdict(list)
    for o in outcome_db.get_all():
        score = getattr(o, f"{engine}_{component}_score")
        bucket = int(score / 5) * 5  # 5-point buckets
        buckets[bucket].append(o.trail_exit_r)
    
    # Compute avg R per bucket
    curve = []
    for bucket in sorted(buckets.keys()):
        if len(buckets[bucket]) >= 10:
            curve.append({
                "score_bucket": bucket,
                "n": len(buckets[bucket]),
                "avg_r": mean(buckets[bucket]),
                "win_rate": mean(1 for r in buckets[bucket] if r > 0)
            })
    
    # Monotonicity check: is avg_r generally increasing with score?
    r_values = [c["avg_r"] for c in curve]
    monotonic = all(r_values[i] <= r_values[i+1] 
                    for i in range(len(r_values)-1))
    
    # Rank correlation
    from scipy.stats import spearmanr
    scores = [c["score_bucket"] for c in curve]
    rho, pval = spearmanr(scores, r_values)
    
    return {
        "component": f"{engine}.{component}",
        "monotonic": monotonic,
        "spearman_rho": rho,
        "p_value": pval,
        "curve": curve,
        "verdict": "VALID" if rho > 0.5 and pval < 0.05 else 
                   "REVIEW" if rho > 0.2 else "BROKEN"
    }
```

## 4.3 Walk-Forward Protocol

**CRITICAL:** All calibration uses walk-forward validation. No in-sample overfitting.

```
Training window: 12 months rolling
Test window: 3 months forward
Step: 1 month

  ├── Train (12mo) ──┤── Test (3mo) ──┤
                      ├── Train (12mo) ──┤── Test (3mo) ──┤
                                         ├── Train (12mo) ──┤── Test (3mo) ──┤
```

```python
def walk_forward_calibration(start_date, end_date, 
                              train_months=12, test_months=3, 
                              step_months=1):
    """
    Walk-forward: train on 12 months, test on next 3, step by 1 month.
    
    Each step produces:
    - Optimal parameters from training window
    - Out-of-sample performance on test window
    - Parameter stability (are optimal params consistent across windows?)
    """
    results = []
    current = start_date
    
    while current + relativedelta(months=train_months + test_months) <= end_date:
        train_end = current + relativedelta(months=train_months)
        test_end = train_end + relativedelta(months=test_months)
        
        # Train: find optimal parameters
        train_outcomes = outcome_db.query(date_range=(current, train_end))
        optimal_params = calibrate_all(train_outcomes)
        
        # Test: apply optimal params to unseen data
        test_outcomes = outcome_db.query(date_range=(train_end, test_end))
        oos_performance = evaluate(test_outcomes, optimal_params)
        
        results.append({
            "train_period": (current, train_end),
            "test_period": (train_end, test_end),
            "optimal_params": optimal_params,
            "oos_win_rate": oos_performance.win_rate,
            "oos_expectancy": oos_performance.expectancy,
            "oos_avg_r": oos_performance.avg_r
        })
        
        current += relativedelta(months=step_months)
    
    # Parameter stability analysis
    param_stability = analyse_stability(
        [r["optimal_params"] for r in results]
    )
    
    return results, param_stability
```

## 4.4 Calibration Governance

**Calibration is NOT auto-applied.** It produces recommendations that the PM reviews.

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────┐
│  Calibration    │────▶│  Recommendation  │────▶│  PM Review  │
│  Engine runs    │     │  Report          │     │  & Approval │
│  (automated,    │     │                  │     │             │
│   weekly)       │     │  "Flow weight    │     │  Accept /   │
│                 │     │   should be 25%  │     │  Reject /   │
│                 │     │   not 30%.       │     │  Defer      │
│                 │     │   Evidence: ..." │     │             │
└─────────────────┘     └──────────────────┘     └──────┬──────┘
                                                        │
                                                        ▼
                                                 ┌─────────────┐
                                                 │  Charter     │
                                                 │  Amendment   │
                                                 │  (if major)  │
                                                 └─────────────┘
```

**Rules:**
1. Minor recalibration (threshold ±5 points, weight ±5%): PM approval, no charter amendment.
2. Structural change (new component, removed gate, weight >10% shift): Charter amendment required (v1.9+).
3. Any change must show improvement in BOTH walk-forward expectancy AND win rate. Improving one while degrading the other is not accepted.
4. Minimum 60 trades in the test dataset for any calibration to be actionable.

---

# 5 — ANALYTICS DASHBOARD

## 5.1 Backtest Performance Metrics

```python
@dataclass
class BacktestAnalytics:
    """Full performance analytics from backtest run."""
    
    # Core metrics
    total_trades: int
    win_rate: float
    avg_r: float
    median_r: float
    expectancy: float            # (win_rate × avg_win) + (loss_rate × avg_loss)
    
    # Risk metrics
    max_drawdown_pct: float
    max_drawdown_duration: int   # days
    sharpe_ratio: float          # annualised, risk-free = treasury rate
    sortino_ratio: float         # downside deviation only
    calmar_ratio: float          # annual return / max drawdown
    
    # R-distribution
    avg_winner_r: float
    avg_loser_r: float
    biggest_winner_r: float
    biggest_loser_r: float
    pct_big_wins: float          # >3R
    pct_scratches: float         # 0 to 1R
    pct_full_stops: float        # hit initial stop
    
    # Trail system effectiveness
    avg_tier_at_exit: float
    pct_reached_tier2: float     # % of trades that earned +1R
    pct_reached_tier3: float     # % that earned +2R
    pct_reached_tier4: float     # % that became runners (+4R)
    avg_trail_capture: float     # exit R / peak R (higher = better trail)
    
    # Engine contribution
    engine_win_rates: dict       # win rate by dominant engine
    gate_failure_rate: dict      # how often each gate blocks a would-be winner
    
    # Regime analysis
    regime_performance: dict     # metrics by GREEN/YELLOW/ORANGE
    
    # Time analysis
    avg_hold_days: float
    avg_hold_winners: float
    avg_hold_losers: float
    monthly_returns: list        # for equity curve
    
    # Confidence layer effectiveness
    bc_lift: float               # PTRS_E improvement over PTRS alone
```

## 5.2 Calibration Report

```python
def generate_calibration_report(outcome_db, current_params):
    """
    Weekly calibration report for PM review.
    """
    report = {}
    
    # Weight optimisation
    report["weights"] = calibrate_weights(outcome_db, "momentum")
    
    # Gate analysis
    for engine, threshold in current_params.gates.items():
        report[f"gate_{engine}"] = analyse_gate_thresholds(
            outcome_db, engine, threshold
        )
    
    # Scoring curve validation
    for engine in ["flow", "energy", "structure", "mp"]:
        for component in get_components(engine):
            report[f"curve_{engine}_{component}"] = validate_scoring_curve(
                outcome_db, engine, component
            )
    
    # PTRS band analysis
    report["ptrs_bands"] = analyse_ptrs_bands(outcome_db)
    
    # Trail tier analysis
    report["trail_tiers"] = analyse_trail_effectiveness(outcome_db)
    
    # Walk-forward results
    report["walk_forward"] = walk_forward_calibration(
        start_date=two_years_ago, end_date=today
    )
    
    # Recommendations
    report["recommendations"] = generate_recommendations(report)
    
    return report
```

---

# 6 — DATA ACCUMULATION TIMELINE

The confidence layer's accuracy scales with data volume:

| Milestone | Approx. Date | Trades | Confidence Layer Status |
|-----------|-------------|--------|------------------------|
| AQE launch | Week 0 | 0 live, ~500 backtest | BC from backtest only. BROAD tier matches. |
| 3 months | Week 12 | ~30 live + 500 backtest | BC starts incorporating live outcomes. CORE tier viable for common profiles. |
| 6 months | Week 26 | ~60 live + 500 backtest | Calibration engine has first walk-forward cycle. Gate threshold review actionable. |
| 1 year | Week 52 | ~120 live + 500 backtest | EXACT tier viable for frequent profiles. Weight calibration actionable. Full regime-conditional analysis. |
| 2 years | Week 104 | ~240 live + 500 backtest | Statistically robust across all tiers. Scoring curve validation complete. System is self-calibrating. |

**The backtest seeds the database with ~500 simulated outcomes from 2 years of historical data.** This gives the confidence layer a working baseline from day one. Live outcomes progressively replace simulated ones as the more authoritative data source.

---

# 7 — WHAT THIS CHANGES

## Before (Static System)

- Indicator parameters fixed at design time
- "Does this work?" answered by gut feel and small-sample anecdote
- No empirical basis for weights, gates, or scoring curves
- Same scoring approach in GREEN and YELLOW regimes
- Win/loss attributed to market or execution, not to score quality

## After (Adaptive System)

- Every parameter has an empirical basis that is continuously verified
- "Does this work?" answered by N=500+ outcome-tagged scores
- Confidence layer tells you: "Stocks that looked like THIS historically produced +1.8R average with 58% win rate"
- Regime-conditional performance means YELLOW regime gets different calibration than GREEN
- Gate failures analysed: "The Elder gate blocked 12 trades that would have been winners — is 6.5 too high?"
- Scoring curves validated: "RS component awards 15 pts for >10% outperformance, but the data shows >5% is the sweet spot — the curve is overweighting extreme outperformers"
- Weights drift toward empirically optimal values over time
- The system learns from its own output

## The Flywheel

```
Better data → Better confidence signals → Better trade selection
    → Better outcomes → More data → Better calibration
        → Better parameters → Better scores → ...
```

Every trade — win or loss — makes the next trade decision better informed. The loss is not wasted. It teaches the system where the scoring is overconfident. The win validates the parameter set. Both feed the calibration engine.

**This is the fundamental shift from "indicator-based trading" to "empirically-calibrated systematic trading."** The indicators remain the foundation. The data tells you whether the foundation is solid, and where to reinforce it.

---

*AQE Backtest Engine Specification v0.1 | 18 May 2026*
*Extends: AQE Engineering Specification v0.1*
*Extends: Aegis Design Committee Specification v1.0*
*Charter authority: AIC v1.8 | Calibration governance: §11*
