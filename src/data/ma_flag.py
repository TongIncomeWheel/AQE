"""M&A flag (PM 2026-11-04): a name with a PENDING merger / acquisition / buyout must be flagged wherever it is picked.

EVIDENCE: ROKU, the only 'agreed outright' ADVANCE on 4 Nov, has a definitive agreement for Fox Corp to acquire it (announced
15 Jun 2026, ~$22B). A deal-pinned stock trades on the deal spread, not on momentum, so flow / energy / structure mean little
and the committee never saw it.

DATA SOURCE (verified 4 Nov on our plan): FMP stock news (`news/stock`) works. FMP's `latest-mergers-acquisitions` lists SEC S-4
filings only (stock-for-stock registrations), so it MISSES cash deals like Fox/Roku; it is not used. The flag is a keyword scan of
the last 120 days of each ticker's stock-news headlines and summaries, and the matched headline + date + url are stored so every flag
is auditable by a human in ten seconds.

CONTRACT
  ma_status  NONE | PENDING_TARGET | PENDING_ACQUIRER | PENDING_UNCLEAR | UNKNOWN
      PENDING_TARGET   this company is being bought (deal-pinned: momentum signals are not the story)
      PENDING_ACQUIRER this company is the buyer
      PENDING_UNCLEAR  a pending deal is in its news but the role could not be read from the text
      UNKNOWN          the scan FAILED for this ticker (HTTP error, quota): NEVER shown as NONE (a failed fetch is loud)
  ma_note    one plain line: the matched headline and its date
  ma_evidence {headline, date, url, terms[]}
Nothing here decides or excludes anything; the committee rule (flag / exclude / require an explicit M&A line) is the PM's.
"""
from __future__ import annotations

import json
import re
from datetime import date, datetime, timedelta
from pathlib import Path

from src.data.paths import DATA_DIR

CACHE_PATH = DATA_DIR / "ma_flags.json"
WINDOW_DAYS = 120
NEWS_LIMIT = 100

# Terms that put a pending DEAL in a headline or summary. Investor-filing noise ("Acquires 29,656 Shares of ...") does not match:
# none of these is the bare word "acquires".
_PENDING = [
    r"\bdefinitive (?:merger |acquisition |purchase )?agreement\b", r"\bmerger agreement\b", r"\bagreement and plan of merger\b",
    r"\bpending (?:merger|acquisition|transaction|takeover|buyout|deal|combination)\b",
    r"\b(?:will|agreed to|agrees to|has agreed to|announces? (?:an? )?(?:agreement|plan)s? to|signs? (?:an? )?(?:agreement|deal) to) (?:acquire|buy|be acquired|be bought|be purchased|be taken private)\b",
    r"\bto acquire\b(?=\s+[A-Z])",   # a headline "X to Acquire Y"; never the lowercase advice "to buy"
    r"\b(?:to|will|being) be (?:acquired|bought|purchased|taken private)\b", r"\b(?:to be|will be|being|is being) acquired by\b",
    r"\btender offer\b", r"\btake-?private\b", r"\bgoing private\b", r"\bbuyout\b",
    r"\bproposed (?:merger|acquisition|combination)\b", r"\bmerger with\b", r"\bper share in cash\b", r"\ball-cash (?:deal|transaction)\b",
    r"\b(?:shareholders|stockholders) approve[sd]? (?:the )?(?:merger|acquisition|deal)\b", r"\bregulatory (?:approval|review)s? (?:of|for) the (?:merger|acquisition|deal)\b",
]
_DONE = re.compile(r"\b(?:completes?|completed|closes?|closed|finali[sz]es?|consummates?) (?:its |the |their )?(?:acquisition|merger|purchase|take-?private|transaction)\b", re.I)
_PENDING_RE = [re.compile(p, re.I) for p in _PENDING]
# Not a deal: fund-holding filings ("13,785 Shares in X Acquired by Y Planning LLC", "$TFC Shares Acquired by ...") and advice pieces ("Stocks to Buy").
_NOISE = re.compile(r"(?:\bshares?\b[^.]{0,80}\b(?:acquired|acquires|bought|purchased|sold)\b|\$[A-Z]{1,5}\b[^.]{0,60}\bacquired by\b|\b(?:stake|position|holdings?)\b[^.]{0,40}\b(?:acquired|raised|boosted|trimmed)\b|\bstocks? to buy\b|\bto buy (?:now|in 20\d\d|for\b|right now)|\brating upgrade\b|\bupgraded to buy\b|\bis it (?:too late|time|finally time) to buy\b)", re.I)
# R44 excludes a name from ADVANCE, so PENDING_TARGET needs strong deal language, not a loose phrase; otherwise the flag stays PENDING_UNCLEAR.
_STRICT = re.compile(r"definitive (?:merger |acquisition |purchase )?agreement|merger agreement|agreement and plan of merger|pending (?:merger|acquisition|transaction|takeover|buyout|combination)|tender offer|take-?private|going private|per share in cash|all-cash|proposed (?:merger|acquisition)|merger with|(?:to|will|being) be acquired|(?:to be|will be|being|is being) acquired by|in light of the pending", re.I)
_SUFFIX = re.compile(r"\b(?:inc|corp|corporation|co|company|ltd|plc|holdings?|group|the|class [a-c]|lp|llc|n\.?v\.?|s\.?a\.?)\b\.?,?", re.I)


