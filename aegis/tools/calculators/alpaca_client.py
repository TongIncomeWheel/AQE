# KERNEL COPY — PM ruling 18 Jul: hardcoded keys acceptable (pure read-only data API). Env vars override if ever set.
"""Alpaca options market-data client — read-only data feed.
import os

Operations: SPY spot · single-option Greeks · batch Greeks · chain snapshot.
No portfolio access. Positions are supplied by the Principal; this client only marks them.

Keys hard-coded for the paper account but only the data API (data.alpaca.markets)
is hit, so the same keys work identically against a live account.
"""
import re
import sys
import json
import time
import argparse
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any

try:
    import requests
except ImportError:
    sys.stderr.write("requests not installed. Run: pip install requests --break-system-packages\n")
    sys.exit(2)


# ---- Credentials (paper account, used for data API only) ------------------
API_KEY = os.environ.get('ALPACA_API_KEY', 'PKIKNPG4C5ZALRZSVKE5UFCOBA')
SECRET_KEY = os.environ.get('ALPACA_SECRET_KEY', '4DpnY9n6ZgLkxnBS5Anu6dEpRLS4r88pjwpqpsehXj1W')
DATA = 'https://data.alpaca.markets'
# ---------------------------------------------------------------------------


def _h() -> Dict[str, str]:
    return {
        'APCA-API-KEY-ID': API_KEY,
        'APCA-API-SECRET-KEY': SECRET_KEY,
        'Accept': 'application/json',
    }


def _get(url: str, params: Optional[dict] = None, retries: int = 1) -> dict:
    last_err = None
    for attempt in range(retries + 1):
        try:
            r = requests.get(url, headers=_h(), params=params, timeout=20)
            if r.status_code in (401, 403):
                raise RuntimeError(f"AUTH FAIL {r.status_code}: {r.text[:200]}")
            if r.status_code == 429:
                if attempt < retries:
                    time.sleep(30); continue
                raise RuntimeError("RATE LIMITED")
            r.raise_for_status()
            return r.json()
        except requests.RequestException as e:
            last_err = str(e)
            if attempt < retries:
                time.sleep(2 ** attempt); continue
    raise RuntimeError(f"GET {url} failed: {last_err}")


# ---- OCC parsing ----------------------------------------------------------
_OCC_RE = re.compile(r'^([A-Z]+)(\d{6})([CP])(\d{8})$')

def parse_occ(symbol: str) -> Optional[dict]:
    m = _OCC_RE.match(symbol.strip())
    if not m: return None
    underlying, ymd, cp, strike = m.groups()
    return {
        'underlying': underlying,
        'expiry': f'{2000 + int(ymd[:2])}-{ymd[2:4]}-{ymd[4:]}',
        'type': 'call' if cp == 'C' else 'put',
        'strike': int(strike) / 1000.0,
    }

def build_occ(underlying: str, expiry: str, opt_type: str, strike: float) -> str:
    """expiry: YYYY-MM-DD; opt_type: 'call' or 'put'; strike: float."""
    y, m, d = expiry.split('-')
    cp = 'C' if opt_type.lower().startswith('c') else 'P'
    strike_int = int(round(strike * 1000))
    return f"{underlying.upper()}{y[2:]}{m}{d}{cp}{strike_int:08d}"

def days_to_expiry(expiry_str: str) -> int:
    expiry = datetime.strptime(expiry_str, '%Y-%m-%d').replace(tzinfo=timezone.utc)
    return (expiry - datetime.now(timezone.utc)).days


# ---- Snapshot extraction --------------------------------------------------
def _extract(snap: dict, occ_symbol: Optional[str] = None) -> dict:
    if not snap:
        return {}
    q = snap.get('latestQuote') or {}
    t = snap.get('latestTrade') or {}
    g = snap.get('greeks') or {}
    bid, ask = q.get('bp', 0), q.get('ap', 0)
    mid = (bid + ask) / 2 if (bid and ask) else (bid or ask or t.get('p', 0) or 0)
    out: Dict[str, Any] = {
        'bid': bid, 'ask': ask, 'mid': mid, 'last': t.get('p'),
        'delta': g.get('delta'), 'gamma': g.get('gamma'),
        'theta': g.get('theta'), 'vega': g.get('vega'), 'rho': g.get('rho'),
        'iv': snap.get('impliedVolatility'),
        'open_interest': snap.get('openInterest'),
        'timestamp': q.get('t') or t.get('t'),
    }
    if occ_symbol:
        parsed = parse_occ(occ_symbol)
        if parsed:
            out['underlying'] = parsed['underlying']
            out['strike'] = parsed['strike']
            out['expiry'] = parsed['expiry']
            out['type'] = parsed['type']
            out['dte'] = days_to_expiry(parsed['expiry'])
    return out


# ---- API ops --------------------------------------------------------------

def get_spot(ticker: str = 'SPY') -> dict:
    """Latest stock quote (spot price for an underlying)."""
    data = _get(f'{DATA}/v2/stocks/{ticker}/quotes/latest')
    q = data.get('quote', {})
    bid, ask = q.get('bp', 0), q.get('ap', 0)
    mid = (bid + ask) / 2 if (bid and ask) else (bid or ask)
    return {'symbol': ticker, 'bid': bid, 'ask': ask, 'mid': mid, 'timestamp': q.get('t')}


