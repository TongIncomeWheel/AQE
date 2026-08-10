"""What is coming, and why each one matters.

Crown's letter opens with a handful of dated events and one sentence each on
what they *test* — not a data dump of every release, and never a forecast. Two
of his five last week were earnings, three were macro prints, and the sentence
attached to each was the reason it was on the list at all.

That is what this builds. The value is the **why**, because a date on its own
tells a reader nothing they could not get from a calendar app.

Two sources, and the split matters:

  * **Macro prints** come from FMP's economic calendar, filtered to US
    high-impact. If that endpoint is gated on our plan the block degrades and
    says so; it never invents a schedule.
  * **Earnings** come from the calendar AQE already pulls every day, filtered
    to names that can actually move this book: what the PM holds first, then
    what is on the daily list, then the largest names left.

Nothing here predicts an outcome. A calendar entry is a **scheduled moment when
the regime read above can change**, which is the only reason the macro layer
cares about it at all.
"""

from __future__ import annotations

from datetime import date, timedelta

LOOKAHEAD_DAYS = 10
MAX_MACRO = 8
MAX_EARNINGS = 6

# US prints worth a committee's attention: what each one tests, and the name to
# print it under.
#
# Three things learned from the live feed on 2026-08-10, each of which silently
# broke the first version:
#   * FMP names CPI as "CPI YoY (Jul)", "Core CPI MoM", "Inflation Rate YoY" —
#     never "Consumer Price Index". Matching the formal name found nothing.
#   * One release arrives as MANY rows. That Wednesday's CPI came back as
#     twelve. A calendar that lists twelve CPIs is worse than no calendar.
#   * Times are UTC. 12:30 there is the 8:30 ET everyone actually quotes.
#
# So each entry maps a set of name fragments to ONE canonical release, and the
# rows are collapsed to one per release per day.
RELEASES = [
    ("fomc",              ("FOMC decision", 0),
     ("fomc", "fed interest rate", "fed press conf")),
    ("payrolls",          ("Non-farm payrolls", 1),
     ("non farm payroll", "nonfarm payroll", "payrolls")),
    ("cpi",               ("Consumer Price Index (CPI)", 2),
     ("cpi", "inflation rate", "consumer price")),
    ("pce",               ("Core PCE", 3), ("pce",)),
    ("ppi",               ("Producer Price Index (PPI)", 4),
     ("ppi", "producer price")),
    ("retail",            ("Retail sales", 5), ("retail sales",)),
    ("unemployment",      ("Unemployment rate", 6), ("unemployment rate",)),
    ("ism_mfg",           ("ISM Manufacturing", 7),
     ("ism manufacturing", "manufacturing pmi")),
    ("gdp",               ("GDP", 8), ("gdp growth", "gdp (")),
    ("ism_svc",           ("ISM Services", 9),
     ("ism services", "services pmi")),
    ("claims",            ("Initial jobless claims", 10), ("initial jobless",)),
    ("michigan",          ("Michigan sentiment", 11), ("michigan",)),
    ("durables",          ("Durable goods orders", 12), ("durable goods",)),
]

WHY_IT_MATTERS = {
    "cpi": ("Whether the easing case survives contact with the inflation data. "
            "A cooler print supports equities, and the cleaner signal is the "
            "long end of the curve falling alongside the front end."),
    "ppi": ("Whether input costs are still feeding through supply chains. A "
            "firm print after a soft CPI limits the rates relief and keeps "
            "pressure on the long end."),
    "pce": ("The Fed's preferred inflation measure. It matters more than CPI "
            "for what the Fed does, and less for what the market does on the "
            "day."),
    "payrolls": ("The single biggest input to rate expectations. Watch the "
                 "revisions and the participation rate, not just the headline "
                 "— unemployment can fall because people left the labour "
                 "force."),
    "unemployment": ("Read it beside the participation rate. It can fall for a "
                     "bad reason."),
    "fomc": ("The rate decision and the language around it. The statement "
             "usually moves the front end; the press conference moves the long "
             "end."),
    "retail": ("Whether weaker employment has reached household spending yet. "
               "Weak spending with cooler inflation supports easing; weak "
               "spending without it is the harder combination."),
    "gdp": "The growth backdrop the whole cross-asset reading sits on.",
    "ism_mfg": ("The cyclical pulse. Read it against copper — if the two "
                "disagree, one of them is wrong about growth."),
    "ism_svc": ("The larger half of the economy, and the stickier inflation "
                "half."),
    "claims": ("The highest-frequency labour signal there is. One week is "
               "noise, but a trend change here leads the monthly payroll "
               "number."),
    "michigan": ("Consumer expectations, including the inflation expectations "
                 "the Fed watches."),
    "durables": "Business investment, and a read on the capex cycle.",
}

IMPACT_RANK = {"high": 0, "medium": 1, "low": 2}


def _classify(event_name: str):
    """(release key, printed name, priority) for an FMP event, or None."""
    low = (event_name or "").lower()
    for key, (label, prio), fragments in RELEASES:
        if any(f in low for f in fragments):
            return key, label, prio
    return None


def _to_eastern(raw: str):
    """FMP timestamps are UTC. 12:30 there is the 8:30 ET everyone quotes."""
    from datetime import datetime, timezone
    from zoneinfo import ZoneInfo
    try:
        dt = datetime.strptime(str(raw)[:19], "%Y-%m-%d %H:%M:%S")
    except ValueError:
        return None, None
    et = dt.replace(tzinfo=timezone.utc).astimezone(ZoneInfo("America/New_York"))
    return et.date(), et.strftime("%H:%M")


