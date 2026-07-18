"""Black-Scholes pricer - THE single canonical copy for all Aegis tools.
Extracted from protege9 engine; hedge_engine.py and any future tool must import from here.
"""
import math
from scipy.stats import norm

def bs_price(S: float, K: float, T: float, sigma: float,
             r: float = DEFAULT_RISK_FREE, q: float = DEFAULT_DIV_YIELD,
             opt_type: str = 'call') -> float:
    """BS option price with continuous dividend yield. T in years.
    At/past expiry returns intrinsic. Zero-vol degenerate handled.
    """
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


# ---------- Leg ----------
@dataclass
class Leg:
    strike: float
    expiry: date
    opt_type: str           # 'call' | 'put'
    side: str               # 'buy' | 'sell'
    qty: int                # contracts (positive integer; ratios use different qty per leg)
    entry_premium: float    # mid at entry
    iv: float               # flat IV per leg

    @property
    def sign(self) -> int:
        return 1 if self.side == 'buy' else -1

    def value_at(self, S: float, eval_date: date,
                 r: float = DEFAULT_RISK_FREE, q: float = DEFAULT_DIV_YIELD) -> float:
        """Theoretical option value per share at (eval_date, S). Intrinsic at/post expiry."""
        if eval_date >= self.expiry:
            if self.opt_type == 'call':
                return max(0.0, S - self.strike)
            return max(0.0, self.strike - S)
        T = (self.expiry - eval_date).days / 365.0
        return bs_price(S, self.strike, T, self.iv, r=r, q=q, opt_type=self.opt_type)

    def pnl_at(self, S: float, eval_date: date) -> float:
        """P&L per leg in dollars at (eval_date, S). Multiplier 100, scaled by qty."""
        v = self.value_at(S, eval_date)
        return self.sign * (v - self.entry_premium) * 100 * self.qty


# ---------- Structure ----------
@dataclass
class Structure:
    name: str
    legs: List[Leg]
    structure_type: str = "custom"   # 'vertical', 'calendar_1to1', 'ratio_2to1', etc.

    def net_debit_credit(self) -> float:
        """Negative = debit, positive = credit. Per structure unit (×100, qty-scaled)."""
        return sum(-leg.sign * leg.entry_premium * 100 * leg.qty for leg in self.legs)

    def pnl_at(self, S: float, eval_date: date) -> float:
        return sum(leg.pnl_at(S, eval_date) for leg in self.legs)

    def all_expiries(self) -> List[date]:
        return sorted(set(leg.expiry for leg in self.legs))

    def front_expiry(self) -> date:
        return min(leg.expiry for leg in self.legs)

    def back_expiry(self) -> date:
        return max(leg.expiry for leg in self.legs)

    def is_multi_expiry(self) -> bool:
        return len(self.all_expiries()) > 1

    def short_legs(self) -> List[Leg]:
        return [l for l in self.legs if l.side == 'sell']

    def long_legs(self) -> List[Leg]:
        return [l for l in self.legs if l.side == 'buy']


# ---------- Grids ----------