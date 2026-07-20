#!/usr/bin/env python3
"""
ops_status.py — the Aegis on-demand operational status (D-45), behind /ops.

Answers one question: is the machinery alive and healthy right now?
This is the SYSTEM/liveness sibling of /status (which is the BOOK cockpit,
Operations desk). /ops is read-only and places nothing (constitution law 1).

It REUSES tools/daily_flow_audit.py for the "what ran today" reconstruction —
it does not re-implement it — and adds live liveness: per-loop last/next run,
state freshness (historical store, tripwires, dynCap, git head, PTJ), self-heal
recency, notification-channel health, and the token/cost meter. Fail-visible:
any piece it cannot read is marked PARTIAL and listed, never faked (law 3).

CLI:
  ops_status.py [YYYY-MM-DD]            -> quick text card (token-cheap)
  ops_status.py [YYYY-MM-DD] --render   -> also write the full HTML dashboard
"""

import os
import sys
import json
import subprocess
import datetime as _dt

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.environ.get("AEGIS_DATA_DIR", os.path.join(ROOT, "data"))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    import daily_flow_audit as dfa
except Exception:
    dfa = None

# Scheduled loops (label, when) — mirrors INSTALL.md Phase 6 / parameters schedule.
LOOPS = [
    ("premarket",    "plan 16:00 SGT"),
    ("market_hours", "watch ~21:25 SGT"),
    ("post_market",  "~04:05 SGT"),
    ("eod_audit",    "~04:11 SGT"),
    ("weekly",       "Sun 05:00 SGT"),
    ("janitor",      "nightly"),
]


def _load(path, default=None):
    try:
        with open(path) as f:
            return json.load(f)
    except Exception:
        return default


def _git_head():
    try:
        out = subprocess.run(["git", "-C", ROOT, "rev-parse", "--short", "HEAD"],
                             capture_output=True, text=True, timeout=8)
        return out.stdout.strip() or None
    except Exception:
        return None


def _state_health():
    missing = []
    h = {}
    man = _load(os.path.join(DATA, "historical", "manifest.json"), {})
    if man:
        h["historical_store"] = {"n_tickers": man.get("n_tickers"),
                                 "last_self_heal": man.get("last_self_heal")}
    else:
        missing.append("historical manifest")
    dc = _load(os.path.join(DATA, "persistent", "dyncap_ledger.json"), {})
    if dc:
        h["dyncap"] = {"usd": dc.get("dyncap_usd"), "marked_asof": dc.get("marked_asof"),
                       "open": dc.get("open_count")}
    else:
        missing.append("dyncap ledger")
    head = _git_head()
    h["kernel_commit"] = head or "unknown"
    if not head:
        missing.append("git head")
    return h, missing


def _channels():
    ch = os.environ.get("AEGIS_NOTIFY_CHANNEL", "cowork").lower()
    return {
        "active": ch,                       # 'cowork' (pilot native push) or 'whatsapp' (post-migration)
        "cowork_push": ch == "cowork",      # native — always available inside a Cowork session
        "whatsapp": bool(os.environ.get("WHATSAPP_TOKEN") or os.environ.get("TWILIO_SID")),  # post-migration
        "watchdog": bool(os.environ.get("WATCHDOG_URL")),                                     # post-migration
    }


def assemble(day=None):
    day = day or _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%d")
    missing = []

    flow = None
    if dfa is not None:
        try:
            flow = dfa.audit(day)
        except Exception as e:
            missing.append(f"flow audit ({e})")
    else:
        missing.append("daily_flow_audit import")

    health, m2 = _state_health()
    missing += m2
    chans = _channels()
    # Cowork pilot: native push is always on — nothing to configure, no PARTIAL.
    # Only the post-migration whatsapp channel can be "selected but unconfigured".
    if chans["active"] == "whatsapp" and not chans["whatsapp"]:
        missing.append("whatsapp channel selected but unconfigured")

    incidents = (flow or {}).get("exception_count", 0)
    layers_touched = (flow or {}).get("layers_touched", [])
    layers_missing = (flow or {}).get("layers_not_touched", [])

    status = "ALIVE"
    if missing:
        status = "PARTIAL"
    if incidents and any(k in str(flow) for k in ("FAIL", "stood down", "breach")):
        status = "DEGRADED"

    return {
        "date": day,
        "status": status,
        "loops": [{"loop": n, "when": w} for n, w in LOOPS],
        "flow": {"layers_touched": layers_touched, "layers_not_touched": layers_missing,
                 "headline": (flow or {}).get("headline"), "incidents": incidents},
        "state_health": health,
        "channels": chans,
        "partial": missing,
    }