# ── macro prints ─────────────────────────────────────────────────────────

def parse_economic_rows(rows, today: date, days: int = LOOKAHEAD_DAYS) -> list[dict]:
    """FMP economic-calendar rows -> one line per release, in Eastern time.

    Pure. The collapse is the important part: a single CPI release arrives as a
    dozen rows (CPI MoM, CPI YoY, Core CPI, Inflation Rate…), and a calendar
    that prints all twelve is worse than no calendar at all.
    """
    horizon = today + timedelta(days=days)
    best: dict = {}
    for r in (rows or []):
        if str(r.get("country", "")).upper() not in ("US", "USA", "UNITED STATES"):
            continue
        hit = _classify(r.get("event") or "")
        if hit is None:
            continue
        key, label, prio = hit
        d, hhmm = _to_eastern(r.get("date"))
        if d is None or not (today <= d <= horizon):
            continue

        impact = IMPACT_RANK.get(str(r.get("impact", "")).lower(), 3)
        slot = (d.isoformat(), key)
        prior = best.get(slot)
        # Keep the highest-impact row for this release, since that is the
        # variant carrying the consensus everyone trades.
        if prior is None or impact < prior["_impact"]:
            best[slot] = {
                "date": d.isoformat(), "day": d.strftime("%A"),
                "time_et": hhmm, "event": label, "kind": "macro",
                "what_it_tests": WHY_IT_MATTERS.get(key),
                "previous": r.get("previous"), "consensus": r.get("estimate"),
                "impact": r.get("impact"),
                "_impact": impact, "_priority": prio,
            }

    out = sorted(best.values(), key=lambda e: (e["date"], e["_priority"]))
    for e in out:
        e.pop("_impact", None)
        e.pop("_priority", None)
    return out[:MAX_MACRO]


def fetch_macro_events(client=None, today: date | None = None,
                       days: int = LOOKAHEAD_DAYS) -> tuple[list[dict], str | None]:
    """(events, reason it is empty). Never invents a schedule."""
    today = today or date.today()
    try:
        from src.data.fmp_client import FMP_BASE_STABLE, FMPClient
        c = client or FMPClient()
        payload = c._get_json(
            f"{FMP_BASE_STABLE}/economics-calendar",
            params={"from": today.isoformat(),
                    "to": (today + timedelta(days=days)).isoformat(),
                    "apikey": c.config.api_key})
    except Exception as exc:  # noqa: BLE001
        return [], f"economic calendar unavailable: {str(exc)[:120]}"
    if not isinstance(payload, list):
        return [], "economic calendar returned no rows (it may be plan-gated)"
    events = parse_economic_rows(payload, today, days)
    return events, None if events else "no US high-impact prints in the window"


# ── earnings that can move this book ─────────────────────────────────────

def select_earnings(calendar: dict, today: date, *, held: set | None = None,
                    watched: set | None = None, days: int = LOOKAHEAD_DAYS,
                    limit: int = MAX_EARNINGS) -> list[dict]:
    """The reports that matter HERE, not the hundred that report this week.

    Ordered by what can actually move the book: positions first, then names on
    the daily list, then everything else. `calendar` is {ticker: 'YYYY-MM-DD'},
    the shape `earnings.load_earnings()` already returns.
    """
    held = {t.upper() for t in (held or set())}
    watched = {t.upper() for t in (watched or set())}
    horizon = today + timedelta(days=days)

    rows = []
    for tk, iso in (calendar or {}).items():
        try:
            d = date.fromisoformat(str(iso)[:10])
        except (ValueError, TypeError):
            continue
        if not (today <= d <= horizon):
            continue
        t = tk.upper()
        if t in held:
            rank, why = 0, "You hold this. It is the report most able to move your book."
        elif t in watched:
            rank, why = 1, "On today's list, so a reaction here changes a name you may act on."
        else:
            continue          # not ours to care about
        rows.append({"date": d.isoformat(), "day": d.strftime("%A"),
                     "event": f"{t} earnings", "ticker": t, "kind": "earnings",
                     "what_it_tests": why, "_rank": rank})

    rows.sort(key=lambda e: (e["_rank"], e["date"]))
    for e in rows:
        e.pop("_rank", None)
    return rows[:limit]


# ── the block ────────────────────────────────────────────────────────────

def build(client=None, today: date | None = None, *,
          held: set | None = None, watched: set | None = None,
          days: int = LOOKAHEAD_DAYS) -> dict:
    """The calendar block: what is coming, and why each one matters."""
    today = today or date.today()
    macro, macro_reason = fetch_macro_events(client, today, days)

    earnings, earn_reason = [], None
    try:
        from src.data.earnings import load_earnings
        cal = load_earnings()
        if cal:
            earnings = select_earnings(cal, today, held=held, watched=watched,
                                       days=days)
            if not earnings:
                earn_reason = "no held or listed name reports in the window"
        else:
            earn_reason = "no earnings calendar on disk yet"
    except Exception as exc:  # noqa: BLE001
        earn_reason = f"earnings calendar unavailable: {str(exc)[:100]}"

    events = sorted(macro + earnings, key=lambda e: e["date"])
    notes = [r for r in (macro_reason, earn_reason) if r]
    return {
        "window_days": days,
        "from": today.isoformat(),
        "to": (today + timedelta(days=days)).isoformat(),
        "events": events,
        "count": len(events),
        "unavailable": notes,
        "note": ("Scheduled moments when the reading above can change. Nothing "
                 "here forecasts an outcome."),
    }
