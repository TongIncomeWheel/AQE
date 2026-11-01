"""
Aegis Hedge Engine v1.0 — candidate generation, BS repricing, scoring.

Generates three put spread candidates (tight/balanced/wide), computes
payout at four gap scenarios via Black-Scholes, scores by weighted
coverage-to-cost ratio, outputs JSON for Alfred to render.

Reuses BS pricing math from protege9 engine (standalone — no import dependency).
"""
import math
import json
import argparse
import sys
from typing import List, Dict, Optional, Tuple

try:
    from scipy.stats import norm
except ImportError:
    sys.stderr.write("scipy not installed. Run: pip install scipy --break-system-packages\n")
    sys.exit(2)


# ---------- Black-Scholes (standalone copy from protege9) ----------
DEFAULT_RISK_FREE = 0.045
DEFAULT_DIV_YIELD = 0.0


def bs_price(S: float, K: float, T: float, sigma: float,
             r: float = DEFAULT_RISK_FREE, q: float = DEFAULT_DIV_YIELD,
             opt_type: str = 'put') -> float:
    """BS option price with continuous dividend yield. T in years."""
    if T <= 1e-9:
        return max(0.0, S - K) if opt_type == 'call' else max(0.0, K - S)
    if sigma <= 1e-9:
        if opt_type == 'call':
            return max(0.0, S * math.exp(-q * T) - K * math.exp(-r * T))
        return max(0.0, K * math.exp(-r * T) - S * math.exp(-q * T))
    d1 = (math.log(S / K) + (r - q + 0.5 * sigma ** 2) * T) / (sigma * math.sqrt(T))
    d2 = d1 - sigma * math.sqrt(T)
    if opt_type == 'call':
        return S * math.exp(-q * T) * norm.cdf(d1) - K * math.exp(-r * T) * norm.cdf(d2)
    return K * math.exp(-r * T) * norm.cdf(-d2) - S * math.exp(-q * T) * norm.cdf(-d1)


# ---------- Chain helpers ----------

def snap_strike(chain: List[dict], target: float, direction: str = 'conservative') -> Optional[dict]:
    """Find nearest available strike to target.
    direction='conservative' means further OTM (lower for puts).
    """
    puts = [c for c in chain if c.get('mid', 0) > 0 and c.get('strike')]
    if not puts:
        return None
    puts.sort(key=lambda c: c['strike'])

    best = None
    best_dist = float('inf')
    for c in puts:
        dist = abs(c['strike'] - target)
        if dist < best_dist:
            best_dist = dist
            best = c
    return best


def find_strike_near_pct(chain: List[dict], spot: float, pct_otm: float) -> Optional[dict]:
    """Find put strike nearest to spot × (1 - pct_otm)."""
    target = spot * (1.0 - pct_otm)
    return snap_strike(chain, target)


def avg_iv_near_strikes(chain: List[dict], k_u: float, k_l: float) -> float:
    """Average IV of chain contracts between the two strikes."""
    relevant = [c for c in chain
                if c.get('iv') and c.get('strike')
                and k_l <= c['strike'] <= k_u]
    if not relevant:
        return 0.20  # default fallback
    ivs = [c['iv'] for c in relevant if c['iv'] > 0]
    return sum(ivs) / len(ivs) if ivs else 0.20


# ---------- Payout computation ----------

def compute_spread_payout(spot: float, k_u: float, k_l: float,
                          T: float, iv: float,
                          gap_pct: float) -> float:
    """BS-repriced payout per contract for a put debit spread at a given gap.
    Returns the gain in spread value (post-gap minus pre-gap), per contract (×100).
    """
    s_gap = spot * (1.0 - gap_pct)

    # Spread value before gap (what we hold now)
    val_u_before = bs_price(spot, k_u, T, iv, opt_type='put')
    val_l_before = bs_price(spot, k_l, T, iv, opt_type='put')
    spread_before = val_u_before - val_l_before

    # Spread value after gap
    val_u_after = bs_price(s_gap, k_u, T, iv, opt_type='put')
    val_l_after = bs_price(s_gap, k_l, T, iv, opt_type='put')
    spread_after = val_u_after - val_l_after

    payout_per_share = spread_after - spread_before
    return max(payout_per_share * 100.0, 0.0)


