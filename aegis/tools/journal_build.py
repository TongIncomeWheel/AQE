#!/usr/bin/env python3
"""Journal build — Operation 1 done by CODE instead of by a model (D-93).

WHY THIS EXISTS (PM, this session: "I asked for post market to be a executable batch to be run").
Post-market could not be a batch, and the reason was this step. Every other operation in the
loop already had a deterministic tool behind it — membership (`held_book_refresh classify`),
the option book (`option_book classify` / `derive-hedge`), carry-forward, metrics, the archive,
the audit, the stamp. Operation 1 — reconcile the two broker payloads into the book of record —
had NO tool. It was performed by the orchestrating model, in context, every night.

WHAT THAT COST, evidenced in the last real journal on disk (2026-07-21, checked before writing
a line of this):
  1. `entry_date: ""` on every open position. Not null, not absent — an empty string a schema
     with `type: string` happily accepts. Nothing downstream can compute a holding period.
  2. `sector: "TBD"` written as a literal placeholder into the book of record.
  3. `option_positions: []` while `hedge` described two live put spreads. The two halves of the
     same file disagreed, because a human-shaped hand wrote one and not the other.
  4. `hedge` written as free prose — `{"XLK_put_spread_aug21": {"legs": "+2x 175P / -2x 165P
     (Tiger)", ...}, "note": "...NOTE (recover 2026-07-22): the scheduled post-market run
     wrongly re-included IWM_put_spread_aug07..."}` — a paragraph of narrative inside the
     structured record `hedge_engine.assess_current_hedge()` is supposed to read by field.
  5. Every raw broker payload discarded. Nothing was retained, so nothing could be re-derived,
     re-checked, or diffed after the fact. A wrong number in the journal had no upstream to
     appeal to.
None of those are model failures — they are what asking a language model to be an ETL job looks
like. The fix is not a better prompt.

THE INPUT CONTRACT. The broker pulls are MCP connector calls; a shell script cannot make them,
so they stay in the harness. The harness writes each tool result VERBATIM — no editing, no
summarising, no "cleaning" — into a directory, and this tool reads that directory:

    data/eod/<DATE>/broker_pull/
        tiger_stock_positions.json      tiger_option_positions.json
        tiger_filled_orders.json        tiger_order_transactions.json
        tiger_account_summary.json      tiger_open_orders.json          (D-105: live protective
                                                                          stops — see _apply_live_stops)
        ibkr_account_positions.json     ibkr_account_orders.json        (D-104: retired, see below —
        ibkr_account_trades.json        ibkr_account_summary.json        harmless to still pull/save,
                                                                          never read into the book)

D-105 (PM, 2026-08-20: "your PTJ does not print the current SL from broker. that is stupid. we
need entry price, SL price, entry date for all held positions") — two real gaps this closed:
  1. `stop_live_broker` was schema-defined and documented as "execution truth" but nothing in
     the pipeline ever wrote it — held_book_refresh.py explicitly refuses to (by design, see its
     docstring), and journal_build.py only ever initialised it to null. There was no bug to trip
     over; the population step simply did not exist. Fixed by `_apply_live_stops()`: reads
     tiger_open_orders.json (Tiger's *working* SELL STP/STP_LMT orders — the tool description
     is explicit these exclude anything already filled or cancelled), matches each to its equity
     position by ticker, and writes the live stop price. A position with no working stop order
     gets `stop_live_broker: null` PLUS a `no_live_stop` flag — an unprotected position must be
     visible, never silently blank the same way a protected one is.
  2. `entry_date` fell back to the RUN DATE (today) whenever carry-forward found nothing in the
     prior journal — which is every position's first appearance, i.e. every new entry got today's
     date stamped as if that were the true entry date, drifting further from reality with every
     day it then gets carried forward unchanged. Fixed by `_derive_entry_date()`: before falling
     back, it searches this pull's own tiger_filled_orders.json for the BUY fill(s) that
     establish the position and uses the fill's own date. Only when no matching fill exists in
     this pull (the position predates everything ever pulled) does it fall back to the run date —
     and that fallback is now flagged `entry_date_unknown` rather than silently indistinguishable
     from a real one.

Verbatim matters twice over: it is the audit trail that never existed, and it is what lets this
tool be fixed against real payloads instead of imagined ones.

THE HONESTY RULES, which are the whole point:
  - NEVER FABRICATE. A row whose ticker or quantity cannot be mapped is not written with a
    guessed value and is not silently dropped. It becomes a HIGH review flag carrying the actual
    keys the payload used, and the build exits 2. The first live run therefore tells us the real
    shape of the payload rather than producing a plausible, wrong book.
  - AN ABSENT FILE AND AN EMPTY FILE ARE DIFFERENT THINGS. No option payload at all means the
    pull did not happen: prior legs are carried untouched (post_market's own empty-book rule).
    An option payload that is present and contains zero rows is a real, unambiguous answer:
    today's legs are empty. Collapsing the two is how a hedge disappears from the record.
  - CLOSES ARE ONLY CLOSES AGAINST OUR OWN BOOK. A fill is a closed Aegis trade only if that
    ticker was in the PRIOR journal's open_positions. The PM runs Income Wheel and Protege9 on
    the same two brokers; a fill on a ticker Aegis never held is somebody else's. It is flagged
    for visibility, never booked as our realised P&L.
  - USD ONLY (Charter §0.6). A non-USD row is skipped and flagged, never converted at a rate
    this tool has no source for.
  - `aqe_snapshot` IS NEVER TOUCHED HERE. That is Operation 2's carry-forward and premarket's
    refresh. This tool records execution truth only.

EXIT CODES — the same three-way grammar as phase_gate / aqe_coverage / artefact_check, mapped
onto post_market's own failure ladder. D-104 (PM ruling, 2026-08-19): IBKR is retired from the
Aegis book — Tiger is the sole broker source, so PARTIAL_SOURCES ("one of two brokers") is no
longer a reachable state; the ladder collapses to two rungs:
    0  FULL          Tiger pulled and reconciled
    2  PROVISIONAL / cannot build — Tiger absent, or rows that cannot be mapped. Page and
       halt held-list mutations downstream.

Deterministic (law 4) — no model, no network, no clock-derived business logic (the run date is
always passed in). `parse_occ` is imported from tools/option_book.py rather than re-implemented,
because two OCC parsers that disagree is worse than none.

Usage:
  python3 tools/journal_build.py build --date 2026-07-28 \
      --pull data/eod/2026-07-28/broker_pull [--prior <journal>] [--out <journal>] [--json]
  python3 tools/journal_build.py selftest
"""