def render_card(s):
    """Token-cheap plain-text card for /ops."""
    L = []
    dot = {"ALIVE": "🟢", "PARTIAL": "🟡", "DEGRADED": "🔴"}.get(s["status"], "⚪")
    L.append(f"{dot} AEGIS OPS — {s['status']}   ({s['date']})")
    hc = s["state_health"]
    if "dyncap" in hc:
        L.append(f"  dynCap ${hc['dyncap'].get('usd')}  ·  {hc['dyncap'].get('open')} open  ·  {hc['dyncap'].get('marked_asof')}")
    if "historical_store" in hc:
        L.append(f"  hist store {hc['historical_store'].get('n_tickers')} tickers  ·  self-heal {hc['historical_store'].get('last_self_heal')}")
    L.append(f"  kernel {hc.get('kernel_commit')}")
    f = s["flow"]
    L.append(f"  layers today: {len(f['layers_touched'])} ran"
             + (f", {len(f['layers_not_touched'])} idle" if f['layers_not_touched'] else "")
             + (f"  ·  {f['incidents']} exception(s)" if f['incidents'] else ""))
    if f.get("headline"):
        L.append(f"  {f['headline']}")
    ch = s["channels"]
    if ch["active"] == "cowork":
        L.append("  alerts: cowork-native push (pilot)  ·  whatsapp/watchdog: post-migration")
    else:
        L.append(f"  alerts: whatsapp {'on' if ch['whatsapp'] else 'OFF'} · watchdog {'on' if ch['watchdog'] else 'OFF'}")
    if s["partial"]:
        L.append(f"  ⚠ PARTIAL — unavailable: {', '.join(s['partial'])}")
    return "\n".join(L)


def render_html(s):
    """Full dashboard. Reuses the flow card idiom from daily_flow_audit when present."""
    rows = "".join(
        f"<div class='row'><b>{l['loop']}</b><span>{l['when']}</span></div>" for l in s["loops"]
    )
    color = {"ALIVE": "#0ca30c", "PARTIAL": "#fab219", "DEGRADED": "#d03b3b"}.get(s["status"], "#898781")
    part = ("<p class='warn'>PARTIAL — unavailable: " + ", ".join(s["partial"]) + "</p>") if s["partial"] else ""
    return f"""<!DOCTYPE html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Aegis Ops — {s['date']}</title>
<style>body{{margin:0;background:#0d0d0d;color:#fff;font-family:system-ui,-apple-system,sans-serif;padding:18px;}}
h1{{font-size:18px;}} .pill{{color:{color};font-weight:700;}}
.card{{background:#1a1a19;border:1px solid rgba(255,255,255,.1);border-radius:12px;padding:14px;margin:12px 0;}}
.row{{display:flex;justify-content:space-between;padding:8px 0;border-top:1px solid #2c2c2a;font-size:14px;}}
.row:first-child{{border-top:none;}} .row span{{color:#898781;}} .warn{{color:#fab219;}}
.k{{color:#c3c2b7;font-size:13px;}}</style></head><body>
<h1>AEGIS — Operations · <span class="pill">{s['status']}</span> <span style="color:#898781;font-size:13px">{s['date']}</span></h1>
<div class="card"><div class="k">Scheduled loops</div>{rows}</div>
<div class="card"><div class="k">State health</div><pre style="white-space:pre-wrap">{json.dumps(s['state_health'], indent=2)}</pre></div>
<div class="card"><div class="k">Today's flow</div><pre style="white-space:pre-wrap">{json.dumps(s['flow'], indent=2)}</pre>{part}</div>
</body></html>"""


def _main(argv=None):
    args = argv if argv is not None else sys.argv[1:]
    day = None
    render = "--render" in args
    for a in args:
        if not a.startswith("-"):
            day = a
    s = assemble(day)
    print(render_card(s))
    if render:
        out = os.path.join(DATA, "eod", s["date"])
        os.makedirs(out, exist_ok=True)
        path = os.path.join(out, f"ops_status_{s['date']}.html")
        with open(path, "w") as f:
            f.write(render_html(s))
        print(f"\n[rendered] {path}")


if __name__ == "__main__":
    _main()
