"""Universe management — load, screen, and persist the scan ticker list.

The universe is NEVER a fixed list. It is a dynamic FMP-driven screen,
auto-refreshed daily at 06:00 SGT by `build_universe()`, written to the local
`universe.txt` AND uploaded as the canonical CSV to a dedicated Google Drive
folder (`UNIVERSE_FOLDER_ID`) so it persists across container restarts.

THE universe rule (PM ruling 2026-08-04) — one eligibility test, shared by
every downstream list (Longlist, Elder, QS). Nothing else belongs here:

    market cap >= $2B  ·  10-day average volume >= 1.5M shares
    ·  US primary listing (NASDAQ/NYSE, warrants/units excluded)

Membership is SIZE + LIQUIDITY + LISTING only. Trend filters (the former
`price > SMA20` / `price > SMA50` conditions) were REMOVED from universe
membership on 2026-08-04: they are a screening opinion, not an eligibility
test, and they silently deleted the pulled-back names the QS engine is built
to find before QS could ever score them. Each list now applies its own trend
view through its own recipe/thresholds, which they already did anyway.

On pipeline startup `restore_universe_from_drive()` overwrites the local
`universe.txt` from that folder (Drive is source of truth between refreshes).

The old `refresh_universe()` (screener-only, no volume filter) is kept for
manual / legacy use; it ballooned the list to ~1800 because it applied no
liquidity floor at all. `build_universe()` keeps the 1.5M floor.
"""

from __future__ import annotations

import os
from datetime import date
from pathlib import Path

from src.data.paths import DATA_DIR, PROJECT_ROOT

DEFAULT_UNIVERSE_FILE = DATA_DIR / "universe.txt"
# Market cap per member, harvested from the SAME screener response that builds
# the universe (see build_universe). A lookup table, never a filter: membership
# is decided by the $2B screen, and this only lets a reader sort and slice by
# size afterwards.
UNIVERSE_MCAP_FILE = DATA_DIR / "universe_mcap.json"


def _write_universe_mcap(mcap_by_ticker: dict) -> None:
    """Best-effort — a missing size table must never fail a universe build."""
    try:
        import json as _json
        UNIVERSE_MCAP_FILE.parent.mkdir(parents=True, exist_ok=True)
        UNIVERSE_MCAP_FILE.write_text(
            _json.dumps({"built": str(date.today()), "mcap": mcap_by_ticker},
                        indent=1), encoding="utf-8")
    except Exception as exc:  # noqa: BLE001
        print(f"[universe] mcap table not written ({exc})")


def load_universe_mcap() -> dict:
    """{ticker: market cap in USD}. Empty when the table has not been built —
    which readers must show as 'unknown', never as a small company."""
    try:
        import json as _json
        if UNIVERSE_MCAP_FILE.exists():
            d = _json.loads(UNIVERSE_MCAP_FILE.read_text(encoding="utf-8"))
            return d.get("mcap") or {}
    except Exception:  # noqa: BLE001
        pass
    return {}
BENCHMARK = "SPY"

# Dedicated Drive folder holding the universe CSV (a subfolder of the AQE
# folder). Override per-deploy with GDRIVE_UNIVERSE_FOLDER_ID.
UNIVERSE_FOLDER_ID = (
    os.environ.get("GDRIVE_UNIVERSE_FOLDER_ID")
    or "16wAS7Xsn6h8bHQRcWxFgq7bXPVd2jQhA"
)
# Canonical filename the app writes — single file, overwritten each upload.
UNIVERSE_DRIVE_FILENAME = "universe.csv"

UNIVERSE_MIN_MCAP = 1_000_000_000
UNIVERSE_MIN_PRICE = 5.0
UNIVERSE_MIN_VOLUME = 500_000
UNIVERSE_EXCHANGES = ["NASDAQ", "NYSE"]

EXCLUDED_SUFFIXES = ("-W", "-U", ".W", ".U")

