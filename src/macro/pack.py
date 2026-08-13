"""One Macro Pack — the fifth, read-only door onto Crown/Macro Weather/SRM/
Thematic Rotation.

PM-signed proposal: docs/AQE_MACRO_PACK_PROPOSAL.md. Read that first — this
module is the implementation of exactly what it describes, nothing more.

**What this is not.** Not a merge of Crown, SRM, Macro Weather or Thematic
Rotation — every one of those stays exactly as it is, including Crown's
standalone status. This reads their FINISHED outputs and adds exactly one new
computation. It never imports `srm.py` into `crown/`, never imports Crown into
`srm.py`, and never feeds anything back into any of the four. Same
non-invasive pattern `scenarios.py` already uses for Crown — this sits beside
that module, not inside `crown/`.

**The one new thing: scenario-sector coherence.** The leading scenario
(computed by `scenarios.py`) names which macro instruments it needs moving,
and in which direction (`SCENARIOS[name]["conditions"]`). SRM already has a
signed sensitivity vector for each sector ETF against those same instruments
(`srm.SENSITIVITY`, built for `compute_macro_headwind`). Multiplying the two
gives a per-sector directional lean the story implies — compared against the
sector's own current grade, that is AGREES / DISAGREES / UNTESTED. Nothing
fitted, nothing scored beyond a category. AQE prints where the picture agrees
with itself and where it doesn't; it does not decide what that means.

**crown_status governs everything downstream, exactly as it does for Crown
alone.** On EARLY_EXIT/UNAVAILABLE, sector_read/thematic_read are ABSENT from
the artifact — not empty — because there is no leading scenario to derive
coherence from when Crown never produced a regime read. See `_gate()`.
"""

from __future__ import annotations

import json
from datetime import datetime
from zoneinfo import ZoneInfo

_SGT = ZoneInfo("Asia/Singapore")

ARTIFACT_NAME = "aqe_macro_pack.json"

# Grades read as directionally bullish / bearish for coherence purposes.
# TURNING and NO_DATA are deliberately excluded — an already-transitional or
# absent grade is not asked to agree or disagree with anything; it reads as
# UNTESTED rather than forcing a call on a name mid-transition.
_BULLISH_GRADES = {"DEPLOY", "HOLD"}
_BEARISH_GRADES = {"WATCH", "AVOID"}


def _sgt_now() -> str:
    return datetime.now(_SGT).isoformat(timespec="seconds")


# ── coherence: the one new computation ───────────────────────────────────

def _scenario_bias(conditions: list[tuple], sensitivity: list[int],
                   instruments: list[str]) -> float | None:
    """Net directional lean the scenario implies for one sector ETF.

    sum over the scenario's own macro-instrument conditions of
    weight * (+1 if expected=='up' else -1) * sensitivity[instrument_index].
    None when no condition in the scenario maps to an instrument this sector
    has a nonzero sensitivity to — genuinely untested, not a weak zero.
    """
    idx = {inst: i for i, inst in enumerate(instruments)}
    total, touched = 0.0, False
    for source, key, expected, weight in conditions:
        if source != "macro" or key not in idx:
            continue                      # COPPER_GOLD and non-macro
        se = sensitivity[idx[key]]        # sensitivity to this sector
        if se == 0:
            continue
        touched = True
        sign = 1.0 if expected == "up" else -1.0
        total += weight * sign * se
    return total if touched else None


def _grade_reads_as(grade: str | None) -> str | None:
    if grade in _BULLISH_GRADES:
        return "bullish"
    if grade in _BEARISH_GRADES:
        return "bearish"
    return None                            # TURNING, NO_DATA, missing


def _coherence_row(name: str, grade: str | None, gate: str | None,
                   conditions: list[tuple], sensitivity: list[int] | None,
                   instruments: list[str], extra: dict | None = None) -> dict:
    row = {"name": name, "grade": grade, "gate": gate, **(extra or {})}
    bias = (_scenario_bias(conditions, sensitivity, instruments)
           if sensitivity is not None else None)
    reads_as = _grade_reads_as(grade)
    if bias is None or reads_as is None:
        row["coherence"] = "UNTESTED"
        row["coherence_reason"] = (
            "no clear sensitivity read for this sector against the leading "
            "scenario's own conditions" if bias is None else
            f"grade is {grade}, not a directional read to test")
        return row
    implies = "tailwind" if bias > 0 else "headwind"
    agrees = (implies == "tailwind" and reads_as == "bullish") or \
             (implies == "headwind" and reads_as == "bearish")
    row["coherence"] = "AGREES" if agrees else "DISAGREES"
    row["coherence_reason"] = (
        f"scenario implies a {implies} for this sector (bias {bias:+.2f}); "
        f"grade reads {reads_as}")
    return row