import argparse
import copy
import glob
import json
import os
import re
import sys
from datetime import datetime, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))

try:
    from option_book import parse_occ  # one OCC parser in the kernel, not two
except Exception:  # pragma: no cover - import guard only
    parse_occ = None

# ---------------------------------------------------------------- payload file contract

TIGER_FILES = {
    "stock_positions": "tiger_stock_positions.json",
    "option_positions": "tiger_option_positions.json",
    "filled_orders": "tiger_filled_orders.json",
    "order_transactions": "tiger_order_transactions.json",
    "account_summary": "tiger_account_summary.json",
    "open_orders": "tiger_open_orders.json",
}

# D-105: working SELL stop order types Tiger returns from get_open_orders.
_STOP_ORDER_TYPES = ("STP", "STP_LMT", "STOP", "STOP_LIMIT", "TRAIL")
IBKR_FILES = {
    "positions": "ibkr_account_positions.json",
    "orders": "ibkr_account_orders.json",
    "trades": "ibkr_account_trades.json",
    "account_summary": "ibkr_account_summary.json",
}

# ---------------------------------------------------------------- field aliases
# Deliberately explicit and deliberately long. Every entry here is a name some broker payload
# has plausibly used. When a live payload turns up a name that is NOT here, the build fails
# loudly with the observed keys (see _require) rather than guessing — add the alias, do not
# add a fallback that invents a value.

A_TICKER = ("symbol", "ticker", "local_symbol", "localSymbol", "contract_symbol",
            "underlying_symbol", "underlyingSymbol", "underlying")
A_QTY = ("quantity", "qty", "position", "size", "shares", "net_position", "netPosition",
         "position_size", "positionSize")
A_ENTRY = ("average_cost", "avgCost", "averageCost", "avg_cost", "average_price", "avgPrice",
           "averagePrice", "avg_price", "avg_entry_price", "cost_basis_price", "costBasisPrice",
           "open_price", "openPrice", "entry")
A_COST_TOTAL = ("cost_basis", "costBasis", "total_cost", "totalCost")
A_MARK = ("market_price", "marketPrice", "latest_price", "latestPrice", "mark_price",
          "markPrice", "last_price", "lastPrice", "current_price", "currentPrice", "last",
          "close", "price")
A_UNREAL = ("unrealized_pnl", "unrealizedPnl", "unrealizedPnL", "unrealised_pnl",
            "unrealisedPnl", "unrealized_profit_loss", "unrealizedProfitLoss", "unrealised_usd",
            "unrealized_usd", "upnl")
A_ASSET = ("asset_class", "assetClass", "sec_type", "secType", "security_type", "securityType",
           "instrument_type", "instrumentType", "asset_type", "assetType")