# --- Automated universe screening (PM ruling, 27 Jun 2026) ---
# The daily pipeline scans only this filtered set. Refreshed at 06:00 SGT
# (before the 08:30 pipeline run) by the in-app scheduler.
# Identifies the RULE a universe file was built under, stamped into its header.
# A universe built by an older rule is treated as stale even if it was built
# today, so a rule change takes effect on the next run instead of waiting for
# the calendar to roll. Bump this whenever the screen changes.
#
# v2 (2026-08-04): dropped the price>SMA20 / price>SMA50 trend conditions —
# membership is an eligibility test, not a screening opinion.
#
# v3 (2026-11-10): the pass-1 volume split read FMP's batch /quote avgVolume, which does not exist (the endpoint answers one symbol and carries
# no avgVolume): every name fell into "verify", the 400-call cap kept an arbitrary 400 plus prior members, and ~400 rule-qualifying names (TTD,
# ADM, MCHP ...) were never scored. Pass 1 now reads the screener's own avgVolume, verifies EVERY uncertain name (no cap, no prior membership),
# admits US-domiciled names only (country == US, no ETFs/funds), and fails loudly below 90% coverage.
#
# v4 (2026-11-10, PM ruling): the country==US domicile rule is DROPPED; the NASDAQ/NYSE listing requirement stays.
# v5 (2026-11-10, PM ruling): ADRs are KEPT. There is no domicile rule and no ADR exclusion at all: a NASDAQ/NYSE listing that meets mcap >= $2B and 10-day average
# volume >= 1.5M is in, whatever its domicile or share type (TSM, ASML, BABA, HSBC, SONY, TD, TTE ... come in if they pass). Only ETFs/funds and warrants/units are out.
# data/universe_overrides.json stays as the PM's exclusion mechanism ("exclude": [...]); it is empty today, and every name it drops is printed in the build log.
UNIVERSE_RULE_ID = "v5-mcap2B-vol1.5M-listed-adrs-in-notrend"

SCREEN_MCAP = 2_000_000_000          # $2B minimum market cap
SCREEN_AVG_VOL_10D = 1_500_000       # 1.5M shares/day (10-day average)
SCREEN_LOOKBACK_DAYS = 90            # calendar days fetched (covers ~55 trading days)
# ---- API-BUDGET BANDS ------------------------------------------------------
# Pass 2 costs ONE FMP call per name, and the client throttles to 80 calls/min
# on cloud IPs, so an unbounded Pass 2 is the difference between a 4-minute
# screen and a 20-minute one. Dropping the old SMA50 pre-filter (which happened
# to halve the candidate set) made this acute — that filter was paying for
# itself in API budget while doing screening work it should not have been doing.
#
# So the batch quote's `avgVolume` (free — ~1 call per 50 names) decides two of
# the three cases outright, and only the genuinely uncertain band spends a bars
# call:
#
#   avgVolume >= HIGH   -> admit,  no bars call   (comfortably above the floor)
#   avgVolume <  LOW    -> reject, no bars call   (comfortably below it)
#   LOW <= av < HIGH    -> fetch bars, apply the true 10-day mean
#
# TRADE-OFF, stated rather than buried: FMP's avgVolume uses a longer window
# than 10 days, so the two shortcut bands are approximations. A name whose
# volume collapsed very recently could be admitted on a stale average, and one
# that just woke up could be rejected. The bands are set wide (2x and 0.5x the
# 1.5M floor) so only names far from the boundary skip verification, and every
# name NEAR the threshold — where the decision actually matters — is still
# measured exactly.
SCREEN_AVG_VOL_HIGH = SCREEN_AVG_VOL_10D * 2      # 3.0M — admit unverified
SCREEN_AVG_VOL_PREFILTER = SCREEN_AVG_VOL_10D // 2  # 750k — reject unverified

# NO CAP (PM 2026-11-10): every name in the uncertain band is verified. A cap was a silent exclusion that depended on screener order, and prior
# membership must never admit or exclude a name. ~600-900 bar calls at 80/min is acceptable for a nightly screen.
UNIVERSE_OVERRIDES_FILE = DATA_DIR / "universe_overrides.json"
SCREEN_MIN_COVERAGE = 0.90            # the build FAILS if it admits fewer than 90% of the screener-qualified US names


