"""One call for the Nick Crown Macro Layer. Degrades loudly, never silently.

    from src.macro.crown.daily import run_crown
    read = run_crown()

`crown_status` is the field to read first:

    OK          every leg sourced
    DEGRADED    the process ran, but at least one leg is missing or on a proxy
    EARLY_EXIT  Heartbeat confidence below the gate — §5 stopped the process,
                which is a RESULT, not a failure
    UNAVAILABLE the Heartbeat itself could not be built; nothing was computed

`degraded` lists what is missing in plain words. AQE's standing rule is that a
failed fetch must be loud (CLAUDE.md), and this layer has more ways to be
partially blind than any other in the system — a gamma map with no open interest
and a market with genuinely flat dealer positioning produce very similar-looking
zeros, and only one of them means anything.

This layer is STANDALONE by directive (2026-08-09). It does not read SRM, Macro
Weather or the Thematic RRG, and it writes nothing they consume. Merging and
de-duplicating against them is a later, separate decision — and keeping them
apart for now is what makes the overlap measurable rather than assumed.
"""

from __future__ import annotations

import json
from datetime import datetime
from zoneinfo import ZoneInfo

from src.data.paths import OUTPUT_DIR
from . import cot as cot_mod
from . import cta as cta_mod
from . import data as feeds
from . import divergence as div_mod
from . import gamma as gamma_mod
from . import heartbeat as hb_mod
from . import kernel as kernel_mod
from . import spec as S
from . import vol as vol_mod

SGT = ZoneInfo("Asia/Singapore")
CROWN_JSON = OUTPUT_DIR / "crown_macro.json"


def run_crown(*, client=None, refresh_cot: bool = True,
              with_gamma: bool = True, write: bool = True) -> dict:
    """Run the hierarchy end to end and return the full Crown read."""
    degraded: list[str] = []

    # ── 1. Heartbeat ──────────────────────────────────────────────────────
    rsp, spy, missing = feeds.heartbeat_bars(client)
    if missing:
        degraded.append(f"heartbeat bars missing: {', '.join(missing)}")
    heartbeat = hb_mod.heartbeat_from_frames(rsp, spy)

    if heartbeat.get("observations", 0) == 0:
        return _envelope("UNAVAILABLE", heartbeat, {}, {}, {}, {},
                         {"checklist_pass": False, "early_exit": True,
                          "expression": {"family": "NONE", "match": "none",
                                         "playbook": S.EXPRESSION_FAMILIES["NONE"]},
                          "recommended_structure": "none", "size_multiplier": 0.0,
                          "size_derivation": "no heartbeat",
                          "final_rationale": "Heartbeat could not be built",
                          "stopped_at": "heartbeat", "messages": []},
                         degraded + ["heartbeat unavailable — nothing computed"],
                         write)

    # ── 2. the gate. Below it, §5 stops. So do we. ────────────────────────
    if not heartbeat.get("passes_gate"):
        decision = kernel_mod.run(heartbeat, {}, {}, {}, {})
        return _envelope("EARLY_EXIT", heartbeat, {}, {}, {}, {}, decision,
                         degraded, write)

    # ── 3. positioning: CTA, COT, gamma ───────────────────────────────────
    fut, fut_missing = feeds.futures_bars(client)
    if fut_missing:
        degraded.append(f"CTA markets without bars: {', '.join(fut_missing)}")
    cta_read = cta_mod.analyse(fut) if fut else {
        "flow": cta_mod.cta_flow_analysis({}), "markets": {}}

    if refresh_cot:
        st = cot_mod.refresh()
        if not st.get("ok"):
            degraded.append(f"COT refresh failed: {st.get('reason')}")
        elif not st.get("weekly_ok"):
            degraded.append("COT weekly file unavailable — using archived history only")
    cot_read = cot_mod.analyse()
    if cot_read.get("status") != "OK":
        degraded.append(f"COT unavailable: {cot_read.get('reason')}")

    gamma_read = {"status": "SKIPPED", "regime": "UNKNOWN", "underlyings": {},
                  "unavailable": {}, "reason": "gamma not requested"}
    if with_gamma:
        chains, chain_bad = feeds.fetch_gamma_chains(client=client)
        gamma_read = gamma_mod.analyse(chains)
        if chain_bad:
            gamma_read.setdefault("unavailable", {}).update(chain_bad)
        if gamma_read.get("status") != "OK":
            degraded.append(f"gamma unavailable: {gamma_read.get('reason')}")

    # ── 4. volatility regime ──────────────────────────────────────────────
    vixes = feeds.vix_bars(client)
    vol_read = vol_mod.analyse(
        vix=vixes.get("vix"), vixeq=vixes.get("vixeq"),
        vix3m=vixes.get("vix3m"), vix9d=vixes.get("vix9d"),
        dspx=vixes.get("dspx"), cor1m=vixes.get("cor1m"),
        panel=feeds.panel_for_dispersion(), spy=spy)
    vol_read["source"] = vixes.get("source")
    if vixes.get("unavailable"):
        degraded.append("volatility series unavailable: "
                        + ", ".join(vixes["unavailable"]))
    if vol_read.get("status") == "DEGRADED_REALISED_PROXY":
        degraded.append("dispersion fell back to the REALISED proxy — the Cboe "
                        "VIXEQ series could not be fetched")
    corr = vol_read.get("corroboration") or {}
    if corr.get("agrees") is False:
        degraded.append("DSPX and implied correlation disagree with the "
                        "VIXEQ-VIX spread — treat the dispersion read with caution")
    elif vol_read.get("status") != "OK":
        degraded.append(f"volatility regime unavailable: {vol_read.get('reason')}")

    # ── 5. divergence ─────────────────────────────────────────────────────
    confirmers = {}
    for name in S.DIV_CONFIRMERS:
        if name in fut:
            confirmers[name] = fut[name]
        else:
            bars = feeds.fetch_bars(name, client=client)
            if len(bars):
                confirmers[name] = bars
    div_read = div_mod.analyse(
        spy, confirmers=confirmers,
        cot_reading=(cot_read.get("markets") or {}).get("ES"))
    if not confirmers:
        degraded.append("no cross-asset confirmers available")

    # ── 6. the decision ───────────────────────────────────────────────────
    decision = kernel_mod.run(heartbeat, cta_read.get("flow", {}), gamma_read,
                              vol_read, div_read)

    status = "OK" if not degraded else "DEGRADED"
    return _envelope(status, heartbeat, cta_read, cot_read, gamma_read,
                     {"vol": vol_read, "divergence": div_read}, decision,
                     degraded, write)


