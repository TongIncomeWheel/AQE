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
    if sym and _OCC_LOOKS_LIKE.match(str(sym).upper().replace(" ", "")):
        return True
    return False


def _right_of(row):
    r = _pick(row, A_RIGHT)
    if r is None:
        return None
    s = str(r).strip().upper()
    if s in ("C", "CALL", "CALLS"):
        return "C"
    if s in ("P", "PUT", "PUTS"):
        return "P"
    return None


def _signed_qty(row, raw_qty):
    """Apply an explicit short/sell marker when the payload reports magnitude separately from
    direction. A short leg recorded as +2 makes a debit spread underivable (D-89)."""
    if raw_qty is None:
        return None
    side = _pick(row, A_SIDE)
    if side and raw_qty > 0:
        s = str(side).strip().upper()
        if s in ("SHORT", "SELL", "SLD", "S", "SELL_TO_OPEN", "SELL_TO_CLOSE", "-1"):
            return -raw_qty
    return raw_qty


# ---------------------------------------------------------------- builders


def _flag(flags, ticker, kind, detail, severity="medium"):
    flags.append({"ticker": ticker or "-", "type": kind, "detail": detail,
                  "severity": severity, "since": None})


def _equity_position(row, broker, flags, unmappable):
    ccy = _pick(row, A_CCY)
    if ccy and str(ccy).upper() not in ("USD", "US$", "$"):
        _flag(flags, str(_pick(row, A_TICKER) or "?"), "non_usd_row",
              f"{broker} row in {ccy} skipped — USD only (Charter §0.6); this tool has no FX "
              f"source and will not convert at a rate it cannot cite", "medium")
        return None

    ticker = _pick(row, A_TICKER)
    if not ticker:
        # IBKR equities arrive as a bare symbol in contract_description and nowhere else.
        # Only a description that IS a plain symbol is accepted — never a parsed fragment.
        desc = str(_pick(row, A_DESC) or "").strip().upper()
        if _DESC_PLAIN.match(desc):
            ticker = desc
    qty = _num(_pick(row, A_QTY))
    if not ticker or qty is None:
        unmappable.append({"broker": broker, "observed_keys": sorted(_flatten(row).keys())[:40]})
        return None
    if qty == 0:
        return None

    ticker = str(ticker).strip().upper()
    entry = _num(_pick(row, A_ENTRY))
    if entry is None:
        total = _num(_pick(row, A_COST_TOTAL))
        if total is not None and qty:
            entry = round(total / qty, 4)
    mark = _num(_pick(row, A_MARK))
    unreal = _num(_pick(row, A_UNREAL))
    if unreal is None and mark is not None and entry is not None:
        unreal = round((mark - entry) * qty, 2)

    return {
        "ticker": ticker,
        "qty": qty,
        "entry": entry if entry is not None else 0.0,
        "entry_date": None,
        "stop_reference": None,
        "stop_live_broker": None,
        "stop_match": None,
        "tp1": None, "tp2": None, "tp3": None,
        "trigger": None,
        "broker": broker,
        "mark_price": mark,
        "unrealised_usd": unreal,
        "_entry_missing": entry is None,
    }


def _option_leg(row, broker, flags, unmappable):
    sym = str(_pick(row, A_TICKER) or "").strip().upper().replace(" ", "")
    underlying = None
    right = _right_of(row)
    strike = _num(_pick(row, A_STRIKE))
    expiry = _expiry_iso(_pick(row, A_EXPIRY))

    if parse_occ and _OCC_LOOKS_LIKE.match(sym):
        try:
            parsed = parse_occ(sym)
        except Exception:
            parsed = None
        if parsed:
            underlying = parsed.get("underlying") or underlying
            right = right or parsed.get("right")
            strike = strike if strike is not None else parsed.get("strike")
            expiry = expiry or parsed.get("expiry")

    desc = _pick(row, A_DESC)
    if desc:
        parsed_desc = _parse_broker_description(desc)
        if parsed_desc:
            underlying = underlying or parsed_desc["underlying"]
            right = right or parsed_desc["right"]
            strike = strike if strike is not None else parsed_desc["strike"]
            expiry = expiry or parsed_desc["expiry"]

    underlying = underlying or _pick(row, ("underlying", "underlying_symbol", "underlyingSymbol",
                                          "root", "root_symbol"))
    if not underlying and sym and not _OCC_LOOKS_LIKE.match(sym):
        underlying = sym

    qty = _signed_qty(row, _num(_pick(row, A_QTY)))
    missing = [n for n, v in (("underlying", underlying), ("right", right),
                              ("strike", strike), ("expiry", expiry), ("qty", qty))
               if v in (None, "")]
    if missing:
        unmappable.append({"broker": broker, "leg": True, "missing": missing,
                           "observed_keys": sorted(_flatten(row).keys())[:40]})
        return None
    if qty == 0:
        return None

    entry = _num(_pick(row, A_ENTRY))
    if entry is None:
        total = _num(_pick(row, A_COST_TOTAL))
        if total is not None and qty:
            entry = round(total / (qty * 100.0), 4)

    return {
        "occ_symbol": sym if _OCC_LOOKS_LIKE.match(sym) else "",
        "underlying": str(underlying).strip().upper(),
        "right": right,
        "strike": float(strike),
        "expiry": expiry,
        "qty": float(qty),
        "entry": entry,
        "entry_date": None,
        "broker": broker,
        "mark_price": _num(_pick(row, A_MARK)),
        "unrealised_usd": _num(_pick(row, A_UNREAL)),
        "delta": None, "gamma": None, "theta": None, "vega": None, "iv": None,
    }


def _fills(payloads, broker):
    """Normalise fills from whichever of the fill-shaped payloads the broker provided."""
    out = []
    for payload in payloads:
        for row in _rows(payload):
            status = _pick(row, A_STATUS)
            if status and str(status).upper() in ("CANCELLED", "CANCELED", "REJECTED",
                                                  "EXPIRED", "PENDING", "SUBMITTED", "NEW",
                                                  "PENDING_SUBMIT", "PRESUBMITTED"):
                continue
            ticker = _pick(row, A_TICKER)
            qty = _num(_pick(row, A_FILL_QTY))
            px = _num(_pick(row, A_FILL_PX))
            if not ticker or qty is None or px is None or qty == 0:
                continue
            side = str(_pick(row, A_SIDE) or "").strip().upper()
            sign = -1.0 if side in ("SELL", "SLD", "S", "SELL_TO_CLOSE",
                                    "SELL_TO_OPEN", "SHORT") else 1.0
            if qty < 0:
                sign, qty = -1.0, abs(qty)
            out.append({
                "ticker": str(ticker).strip().upper(),
                "qty": qty * sign,
                "price": px,
                "time": _date_only(_pick(row, A_FILL_TIME)),
                "broker": broker,
                "is_option": _is_option_row(row),
            })
    return out