def load_universe_overrides(path: Path | None = None) -> dict:
    """The PM's exclusion list: {"exclude": {...}} (upper-case tickers); "include" is read for old files and ignored. A missing file is no overrides; a malformed one
    is an error (a silent empty list would quietly re-admit names the PM ruled out)."""
    import json as _json
    f = path or UNIVERSE_OVERRIDES_FILE
    if not f.exists():
        return {"exclude": set(), "include": set()}
    raw = _json.loads(f.read_text(encoding="utf-8"))
    return {"exclude": {str(x).upper() for x in raw.get("exclude", [])}, "include": {str(x).upper() for x in raw.get("include", [])}}


def _today_sgt() -> date:
    """Today in Singapore (the house clock). date.today() is UTC on the runner, so a same-day rebuild was skipped on a UTC stamp."""
    from datetime import datetime
    from zoneinfo import ZoneInfo
    return datetime.now(ZoneInfo("Asia/Singapore")).date()


def load_universe(path: Path | None = None, include_benchmark: bool = True) -> list[str]:
    """Read tickers from universe.txt.

    Strips comments (# ...) and blank lines. De-duplicates while preserving order.
    """
    file = path or DEFAULT_UNIVERSE_FILE
    tickers: list[str] = []
    seen: set[str] = set()
    for raw in file.read_text(encoding="utf-8").splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue
        sym = line.upper()
        if sym in seen:
            continue
        seen.add(sym)
        tickers.append(sym)

    if include_benchmark and BENCHMARK not in seen:
        tickers.insert(0, BENCHMARK)
    return tickers


def refresh_universe(dry_run: bool = False) -> dict:
    """Pull FMP screener and update universe.txt with qualifying tickers.

    Returns dict with: added (new tickers), removed (dropped below threshold),
    total (final count), unchanged (bool).
    """
    from src.data.fmp_client import FMPClient

    client = FMPClient()
    results = client.get_screener(
        min_mcap=UNIVERSE_MIN_MCAP,
        min_price=UNIVERSE_MIN_PRICE,
        min_volume=UNIVERSE_MIN_VOLUME,
        exchanges=UNIVERSE_EXCHANGES,
    )

    new_tickers: list[str] = []
    for item in results:
        sym = item.get("symbol", "").upper().strip()
        if not sym or any(sym.endswith(s) for s in EXCLUDED_SUFFIXES):
            continue
        if "." in sym or " " in sym:
            continue
        new_tickers.append(sym)

    new_set = set(new_tickers)
    current = load_universe(include_benchmark=False)
    current_set = set(current)

    added = sorted(new_set - current_set)
    removed = sorted(current_set - new_set)

    if not added and not removed:
        return {"added": [], "removed": [], "total": len(current), "unchanged": True}

    # Merge: keep existing order, append new at end, drop removed
    merged: list[str] = [t for t in current if t not in removed]
    merged.extend(added)

    if not dry_run:
        _write_universe(merged)

    return {
        "added": added,
        "removed": removed,
        "total": len(merged),
        "unchanged": False,
    }