def _sector_read(srm_rows: list[dict], leading_conditions: list[tuple],
                 sensitivity_map: dict, instruments: list[str]) -> list[dict]:
    rows = [
        _coherence_row(
            r.get("etf") or r.get("sector"), r.get("grade"), r.get("entry_gate"),
            leading_conditions, sensitivity_map.get(r.get("etf")), instruments,
            extra={"sector_name": r.get("sector"),
                  "rrg_quadrant": r.get("rrg_quadrant")})
        for r in (srm_rows or [])
    ]
    order = {"DISAGREES": 0, "AGREES": 1, "UNTESTED": 2}
    rows.sort(key=lambda r: order.get(r["coherence"], 3))
    return rows


def _thematic_read(basket_rows: list[dict], leading_conditions: list[tuple],
                   sensitivity_map: dict, instruments: list[str]) -> list[dict]:
    """Same tagging, one level down. A basket has no sensitivity vector of
    its own — it inherits its parent GICS sector's, so the row states plainly
    that this is 'does the theme agree with what the story implies for its
    PARENT sector', not a theme-specific macro read."""
    rows = []
    for b in (basket_rows or []):
        parent = b.get("parent_gics")
        row = _coherence_row(
            b.get("basket"), b.get("grade"), None,
            leading_conditions, sensitivity_map.get(parent), instruments,
            extra={"parent_gics": parent})
        row["coherence_reason"] = (
            row["coherence_reason"] + f" (inherited from parent sector {parent})"
            if row["coherence"] != "UNTESTED" or parent else row["coherence_reason"])
        rows.append(row)
    order = {"DISAGREES": 0, "AGREES": 1, "UNTESTED": 2}
    rows.sort(key=lambda r: order.get(r["coherence"], 3))
    return rows


# ── gate: crown_status governs the whole artifact ────────────────────────

def _gate(crown: dict, scenarios_read: dict) -> tuple[str, str | None]:
    """(pack_status, reason). PARTIAL means sector_read/thematic_read will be
    ABSENT from the artifact — never present-but-empty."""
    crown_status = (crown or {}).get("crown_status", "UNAVAILABLE")
    if crown_status in ("EARLY_EXIT", "UNAVAILABLE"):
        return "PARTIAL", (
            "Crown's own gate stopped the process this run — no regime read, "
            "so no sector coherence either." if crown_status == "EARLY_EXIT" else
            "Crown produced no read this run — the Heartbeat itself could not "
            "be built, so there is nothing to check sector grades against.")
    if not scenarios_read or scenarios_read.get("status") != "OK" \
            or not scenarios_read.get("leading"):
        return "PARTIAL", (
            "No scenario currently leads (either no clean macro story is "
            "expressing, or the scenario read itself is unavailable) — "
            "sector coherence needs a leading scenario to compare against.")
    if crown_status == "DEGRADED":
        return "DEGRADED", None
    return "OK", None


# ── assembly ──────────────────────────────────────────────────────────────

def _read_me_first(crown: dict, scenarios_read: dict, pack_status: str,
                   reason: str | None, n_disagree: int, n_agree: int) -> str:
    crown_pe = (crown or {}).get("plain_english") or {}
    headline = crown_pe.get("headline") or "No Crown regime read available."
    if pack_status == "PARTIAL":
        return f"{headline} {reason}"
    leading = scenarios_read.get("leading")
    reading = scenarios_read.get("reading", "")
    coherence_bit = (
        f" {n_disagree} sector{'s' if n_disagree != 1 else ''} currently "
        f"disagree with that story, {n_agree} agree."
        if (n_disagree or n_agree) else
        " No sector currently has a clear enough macro sensitivity to test "
        "against this story.")
    contested_bit = " Two stories fit the tape about equally." \
        if scenarios_read.get("contested") else ""
    return f"{headline} Leading scenario: {leading}.{contested_bit}{coherence_bit}"


def _diff_pack(today: dict, previous: dict | None) -> dict:
    """What moved since the last pack, in Crown's changes.py spirit: only
    report what would change a decision, and silence is a real answer."""
    if not previous:
        return {"available": False, "changes": [],
                "note": "No previous pack to compare against."}
    out: list[str] = []
    t_lead = today.get("scenario", {}).get("leading")
    p_lead = previous.get("scenario", {}).get("leading")
    if t_lead != p_lead and p_lead:
        out.append(f"Leading scenario flipped from {p_lead} to {t_lead}.")
    t_status, p_status = today.get("pack_status"), previous.get("pack_status")
    if t_status != p_status:
        out.append(f"Pack status moved from {p_status} to {t_status}.")
    t_dis = {r["name"] for r in (today.get("sector_read") or [])
            if r["coherence"] == "DISAGREES"}
    p_dis = {r["name"] for r in (previous.get("sector_read") or [])
            if r["coherence"] == "DISAGREES"}
    newly = t_dis - p_dis
    resolved = p_dis - t_dis
    if newly:
        out.append(f"Newly disagreeing with the leading scenario: "
                   f"{', '.join(sorted(newly))}.")
    if resolved:
        out.append(f"No longer disagreeing: {', '.join(sorted(resolved))}.")
    return {"available": True, "changes": out,
           "note": "" if out else "Nothing that changes a decision moved."}