def _closed_trades(fills, prior_open, date):
    """A fill is an Aegis close only if that ticker was in the PRIOR journal's open_positions.

    The PM runs other books on the same two brokers and there is no broker-native tag to filter
    by, so "this ticker was in our book yesterday" is the only honest membership test available
    at this stage. Everything else is surfaced, never booked.
    """
    prior = {}
    for p in prior_open or []:
        t = str(p.get("ticker", "")).upper()
        if not t:
            continue
        prior.setdefault(t, {"qty": 0.0, "entry": None})
        prior[t]["qty"] += float(p.get("qty") or 0)
        if prior[t]["entry"] is None:
            prior[t]["entry"] = p.get("entry")

    closed, unmatched = [], []
    for f in sorted(fills, key=lambda x: (x["ticker"], x["broker"], x["price"], x["qty"])):
        if f["is_option"]:
            continue
        t = f["ticker"]
        held = prior.get(t)
        if not held or held["qty"] == 0:
            unmatched.append(f)
            continue
        held_sign = 1.0 if held["qty"] > 0 else -1.0
        fill_sign = 1.0 if f["qty"] > 0 else -1.0
        if fill_sign == held_sign:
            continue  # an add, not a close
        closing_qty = min(abs(f["qty"]), abs(held["qty"]))
        entry = held["entry"]
        realised = None
        if entry is not None:
            realised = round((f["price"] - float(entry)) * closing_qty * held_sign, 2)
        closed.append({
            "ticker": t,
            "qty": closing_qty * held_sign,
            "entry": entry,
            "exit": f["price"],
            "realised_usd": realised,
            "broker": f["broker"],
            "closed_date": f["time"] or date,
            "partial": closing_qty < abs(held["qty"]),
            "source": "broker_fill",
        })
        held["qty"] -= closing_qty * held_sign
    return closed, unmatched


def _carry(new_positions, prior_open):
    """Carry the fields the broker does not know about: when we opened, and what the stop is.

    Prefers a prior row from the same broker, falls back to any prior row for the ticker. This
    is execution-truth housekeeping only — `aqe_snapshot` is deliberately untouched, that is
    Operation 2's carry-forward and premarket's refresh.
    """
    by_key, by_ticker = {}, {}
    for p in prior_open or []:
        t = str(p.get("ticker", "")).upper()
        by_key[(t, p.get("broker"))] = p
        by_ticker.setdefault(t, p)
    for pos in new_positions:
        src = by_key.get((pos["ticker"], pos["broker"])) or by_ticker.get(pos["ticker"])
        if not src:
            continue
        for field in ("entry_date", "stop_reference", "stop_live_broker", "stop_match",
                      "tp1", "tp2", "tp3", "trigger"):
            if src.get(field) not in (None, ""):
                pos[field] = src[field]
        if src.get("aqe_snapshot"):
            pos["aqe_snapshot"] = src["aqe_snapshot"]
    return new_positions


def _derive_entry_date(equities, fills, flags):
    """D-105: before falling back to today's run date, look for the establishing BUY fill.

    Only searches THIS pull's own fills — the same conservative, no-guessing posture as the
    rest of this tool. A position whose entry predates every pull this tool has ever seen (the
    common case for old book) gets no evidence here and stays on the run-date fallback, but that
    fallback is now flagged so it is never silently mistaken for a real entry date.
    """
    buys_by_ticker = {}
    for f in fills:
        if f["qty"] > 0:  # BUY only; sign convention set in _fills()
            buys_by_ticker.setdefault(f["ticker"], []).append(f)

    for pos in equities:
        if pos.get("entry_date"):
            continue  # carried forward from a real prior entry_date — leave it alone
        candidates = buys_by_ticker.get(pos["ticker"]) or []
        if not candidates:
            continue
        exact = [f for f in candidates if abs(f["qty"] - pos["qty"]) < 1e-6]
        chosen = exact if exact else candidates
        earliest = min((f["time"] for f in chosen if f.get("time")), default=None)
        if earliest:
            pos["entry_date"] = earliest
            if not exact:
                _flag(flags, pos["ticker"], "entry_date_estimated",
                      f"No single BUY fill in this pull matches {pos['ticker']}'s current qty "
                      f"of {pos['qty']:g} exactly (partial builds across multiple fills, or a "
                      f"qty change since); entry_date set to the earliest BUY fill found "
                      f"({earliest}) rather than a today's-run-date guess, but treat it as an "
                      f"estimate, not confirmed fact.", "low")


def _apply_live_stops(equities, open_orders, flags):
    """D-105: write stop_live_broker from Tiger's currently-working SELL stop orders.

    get_open_orders only returns orders "not yet filled or cancelled" (see the MCP tool's own
    description) — so every row here is a genuinely live protective order right now, not history.
    A position with zero matching rows has NO working stop at the broker; that is surfaced with
    a flag, never left indistinguishable from "we just haven't checked".
    """
    by_ticker = {}
    for row in _rows(open_orders):
        action = str(_pick(row, A_SIDE) or "").strip().upper()
        otype = str(row.get("order_type") or "").strip().upper()
        sec = str(_pick(row, A_ASSET) or "").strip().upper()
        if action not in ("SELL", "SLD", "S") or sec not in ("STK", "STOCK", "EQUITY", ""):
            continue
        if otype not in _STOP_ORDER_TYPES:
            continue
        ticker = _pick(row, A_TICKER)
        stop_px = _num(row.get("stop_price")) or _num(row.get("trail_stop_price"))
        if not ticker or stop_px is None:
            continue
        by_ticker.setdefault(str(ticker).strip().upper(), []).append({
            "stop_price": stop_px, "quantity": _num(_pick(row, A_QTY)),
            "order_id": row.get("id"), "order_time": row.get("order_time"),
        })

    for pos in equities:
        rows = by_ticker.get(pos["ticker"]) or []
        if not rows:
            _flag(flags, pos["ticker"], "no_live_stop",
                  f"No working SELL stop order found at the broker for {pos['ticker']} — this "
                  f"position is currently UNPROTECTED. stop_live_broker is null, not a guess.",
                  "high")
            continue
        exact_qty = [r for r in rows if r["quantity"] is not None
                     and abs(r["quantity"] - pos["qty"]) < 1e-6]
        chosen = exact_qty[0] if len(exact_qty) == 1 else max(
            rows, key=lambda r: r.get("order_time") or 0)
        pos["stop_live_broker"] = chosen["stop_price"]
        if len(rows) > 1 and len(exact_qty) != 1:
            _flag(flags, pos["ticker"], "multiple_live_stops",
                  f"{len(rows)} working SELL stop orders found for {pos['ticker']} and none "
                  f"matches the full position qty of {pos['qty']:g} exactly — used the most "
                  f"recently placed one ({chosen['stop_price']}, order {chosen['order_id']}). "
                  f"Verify manually; this may be a partial stop or a stale duplicate.", "medium")
        ref = pos.get("stop_reference")
        if ref is None:
            pos["stop_match"] = None
        else:
            pos["stop_match"] = "MATCH" if abs(float(ref) - chosen["stop_price"]) < 0.01 \
                else "MISMATCH"


def _dyncap(open_positions, closed_today, prior_ledger, allocated, one_r_pct):
    realised_prior = float((prior_ledger or {}).get("realised_pnl_usd") or 0.0)
    realised_today = sum(c["realised_usd"] for c in closed_today
                         if c.get("realised_usd") is not None)
    unrealised = sum(p["unrealised_usd"] for p in open_positions
                     if p.get("unrealised_usd") is not None)
    realised = round(realised_prior + realised_today, 2)
    unrealised = round(unrealised, 2)
    value = round(float(allocated) + realised + unrealised, 2)
    return {
        "value": value,
        "one_r": round(value * float(one_r_pct) / 100.0, 2),
        "method": (f"D-41 mark-to-market, computed by tools/journal_build.py: allocated "
                   f"{float(allocated):.2f} + realised {realised:.2f} "
                   f"(prior {realised_prior:.2f} + today {realised_today:.2f}) + unrealised "
                   f"{unrealised:.2f} (broker marks, equity book only — hedge MTM excluded) "
                   f"= {value:.2f}. 1R = {one_r_pct}% [RB:capital.one_r_pct_of_dyncap]. "
                   f"AEGIS book only [RB:identity.capital_segregation]."),
    }