def build_universe(dry_run: bool = False) -> dict:
    """Screen US equities to produce the AQE scan universe.

    THE universe rule — size + liquidity + listing, nothing else:
      1. Market cap >= $2B                    (FMP screener)
      2. 10-day average volume >= 1.5M shares (measured from bars)
      3. US primary listing, NASDAQ/NYSE, warrants/units excluded

    NO trend filter. `price > SMA20` / `price > SMA50` were removed on
    2026-08-04 (PM ruling): universe membership is an eligibility test, not a
    screening opinion, and the SMA conditions deleted exactly the pulled-back
    names QS is designed to surface. Longlist/Elder apply their own trend view
    downstream via their own thresholds.

    US-only (2026-11-10): `country == US` on the screener row; ADRs, foreign listings, ETFs and funds are excluded and LISTED in the build
    log (foreign-incorporated BIRK/GLBE/G/SBSW/LU wait for the PM's definition).

    Two-pass for API efficiency:
      Pass 1 — FMP screener (one call). Its own `avgVolume` splits the names: admit at SCREEN_AVG_VOL_HIGH, reject below
               SCREEN_AVG_VOL_PREFILTER, and VERIFY everything between (and anything with no average). No cap; prior membership
               never admits or excludes a name.
      Pass 2 — Fetch ~55 bars per uncertain name (1 call each) and apply the real 10-day average volume test.

    Fails (status "error", nothing written) when coverage of the screener-qualified US names is under SCREEN_MIN_COVERAGE or bar calls fail.

    Writes universe.txt locally AND uploads the CSV to Drive so it persists
    across container restarts.  Returns a summary dict.
    """
    from datetime import timedelta

    from src.data.fmp_client import FMPClient, FMPError

    client = FMPClient()
    today = _today_sgt()
    from_dt = today - timedelta(days=SCREEN_LOOKBACK_DAYS)
    stages: dict = {}

    # ── Pass 1: FMP screener. NO volume / price floor in the call: the screener's `volume` is the LAST SESSION's, so a volume floor dropped
    # names whose average is high but whose last day was light, and the rule has no price floor. Country, listing and fund filters are
    # applied below on the returned fields so every exclusion can be listed.
    print(f"[universe] Screening: mcap > ${SCREEN_MCAP / 1e9:.0f}B, NASDAQ/NYSE listing, no domicile rule, ADRs kept...")
    try:
        raw = client.get_screener(
            min_mcap=SCREEN_MCAP,
            min_price=0,
            min_volume=0,
            exchanges=UNIVERSE_EXCHANGES,
            limit=5000,
        )
    except FMPError as exc:
        return {"status": "error", "reason": f"screener failed: {exc}"}
    stages["screener_rows"] = len(raw)

    excluded: dict[str, list[str]] = {"etf_fund": [], "symbol_form": [], "not_listed": [], "no_symbol": [], "override": []}
    rows_ok: dict[str, dict] = {}
    for r in raw:
        sym = (r.get("symbol") or "").upper().strip()
        if not sym:
            excluded["no_symbol"].append("?"); continue
        if r.get("isEtf") or r.get("isFund"):
            excluded["etf_fund"].append(sym); continue
        exch = (r.get("exchangeShortName") or r.get("exchange") or "").upper()
        if exch and exch not in UNIVERSE_EXCHANGES:
            excluded["not_listed"].append(f"{sym}({exch})"); continue
        if any(sym.endswith(x) for x in EXCLUDED_SUFFIXES) or "." in sym or " " in sym:
            excluded["symbol_form"].append(sym); continue
        rows_ok[sym] = r
    stages.update(listed_candidates=len(rows_ok), excluded_etf_fund=len(excluded["etf_fund"]), excluded_symbol_form=len(excluded["symbol_form"]),
                  excluded_not_listed=len(excluded["not_listed"]))
    print(f"[universe] Screener {len(raw)} rows -> {len(rows_ok)} NASDAQ/NYSE candidates; excluded: {len(excluded['etf_fund'])} ETF/fund, "
          f"{len(excluded['symbol_form'])} symbol form, {len(excluded['not_listed'])} not NASDAQ/NYSE")
    if not rows_ok:
        return {"status": "error", "reason": "screener returned 0 listed candidates", "stages": stages}

    # ── Three-way split on the screener's own avgVolume (free: it is in the row). The batch /quote has NO avgVolume. ──
    def _av(row):
        try:
            v = row.get("avgVolume")
            return float(v) if v is not None else None
        except (TypeError, ValueError):
            return None

    # ── The PM's exclusion list (data/universe_overrides.json "exclude"; empty today). ADRs are NOT excluded (PM 2026-11-10: keep the ADRs). ──
    over = load_universe_overrides()
    excluded["override"] = sorted(t for t in over["exclude"] if t in rows_ok)
    for tk in excluded["override"]:
        rows_ok.pop(tk, None)
    stages["excluded_override"] = len(excluded["override"])
    print(f"[universe] Excluded by the PM's override list: {excluded['override'] or 'none (the list is empty)'}; ADRs are kept (no ADR exclusion)")
    rows_us = rows_ok   # (name kept for the code below: the candidate set after listing, fund and ADR filters)
    # The screener already returns marketCap; kept for the Option Scanner's size filter (zero extra cost).
    mcap_by_tk = {}
    for _sym, _r in rows_us.items():
        _mc = _r.get("marketCap") or _r.get("marketCapitalization")
        try:
            if _mc:
                mcap_by_tk[_sym] = float(_mc)
        except (TypeError, ValueError):
            pass
    stages["candidates"] = len(rows_us)
    foreign_in = sorted(t for t, r in rows_us.items() if (r.get("country") or "").upper() != "US")
    print(f"[universe] Foreign-domiciled names (ordinary shares and ADRs) carried in the candidate set: {len(foreign_in)}")

    passed: list[str] = []          # admitted without verification
    to_verify: list[str] = []       # in the band, or no avgVolume: measured on bars
    rejected_cheap = 0
    qualified_est = 0               # names whose avgVolume is at or above the rule's floor (the coverage guard's denominator)
    for tk, row in rows_us.items():
        av = _av(row)
        if av is not None and av >= SCREEN_AVG_VOL_10D:
            qualified_est += 1
        if av is None:
            to_verify.append(tk)                    # a missing average is an FMP gap, not a screening result: measure it
        elif av >= SCREEN_AVG_VOL_HIGH:
            passed.append(tk)
        elif av < SCREEN_AVG_VOL_PREFILTER:
            rejected_cheap += 1
        else:
            to_verify.append(tk)
    stages.update(admitted_unverified=len(passed), rejected_cheap=rejected_cheap, to_verify=len(to_verify), qualified_est=qualified_est)
    print(f"[universe] avgVolume split: {len(passed)} admitted (>= {SCREEN_AVG_VOL_HIGH:,}), {rejected_cheap} rejected "
          f"(< {SCREEN_AVG_VOL_PREFILTER:,}), {len(to_verify)} to verify; qualified estimate (avgVolume >= {SCREEN_AVG_VOL_10D:,}): {qualified_est}")

    est_min = len(to_verify) / max(client.config.rate_limit_per_min, 1)
    print(f"[universe] Pass 2: {len(to_verify)} bars calls, NO cap (~{est_min:.1f} min at {client.config.rate_limit_per_min}/min)")

    # ── Pass 2: fetch bars → true 10-day average volume. Every outcome is counted; nothing is dropped silently. ──
    errors: list[str] = []
    short_history: list[str] = []
    below_floor = 0
    verified_in = 0
    for i, tk in enumerate(to_verify):
        if (i + 1) % 100 == 0:
            print(f"[universe] Checking bars {i + 1}/{len(to_verify)}...")
        try:
            bars = client.get_daily_bars(tk, from_date=from_dt, to_date=today)
            if bars is None or bars.empty or len(bars) < 50:
                short_history.append(tk)
                continue
            volume = bars["volume"].astype(float)
            avg_vol = float(volume.tail(10).mean())
            if avg_vol >= SCREEN_AVG_VOL_10D:
                passed.append(tk)
                verified_in += 1
            else:
                below_floor += 1
        except Exception as exc:  # noqa: BLE001
            errors.append(f"{tk}: {exc}")
    passed = sorted(set(passed))
    stages.update(verified_in=verified_in, verified_below_floor=below_floor, short_history=len(short_history), bar_errors=len(errors),
                  final=len(passed))
    print(f"[universe] {len(passed)} tickers passed all filters ({verified_in} verified in, {below_floor} below the volume floor, "
          f"{len(short_history)} under 50 bars, {len(errors)} bar errors)")
    if short_history:
        print(f"[universe] Under 50 bars (not scoreable yet): {short_history[:40]}")

    # ── The guard: a build that lost names to errors must FAIL, never be reused silently. ──
    coverage = (len(passed) / qualified_est) if qualified_est else 0.0
    stages["coverage"] = round(coverage, 3)
    bad_calls = len(errors)
    if qualified_est and (coverage < SCREEN_MIN_COVERAGE or bad_calls > max(5, 0.05 * max(len(to_verify), 1))):
        reason = (f"coverage {coverage:.1%} of {qualified_est} screener-qualified US names is under {SCREEN_MIN_COVERAGE:.0%}"
                  if coverage < SCREEN_MIN_COVERAGE else f"{bad_calls} of {len(to_verify)} bar calls failed")
        print(f"[universe] [FAIL] {reason}; the universe file is NOT written")
        return {"status": "error", "reason": reason, "stages": stages, "total": len(passed), "errors": errors[:20]}

    # ── Compare with existing ─────────────────────────────────────────────
    try:
        existing = set(load_universe(include_benchmark=False))
    except Exception:  # noqa: BLE001
        existing = set()
    new_set = set(passed)
    added = sorted(new_set - existing)
    removed = sorted(existing - new_set)
    kept = sorted(existing & new_set)

    if dry_run:
        return {"status": "dry_run", "total": len(passed),
                "added": len(added), "removed": len(removed), "kept": len(kept),
                "tickers": sorted(passed), "errors": errors[:20], "stages": stages,
                "excluded_override": excluded["override"], "short_history": short_history}

    # ── Write + upload ────────────────────────────────────────────────────
    final = sorted(passed)
    _write_universe(final, stages)
    _write_universe_mcap({t: mcap_by_tk[t] for t in final if t in mcap_by_tk})

    csv_text = "Symbol\n" + "\n".join(final) + "\n"
    drive_ok, drive_reason = False, "not attempted"
    try:
        result = upload_universe(csv_text.encode("utf-8"))
        drive_ok = result.get("drive_ok", False)
        drive_reason = result.get("drive_reason", "unknown")
    except Exception as exc:  # noqa: BLE001
        drive_reason = f"{type(exc).__name__}: {exc}"

    summary = {
        "status": "ok",
        "total": len(final),
        "added": len(added),
        "removed": len(removed),
        "kept": len(kept),
        "drive_ok": drive_ok,
        "drive_reason": drive_reason,
        "errors": errors[:20],
        "stages": stages,
        "excluded_override": excluded["override"],
    }
    print(f"[universe] Done: {len(final)} tickers "
          f"(+{len(added)} / -{len(removed)} / ={len(kept)})"
          f" | Drive: {'ok' if drive_ok else drive_reason}")
    return summary


