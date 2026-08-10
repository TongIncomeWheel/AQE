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

# US prints worth a committee's attention, and what each one actually tests.
# Keyed on a lowercase fragment of the event name so FMP's exact wording can
# drift without silently dropping the event.
WHY_IT_MATTERS = {
    "consumer price index": (
        "Whether the easing case survives contact with the inflation data. A "
        "cooler print supports equities; the cleaner signal is the long end of "
        "the curve falling alongside the front end."),
    "producer price index": (
        "Whether input costs are still feeding through supply chains. A firm "
        "print after a soft CPI limits the rates relief and keeps pressure on "
        "the long end."),
    "core pce": (
        "The Fed's preferred inflation measure. It matters more than CPI for "
        "what the Fed actually does, and less for what the market does on the "
        "day."),
    "nonfarm payroll": (
        "The single biggest input to rate expectations. Watch the revisions "
        "and the participation rate, not just the headline — a falling "
        "unemployment rate can come from people leaving the labour force."),
    "unemployment rate": (
        "Read it beside the participation rate. It can fall for a bad reason."),
    "fomc": (
        "The rate decision and the language around it. The statement usually "
        "moves the front end; the press conference moves the long end."),
    "fed interest rate": (
        "The rate decision itself. What matters for this layer is whether it "
        "changes the trend-following models' rates positioning."),
    "retail sales": (
        "Whether weaker employment has reached household spending yet. Weak "
        "spending with cooler inflation supports easing; weak spending without "
        "it is the harder combination."),
    "gdp": ("The growth backdrop the whole cross-asset read sits on."),
    "ism manufacturing": (
        "The cyclical pulse. Read it against copper — if they disagree, one of "
        "them is wrong about growth."),
    "ism services": ("The larger half of the economy, and the stickier "
                     "inflation half."),
    "initial jobless": (
        "The highest-frequency labour signal there is. One week is noise; a "
        "trend change here leads the monthly payroll number."),
    "michigan": ("Consumer expectations, including the inflation expectations "
                 "the Fed watches."),
    "durable goods": ("Business investment, and a read on the capex cycle."),
}

# Ranked by how much they move a macro regime, so the list can be trimmed
# without dropping the one that mattered.
PRIORITY = ["fomc", "nonfarm payroll", "consumer price index",
            "core pce", "producer price index", "retail sales",
            "fed interest rate", "unemployment rate", "ism manufacturing",
            "gdp", "ism services", "initial jobless", "michigan",
            "durable goods"]


def _why(event_name: str) -> tuple[str | None, int]:
    """(why it matters, priority). Unknown events sort last and say nothing."""
    low = (event_name or "").lower()
    for i, key in enumerate(PRIORITY):
        if key in low:
            return WHY_IT_MATTERS.get(key), i
    for key, why in WHY_IT_MATTERS.items():
        if key in low:
            return why, len(PRIORITY)
    return None, len(PRIORITY) + 1


# ── macro prints ─────────────────────────────────────────────────────────

def parse_economic_rows(rows, today: date, days: int = LOOKAHEAD_DAYS) -> list[dict]:
    """FMP economic-calendar rows -> the events worth putting in front of a PM.

    Pure. Keeps US high-impact prints inside the window that we have something
    to say about, because an event with no `why` is a date and nothing more.
    """
    out = []
    horizon = today + timedelta(days=days)
    for r in (rows or []):
        if str(r.get("country", "")).upper() not in ("US", "USA", "UNITED STATES"):
            continue
        raw = str(r.get("date") or "")[:10]
        try:
            d = date.fromisoformat(raw)
        except ValueError:
            continue
        if not (today <= d <= horizon):
            continue
        name = r.get("event") or ""
        why, prio = _why(name)
        if why is None:
            continue
        out.append({
            "date": d.isoformat(),
            "day": d.strftime("%A"),
            "time_et": (str(r.get("date"))[11:16] or None),
            "event": name,
            "kind": "macro",
            "what_it_tests": why,
            "previous": r.get("previous"),
            "consensus": r.get("estimate"),
            "_priority": prio,
        })
    out.sort(key=lambda e: (e["date"], e["_priority"]))
    for e in out:
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
            f"{FMP_BASE_STABLE}/economic-calendar",
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