# ---------------------------------------------------------------- main build


def build(date, pull_dir, prior_journal=None, allocated=None, one_r_pct=1.5,
          prior_ledger=None, now_utc=None):
    """Reconcile the saved broker payloads into a journal document.

    Returns (journal, report). Never raises on bad payload content — a payload this tool cannot
    read is a finding in the report, which is the thing that gets acted on.
    """
    flags, unmappable, notes = [], [], []
    connectors, sources_present = [], []

    def _read(name):
        obj, err = _load_json(os.path.join(pull_dir, name))
        if err == "absent":
            return None, False
        if err:
            _flag(flags, "-", "payload_unreadable", f"{name}: {err}", "high")
            return None, True
        return obj, True

    tiger_stock, tiger_stock_present = _read(TIGER_FILES["stock_positions"])
    tiger_opt, tiger_opt_present = _read(TIGER_FILES["option_positions"])
    tiger_fills_a, _ = _read(TIGER_FILES["filled_orders"])
    tiger_fills_b, _ = _read(TIGER_FILES["order_transactions"])
    tiger_open, tiger_open_present = _read(TIGER_FILES["open_orders"])
    ibkr_pos, ibkr_pos_present = _read(IBKR_FILES["positions"])
    ibkr_trades, _ = _read(IBKR_FILES["trades"])

    equities, legs = [], []

    if tiger_stock_present:
        connectors.append("TIGER")
        sources_present.append("TIGER")
        for row in _rows(tiger_stock):
            if _is_option_row(row):
                leg = _option_leg(row, "TIGER", flags, unmappable)
                if leg:
                    legs.append(leg)
                continue
            pos = _equity_position(row, "TIGER", flags, unmappable)
            if pos:
                equities.append(pos)

    if tiger_opt_present:
        for row in _rows(tiger_opt):
            leg = _option_leg(row, "TIGER", flags, unmappable)
            if leg:
                legs.append(leg)

    # D-104 (PM ruling, 2026-08-19): IBKR retired from the Aegis book. "Tiger (default broker;
    # IBKR if in use)" is no longer the rule — Tiger is now the SOLE broker source read into
    # open_positions/option_positions/closed_trades. An ibkr_account_positions.json /
    # ibkr_account_trades.json payload may still be present in a pull (harmless to save, and
    # useful for audit of other, non-Aegis books on the same IBKR account) but its rows are no
    # longer ingested here. This mirrors the same retirement already ratified for bracket.py's
    # spot-quote path (D-98: Tiger primary, FMP fallback, IBKR retired) — the two ran on
    # different clocks and the post-market side never caught up until now.
    if ibkr_pos_present:
        _flag(flags, "-", "ibkr_ignored",
              "ibkr_account_positions.json was present in this pull but IBKR is retired from "
              "the Aegis book (D-104, PM ruling 2026-08-19) — its rows were NOT read into "
              "open_positions or option_positions. Tiger is the sole broker source.", "low")

    for pos in equities:
        if pos.pop("_entry_missing", False):
            _flag(flags, pos["ticker"], "entry_price_missing",
                  f"{pos['broker']} reported no average cost and no cost basis for "
                  f"{pos['ticker']}; entry recorded as 0.0 and P&L on this name is not "
                  f"trustworthy until it is corrected", "high")

    equities.sort(key=lambda p: (p["ticker"], p["broker"]))
    legs.sort(key=lambda l: (l["underlying"], l["expiry"], l["right"], l["strike"], l["broker"]))

    prior = {}
    if prior_journal and os.path.exists(prior_journal):
        obj, err = _load_json(prior_journal)
        if err:
            _flag(flags, "-", "prior_journal_unreadable", f"{prior_journal}: {err}", "high")
        else:
            prior = obj or {}

    fills = _fills([p for p in (tiger_fills_a, tiger_fills_b) if p is not None], "TIGER")
    # D-104: IBKR fills are no longer read into Aegis close-matching either — see the ibkr_pos
    # retirement note above. (ibkr_trades is still loaded above so an absent-vs-unreadable
    # distinction is possible if this is ever revisited, but it is deliberately unused here.)
    closed, unmatched_fills = _closed_trades(fills, prior.get("open_positions"), date)

    for f in unmatched_fills:
        _flag(flags, f["ticker"], "unmatched_fill",
              f"{f['broker']} filled {f['qty']:+g} {f['ticker']} @ {f['price']} but that ticker "
              f"was not in yesterday's Aegis book — not booked as an Aegis close. Another "
              f"strategy on the same account, or a new Aegis entry pending membership review.",
              "low")

    _carry(equities, prior.get("open_positions"))
    _derive_entry_date(equities, fills, flags)
    for pos in equities:
        if not pos.get("entry_date"):
            pos["entry_date"] = date
            _flag(flags, pos["ticker"], "entry_date_unknown",
                  f"No prior journal and no matching BUY fill in this pull for "
                  f"{pos['ticker']} — entry_date stamped with today's run date "
                  f"({date}) as a placeholder, NOT a confirmed entry date.", "medium")

    # D-105: live protective stop from the broker's currently-working orders. Absent-vs-empty
    # follows the same rule as the option pull below — an absent payload (the pull never
    # happened) leaves stop_live_broker untouched from carry-forward rather than wiping it to
    # null and flagging every position "unprotected" when the truth is just "not checked".
    if tiger_open_present:
        _apply_live_stops(equities, tiger_open, flags)
    else:
        _flag(flags, "-", "open_orders_pull_absent",
              "No tiger_open_orders.json in this pull — stop_live_broker was NOT refreshed "
              "this run; whatever it carried forward (if anything) is unverified as of today.",
              "medium")

    # An absent option payload and an empty one are different facts (post_market's empty-book
    # rule). Absent = the pull did not happen, keep what we had. Present-and-empty = a real
    # answer, and derive-hedge is the thing entitled to act on it.
    # D-104: only Tiger's option pull counts — an IBKR-only pull is no longer "the option pull
    # ran" for Aegis purposes, since IBKR rows are ignored regardless of presence.
    option_pull_ran = tiger_opt_present
    if not option_pull_ran:
        legs = copy.deepcopy(prior.get("option_positions") or [])
        if legs:
            _flag(flags, "-", "option_pull_absent",
                  f"No option payload was saved this run; {len(legs)} prior leg(s) carried "
                  f"untouched rather than emptied. An empty pull and a closed hedge are "
                  f"indistinguishable from absent data.", "high")

    # The prior hedge record is carried, never wiped — `option_book derive-hedge` is the only
    # thing entitled to adjudicate it. But it is carried THROUGH the contract, not around it.
    # A malformed prior record (the 21 Jul journal's free-prose hedge is the live example)
    # would otherwise fail validation on a field this tool never wrote, halting post-market
    # every night until someone hand-edited a journal. So: a record that satisfies the hedge
    # sub-schema rides in `hedge`; one that does not is quarantined verbatim under
    # `hedge_quarantined` (nothing is discarded), flagged high, and `hedge` left null for
    # derive-hedge to rebuild from the actual legs.
    hedge = copy.deepcopy(prior.get("hedge"))
    hedge_quarantined = None
    if hedge is not None:
        hedge_errs = _hedge_errors(hedge)
        if hedge_errs:
            hedge_quarantined = hedge
            hedge = None
            _flag(flags, "-", "prior_hedge_malformed",
                  f"The prior journal's hedge record does not satisfy the journal contract "
                  f"({'; '.join(hedge_errs[:4])}). It is preserved verbatim under "
                  f"hedge_quarantined and hedge is null — option_book derive-hedge must "
                  f"rebuild it from the confirmed legs. Coverage is UNKNOWN until it does.",
                  "high")

    # D-104: IBKR is retired from the Aegis book — Tiger is the SOLE broker source, so
    # sources_present can now only ever be [] or ["TIGER"]. The old three-way FULL/
    # PARTIAL_SOURCES/PROVISIONAL grammar existed to distinguish "both brokers", "one of two",
    # and "neither" — with one broker left, "one of two" no longer exists as a state. FULL now
    # means Tiger reported; PROVISIONAL means it didn't and there is no book of record.
    if not sources_present:
        status = "PROVISIONAL"
        exit_code = 2
        notes.append("Tiger's payload was not present — no book of record could be built from "
                     "execution truth. (IBKR's absence never affects this: IBKR is retired "
                     "from the Aegis book, D-104.)")
    else:
        status = "FULL"
        exit_code = 0

    if unmappable:
        exit_code = 2
        for u in unmappable[:20]:
            _flag(flags, "-", "unmappable_row",
                  f"{u['broker']} returned a {'leg' if u.get('leg') else 'position'} this tool "
                  f"could not map"
                  + (f" (missing {', '.join(u['missing'])})" if u.get("missing") else "")
                  + f". Observed keys: {', '.join(u['observed_keys'])}. Nothing was guessed and "
                    f"nothing was dropped silently — add the alias to journal_build.py.", "high")
        notes.append(f"{len(unmappable)} row(s) could not be mapped to the journal contract.")

    allocated = allocated if allocated is not None else 0.0
    dyncap = _dyncap(equities, closed, prior_ledger, allocated, one_r_pct)

    journal = {
        "date": date,
        "dyncap": dyncap,
        "open_positions": equities,
        "closed_trades": closed,
        "option_positions": legs,
        "hedge": hedge,
        # portfolio_metrics.py owns this key and runs later in the same batch. Carrying
        # yesterday's numbers forward would be indistinguishable from today's once written.
        "metrics": {},
        "review_flags": flags,
        "broker_sync": {
            "last_sync_utc": now_utc or datetime.now(timezone.utc).strftime(
                "%Y-%m-%dT%H:%M:%SZ"),
            "sync_phase": "POST_MARKET",
            "connectors": connectors,
            "sources": status,
            "built_by": "tools/journal_build.py (D-93, deterministic)",
            "equity_rows": len(equities),
            "option_legs": len(legs),
            "fills_seen": len(fills),
            "closes_booked": len(closed),
            "fills_unmatched": len(unmatched_fills),
            "option_pull_ran": bool(option_pull_ran),
        },
        "provenance": {
            "pull_dir": os.path.relpath(pull_dir, ROOT) if pull_dir.startswith(ROOT) else pull_dir,
            "prior_journal": (os.path.basename(prior_journal) if prior_journal else None),
            "payloads_present": sorted(
                [n for n in list(TIGER_FILES.values()) + list(IBKR_FILES.values())
                 if os.path.exists(os.path.join(pull_dir, n))]),
        },
    }

    if hedge_quarantined is not None:
        journal["hedge_quarantined"] = hedge_quarantined

    report = {
        "date": date,
        "status": status,
        "exit_code": exit_code,
        "equity_rows": len(equities),
        "option_legs": len(legs),
        "closes_booked": len(closed),
        "fills_unmatched": len(unmatched_fills),
        "unmappable": len(unmappable),
        "flags_high": sum(1 for f in flags if f["severity"] == "high"),
        "dyncap": dyncap["value"],
        "one_r": dyncap["one_r"],
        "notes": notes,
    }
    return journal, report