def _read_text(csv_path_or_bytes) -> str:
    """Read CSV text from a path, a Streamlit UploadedFile, or raw bytes/str."""
    if isinstance(csv_path_or_bytes, (str, Path)):
        return Path(csv_path_or_bytes).read_text(encoding="utf-8-sig")
    data = (csv_path_or_bytes.getvalue() if hasattr(csv_path_or_bytes, "getvalue")
            else csv_path_or_bytes.read())
    return data.decode("utf-8-sig") if isinstance(data, bytes) else data


def upload_universe(csv_path_or_bytes) -> dict:
    """Set the universe from a screener CSV (with a Symbol column).

    Writes the parsed tickers to the local universe.txt AND uploads the raw CSV
    to the universe Drive folder as the canonical file (overwriting it), so the
    new list persists across container restarts. Accepts a path or a Streamlit
    UploadedFile.

    Returns: {tickers, count, previous_count, drive_ok, drive_reason}.
    """
    raw = _read_text(csv_path_or_bytes)
    universe_txt = _csv_to_universe_text(raw)
    if universe_txt is None:
        raise ValueError("CSV has no recognisable 'Symbol' column.")

    try:
        previous = load_universe(include_benchmark=False)
    except Exception:  # noqa: BLE001
        previous = []

    DEFAULT_UNIVERSE_FILE.parent.mkdir(parents=True, exist_ok=True)
    DEFAULT_UNIVERSE_FILE.write_text(universe_txt, encoding="utf-8")
    tickers = [ln for ln in universe_txt.splitlines() if ln and not ln.startswith("#")]

    # Overwrite the canonical CSV in the universe Drive folder.
    drive_ok, drive_reason = False, "not configured"
    try:
        from src.data import gdrive_uploader
        if gdrive_uploader.is_configured():
            r = gdrive_uploader.upload_or_replace(
                UNIVERSE_DRIVE_FILENAME, raw, mime="text/csv",
                folder_id=UNIVERSE_FOLDER_ID,
            )
            drive_ok = bool(r.get("ok"))
            drive_reason = r.get("reason", "ok" if drive_ok else "failed")
    except Exception as exc:  # noqa: BLE001
        drive_reason = f"{type(exc).__name__}: {exc}"

    return {
        "tickers": tickers,
        "count": len(tickers),
        "previous_count": len(previous),
        "drive_ok": drive_ok,
        "drive_reason": drive_reason,
    }