def get_option(occ_symbol: str) -> dict:
    """Single-contract Greeks snapshot. Delegates to batch endpoint."""
    data = _get(f'{DATA}/v1beta1/options/snapshots',
                params={'symbols': occ_symbol})
    snap = data.get('snapshots', {}).get(occ_symbol, {})
    out = _extract(snap, occ_symbol)
    out['symbol'] = occ_symbol
    return out


def get_options_batch(symbols: List[str]) -> Dict[str, dict]:
    """Batch Greeks for a list of OCC symbols. Chunks at 50/call."""
    if not symbols:
        return {}
    out: Dict[str, dict] = {}
    for i in range(0, len(symbols), 50):
        chunk = symbols[i:i + 50]
        try:
            data = _get(f'{DATA}/v1beta1/options/snapshots',
                        params={'symbols': ','.join(chunk)})
            snaps = data.get('snapshots', {})
            for sym in chunk:
                row = _extract(snaps.get(sym), sym)
                row['symbol'] = sym
                out[sym] = row
        except Exception as e:
            for sym in chunk:
                out[sym] = {'symbol': sym, '_error': str(e)}
    return out


def get_chain(underlying: str = 'SPY',
              expiry_from: Optional[str] = None,
              expiry_to: Optional[str] = None,
              option_type: Optional[str] = None,
              strike_min: Optional[float] = None,
              strike_max: Optional[float] = None,
              limit: int = 200) -> List[dict]:
    """Chain snapshot for an underlying.

    Filters:
      expiry_from — YYYY-MM-DD inclusive lower bound (sent as expiration_date_gte)
      expiry_to   — YYYY-MM-DD inclusive upper bound (sent as expiration_date_lte)
      option_type — 'call' or 'put'
      strike_min  — strike floor (inclusive)
      strike_max  — strike ceiling (inclusive)

    Returns flat list of contracts with mark, Greeks, IV, OI, DTE.
    Paginates internally up to `limit` contracts.

    Note on Alpaca behavior: a single `expiration_date` filter is exact-match
    and frequently returns zero rows because monthly expiries occasionally
    settle on Thursday rather than the third Friday. Always use a range.
    """
    params: Dict[str, Any] = {'limit': min(limit, 1000)}
    if expiry_from: params['expiration_date_gte'] = expiry_from
    if expiry_to: params['expiration_date_lte'] = expiry_to
    if option_type: params['type'] = option_type
    if strike_min is not None: params['strike_price_gte'] = strike_min
    if strike_max is not None: params['strike_price_lte'] = strike_max

    contracts: List[dict] = []
    page_token: Optional[str] = None
    pages = 0
    while pages < 20:
        if page_token:
            params['page_token'] = page_token
        data = _get(f'{DATA}/v1beta1/options/snapshots/{underlying}', params=params)
        snaps = data.get('snapshots', {})
        for sym, snap in snaps.items():
            row = _extract(snap, sym)
            row['symbol'] = sym
            contracts.append(row)
        page_token = data.get('next_page_token')
        pages += 1
        if not page_token or len(contracts) >= limit:
            break

    contracts.sort(key=lambda c: (c.get('expiry', ''), c.get('strike') or 0))
    return contracts[:limit]


# ---- CLI ------------------------------------------------------------------

def main():
    p = argparse.ArgumentParser(description="Alpaca options data feed (read-only)")
    p.add_argument('--cmd', default='health',
                   choices=['health', 'spot', 'option', 'batch', 'chain'])
    p.add_argument('--ticker', default='SPY', help='underlying for --cmd spot/chain (default SPY)')
    p.add_argument('--symbol', help='OCC symbol for --cmd option')
    p.add_argument('--symbols', help='Comma-separated OCC symbols for --cmd batch')
    p.add_argument('--expiry-from', help='YYYY-MM-DD lower bound for --cmd chain')
    p.add_argument('--expiry-to', help='YYYY-MM-DD upper bound for --cmd chain')
    p.add_argument('--type', choices=['call', 'put'], help='filter for --cmd chain')
    p.add_argument('--strike-min', type=float, help='strike floor for --cmd chain')
    p.add_argument('--strike-max', type=float, help='strike ceiling for --cmd chain')
    p.add_argument('--limit', type=int, default=200, help='max contracts for --cmd chain')
    args = p.parse_args()
    try:
        if args.cmd == 'health':
            spy = get_spot('SPY')
            print(json.dumps({
                'auth': 'ok',
                'spy_mid': spy['mid'],
                'data_url': DATA,
            }, indent=2, default=str))
        elif args.cmd == 'spot':
            print(json.dumps(get_spot(args.ticker), indent=2, default=str))
        elif args.cmd == 'option':
            if not args.symbol:
                sys.stderr.write("--symbol required\n"); sys.exit(1)
            print(json.dumps(get_option(args.symbol), indent=2, default=str))
        elif args.cmd == 'batch':
            if not args.symbols:
                sys.stderr.write("--symbols required\n"); sys.exit(1)
            syms = [s.strip() for s in args.symbols.split(',') if s.strip()]
            print(json.dumps(get_options_batch(syms), indent=2, default=str))
        elif args.cmd == 'chain':
            chain = get_chain(args.ticker, args.expiry_from, args.expiry_to, args.type,
                              args.strike_min, args.strike_max, args.limit)
            print(json.dumps(chain, indent=2, default=str))
    except RuntimeError as e:
        sys.stderr.write(f"FAIL: {e}\n"); sys.exit(1)


if __name__ == '__main__':
    main()