def _hedge_errors(hedge, schema_path=None):
    """Validate one hedge record against the journal contract's own hedge sub-schema.
    Single source of truth — the required-key list is never restated here."""
    schema_path = schema_path or os.path.join(ROOT, "contracts", "journal.schema.json")
    try:
        with open(schema_path) as fh:
            sub = (json.load(fh).get("properties") or {}).get("hedge")
    except Exception as exc:
        return [f"hedge sub-schema unreadable: {exc}"]
    if not sub:
        return []
    try:
        import jsonschema
    except Exception:
        return [f"missing required property: {k}"
                for k in (sub.get("required") or []) if k not in hedge]
    v = jsonschema.Draft7Validator(sub)
    return [e.message for e in sorted(v.iter_errors(hedge), key=lambda e: list(e.path))][:10]


def validate(journal, schema_path=None):
    """Validate against contracts/journal.schema.json. Returns a list of error strings."""
    schema_path = schema_path or os.path.join(ROOT, "contracts", "journal.schema.json")
    try:
        import jsonschema
    except Exception:
        required = ["date", "dyncap", "open_positions", "closed_trades", "metrics"]
        return [f"missing required key: {k}" for k in required if k not in journal]
    try:
        with open(schema_path) as fh:
            schema = json.load(fh)
    except Exception as exc:
        return [f"schema unreadable: {exc}"]
    v = jsonschema.Draft7Validator(schema)
    return [f"{'/'.join(str(p) for p in e.path) or '<root>'}: {e.message}"
            for e in sorted(v.iter_errors(journal), key=lambda e: list(e.path))][:20]


def render(report):
    lines = [f"JOURNAL BUILD {report['date']} — {report['status']} (exit {report['exit_code']})"]
    lines.append(f"  equity rows {report['equity_rows']} · option legs {report['option_legs']} "
                 f"· closes booked {report['closes_booked']} "
                 f"· unmatched fills {report['fills_unmatched']}")
    lines.append(f"  dynCap {report['dyncap']:,.2f} · 1R {report['one_r']:,.2f}")
    if report["unmappable"]:
        lines.append(f"  UNMAPPABLE ROWS: {report['unmappable']} — see review_flags")
    if report["flags_high"]:
        lines.append(f"  high-severity flags: {report['flags_high']}")
    for n in report["notes"]:
        lines.append(f"  note: {n}")
    return "\n".join(lines)


# ---------------------------------------------------------------- CLI


def _latest_prior(date):
    paths = sorted(glob.glob(os.path.join(ROOT, "data", "journal", "aegis_journal_*.json")))
    prior = [p for p in paths if os.path.basename(p) < f"aegis_journal_{date}.json"]
    return prior[-1] if prior else None