def _write_universe(tickers: list[str], stages: dict | None = None) -> None:
    """Write universe.txt locally, stamped with the date (SGT), the rule used and the per-stage counts of the build."""
    lines = [f"# AQE Universe — updated {_today_sgt()}",
             f"# rule: {UNIVERSE_RULE_ID}",
             f"# {len(tickers)} tickers"]
    if stages:
        lines.append("# stages: " + ", ".join(f"{k}={v}" for k, v in stages.items() if isinstance(v, (int, float, str))))
    lines += ["", *tickers, ""]
    DEFAULT_UNIVERSE_FILE.parent.mkdir(parents=True, exist_ok=True)
    DEFAULT_UNIVERSE_FILE.write_text("\n".join(lines), encoding="utf-8")


def universe_built_date(path: Path | None = None) -> date | None:
    """The date stamped in universe.txt's header, or None if unreadable.

    The universe is a DYNAMIC daily screen, so "when was this built" is a
    first-class question: a pipeline run against a stale list scans names that
    may no longer meet the size/liquidity rule and misses ones that now do,
    with nothing in the output revealing it.
    """
    file = path or DEFAULT_UNIVERSE_FILE
    try:
        for raw in file.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line.startswith("#"):
                break
            if "updated" in line:
                token = line.rsplit(" ", 1)[-1]
                return date.fromisoformat(token)
    except Exception:  # noqa: BLE001
        return None
    return None