def _envelope(status, heartbeat, cta_read, cot_read, gamma_read, extra,
              decision, degraded, write) -> dict:
    out = {
        "layer": "Nick Crown Macro Layer",
        "kernel_version": "1.4",
        "crown_status": status,
        "degraded": degraded,
        "generated_at": datetime.now(SGT).isoformat(timespec="seconds"),
        "hierarchy": list(S.HIERARCHY),
        "heartbeat": heartbeat,
        "cta": cta_read.get("flow", {}) if cta_read else {},
        "cta_markets": cta_read.get("markets", {}) if cta_read else {},
        "cot": cot_read or {},
        "gamma": gamma_read or {},
        "volatility": (extra or {}).get("vol", {}),
        "divergence": (extra or {}).get("divergence", {}),
        "decision": decision,
        "standalone_note": (
            "Built standalone by PM directive (2026-08-09). Reads nothing from "
            "SRM / Macro Weather / Thematic RRG and feeds nothing to them. "
            "Merge and de-dup is a later decision."),
    }
    if write:
        try:
            OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
            CROWN_JSON.write_text(json.dumps(out, indent=2, ensure_ascii=False),
                                  encoding="utf-8")
        except Exception as exc:
            print(f"[crown] could not write {CROWN_JSON}: {exc}", flush=True)
    return out


def load_crown() -> dict | None:
    """The last written Crown read, for the UI to render without re-running."""
    if not CROWN_JSON.exists():
        return None
    try:
        return json.loads(CROWN_JSON.read_text(encoding="utf-8"))
    except Exception:
        return None


if __name__ == "__main__":       # pragma: no cover
    r = run_crown()
    print(f"crown_status = {r['crown_status']}")
    for m in r["decision"].get("messages", []):
        print("  " + m)
    for d in r["degraded"]:
        print("  ! " + d)