def cmd_build(args):
    date = args.date
    pull_dir = args.pull or os.path.join(ROOT, "data", "eod", date, "broker_pull")
    prior = args.prior or _latest_prior(date)

    allocated, one_r_pct = args.allocated, args.one_r_pct
    if allocated is None:
        try:
            import fund_config
            allocated = fund_config.allocated_capital()
        except Exception:
            allocated = 0.0
    if one_r_pct is None:
        one_r_pct = 1.5
        try:
            import yaml
            params = yaml.safe_load(open(os.path.join(ROOT, "charter", "parameters.yaml")))
            one_r_pct = params["capital"]["one_r_pct_of_dyncap"]
        except Exception:
            pass

    prior_ledger = None
    led_path = os.path.join(ROOT, "data", "persistent", "dyncap_ledger.json")
    if os.path.exists(led_path):
        prior_ledger, _ = _load_json(led_path)

    journal, report = build(date, pull_dir, prior_journal=prior, allocated=allocated,
                            one_r_pct=one_r_pct, prior_ledger=prior_ledger)

    errors = validate(journal)
    if errors:
        report["exit_code"] = 2
        report["schema_errors"] = errors
        report["notes"].append("Journal failed contracts/journal.schema.json — NOT written. "
                               "Ordering rule Arch-F9: nothing downstream may run.")
        print(json.dumps(report, indent=1) if args.json else render(report))
        for e in errors:
            print(f"  schema: {e}", file=sys.stderr)
        return 2

    out = args.out or os.path.join(ROOT, "data", "journal", f"aegis_journal_{date}.json")
    if report["exit_code"] == 2 and not args.write_anyway:
        report["notes"].append(f"NOT written to {os.path.basename(out)} — build did not reach a "
                               "state worth recording as the book.")
        print(json.dumps(report, indent=1) if args.json else render(report))
        return 2

    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w") as fh:
        json.dump(journal, fh, indent=1)
    # Read back, don't trust the write (post_market step 2's verification rule).
    check, err = _load_json(out)
    if err or not check or check.get("date") != date:
        print(f"read-back verification FAILED for {out}: {err or 'date mismatch'}",
              file=sys.stderr)
        return 2
    report["written"] = os.path.relpath(out, ROOT)
    print(json.dumps(report, indent=1) if args.json else render(report))
    return report["exit_code"]


def cmd_verify(args):
    """The read-back verification post_market step 2 demands, as its own command.

    `build` verifies its own write, but four tools mutate that file afterwards
    (held_book classify, option_book classify, derive-hedge, carry-forward). This is the
    check that the file on disk is STILL the book of record after they are done: named to
    convention, parses, carries the right date, and passes the contract. Exit 2 on any
    failure — Arch-F9 says nothing downstream of a bad journal may run."""
    path = args.journal or os.path.join(ROOT, "data", "journal",
                                        f"aegis_journal_{args.date}.json")
    problems = []
    expected = f"aegis_journal_{args.date}.json"
    if os.path.basename(path) != expected:
        problems.append(f"filename is {os.path.basename(path)}, RB:journal.naming wants {expected}")
    if not os.path.exists(path):
        problems.append("file does not exist on disk")
    else:
        obj, err = _load_json(path)
        if err:
            problems.append(f"does not parse: {err}")
        elif not isinstance(obj, dict):
            problems.append(f"top level is {type(obj).__name__}, not an object")
        else:
            if obj.get("date") != args.date:
                problems.append(f"date field is {obj.get('date')!r}, expected {args.date!r}")
            problems += [f"schema: {e}" for e in validate(obj)]

    if problems:
        print(f"JOURNAL VERIFY {args.date} — FAILED ({len(problems)})")
        for p in problems:
            print(f"  {p}")
        return 2
    print(f"JOURNAL VERIFY {args.date} — ok ({os.path.relpath(path, ROOT)})")
    return 0


# ---------------------------------------------------------------- selftest


def _tmpdir():
    import tempfile
    return tempfile.mkdtemp(prefix="journal_build_")