def universe_built_rule(path: Path | None = None) -> str | None:
    """The rule id stamped in universe.txt's header, or None if absent.

    Absent means the file predates rule stamping, which is itself a mismatch —
    it was built by an older screen.
    """
    file = path or DEFAULT_UNIVERSE_FILE
    try:
        for raw in file.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line.startswith("#"):
                break
            if line.lower().startswith("# rule:"):
                return line.split(":", 1)[1].strip()
    except Exception:  # noqa: BLE001
        return None
    return None


def universe_is_stale(as_of: date | None = None) -> bool:
    """True when the universe must be rebuilt before it can be trusted.

    Stale on EITHER count:
      - not built today, or
      - built under a DIFFERENT screen rule.

    The rule check matters on the day a rule changes: a file built this morning
    by the previous screen is fresh by date but wrong by definition, and
    without this the new rule would not take effect until the calendar rolled.
    An unstamped file (predating rule stamping) counts as a mismatch.
    """
    if universe_built_rule() != UNIVERSE_RULE_ID:
        return True
    built = universe_built_date()
    return built is None or built != (as_of or _today_sgt())


def universe_status() -> dict:
    """{built, rule, count, stale, stale_reason} — pipeline log + UI status."""
    built = universe_built_date()
    rule = universe_built_rule()
    try:
        count = len(load_universe(include_benchmark=False))
    except Exception:  # noqa: BLE001
        count = 0
    if rule != UNIVERSE_RULE_ID:
        reason = f"built under rule {rule or 'unstamped'}, current is {UNIVERSE_RULE_ID}"
    elif built != _today_sgt():
        reason = f"built {built}, not today"
    else:
        reason = None
    return {"built": built.isoformat() if built else None,
            "rule": rule, "count": count,
            "stale": universe_is_stale(), "stale_reason": reason}