def short_name(company_name: str | None, ticker: str) -> str:
    """'Roku, Inc.' -> 'Roku' (first meaningful words); falls back to the ticker."""
    n = _SUFFIX.sub(" ", company_name or "")
    n = re.sub(r"[^A-Za-z0-9&.\- ]+", " ", n).strip()
    words = n.split()
    return " ".join(words[:2]) if words else ticker


def _name_variants(name: str) -> list[str]:
    """'LCI Industries' -> ['LCI Industries', 'LCI']: releases refer to their company by its short alias ("LCI"), not its full name."""
    out = [name] if name else []
    first = (name or "").split()[0] if name else ""
    if first and first != name and len(first) >= 3 and first.lower() not in {"the", "new", "first", "united", "american", "global", "general", "national", "international"}:
        out.append(first)
    return out


def _role(text: str, name: str) -> str | None:
    """'TARGET' / 'ACQUIRER' / 'BOTH' / None from one headline+summary, judged around this company's own short name (or its first-word alias)."""
    t = a = False
    for nm in _name_variants(name):
        n = re.escape(nm)
        target = [rf"(?:acquire[sd]?|acquisition of|buy(?:ing)?|purchase of|merger with|takeover of|take[- ]private)\s+(?:the\s+)?(?:\w+\s+){{0,2}}{n}\b",
                  rf"\b{n}\b[^.]{{0,70}}(?:to be acquired|will be acquired|agreed to be acquired|be acquired by|is being acquired|to be bought|going private|take-?private|merger with)",
                  rf"(?:acquisition|merger|deal)[^.]{{0,40}}\b{n}\b[^.]{{0,20}}(?:pending|announced)"]
        acq = [rf"\b{n}\b[^.]{{0,40}}(?:to acquire|will acquire|agrees? to (?:acquire|buy)|agreed to (?:acquire|buy)|planned acquisition of|pending acquisition of|acquisition of)"]
        t = t or any(re.search(p, text, re.I) for p in target)
        a = a or any(re.search(p, text, re.I) for p in acq)
    if t and not a:
        return "TARGET"
    if a and not t:
        return "ACQUIRER"
    return "BOTH" if (t and a) else None


def classify(ticker: str, company_name: str | None, items: list[dict], today: date | None = None) -> dict:
    """Pure: one ticker's recent news items -> the flag dict. `items` = [{publishedDate, title, text, url, site}, ...]."""
    today = today or date.today()
    name = short_name(company_name, ticker)
    hits = []
    done = []
    for it in items or []:
        title, text = str(it.get("title") or ""), str(it.get("text") or "")
        blob = f"{title}. {text}"
        d = str(it.get("publishedDate") or "")[:10]
        if _NOISE.search(blob) and not _STRICT.search(blob):
            continue                                        # a fund-holding filing or an advice piece is not deal news
        if _DONE.search(blob):
            done.append(d)                                  # a completion headline is evidence on its own, even with no pending term
            continue
        found = [m.group(0) for rx in _PENDING_RE for m in [rx.search(blob)] if m]
        if not found:
            continue
        terms = found
        sent = next((x.strip() for x in re.split(r"(?<=[.!?])\s+", blob) if any(rx.search(x) for rx in _PENDING_RE)), title)
        hits.append({"date": d, "headline": title, "sentence": sent[:200], "url": it.get("url"), "terms": terms[:3], "role": _role(blob, name), "blob": blob})
    base = {"ma_status": "NONE", "ma_note": f"no pending deal found in {WINDOW_DAYS} days of news", "ma_evidence": None}      # never null: a null column reads as a missing field in the voice packets
    if not hits:
        return base
    hits.sort(key=lambda h: h["date"], reverse=True)
    if done and max(done) > hits[0]["date"]:
        return base                                        # the newest deal item says it closed
    roles = [h["role"] for h in hits if h["role"] in ("TARGET", "ACQUIRER")]
    # the company's own releases ("In light of the pending transaction ...") are the strongest target signal
    own_pending = any(re.search(r"in light of the pending (?:transaction|merger|acquisition)|definitive agreement under which .{0,40} will acquire", h["blob"], re.I) for h in hits)
    if roles.count("TARGET") > roles.count("ACQUIRER") or (own_pending and "ACQUIRER" not in roles):
        status = "PENDING_TARGET"
        if not any(h["role"] == "TARGET" and _STRICT.search(h["blob"]) for h in hits) and not own_pending:
            status = "PENDING_UNCLEAR"                     # loose language never deal-pins a name
    elif roles.count("ACQUIRER") > roles.count("TARGET"):
        status = "PENDING_ACQUIRER"
    else:
        status = "PENDING_UNCLEAR"
    pick = next((h for h in hits if (status == "PENDING_TARGET" and h["role"] == "TARGET") or (status == "PENDING_ACQUIRER" and h["role"] == "ACQUIRER")), hits[0])
    return {"ma_status": status, "ma_note": f"{pick['sentence']} ({pick['date']})"[:240],
            "ma_evidence": {"headline": pick["headline"], "date": pick["date"], "url": pick["url"], "terms": pick["terms"],
                            "n_deal_items": len(hits)}}