def build_pack(crown: dict | None, scenarios_read: dict | None,
              srm_rows: list[dict] | None,
              basket_rows: list[dict] | None,
              previous: dict | None = None) -> dict:
    """Assemble the pack from four already-finished reads. Pure function —
    no I/O, no network. Every input is a dict/list already produced elsewhere;
    this never recomputes any of them."""
    from src.engines.srm import MACRO_INSTRUMENTS, SENSITIVITY

    crown = crown or {}
    scenarios_read = scenarios_read or {}
    pack_status, reason = _gate(crown, scenarios_read)

    out: dict = {
        "artifact": "aqe_macro_pack",
        "generated_at": _sgt_now(),
        "pack_status": pack_status,
        "crown_status": crown.get("crown_status", "UNAVAILABLE"),
        "oldest_leg": (crown.get("freshness") or {}).get("oldest_leg"),
        "what_this_is": (
            "One read assembled from four already-independent systems — "
            "Crown (regime/positioning/volatility), the Macro Weather x Crown "
            "scenario read, SRM sector grades and Thematic Rotation. Nothing "
            "here is a new gate or a new score beyond one thing: whether a "
            "sector's or theme's current grade agrees with what the leading "
            "scenario implies for it."),
    }

    n_agree = n_disagree = 0
    if pack_status != "PARTIAL":
        leading = scenarios_read["leading"]
        conditions = _SCENARIOS_LOOKUP()[leading]["conditions"]
        sector_read = _sector_read(srm_rows or [], conditions, SENSITIVITY,
                                   MACRO_INSTRUMENTS)
        thematic_read = _thematic_read(basket_rows or [], conditions,
                                       SENSITIVITY, MACRO_INSTRUMENTS)
        n_agree = sum(1 for r in sector_read if r["coherence"] == "AGREES")
        n_disagree = sum(1 for r in sector_read if r["coherence"] == "DISAGREES")
        out["sector_read"] = sector_read
        out["thematic_read"] = thematic_read
    # PARTIAL: sector_read/thematic_read are simply absent — never an empty list.

    out["read_me_first"] = _read_me_first(crown, scenarios_read, pack_status,
                                          reason, n_disagree, n_agree)
    out["crown"] = crown.get("plain_english") or {}
    out["scenario"] = {
        k: scenarios_read.get(k)
        for k in ("leading", "leading_score", "runner_up", "contested",
                  "reading", "note", "scenarios")
    } if scenarios_read else {}

    limits = list((crown.get("plain_english") or {}).get("caveats") or [])
    limits += [f"Crown: {d}" for d in (crown.get("degraded") or [])]
    limits += [f"Scenario: {d}" for d in (scenarios_read.get("degraded") or [])]
    if pack_status == "PARTIAL":
        limits.insert(0, reason)
    limits += [
        "This pack does not size. It reports agreement/disagreement only.",
        "This pack does not name a ticker. Sector and theme rows are the "
        "finest grain.",
        "Coherence is a category (AGREES/DISAGREES/UNTESTED), never a "
        "probability — same rule as the scenario scores it is built from.",
    ]
    out["limits"] = limits
    out["what_changed"] = _diff_pack(out, previous)
    return out


def _SCENARIOS_LOOKUP() -> dict:
    from src.macro.scenarios import SCENARIOS
    return SCENARIOS


# ── I/O — reading finished artifacts, writing the pack ───────────────────

def run_pack(write: bool = True) -> dict:
    """Read Crown, the scenario read, and the day's SRM/thematic grades from
    their already-written artifacts, and assemble the pack. Must run AFTER
    the main daily export (srm[]/thematic_baskets[] live there) and after
    Crown + scenarios have already written their own artifacts."""
    from src.data.paths import OUTPUT_DIR
    from src.macro.crown.daily import load_crown
    from src.macro.scenarios import load_scenarios

    crown = load_crown()
    scenarios_read = load_scenarios()

    srm_rows: list[dict] = []
    basket_rows: list[dict] = []
    export_path = OUTPUT_DIR / "aqe_daily_export.json"
    if export_path.exists():
        try:
            export = json.loads(export_path.read_text(encoding="utf-8"))
            srm_rows = export.get("srm") or []
            seen: set = set()
            for rec in (export.get("daily_list") or []):
                for b in (rec.get("thematic_baskets") or []):
                    key = b.get("basket")
                    if key and key not in seen:
                        seen.add(key)
                        basket_rows.append(b)
        except Exception as exc:  # noqa: BLE001
            print(f"[pack] could not read daily export: {exc}", flush=True)

    previous = load_pack()
    out = build_pack(crown, scenarios_read, srm_rows, basket_rows, previous)

    if write:
        try:
            OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
            (OUTPUT_DIR / ARTIFACT_NAME).write_text(
                json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
        except Exception as exc:  # noqa: BLE001
            print(f"[pack] could not write artifact: {exc}", flush=True)
    return out


def load_pack() -> dict | None:
    """The last written pack, for the UI to render without re-running."""
    from src.data.paths import OUTPUT_DIR

    p = OUTPUT_DIR / ARTIFACT_NAME
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return None