A_CCY = ("currency", "curr", "trading_currency", "tradingCurrency", "base_currency")
A_RIGHT = ("right", "put_call", "putCall", "option_type", "optionType", "call_or_put",
           "callOrPut")
A_STRIKE = ("strike", "strike_price", "strikePrice")
A_EXPIRY = ("expiry", "expiration", "expiry_date", "expiryDate", "expiration_date",
            "expirationDate", "maturity_date", "maturityDate",
            "last_trade_date_or_contract_month", "lastTradeDateOrContractMonth")
A_SIDE = ("side", "action", "direction", "buy_sell", "buySell", "order_side", "orderSide")
A_FILL_QTY = ("filled_quantity", "filledQuantity", "filled_qty", "cum_qty", "cumQty",
              "quantity", "qty", "size", "shares")
A_FILL_PX = ("filled_price", "filledPrice", "avg_fill_price", "avgFillPrice", "fill_price",
             "fillPrice", "average_price", "averagePrice", "trade_price", "tradePrice", "price")
A_FILL_TIME = ("filled_time", "filledTime", "trade_time", "tradeTime", "transaction_time",
               "transactionTime", "execution_time", "executionTime", "trade_date", "tradeDate",
               "datetime", "time", "timestamp")
A_STATUS = ("status", "order_status", "orderStatus", "state")

A_DESC = ("contract_description", "contractDescription", "description", "desc",
          "instrument", "instrument_name", "name")

OPTION_ASSET_WORDS = {"OPT", "FOP", "OPTION", "OPTIONS", "EQUITY_OPTION", "STK_OPT"}
_OCC_LOOKS_LIKE = re.compile(r"^[A-Z]{1,6}\s?\d{6}[CP]\d{8}$")

# IBKR does not return structured option fields. `get_account_positions` returns ONE string —
# "AEHR Jul31'26 80 PUT @AMEX" — and the strike, right and expiry exist nowhere else in the
# row. Without this, every IBKR option leg is unmappable and the whole run halts at exit 2,
# which is what the first live rehearsal of the batch actually did. Equities come back as a
# bare symbol ("CHYM"); the HKD sleeve as an exchange-qualified number ("700 @SEHK"), which
# the currency check drops before this is ever consulted.
_MONTHS = {m: i for i, m in enumerate(
    ["JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"], 1)}
_DESC_OPTION = re.compile(
    r"^(?P<root>[A-Z][A-Z0-9.]{0,5})\s+"
    r"(?P<mon>[A-Za-z]{3})(?P<day>\d{1,2})'(?P<yy>\d{2})\s+"
    r"(?P<strike>\d+(?:\.\d+)?)\s+"
    r"(?P<right>CALL|PUT|C|P)\b", re.IGNORECASE)
_DESC_PLAIN = re.compile(r"^[A-Z][A-Z0-9.]{0,5}$")


def _parse_broker_description(desc):
    """Pull underlying/expiry/strike/right out of a broker's one-line contract description.
    Returns None rather than a partial guess — a half-parsed leg is worse than an honest
    unmappable row, because the unmappable path names the observed keys and stops the run."""
    m = _DESC_OPTION.match(str(desc).strip())
    if not m:
        return None
    mon = _MONTHS.get(m.group("mon").upper())
    if not mon:
        return None
    return {
        "underlying": m.group("root").upper(),
        "expiry": f"20{m.group('yy')}-{mon:02d}-{int(m.group('day')):02d}",
        "strike": float(m.group("strike")),
        "right": "C" if m.group("right").upper().startswith("C") else "P",
    }

# ---------------------------------------------------------------- generic payload handling


def _unwrap(obj, _depth=0):
    """Peel the envelopes an MCP tool result can arrive in and return the payload underneath.

    Handles: a JSON string; the {"content":[{"type":"text","text":"<json>"}]} block form; and
    the single-key container forms ({"data": ...}, {"positions": ...}, {"result": ...}). Depth
    is bounded so a self-referential or pathological structure cannot spin.
    """
    if _depth > 6:
        return obj
    if isinstance(obj, str):
        s = obj.strip()
        if s[:1] in "[{":
            try:
                return _unwrap(json.loads(s), _depth + 1)
            except Exception:
                return obj
        return obj
    if isinstance(obj, dict):
        if "content" in obj and isinstance(obj["content"], list):
            texts = [b.get("text", "") for b in obj["content"]
                     if isinstance(b, dict) and b.get("type") in (None, "text")]
            joined = "".join(texts).strip()
            if joined:
                return _unwrap(joined, _depth + 1)
        for key in ("data", "result", "results", "rows", "items", "positions", "orders",
                    "trades", "records", "list"):
            if key in obj and isinstance(obj[key], (list, dict, str)):
                return _unwrap(obj[key], _depth + 1)
    return obj