def _csv_to_universe_text(content: str) -> str | None:
    """Extract tickers from a screener CSV (Symbol column) → universe.txt text.

    Returns None if there is no recognisable Symbol column.
    """
    import csv
    import io

    reader = csv.reader(io.StringIO(content))
    rows = [r for r in reader if any(c.strip() for c in r)]
    if not rows:
        return None
    header = [h.strip().lower() for h in rows[0]]
    try:
        sym_idx = next(i for i, h in enumerate(header)
                       if h in ("symbol", "ticker", "symbols", "tickers"))
    except StopIteration:
        return None

    tickers: list[str] = []
    seen: set[str] = set()
    for r in rows[1:]:
        if len(r) <= sym_idx:
            continue
        sym = r[sym_idx].strip().upper()
        if not sym or sym in seen:
            continue
        if any(sym.endswith(s) for s in EXCLUDED_SUFFIXES) or "." in sym or " " in sym:
            continue
        seen.add(sym)
        tickers.append(sym)
    if not tickers:
        return None
    return "\n".join([f"# AQE Universe — restored from Drive CSV ({date.today()})",
                      f"# {len(tickers)} tickers", "", *tickers, ""])


def _drive_service():
    """Return (service, universe_folder_id), or (None, None) if Drive isn't set up."""
    from src.data import gdrive_uploader
    if not gdrive_uploader.is_configured():
        return None, None
    cfg = gdrive_uploader.DriveConfig.from_env()
    if cfg is None:
        return None, None
    return gdrive_uploader._build_service(cfg), UNIVERSE_FOLDER_ID


def _active_universe_file(service, folder_id) -> dict | None:
    """The canonical universe.csv if present, else the newest CSV in the folder."""
    q = f"'{folder_id}' in parents and trashed = false"
    res = service.files().list(
        q=q, orderBy="modifiedTime desc",
        fields="files(id,name,modifiedTime,mimeType)",
    ).execute()
    files = [f for f in (res.get("files") or [])
             if f.get("name", "").lower().endswith(".csv")
             or f.get("mimeType") == "text/csv"]
    if not files:
        return None
    for f in files:
        if f.get("name", "").lower() == UNIVERSE_DRIVE_FILENAME:
            return f
    return files[0]  # newest by modifiedTime


def restore_universe_from_drive() -> bool:
    """Overwrite the local universe.txt from the universe Drive folder.

    Drive is the single source of truth. Reads the canonical universe.csv (or the
    newest CSV in the folder), parses the Symbol column, and writes universe.txt.
    Runs on every pipeline startup so a fresh/ephemeral container always reflects
    what's in Drive. Returns True if a restore happened.
    """
    try:
        service, folder_id = _drive_service()
        if not service:
            return False
        f = _active_universe_file(service, folder_id)
        if not f:
            return False
        content = service.files().get_media(fileId=f["id"]).execute()
        if isinstance(content, bytes):
            content = content.decode("utf-8")
        txt = _csv_to_universe_text(content)
        if txt is None:  # not a Symbol-column CSV — treat as a plain ticker list
            txt = content if content.strip() else None
        if txt is None:
            return False
        DEFAULT_UNIVERSE_FILE.parent.mkdir(parents=True, exist_ok=True)
        DEFAULT_UNIVERSE_FILE.write_text(txt, encoding="utf-8")
        return True
    except Exception:  # noqa: BLE001
        return False


def get_drive_universe_status() -> dict | None:
    """Metadata for the active universe file in Drive: {name, modified, count}.

    None when Drive isn't configured or the folder has no CSV. Downloads the file
    to count tickers, so callers should cache the result.
    """
    try:
        service, folder_id = _drive_service()
        if not service:
            return None
        f = _active_universe_file(service, folder_id)
        if not f:
            return None
        content = service.files().get_media(fileId=f["id"]).execute()
        if isinstance(content, bytes):
            content = content.decode("utf-8")
        txt = _csv_to_universe_text(content) or ""
        count = len([ln for ln in txt.splitlines() if ln and not ln.startswith("#")])
        return {"name": f.get("name"), "modified": f.get("modifiedTime"), "count": count}
    except Exception:  # noqa: BLE001
        return None
