#!/usr/bin/env python3
"""aqe_notice.py -- render the AQE alert notice for the cockpit.

Reads ONE file, `aegis/output/alerts/live/latest.json` (contract:
aegis-core/contracts/aqe_alert_notice.schema.json), written by the AQE alert
engine every in-window cycle from the SAME cards the [AQE] email renders. This
tool prints the executive block the live review shows the PM. Deterministic,
stdlib only, no models. Read-only: places nothing, sizes nothing -- the share
count is floor(one_r / risk_per_share), arithmetic on the Aegis 1R.

    python3 aqe_notice.py render --repo <checkout> --fetch [--state f] [--one-r 620]
    python3 aqe_notice.py status --repo <checkout> [--fetch]

Exit codes (render): 0 rendered · 3 nothing new / not actionable · 4 STALE
(engine silent inside the US window) · 5 no notice file.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import re
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

NOTICE_PATH = "aegis/output/alerts/live/latest.json"
FUND_PATH = "aegis/plugin/aegis-core/config/aegis_fund.md"
DEFAULT_ONE_R = 620.0
_ET = ZoneInfo("America/New_York")
_SGT = ZoneInfo("Asia/Singapore")
WINDOW_OPEN_MIN = 9 * 60 + 45
WINDOW_END_MIN = 16 * 60 + 45
SEV_ORDER = {"ACT": 0, "RISK": 1, "INFO": 2}

# ---------------------------------------------------------------- loading


def _git_show(repo: str, path: str, fetch: bool) -> str | None:
    try:
        if fetch:
            subprocess.run(["git", "-C", repo, "fetch", "-q", "origin", "main"],
                           check=False, capture_output=True, timeout=60)
        r = subprocess.run(["git", "-C", repo, "show", f"origin/main:{path}"],
                           capture_output=True, text=True, timeout=30)
        return r.stdout if r.returncode == 0 and r.stdout.strip() else None
    except Exception:  # noqa: BLE001
        return None


def load_notice(repo: str | None, file: str | None, fetch: bool) -> tuple[dict | None, str | None]:
    """(notice, problem). None notice with a reason on any miss; never raises."""
    txt = None
    if file:
        p = Path(file)
        if not p.exists():
            return None, f"no notice file at {file}"
        txt = p.read_text(encoding="utf-8")
    elif repo:
        if fetch:
            txt = _git_show(repo, NOTICE_PATH, True)
        if txt is None:
            p = Path(repo) / NOTICE_PATH
            if p.exists():
                txt = p.read_text(encoding="utf-8")
        if txt is None:
            return None, f"no notice at {NOTICE_PATH} (origin/main or working tree)"
    else:
        return None, "no --repo or --file given"
    try:
        doc = json.loads(txt)
    except Exception as exc:  # noqa: BLE001
        return None, f"notice unreadable: {exc}"
    if not isinstance(doc, dict):
        return None, "notice is not an object"
    return doc, None


def one_r_from_fund(repo: str | None) -> float:
    if not repo:
        return DEFAULT_ONE_R
    try:
        txt = (Path(repo) / FUND_PATH).read_text(encoding="utf-8")
        m = re.search(r"^one_r_usd:\s*([0-9.]+)", txt, re.M)
        return float(m.group(1)) if m else DEFAULT_ONE_R
    except Exception:  # noqa: BLE001
        return DEFAULT_ONE_R


# ---------------------------------------------------------------- state


def state_path(arg: str | None) -> Path:
    if arg:
        return Path(arg)
    d = os.environ.get("AEGIS_LIVE_DIR")
    return Path(d) / "aqe_notice_state.json" if d else Path("aqe_notice_state.json")


def load_state(p: Path) -> dict:
    try:
        return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}
    except Exception:  # noqa: BLE001
        return {}


def save_state(p: Path, st: dict) -> None:
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(st, indent=2), encoding="utf-8")
    except Exception:  # noqa: BLE001
        pass


# ---------------------------------------------------------------- helpers


def _n(v):
    try:
        f = float(v)
        return f if f == f else None
    except (TypeError, ValueError):
        return None


def _s(v, default="?") -> str:
    return str(v) if v not in (None, "") else default


def fmt(x) -> str:
    f = _n(x)
    return f"{f:.2f}" if f is not None else "—"


def _parse_utc(s) -> datetime | None:
    try:
        d = datetime.fromisoformat(str(s).replace("Z", "+00:00"))
        return d if d.tzinfo else d.replace(tzinfo=timezone.utc)
    except Exception:  # noqa: BLE001
        return None


def in_window(now_et: datetime) -> bool:
    if now_et.weekday() >= 5:
        return False
    m = now_et.hour * 60 + now_et.minute
    return WINDOW_OPEN_MIN <= m < WINDOW_END_MIN


def staleness(doc: dict, now_utc: datetime, max_age_min: int) -> tuple[bool, float | None]:
    """(stale, age_min). Stale only inside the US window."""
    t = _parse_utc(doc.get("cycle_at_utc"))
    if t is None:
        return in_window(now_utc.astimezone(_ET)), None
    age = (now_utc - t).total_seconds() / 60.0
    return (age > max_age_min and in_window(now_utc.astimezone(_ET))), age


def _sgt_hhmm(doc: dict) -> str:
    s = str(doc.get("cycle_at_sgt") or "")
    m = re.search(r"(\d{2}:\d{2})", s)
    if m:
        return m.group(1)
    t = _parse_utc(doc.get("cycle_at_utc"))
    return t.astimezone(_SGT).strftime("%H:%M") if t else "??:??"


def _item_key(it: dict) -> str:
    return f"{it.get('ticker')}|{','.join(sorted(str(s) for s in (it.get('states') or [])))}"


# ---------------------------------------------------------------- rendering

_BANNED = (r"\bline\b", r"hourly close", r"AQE default")


def _clean(text: str) -> str:
    """House wording: never 'AQE default'; the rest is checked, not rewritten."""
    return re.sub(r"AQE default criteria|AQE default", "AQE criteria", text)


def _trigger_stop(it: dict) -> str:
    entry, stop = _n(it.get("entry")), _n(it.get("stop"))
    bits = []
    if it.get("held"):
        if stop is not None:
            bits.append(f"stop {fmt(stop)}")
        tgt = _n(it.get("target"))
        if tgt is not None:
            bits.append(f"target {fmt(tgt)}")
    else:
        if entry is not None:
            bits.append(f"buy above {fmt(entry)}")
        if stop is not None:
            tag = " (ATR fallback)" if it.get("stop_type") == "aqe_atr_fallback" else ""
            bits.append(f"stop {fmt(stop)}{tag}")
    return " · ".join(bits) if bits else "—"


def _action(it: dict, one_r: float) -> str:
    act = _clean(_s(it.get("action"), "—"))
    if it.get("severity") == "ACT":
        rps = _n(it.get("risk_per_share"))
        if rps is None:
            e, s = _n(it.get("entry")), _n(it.get("stop"))
            rps = (e - s) if (e is not None and s is not None and e > s) else None
        if rps and rps > 0:
            n = math.floor(one_r / rps)
            act += f" · ~{n} sh at stop {fmt(it.get('stop'))}"
        else:
            act += " · no stop known, no share count"
    return act


def render(doc: dict, prev_items: list[str] | None, one_r: float, first_of_session: bool) -> str:
    out: list[str] = []
    data = doc.get("data") or {}
    header = (f"{_sgt_hhmm(doc)} SGT · AQE cycle {_s(doc.get('seq'))} · PMA run {_s(data.get('pma_run'), 'none')}"
              f" · AQE export {_s(data.get('aqe_date'), 'unknown')}")
    out.append(header)

    # PM 2026-11-02: no market sentence in the cockpit; a confirmed break arrives as a normal MARKET row.
    items = [i for i in (doc.get("items") or []) if isinstance(i, dict)]
    items.sort(key=lambda i: SEV_ORDER.get(i.get("severity"), 9))
    prev = set(prev_items or [])
    skipped = 0
    if items:
        out.append("")
        out.append("| Name | Price | Trigger/Stop | Action |")
        out.append("|---|---|---|---|")
        for it in items:
            tk = it.get("ticker")
            if not tk:
                skipped += 1
                continue
            name = str(tk) + (" (you hold)" if it.get("held") else "")
            if it.get("class") == "MARKET":
                name = f"{tk} · MARKET CONDITION BROKEN"
            if prev_items is not None and _item_key(it) not in prev:
                name += " ▲NEW"
            px = fmt(it.get("price"))
            dp = _n(it.get("day_pct"))
            if dp is not None:
                px += f" ({dp:+.1f}%)"
            out.append(f"| {name} | {px} | {_trigger_stop(it)} | {_action(it, one_r)} |")
    setups = [s.get("ticker") for s in (doc.get("setups_forming") or []) if isinstance(s, dict) and s.get("ticker")]
    if setups:
        out.append("")
        out.append("Setups forming: " + ", ".join(str(s) for s in setups))

    foot: list[str] = []
    sup = _n(doc.get("suppressed"))
    if sup:
        foot.append(f"{int(sup)} entry alert{'s' if sup != 1 else ''} suppressed by the broken market condition.")
    if data.get("aqe_current") is False:
        foot.append("⚠ AQE export is older than the last close — AQE-criteria names were skipped.")
    if data.get("pma_missing"):
        foot.append(f"⚠ No PMA file for today's session (latest is {data['pma_missing']}) — no committee names.")
    if skipped:
        foot.append(f"{skipped} item{'s' if skipped != 1 else ''} unreadable (no ticker) — not shown.")
    if any(i.get("severity") == "ACT" for i in items):
        foot.append(f"Share counts: floor(${one_r:,.0f} / (buy − stop)) — arithmetic, not a recommendation. "
                    "Any order goes through the Tiger preview and your explicit confirm.")
    if foot:
        out.append("")
        out.extend(foot)
    return _clean("\n".join(out))


def wording_check(text: str) -> list[str]:
    probe = text.replace("Bottom line", "")
    return [b for b in _BANNED if re.search(b, probe, re.I)]


# ---------------------------------------------------------------- commands


def cmd_render(a) -> int:
    doc, problem = load_notice(a.repo, a.file, a.fetch)
    if doc is None:
        print(f"No AQE notice published yet ({problem}).")
        return 5
    now = _parse_utc(a.now) if a.now else datetime.now(timezone.utc)
    sp = state_path(a.state)
    st = load_state(sp)
    sess, seq = doc.get("session_date"), doc.get("seq")
    key = f"{sess}|{seq}"
    alarm = doc.get("alarm") if isinstance(doc.get("alarm"), dict) else None
    if alarm:
        # The dead-man ALARM record (never an email): print once, exit 4.
        if st.get("last_key") == key:
            return 3
        st.update({"last_key": key, "session": sess, "seq": seq})
        save_state(sp, st)
        print(_clean(str(alarm.get("text") or f"AQE ALERT ENGINE SILENT: {alarm.get('reason') or 'no reason given'}")))
        return 4
    stale, age = staleness(doc, now, a.max_age_min)
    if stale:
        ago = f"{age:.0f} min ago" if age is not None else "time unreadable"
        print(f"AQE alert engine silent: last cycle {_sgt_hhmm(doc)} SGT ({ago}).")
        return 4
    if st.get("last_key") == key:
        return 3
    first = st.get("session") != sess
    prev_items = None if first else (st.get("items") or [])
    actionable = bool(doc.get("actionable")) or bool((doc.get("market") or {}).get("just_broke"))
    text = None
    if actionable:
        text = render(doc, prev_items, a.one_r if a.one_r is not None else one_r_from_fund(a.repo), first)
    elif a.quiet_line and doc.get("quiet_line"):
        text = _clean(str(doc["quiet_line"]))
    st.update({"last_key": key, "session": sess, "seq": seq,
               "items": [_item_key(i) for i in (doc.get("items") or []) if isinstance(i, dict)]})
    save_state(sp, st)
    if text:
        print(text)
        for bad in wording_check(text):
            print(f"[wording check] banned phrase {bad!r} present", file=sys.stderr)
    return 0 if actionable else 3


def cmd_status(a) -> int:
    doc, problem = load_notice(a.repo, a.file, a.fetch)
    if doc is None:
        print(f"AQE notice: none ({problem})")
        return 5
    now = _parse_utc(a.now) if a.now else datetime.now(timezone.utc)
    _stale, age = staleness(doc, now, a.max_age_min)
    em = doc.get("email") or {}
    print(f"AQE notice: cycle {_s(doc.get('seq'))} at {_s(doc.get('cycle_at_sgt'))} "
          f"({'%.0f min ago' % age if age is not None else 'age unknown'}) · "
          f"actionable {str(bool(doc.get('actionable'))).lower()} · {len(doc.get('items') or [])} items · "
          f"email sent {str(em.get('sent')).lower()}")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name, fn in (("render", cmd_render), ("status", cmd_status)):
        p = sub.add_parser(name)
        p.add_argument("--repo", default=None, help="checkout root of TongIncomeWheel/AQE")
        p.add_argument("--file", default=None, help="read this notice file instead of the repo")
        p.add_argument("--fetch", action="store_true", help="git fetch origin main and read origin/main's copy")
        p.add_argument("--state", default=None, help="dedup state file (default $AEGIS_LIVE_DIR/aqe_notice_state.json)")
        p.add_argument("--one-r", type=float, default=None, help="1R in USD (default: aegis_fund.md one_r_usd, else 620)")
        p.add_argument("--max-age-min", type=int, default=45)
        p.add_argument("--quiet-line", action="store_true", help="print the notice's quiet line when not actionable")
        p.add_argument("--now", default=None, help="ISO UTC override (tests only)")
        p.set_defaults(fn=fn)
    a = ap.parse_args(argv)
    return a.fn(a)


if __name__ == "__main__":
    raise SystemExit(main())