def _write(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as fh:
        json.dump(obj, fh)


def selftest():
    import shutil
    failures = []

    def check(name, cond, detail=""):
        if cond:
            print(f"  ok   {name}")
        else:
            print(f"  FAIL {name} {detail}")
            failures.append(name)

    D = "2026-07-28"
    tmp = _tmpdir()
    pull = os.path.join(tmp, "pull")
    prior_path = os.path.join(tmp, "prior.json")

    _write(prior_path, {
        "date": "2026-07-27",
        "dyncap": {"value": 65000.0, "one_r": 975.0},
        "open_positions": [
            {"ticker": "AMPL", "qty": 571, "entry": 9.7494, "entry_date": "2026-07-10",
             "stop_reference": 8.9, "broker": "TIGER",
             "aqe_snapshot": {"gics_sector": "Technology"}},
            {"ticker": "HBAN", "qty": 300, "entry": 18.40, "entry_date": "2026-07-15",
             "stop_reference": 17.82, "broker": "IBKR"},
        ],
        "closed_trades": [], "metrics": {"gross_exposure_usd": 1.0},
        "option_positions": [{"occ_symbol": "XLK260821P00175000", "underlying": "XLK",
                              "right": "P", "strike": 175.0, "expiry": "2026-08-21",
                              "qty": 2.0, "broker": "TIGER"}],
        "hedge": {"structure_id": "prior-xlk", "legs": []},
    })
    prior_ledger = {"realised_pnl_usd": -3142.93}

    # ---- 1. the happy path — Tiger only (D-104: IBKR retired, Tiger is the sole broker
    # source). MCP text-envelope on the one payload we do have.
    _write(os.path.join(pull, TIGER_FILES["stock_positions"]), {
        "content": [{"type": "text", "text": json.dumps([
            {"symbol": "AMPL", "quantity": 571, "average_cost": 9.7494,
             "latest_price": 9.69, "unrealized_pnl": -32.77, "currency": "USD"},
        ])}]})
    j, r = build(D, pull, prior_journal=prior_path, allocated=75000.0, one_r_pct=1.5,
                 prior_ledger=prior_ledger, now_utc="2026-07-28T21:00:00Z")
    check("Tiger alone -> FULL, exit 0", r["status"] == "FULL" and r["exit_code"] == 0, r)
    check("one equity row", r["equity_rows"] == 1, r["equity_rows"])
    check("MCP text envelope unwrapped", j["open_positions"][0]["ticker"] == "AMPL")
    check("entry_date carried from prior, not stamped today",
          j["open_positions"][0]["entry_date"] == "2026-07-10")
    check("stop_reference carried from prior",
          j["open_positions"][0]["stop_reference"] == 8.9)
    check("aqe_snapshot carried but never invented",
          j["open_positions"][0].get("aqe_snapshot") == {"gics_sector": "Technology"})
    check("schema valid", validate(j) == [], validate(j))

    # dynCap arithmetic: 75000 + (-3142.93 + 0) + (-32.77)
    unreal = sum(p["unrealised_usd"] for p in j["open_positions"])
    check("dyncap = allocated + realised + unrealised",
          abs(j["dyncap"]["value"] - (75000.0 - 3142.93 + round(unreal, 2))) < 0.02,
          (j["dyncap"]["value"], unreal))
    check("1R is 1.5% of dyncap",
          abs(j["dyncap"]["one_r"] - round(j["dyncap"]["value"] * 0.015, 2)) < 0.01)

    # ---- 1b. D-104 regression: an IBKR payload can still land in the pull dir (nothing stops
    # the harness saving it), but it must never move the needle — not on equity_rows, not on
    # status, not silently.
    _write(os.path.join(pull, IBKR_FILES["positions"]), [
        {"contract": {"symbol": "HBAN", "secType": "STK"}, "position": 300,
         "avgCost": 18.40, "marketPrice": 18.95, "currency": "USD"},
    ])
    j1b, r1b = build(D, pull, prior_journal=prior_path, allocated=75000.0, one_r_pct=1.5,
                      prior_ledger=prior_ledger, now_utc="2026-07-28T21:00:00Z")
    check("D-104: an IBKR payload present changes nothing — still one equity row",
          r1b["equity_rows"] == 1 and r1b["status"] == "FULL", r1b)
    check("D-104: IBKR presence is flagged, not silently ignored",
          any(f["type"] == "ibkr_ignored" for f in j1b["review_flags"]), j1b["review_flags"])
    os.remove(os.path.join(pull, IBKR_FILES["positions"]))  # back to the Tiger-only fixture

    # ---- 1c. D-105: no tiger_open_orders.json in this pull -> flagged absent, stop_live_broker
    # untouched (not wiped to null just because today's pull didn't check).
    check("D-105: open_orders pull absent is flagged",
          any(f["type"] == "open_orders_pull_absent" for f in j1b["review_flags"]),
          j1b["review_flags"])

    # ---- 1d. D-105: live stop applied when present; no_live_stop flagged when it is not; and
    # entry_date derived from a matching BUY fill instead of stamped with today's run date.
    _write(os.path.join(pull, TIGER_FILES["stock_positions"]), {
        "content": [{"type": "text", "text": json.dumps([
            {"symbol": "AMPL", "quantity": 571, "average_cost": 9.7494,
             "latest_price": 9.69, "unrealized_pnl": -32.77, "currency": "USD"},
            {"symbol": "NEWCO", "quantity": 100, "average_cost": 50.0,
             "latest_price": 51.0, "unrealized_pnl": 100.0, "currency": "USD"},
        ])}]})
    _write(os.path.join(pull, TIGER_FILES["filled_orders"]), [
        {"symbol": "NEWCO", "action": "BUY", "filled_quantity": 100, "avg_fill_price": 50.0,
         "trade_time": "2026-07-26T14:00:00Z", "status": "FILLED"},
    ])
    _write(os.path.join(pull, TIGER_FILES["open_orders"]), [
        {"symbol": "AMPL", "action": "SELL", "order_type": "STP", "sec_type": "STK",
         "quantity": 571, "stop_price": 8.5, "id": "o1", "order_time": 1},
    ])
    j1d, r1d = build(D, pull, prior_journal=prior_path, allocated=75000.0, one_r_pct=1.5,
                      prior_ledger=prior_ledger, now_utc="2026-07-28T21:00:00Z")
    by_ticker_1d = {p["ticker"]: p for p in j1d["open_positions"]}
    check("D-105: live stop written from open_orders",
          by_ticker_1d["AMPL"]["stop_live_broker"] == 8.5, by_ticker_1d["AMPL"])
    check("D-105: stop_match recomputed against the live stop (prior stop_reference 8.9)",
          by_ticker_1d["AMPL"]["stop_match"] == "MISMATCH", by_ticker_1d["AMPL"])
    check("D-105: no working stop -> no_live_stop flagged, stop_live_broker stays null",
          by_ticker_1d["NEWCO"]["stop_live_broker"] is None
          and any(f["type"] == "no_live_stop" and f["ticker"] == "NEWCO"
                  for f in j1d["review_flags"]), by_ticker_1d["NEWCO"])
    check("D-105: entry_date derived from the matching BUY fill, not today's run date",
          by_ticker_1d["NEWCO"]["entry_date"] == "2026-07-26", by_ticker_1d["NEWCO"])
    check("D-105: a real derived entry_date raises no entry_date_unknown flag",
          not any(f["type"] == "entry_date_unknown" and f["ticker"] == "NEWCO"
                  for f in j1d["review_flags"]))
    os.remove(os.path.join(pull, TIGER_FILES["open_orders"]))
    os.remove(os.path.join(pull, TIGER_FILES["filled_orders"]))
    _write(os.path.join(pull, TIGER_FILES["stock_positions"]), {
        "content": [{"type": "text", "text": json.dumps([
            {"symbol": "AMPL", "quantity": 571, "average_cost": 9.7494,
             "latest_price": 9.69, "unrealized_pnl": -32.77, "currency": "USD"},
        ])}]})  # restore the plain Tiger-only fixture for the tests below

    # ---- 1e. D-105: genuinely no prior AND no matching fill anywhere in this pull -> falls
    # back to the run date, but that fallback is flagged, not silently indistinguishable from
    # a real entry date.
    _write(os.path.join(pull, TIGER_FILES["stock_positions"]), {
        "content": [{"type": "text", "text": json.dumps([
            {"symbol": "AMPL", "quantity": 571, "average_cost": 9.7494,
             "latest_price": 9.69, "unrealized_pnl": -32.77, "currency": "USD"},
            {"symbol": "MYSTERY", "quantity": 10, "average_cost": 5.0,
             "latest_price": 5.5, "unrealized_pnl": 5.0, "currency": "USD"},
        ])}]})
    j1e, r1e = build(D, pull, prior_journal=prior_path, allocated=75000.0, one_r_pct=1.5,
                      prior_ledger=prior_ledger, now_utc="2026-07-28T21:00:00Z")
    my = next(p for p in j1e["open_positions"] if p["ticker"] == "MYSTERY")
    check("D-105: no evidence anywhere -> falls back to run date",
          my["entry_date"] == D, my)
    check("D-105: that fallback is flagged entry_date_unknown",
          any(f["type"] == "entry_date_unknown" and f["ticker"] == "MYSTERY"
              for f in j1e["review_flags"]), j1e["review_flags"])
    _write(os.path.join(pull, TIGER_FILES["stock_positions"]), {
        "content": [{"type": "text", "text": json.dumps([
            {"symbol": "AMPL", "quantity": 571, "average_cost": 9.7494,
             "latest_price": 9.69, "unrealized_pnl": -32.77, "currency": "USD"},
        ])}]})  # restore the plain Tiger-only fixture for the tests below

    # ---- 2. determinism
    j2, r2 = build(D, pull, prior_journal=prior_path, allocated=75000.0, one_r_pct=1.5,
                   prior_ledger=prior_ledger, now_utc="2026-07-28T21:00:00Z")
    check("deterministic", json.dumps(j, sort_keys=True) == json.dumps(j2, sort_keys=True))

    # ---- 3. Tiger absent -> PROVISIONAL, exit 2 (D-104: there is no second broker to fall
    # back to anymore — Tiger missing means no book of record, full stop)
    os.remove(os.path.join(pull, TIGER_FILES["stock_positions"]))
    j3prov, r3prov = build(D, pull, prior_journal=prior_path, allocated=75000.0, one_r_pct=1.5,
                            prior_ledger=prior_ledger, now_utc="2026-07-28T21:00:00Z")
    check("Tiger absent -> PROVISIONAL exit 2",
          r3prov["status"] == "PROVISIONAL" and r3prov["exit_code"] == 2, r3prov)
    check("Tiger absent produces zero equity rows", r3prov["equity_rows"] == 0)
    _write(os.path.join(pull, TIGER_FILES["stock_positions"]), {
        "content": [{"type": "text", "text": json.dumps([
            {"symbol": "AMPL", "quantity": 571, "average_cost": 9.7494,
             "latest_price": 9.69, "unrealized_pnl": -32.77, "currency": "USD"},
        ])}]})  # restore for the tests below, which reuse `pull`

    # ---- 4. option payload ABSENT -> prior legs carried, not emptied (Tiger never wrote
    # tiger_option_positions.json in this fixture, so this is naturally exercised by every
    # build above too — j3 below is just the current state of `pull`)
    j3, r3 = build(D, pull, prior_journal=prior_path, allocated=75000.0, one_r_pct=1.5,
                   prior_ledger=prior_ledger, now_utc="2026-07-28T21:00:00Z")
    check("absent option pull carries prior legs",
          len(j3["option_positions"]) == 1
          and j3["option_positions"][0]["underlying"] == "XLK",
          j3["option_positions"])
    check("absent option pull is flagged high",
          any(f["type"] == "option_pull_absent" and f["severity"] == "high"
              for f in j3["review_flags"]))
    # The fixture's prior hedge is deliberately the shape the 21 Jul journal actually carried:
    # a record that does not satisfy the contract. It must be quarantined, not propagated, and
    # not discarded — and the journal it lands in must still validate.
    check("malformed prior hedge quarantined verbatim, not propagated",
          j3["hedge"] is None
          and j3.get("hedge_quarantined") == {"structure_id": "prior-xlk", "legs": []},
          (j3["hedge"], j3.get("hedge_quarantined")))
    check("malformed prior hedge flagged high",
          any(f["type"] == "prior_hedge_malformed" and f["severity"] == "high"
              for f in j3["review_flags"]))
    check("a journal carrying a malformed prior hedge still validates",
          validate(j3) == [], validate(j3))

    # ---- 4a. a WELL-FORMED prior hedge rides through untouched — derive-hedge adjudicates it,
    # this tool never edits it and never invents one.
    good_prior = os.path.join(tmp, "prior_good.json")
    good_hedge = {"structure_id": "XLK_put_spread_aug21", "kind": "put_debit_spread",
                  "underlying": "XLK", "expiry": "2026-08-21", "upper": 175.0,
                  "lower": 165.0, "contracts": 2, "legs": ["XLK260821P00175000",
                                                           "XLK260821P00165000"]}
    _write(good_prior, {"date": "2026-07-27", "dyncap": {"value": 65000.0, "one_r": 975.0},
                        "open_positions": [], "closed_trades": [], "metrics": {},
                        "hedge": good_hedge})
    j3b, _ = build(D, pull, prior_journal=good_prior, allocated=75000.0, one_r_pct=1.5,
                   prior_ledger=prior_ledger, now_utc="2026-07-28T21:00:00Z")
    check("well-formed prior hedge carried untouched",
          j3b["hedge"] == good_hedge and "hedge_quarantined" not in j3b, j3b["hedge"])
    check("well-formed prior hedge raises no malformed flag",
          not any(f["type"] == "prior_hedge_malformed" for f in j3b["review_flags"]))
    check("no hedge invented when the prior had none",
          build(D, pull, prior_journal=None, allocated=75000.0, one_r_pct=1.5,
                prior_ledger=prior_ledger,
                now_utc="2026-07-28T21:00:00Z")[0]["hedge"] is None)

    # ---- 5. option payload PRESENT AND EMPTY -> a real answer, legs empty
    _write(os.path.join(pull, TIGER_FILES["option_positions"]), [])
    j4, _ = build(D, pull, prior_journal=prior_path, allocated=75000.0, one_r_pct=1.5,
                  prior_ledger=prior_ledger, now_utc="2026-07-28T21:00:00Z")
    check("present-and-empty option pull is NOT the same as absent",
          j4["option_positions"] == [] and j4["broker_sync"]["option_pull_ran"] is True)

    # ---- 6. neither broker -> PROVISIONAL, exit 2
    shutil.rmtree(pull)
    os.makedirs(pull)
    j5, r5 = build(D, pull, prior_journal=prior_path, allocated=75000.0, one_r_pct=1.5,
                   prior_ledger=prior_ledger, now_utc="2026-07-28T21:00:00Z")
    check("no brokers -> PROVISIONAL exit 2",
          r5["status"] == "PROVISIONAL" and r5["exit_code"] == 2, r5)

    # ---- 7. an unmappable row is a HIGH flag with the observed keys, never a guess
    _write(os.path.join(pull, TIGER_FILES["stock_positions"]),
           [{"instrument_id": 9182, "held": 100, "book_cost": 1234.0}])
    j6, r6 = build(D, pull, prior_journal=prior_path, allocated=75000.0, one_r_pct=1.5,
                   prior_ledger=prior_ledger, now_utc="2026-07-28T21:00:00Z")
    check("unmappable row forces exit 2", r6["exit_code"] == 2 and r6["unmappable"] == 1, r6)
    flag = next((f for f in j6["review_flags"] if f["type"] == "unmappable_row"), None)
    check("unmappable flag names the observed keys",
          flag is not None and "instrument_id" in flag["detail"], flag)
    check("unmappable row is not silently written as a position", r6["equity_rows"] == 0)

    # ---- 8. non-USD row skipped, never converted
    _write(os.path.join(pull, TIGER_FILES["stock_positions"]),
           [{"symbol": "SHOP", "quantity": 50, "average_cost": 90.0, "currency": "CAD"}])
    j7, r7 = build(D, pull, prior_journal=prior_path, allocated=75000.0, one_r_pct=1.5,
                   prior_ledger=prior_ledger, now_utc="2026-07-28T21:00:00Z")
    check("non-USD row skipped and flagged",
          r7["equity_rows"] == 0
          and any(f["type"] == "non_usd_row" for f in j7["review_flags"]))

    # ---- 9. closes are booked only against our own prior book
    _write(os.path.join(pull, TIGER_FILES["stock_positions"]), [])
    _write(os.path.join(pull, TIGER_FILES["filled_orders"]), [
        {"symbol": "AMPL", "side": "SELL", "filled_quantity": 571, "filled_price": 10.20,
         "status": "FILLED", "trade_time": "2026-07-28T15:31:00Z"},
        {"symbol": "NVDA", "side": "SELL", "filled_quantity": 10, "filled_price": 900.0,
         "status": "FILLED", "trade_time": "2026-07-28T15:31:00Z"},
        {"symbol": "AMPL", "side": "BUY", "filled_quantity": 100, "filled_price": 9.50,
         "status": "CANCELLED"},
    ])
    j8, r8 = build(D, pull, prior_journal=prior_path, allocated=75000.0, one_r_pct=1.5,
                   prior_ledger=prior_ledger, now_utc="2026-07-28T21:00:00Z")
    check("held ticker sold -> one close booked", r8["closes_booked"] == 1, r8)
    closed = j8["closed_trades"][0]
    check("realised computed from prior entry",
          closed["ticker"] == "AMPL"
          and abs(closed["realised_usd"] - round((10.20 - 9.7494) * 571, 2)) < 0.01, closed)
    check("a ticker we never held is NOT booked as our close",
          all(c["ticker"] != "NVDA" for c in j8["closed_trades"]))
    check("that fill is still surfaced, not swallowed",
          any(f["type"] == "unmatched_fill" and f["ticker"] == "NVDA"
              for f in j8["review_flags"]))
    check("a cancelled order is not a fill", r8["closes_booked"] == 1)
    check("today's realised rolls into dyncap",
          abs(j8["dyncap"]["value"]
              - round(75000.0 - 3142.93 + closed["realised_usd"], 2)) < 0.02,
          j8["dyncap"]["value"])

    # ---- 10. a corrupt payload is a finding, not a crash
    with open(os.path.join(pull, TIGER_FILES["stock_positions"]), "w") as fh:
        fh.write("{not json")
    j9, r9 = build(D, pull, prior_journal=prior_path, allocated=75000.0, one_r_pct=1.5,
                   prior_ledger=prior_ledger, now_utc="2026-07-28T21:00:00Z")
    check("corrupt payload is a high flag, not an exception",
          any(f["type"] == "payload_unreadable" for f in j9["review_flags"]))

    # ---- 11. aqe_snapshot is never fabricated for a name that had none
    check("no aqe_snapshot invented anywhere",
          all("aqe_snapshot" not in p or p["aqe_snapshot"]
              for p in j["open_positions"]))

    # ---- 11a. D-104: IBKR is retired from the Aegis book (PM ruling, 2026-08-19). These are
    # the same verbatim rows from a live get_account_positions pull (28 Jul 2026) that used to
    # be pinned here as a successful IBKR-parsing test — now pinned as a successful IGNORE test:
    # the payload is present, but none of it may reach open_positions/option_positions, and its
    # presence is flagged so a silent no-op never looks the same as "the pull didn't happen".
    ibkr_real = os.path.join(tmp, "ibkr_real")
    _write(os.path.join(ibkr_real, IBKR_FILES["positions"]), [
        {"contract_id": 891706384, "contract_description": "AEHR Jul31'26 80 PUT @AMEX",
         "position": 1, "market_price": 6.8492799, "market_value": 684.92799,
         "currency": "USD", "average_price": 11.300363, "unrealized_pnl": -445.10831,
         "asset_class": "OPT"},
        {"contract_id": 839707348, "contract_description": "DUOL Aug21'26 220 CALL @AMEX",
         "position": -1, "market_price": 0.195935, "market_value": -19.5935,
         "currency": "USD", "average_price": 1.23723, "unrealized_pnl": 104.1295,
         "asset_class": "OPT"},
        {"contract_id": 790904952, "contract_description": "CHYM", "position": 479,
         "market_price": 22, "market_value": 10538, "currency": "USD",
         "average_price": 21.15262213, "unrealized_pnl": 405.894, "asset_class": "STK"},
        {"contract_id": 258298726, "contract_description": "ICHR", "position": -100,
         "market_price": 72.09999845, "market_value": -7209.999845, "currency": "USD",
         "average_price": 84.686397, "unrealized_pnl": 1258.639855, "asset_class": "STK"},
        {"contract_id": 4116507, "contract_description": "992 @SEHK", "position": 16000,
         "market_price": 23.52, "market_value": 376320.0, "currency": "HKD",
         "average_price": 10.90987121, "unrealized_pnl": 201762.07, "asset_class": "STK"},
    ])
    jr, rr = build(D, ibkr_real, prior_journal=None, allocated=75000.0, one_r_pct=1.5,
                   prior_ledger=None, now_utc="2026-07-28T21:00:00Z")
    check("D-104: IBKR payload present but zero rows read into the book",
          jr["open_positions"] == [] and jr["option_positions"] == [], jr)
    check("D-104: IBKR presence is flagged, not silently swallowed",
          any(f["type"] == "ibkr_ignored" for f in jr["review_flags"]),
          jr["review_flags"])
    check("D-104: IBKR never appears in connectors/sources_present",
          "IBKR" not in (jr.get("broker_sync", {}).get("connectors") or []))
    # the description parser itself is retained (still a correct, tested primitive — it is just
    # no longer WIRED to any live ingestion path) —
    check("a description that is not a contract is never half-parsed",
          _parse_broker_description("700 @SEHK") is None
          and _parse_broker_description("CHYM") is None
          and _parse_broker_description("AEHR Zzz31'26 80 PUT") is None)

    # ---- 12. verify: the gate the batch runs AFTER the four mutating tools have touched
    # the file. It must catch a wrong name, a missing file, a corrupt file and a broken
    # contract — each of those is a reason nothing downstream may run.
    class _A:
        def __init__(self, date, journal):
            self.date, self.journal = date, journal

    good = os.path.join(tmp, "journal", f"aegis_journal_{D}.json")
    _write(good, j)
    check("verify passes a good journal", cmd_verify(_A(D, good)) == 0)
    check("verify rejects a mis-named file",
          cmd_verify(_A(D, os.path.join(tmp, "journal", "journal.json"))) == 2)
    check("verify rejects a missing file",
          cmd_verify(_A(D, os.path.join(tmp, "journal", f"aegis_journal_{D}.json.absent"))) == 2)
    trunc = os.path.join(tmp, "trunc", f"aegis_journal_{D}.json")
    os.makedirs(os.path.dirname(trunc), exist_ok=True)
    with open(trunc, "w") as fh:
        fh.write(json.dumps(j)[:120])
    check("verify rejects a truncated file", cmd_verify(_A(D, trunc)) == 2)
    broken = copy.deepcopy(j)
    broken.pop("dyncap")
    bad = os.path.join(tmp, "broken", f"aegis_journal_{D}.json")
    _write(bad, broken)
    check("verify rejects a journal that fails the contract", cmd_verify(_A(D, bad)) == 2)
    stale = copy.deepcopy(j)
    stale["date"] = "2026-07-27"
    sp = os.path.join(tmp, "stale", f"aegis_journal_{D}.json")
    _write(sp, stale)
    check("verify rejects yesterday's content under today's name", cmd_verify(_A(D, sp)) == 2)

    shutil.rmtree(tmp, ignore_errors=True)
    print(f"\n{'SELFTEST PASS' if not failures else 'SELFTEST FAIL: ' + ', '.join(failures)}")
    return 0 if not failures else 1


def main():
    ap = argparse.ArgumentParser(description="Journal build — Operation 1, deterministic (D-93)")
    sub = ap.add_subparsers(dest="cmd", required=True)

    b = sub.add_parser("build", help="reconcile saved broker payloads into the journal")
    b.add_argument("--date", required=True)
    b.add_argument("--pull", help="directory of saved broker payloads")
    b.add_argument("--prior", help="prior journal (default: most recent before --date)")
    b.add_argument("--out", help="output journal path")
    b.add_argument("--allocated", type=float, help="override allocated capital")
    b.add_argument("--one-r-pct", dest="one_r_pct", type=float,
                   help="override RB:capital.one_r_pct_of_dyncap")
    b.add_argument("--write-anyway", action="store_true",
                   help="write even on exit 2 (recovery use only)")
    b.add_argument("--json", action="store_true")
    b.set_defaults(func=cmd_build)

    # The batch needs the same "most recent journal before --date" answer that build uses for
    # its carry, to hand to held_book_refresh carry-forward --prior. One implementation.
    p = sub.add_parser("prior", help="print the most recent journal path before --date")
    p.add_argument("--date", required=True)
    p.set_defaults(func=lambda a: (print(_latest_prior(a.date) or ""), 0)[1])

    v = sub.add_parser("verify", help="read the journal back off disk and re-check the contract")
    v.add_argument("--date", required=True)
    v.add_argument("--journal", help="path (default: data/journal/aegis_journal_<date>.json)")
    v.set_defaults(func=cmd_verify)

    s = sub.add_parser("selftest")
    s.set_defaults(func=lambda a: selftest())

    args = ap.parse_args()
    sys.exit(args.func(args))


if __name__ == "__main__":
    main()