def fetch_items(client, ticker: str, today: date) -> list[dict]:
    """One FMP call. Raises on HTTP / quota failure so the caller records UNKNOWN (never a silent NONE)."""
    from src.data.fmp_client import FMP_BASE_STABLE
    frm = (today - timedelta(days=WINDOW_DAYS)).isoformat()
    payload = client._get_json(f"{FMP_BASE_STABLE}/news/stock",
                               params={"symbols": ticker, "from": frm, "to": today.isoformat(), "limit": NEWS_LIMIT,
                                       "apikey": client.config.api_key})
    if not isinstance(payload, list):
        raise ValueError(f"news/stock returned {type(payload).__name__}")
    return payload


def company_name(client, ticker: str) -> str | None:
    from src.data.fmp_client import FMP_BASE_STABLE
    try:
        p = client._get_json(f"{FMP_BASE_STABLE}/profile", params={"symbol": ticker, "apikey": client.config.api_key})
        return (p[0].get("companyName") if isinstance(p, list) and p else None)
    except Exception:  # noqa: BLE001
        return None


def load_cache(path: Path | None = None) -> dict:
    try:
        d = json.loads(Path(path or CACHE_PATH).read_text(encoding="utf-8"))
        return d if isinstance(d, dict) else {}
    except Exception:  # noqa: BLE001
        return {}


def refresh(tickers, client, today: date | None = None, cache_path: Path | None = None, names: dict | None = None) -> dict:
    """Scan every ticker once per day (cache per ticker per day). Returns the artifact:
    {asof, window_days, scan_status: ok|partial|failed, n_scanned, n_failed, n_flagged, failed[], tickers{tk: flag}}.
    A ticker whose fetch failed carries ma_status UNKNOWN; if more than 10% fail the scan is `partial` (loud in data_quality)."""
    today = today or date.today()
    cache_path = cache_path or CACHE_PATH                # resolved at CALL time so a test (or a relocated data dir) can redirect it
    cache = load_cache(cache_path)
    done = cache.get("tickers") or {} if cache.get("asof") == today.isoformat() else {}
    out, failed = {}, []
    for tk in sorted({t for t in tickers if t}):
        prev = done.get(tk)
        if prev and prev.get("ma_status") != "UNKNOWN":
            out[tk] = prev
            continue
        try:
            items = fetch_items(client, tk, today)
            flag = classify(tk, (names or {}).get(tk), items, today)
            if flag["ma_status"] != "NONE" and not (names or {}).get(tk):
                flag = classify(tk, company_name(client, tk), items, today)      # name only for the few flagged tickers
            out[tk] = flag
        except Exception as e:  # noqa: BLE001
            failed.append(tk)
            out[tk] = {"ma_status": "UNKNOWN", "ma_note": f"M&A scan failed: {e.__class__.__name__}", "ma_evidence": None}
    n = len(out)
    status = "ok" if not failed else ("failed" if len(failed) == n else ("partial" if len(failed) / max(n, 1) > 0.10 else "ok"))
    art = {"asof": today.isoformat(), "window_days": WINDOW_DAYS, "scan_status": status, "n_scanned": n, "n_failed": len(failed),
           "n_flagged": sum(1 for v in out.values() if str(v.get("ma_status", "")).startswith("PENDING")),
           "failed": failed[:50], "tickers": out}
    try:
        Path(cache_path).parent.mkdir(parents=True, exist_ok=True)
        Path(cache_path).write_text(json.dumps(art, indent=1), encoding="utf-8")
    except OSError:
        pass
    return art