def _rows(payload):
    """Return the list of record dicts in a payload, whatever shape it arrived in."""
    p = _unwrap(payload)
    if isinstance(p, list):
        return [r for r in p if isinstance(r, dict)]
    if isinstance(p, dict):
        # a dict of ticker -> record is a legitimate shape too
        vals = list(p.values())
        if vals and all(isinstance(v, dict) for v in vals):
            out = []
            for k, v in p.items():
                r = dict(v)
                r.setdefault("symbol", k)
                out.append(r)
            return out
        return [p]
    return []


def _flatten(row, prefix="", out=None, _depth=0):
    """Flatten one level of nesting so contract.symbol is reachable as both 'symbol' and
    'contract.symbol'. Brokers habitually nest the instrument under `contract`."""
    if out is None:
        out = {}
    if _depth > 3 or not isinstance(row, dict):
        return out
    for k, v in row.items():
        key = f"{prefix}{k}"
        if isinstance(v, dict):
            _flatten(v, f"{key}.", out, _depth + 1)
            for kk, vv in v.items():
                if not isinstance(vv, (dict, list)):
                    out.setdefault(kk, vv)
        else:
            out[key] = v
    return out


def _pick(row, aliases):
    flat = _flatten(row)
    for a in aliases:
        if a in flat and flat[a] not in (None, ""):
            return flat[a]
        for k, v in flat.items():
            if k.endswith("." + a) and v not in (None, ""):
                return v
    return None


def _num(v):
    """Parse a number out of the several ways a broker can spell one. Returns None, never 0,
    when there is nothing to parse — a missing price and a zero price are different facts."""
    if v is None or isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        return float(v)
    s = str(v).strip()
    if not s:
        return None
    neg = s.startswith("(") and s.endswith(")")
    s = s.strip("()").replace(",", "").replace("$", "").replace("%", "").strip()
    try:
        n = float(s)
    except ValueError:
        return None
    return -n if neg else n


def _date_only(s):
    """D-101 fix: this previously regex-matched digit patterns only, so a raw epoch-millisecond
    trade_time (e.g. 1787059812246, what Tiger's get_transactions/get_filled_orders actually
    return for trade_time/order_time — see A_FILL_TIME) fell through to the 8-digit fallback and
    produced garbage like '1787-05-98' (first 8 digits of the epoch, sliced as if it were
    YYYYMMDD). Never caught before because no closed_trade had ever been booked (D-100 was the
    first). Epoch ms/seconds are now detected and converted properly before any digit-pattern
    fallback is tried."""
    if not s:
        return None
    if isinstance(s, (int, float)) or (isinstance(s, str) and re.match(r"^\d+$", s.strip())):
        n = int(s)
        try:
            if n > 10**12:      # milliseconds since epoch
                return datetime.fromtimestamp(n / 1000.0, tz=timezone.utc).strftime("%Y-%m-%d")
            if n > 10**9:       # seconds since epoch (10-digit)
                return datetime.fromtimestamp(n, tz=timezone.utc).strftime("%Y-%m-%d")
        except (ValueError, OSError, OverflowError):
            pass
    m = re.search(r"(\d{4})[-/](\d{2})[-/](\d{2})", str(s))
    if m:
        return f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
    m = re.match(r"^(\d{8})$", str(s).strip())
    if m:
        d = m.group(1)
        return f"{d[0:4]}-{d[4:6]}-{d[6:8]}"
    return None


def _expiry_iso(v):
    d = _date_only(v)
    if d:
        return d
    s = str(v or "").strip()
    if re.fullmatch(r"\d{6}", s):  # YYMMDD
        return f"20{s[0:2]}-{s[2:4]}-{s[4:6]}"
    return None


def _load_json(path):
    """Read a payload file. Returns (obj, error). A corrupt file is a finding, never a crash."""
    if not os.path.exists(path):
        return None, "absent"
    try:
        with open(path) as fh:
            return json.load(fh), None
    except Exception as exc:
        return None, f"unreadable: {exc.__class__.__name__}: {exc}"


# ---------------------------------------------------------------- row classification


def _is_option_row(row):
    asset = _pick(row, A_ASSET)
    if asset and str(asset).upper().replace(" ", "_") in OPTION_ASSET_WORDS:
        return True
    if _pick(row, A_STRIKE) is not None and _pick(row, A_RIGHT) is not None:
        return True
    sym = _pick(row, A_TICKER)
    if