# ---------- Candidate generation ----------

PROFILES = {
    'tight':    {'upper_otm': 0.03, 'lower_otm': 0.08, 'label': 'TIGHT'},
    'balanced': {'upper_otm': 0.04, 'lower_otm': 0.09, 'label': 'BALANCED'},
    'wide':     {'upper_otm': 0.05, 'lower_otm': 0.12, 'label': 'WIDE'},
}

GAP_SCENARIOS = [0.03, 0.05, 0.07, 0.10]
GAP_LABELS = ['3pct', '5pct', '7pct', '10pct']

# Scoring weights (configurable — review quarterly per Design Committee T-1)
SCORE_WEIGHTS = {
    '5pct': 0.45,
    '3pct': 0.05,
    '7pct': 0.25,
    'cost': 0.25,
}


def generate_candidate(profile_name: str, chain: List[dict], spot: float,
                        beta_adj_exposure: float, r_size: float,
                        dte: int, breadth_efficiency: float) -> Optional[dict]:
    """Generate a single candidate structure from the chain."""
    profile = PROFILES[profile_name]

    # Find strikes
    upper_contract = find_strike_near_pct(chain, spot, profile['upper_otm'])
    lower_contract = find_strike_near_pct(chain, spot, profile['lower_otm'])

    if not upper_contract or not lower_contract:
        return None

    k_u = upper_contract['strike']
    k_l = lower_contract['strike']

    if k_u <= k_l:
        return None  # invalid spread

    # Premiums
    p_u = upper_contract.get('mid', 0)
    p_l = lower_contract.get('mid', 0)
    net_debit = p_u - p_l

    if net_debit <= 0:
        return None  # credit spread — wrong direction

    net_debit_per_contract = net_debit * 100.0
    spread_width = k_u - k_l

    # IV for BS repricing
    iv = avg_iv_near_strikes(chain, k_u, k_l)
    T = dte / 365.0

    # Payout at each gap scenario
    gap_coverage = {}
    payout_5pct_per_contract = 0.0

    for gap_pct, gap_label in zip(GAP_SCENARIOS, GAP_LABELS):
        est_loss = beta_adj_exposure * gap_pct
        payout_per_contract = compute_spread_payout(spot, k_u, k_l, T, iv, gap_pct)

        gap_coverage[gap_label] = {
            'est_loss': round(est_loss, 0),
            'payout_per_contract': round(payout_per_contract, 2),
        }

        if gap_label == '5pct':
            payout_5pct_per_contract = payout_per_contract

    # Contract sizing
    if payout_5pct_per_contract <= 0:
        # Upper strike too far OTM for 5% gap — use 7% scenario
        payout_7pct = gap_coverage.get('7pct', {}).get('payout_per_contract', 0)
        if payout_7pct > 0:
            target = beta_adj_exposure * 0.07
            contracts_ideal = math.ceil(target / payout_7pct)
        else:
            return None
    else:
        target = beta_adj_exposure * 0.05
        contracts_ideal = math.ceil(target / payout_5pct_per_contract)

    r_budget = r_size  # 1R default
    total_premium = net_debit_per_contract * contracts_ideal
    residual = 0.0

    if total_premium > r_budget:
        contracts = max(1, int(r_budget // net_debit_per_contract))
        residual = target - (payout_5pct_per_contract * contracts)
    else:
        contracts = contracts_ideal

    total_premium = net_debit_per_contract * contracts
    cost_r = total_premium / r_size

    # Finalise gap coverage with actual contracts
    max_payout_total = spread_width * 100.0 * contracts
    for gap_label in GAP_LABELS:
        gc = gap_coverage[gap_label]
        total_payout = gc['payout_per_contract'] * contracts
        est_loss = gc['est_loss']
        raw_cov = total_payout / est_loss if est_loss > 0 else 0
        adj_cov = raw_cov * breadth_efficiency

        gc['total_payout'] = round(total_payout, 0)
        gc['raw_cov'] = round(raw_cov, 4)
        gc['adj_cov'] = round(adj_cov, 4)

    # Efficiency
    efficiency = max_payout_total / total_premium if total_premium > 0 else 0

    # Scoring
    cov_5 = gap_coverage['5pct']['adj_cov']
    cov_3 = gap_coverage['3pct']['adj_cov']
    cov_7 = gap_coverage['7pct']['adj_cov']
    cost_ratio = min(cost_r, 1.0)  # cap at 1 for scoring

    # Coverage values capped at 2.0 for scoring (avoid runaway scores)
    score = (min(cov_5, 2.0) * SCORE_WEIGHTS['5pct']
             + min(cov_3, 2.0) * SCORE_WEIGHTS['3pct']
             + min(cov_7, 2.0) * SCORE_WEIGHTS['7pct']
             + (1.0 - cost_ratio) * SCORE_WEIGHTS['cost'])

    # Premium range (±10% for sensitivity)
    premium_low = round(net_debit * 0.90, 2)
    premium_high = round(net_debit * 1.10, 2)

    upper_otm_actual = round((spot - k_u) / spot * 100, 1)
    lower_otm_actual = round((spot - k_l) / spot * 100, 1)

    return {
        'profile': profile_name,
        'label': profile['label'],
        'upper_strike': k_u,
        'lower_strike': k_l,
        'upper_otm_pct': upper_otm_actual,
        'lower_otm_pct': lower_otm_actual,
        'spread_width': round(spread_width, 2),
        'net_debit': round(net_debit, 2),
        'net_debit_per_contract': round(net_debit_per_contract, 2),
        'contracts': contracts,
        'contracts_ideal': contracts_ideal,
        'total_premium': round(total_premium, 2),
        'cost_r': round(cost_r, 4),
        'premium_range': [premium_low, premium_high],
        'gap_coverage': gap_coverage,
        'max_payout_total': round(max_payout_total, 2),
        'efficiency': round(efficiency, 2),
        'score': round(score, 4),
        'residual_5pct': round(max(residual, 0), 0),
        'iv_used': round(iv, 4),
        'dte': dte,
    }


# ---------- Current hedge assessment ----------

def assess_current_hedge(spot: float, hedge: dict, beta_adj_exposure: float,
                         breadth_efficiency: float) -> Optional[dict]:
    """Compute coverage of current hedge from PTJ record."""
    if not hedge or not hedge.get('upper'):
        return None

    k_u = hedge['upper']
    k_l = hedge['lower']
    contracts = hedge.get('contracts', 0)
    dte = hedge.get('dte', 30)
    iv = hedge.get('iv', 0.20)
    T = dte / 365.0

    coverage = {}
    for gap_pct, gap_label in zip(GAP_SCENARIOS, GAP_LABELS):
        est_loss = beta_adj_exposure * gap_pct
        payout_per_contract = compute_spread_payout(spot, k_u, k_l, T, iv, gap_pct)
        total_payout = payout_per_contract * contracts
        raw_cov = total_payout / est_loss if est_loss > 0 else 0
        adj_cov = raw_cov * breadth_efficiency

        coverage[gap_label] = {
            'est_loss': round(est_loss, 0),
            'total_payout': round(total_payout, 0),
            'raw_cov': round(raw_cov, 4),
            'adj_cov': round(adj_cov, 4),
        }

    return coverage


# ---------- Nudge logic ----------

def check_nudge(candidates: List[dict], gap_posture: str, r_size: float) -> Optional[str]:
    """Check if nudge to PM is warranted."""
    if gap_posture not in ('ELEVATED', 'HIGH'):
        return None

    # Find the balanced candidate
    balanced = next((c for c in candidates if c['profile'] == 'balanced'), None)
    if not balanced:
        return None

    adj_cov_5 = balanced['gap_coverage']['5pct']['adj_cov']
    if adj_cov_5 >= 0.60:
        return None  # adequate — no nudge

    # Compute what 1.25R would allow
    extra_budget = r_size * 1.25
    extra_contracts = max(1, int(extra_budget // balanced['net_debit_per_contract']))
    extra_payout = balanced['gap_coverage']['5pct']['payout_per_contract'] * extra_contracts
    extra_loss = balanced['gap_coverage']['5pct']['est_loss']
    extra_cov = (extra_payout / extra_loss) if extra_loss > 0 else 0

    return (f"At 1R budget, the balanced candidate achieves {adj_cov_5:.0%} adjusted "
            f"coverage at the 5% gap scenario. Increasing to 1.25R would allow "
            f"{extra_contracts} contracts, bringing coverage to {extra_cov:.0%}. "
            f"PM to decide — 1R default stands unless overridden.")


# ---------- Main ----------

def main():
    p = argparse.ArgumentParser(description="Aegis Hedge Engine v1.0")
    p.add_argument('--instrument', required=True, help='Index ticker (QQQ, SPY, IWM, SMH)')
    p.add_argument('--spot', type=float, required=True, help='Current index spot price')
    p.add_argument('--beta-adj-exposure', type=float, required=True,
                   help='Total beta-adjusted book exposure in USD')
    p.add_argument('--loss-per-1pct', type=float, required=True,
                   help='Dollar loss per 1%% index gap')
    p.add_argument('--r-size', type=float, required=True, help='1R in dollars')
    p.add_argument('--chain-file', required=True, help='Path to Alpaca chain JSON')
    p.add_argument('--dte', type=int, default=30, help='DTE of selected expiry')
    p.add_argument('--breadth-efficiency', type=float, default=1.0,
                   help='Breadth efficiency factor (0.70–1.00)')
    p.add_argument('--current-hedge', default=None,
                   help='JSON string of current hedge: {"upper":X,"lower":X,"contracts":X,"dte":X,"iv":X}')
    p.add_argument('--gap-posture', default='BASELINE',
                   help='Gap risk posture from Phase 1 (BASELINE/ELEVATED/HIGH)')

    args = p.parse_args()

    # Load chain
    try:
        with open(args.chain_file, 'r') as f:
            chain = json.load(f)
    except Exception as e:
        sys.stderr.write(f"Failed to load chain: {e}\n")
        sys.exit(1)

    # Generate candidates
    candidates = []
    for profile_name in ['tight', 'balanced', 'wide']:
        c = generate_candidate(
            profile_name, chain, args.spot,
            args.beta_adj_exposure, args.r_size,
            args.dte, args.breadth_efficiency
        )
        if c:
            candidates.append(c)

    # Sort by score descending
    candidates.sort(key=lambda x: -x['score'])

    # Mark recommended
    recommended = candidates[0]['profile'] if candidates else None

    # Assess current hedge
    current_coverage = None
    if args.current_hedge:
        try:
            hedge = json.loads(args.current_hedge)
            current_coverage = assess_current_hedge(
                args.spot, hedge, args.beta_adj_exposure,
                args.breadth_efficiency
            )
        except Exception:
            current_coverage = None

    # Check nudge
    nudge = check_nudge(candidates, args.gap_posture, args.r_size)

    # Output
    output = {
        'instrument': args.instrument,
        'spot': args.spot,
        'beta_adj_exposure': args.beta_adj_exposure,
        'loss_per_1pct': args.loss_per_1pct,
        'r_size': args.r_size,
        'dte': args.dte,
        'breadth_efficiency': args.breadth_efficiency,
        'candidates': candidates,
        'recommended': recommended,
        'nudge': nudge,
        'current_hedge_coverage': current_coverage,
    }

    print(json.dumps(output, indent=2))


if __name__ == '__main__':
    main()
