"""The Crown read, shaped for whoever reads it next — a person or an LLM.

There are two different artifacts and conflating them would spoil both.

`output/crown_macro.json` is the RUNTIME record. It carries the full series —
252 heartbeat bars, 504 dispersion points, every strike in the gamma profile —
because the page draws charts from it and Daily Persist restores it after a
container recycle.

This one is the READING copy, published to Drive beside the daily export. It is
built for a committee member or a model opening it cold, so:

  * **The plain English comes first and wraps the data.** `read_me_first` is the
    whole reading in four fields. Everything below it is the evidence, in case
    someone wants to check a number.
  * **The series are dropped.** A model does not need 504 dispersion points to
    know the gap is closing, and pasting them into a prompt costs context that
    the sentence already bought.
  * **It says what it is.** `how_to_read` explains each block in the same plain
    words, so nobody has to have read the kernel to use the file.
  * **The limits travel with it.** A reader who does not know gamma was off, or
    that a market ran on an ETF proxy, will over-trust what they are holding.

The flip levels are flattened into one list on purpose. It is the only genuinely
actionable table in the layer, and a reader should not have to walk a nested
dict to find "the S&P turns seller below 7,014".
"""

from __future__ import annotations

ARTIFACT_NAME = "aqe_crown_macro.json"
ARTIFACT_VERSION = "1.0"

HOW_TO_READ = {
    "read_me_first": "The whole reading in plain English. If you only read one "
                     "block, read this one. Everything else is the evidence.",
    "the_call": "The allowed FAMILY of trade expressions and a multiplier on "
                "the PM's own risk budget. Never a ticker, never a position, "
                "never an order. The individual setup is the PM's choice.",
    "how_current": "Every source with its own date. The reading is only as "
                   "current as its oldest leg, whatever the generated time says.",
    "scenario": "Which cross-asset story best fits today. The score is the "
                "SHARE OF CONDITIONS MET, not a probability — nothing here was "
                "fitted or backtested and no base rate was measured.",
    "readings": "The four stages behind the call: breadth, positioning, "
                "volatility and divergence.",
    "what_changed": "Only the moves since the last run that would change what "
                    "a PM does. An empty list means today continues yesterday.",
    "what_is_coming": "Scheduled moments when the reading above can change. "
                      "Each carries what it tests, not a forecast.",
    "key_levels": "EVERY line in the sand this layer knows about, in one list "
                  "sorted nearest first. Most are NOT prices: a breadth ratio, "
                  "a volatility gap and a correlation percentile all have "
                  "levels that change the regime when they break. Rows with "
                  "kind='trend followers' are where systematic funds turn from "
                  "buyer to seller, and any row with quotable_as_contract "
                  "false carries a tracking fund's price rather than the "
                  "contract's.",
    "limits": "What was missing or degraded in this run. Read before trusting "
              "anything above.",
}


def _limits(crown: dict, scen: dict) -> list[str]:
    """What a reader must know before trusting the rest, in plain words."""
    out = list(crown.get("degraded") or [])
    if (crown.get("gamma") or {}).get("status") != "OK":
        out.append("No dealer-positioning reading today, so nothing here "
                   "accounts for option hedging flows.")
    if scen and scen.get("contested"):
        out.append("Two macro scenarios fit today's data almost equally well. "
                   "Treat the overlap between them as the honest read rather "
                   "than the winner.")
    out.append("A scenario score is the share of that story's conditions "
               "currently met. It is not a probability and was never fitted "
               "to history.")
    out.append("This layer does not size, does not name a ticker and places "
               "nothing. It produces a family of expressions and a multiplier "
               "on the PM's own risk budget.")
    return out


def build_llm_export(crown: dict, scenarios: dict | None = None) -> dict:
    """The reading copy. Pure — no network, no files, no recomputation."""
    crown = crown or {}
    scen = scenarios or {}
    pe = crown.get("plain_english") or {}
    dec = crown.get("decision") or {}
    expr = dec.get("expression") or {}
    hb = crown.get("heartbeat") or {}
    vol = crown.get("volatility") or {}
    disp = vol.get("dispersion") or {}
    corr = vol.get("corroboration") or {}
    cta = crown.get("cta") or {}
    cot = crown.get("cot") or {}
    gam = crown.get("gamma") or {}
    div = crown.get("divergence") or {}
    fresh = crown.get("freshness") or {}

    lead = scen.get("leading")
    lead_detail = next((s for s in (scen.get("scenarios") or [])
                        if s.get("scenario") == lead), {})

    return {
        "artifact": "aqe_crown_macro",
        "version": ARTIFACT_VERSION,
        "kernel_version": crown.get("kernel_version"),
        "what_this_is": (
            "The Nick Crown macro layer: positioning, breadth and regime read "
            "BEFORE any individual stock. It answers what kind of market this "
            "is, and therefore which family of trades is allowed today. It is "
            "deliberately separate from AQE's stock scanner and sector work."),
        "generated_at": crown.get("generated_at"),
        "status": crown.get("crown_status"),
        "status_means": {
            "OK": "every input was available",
            "DEGRADED": "it ran, but something was missing or on a substitute "
                        "source — see limits",
            "EARLY_EXIT": "breadth was too unclear to read, so the process "
                          "stopped on purpose. This is a result, not a failure",
            "UNAVAILABLE": "nothing could be computed",
        }.get(crown.get("crown_status")),

        # ── the plain English, wrapping everything below it ──
        "read_me_first": {
            "headline": pe.get("headline"),
            "why": pe.get("because") or [],
            "so_what": pe.get("so_what"),
            "what_would_change_it": pe.get("watch_for") or [],
            "caveats": pe.get("caveats") or [],
        },

        "the_call": {
            "expression_family": expr.get("family"),
            "match_quality": expr.get("match"),
            "size_multiplier": dec.get("size_multiplier"),
            "size_multiplier_means": (
                "Multiply the PM's OWN normal risk per trade by this. AQE does "
                "not size and does not know the book."),
            "how_the_size_was_reached": dec.get("size_derivation"),
            "structure": dec.get("recommended_structure"),
            "playbook": expr.get("playbook") or {},
            "conditions_met": expr.get("conditions_met") or [],
            "conditions_not_met": expr.get("conditions_unmet") or [],
        },

        "how_current": {
            "today": fresh.get("today"),
            "oldest_source": fresh.get("oldest_leg"),
            "oldest_source_days_behind": fresh.get("oldest_leg_days"),
            "newest_source": fresh.get("newest_leg"),
            "volatility_as_of": (fresh.get("volatility") or {}).get("as_of"),
            "positioning_as_of": (fresh.get("cot") or {}).get("as_of"),
        },

        "scenario": {
            "leading": lead,
            "score_share_of_conditions": lead_detail.get("score"),
            "coverage": lead_detail.get("coverage"),
            "contested": scen.get("contested"),
            "runner_up": scen.get("runner_up"),
            "reading": scen.get("reading"),
            "story": lead_detail.get("story"),
            "evidence_for": lead_detail.get("evidence") or [],
            "what_is_missing": lead_detail.get("missing_conditions") or [],
        },

        "readings": {
            "breadth": {
                "regime": hb.get("regime"),
                "means": {"broadening": "the average stock is keeping up with "
                                        "the index",
                          "narrowing": "a few large names are carrying the "
                                       "index while the average stock lags",
                          "neutral": "no clear lead either way"}.get(hb.get("regime")),
                "position_in_12_month_range": hb.get("range_position"),
                "days_in_this_regime": hb.get("days_in_regime"),
                "change_5d_pct": hb.get("change_5d_pct"),
                "change_20d_pct": hb.get("change_20d_pct"),
                "change_60d_pct": hb.get("change_60d_pct"),
                "confidence": hb.get("confidence"),
                "passed_the_gate": hb.get("passes_gate"),
            },
            "positioning": {
                "trend_funds": {
                    "bias": cta.get("overall_bias"),
                    "markets_read": cta.get("n_markets"),
                    "share_at_an_extreme": cta.get("flip_risk"),
                    "extreme_means": "how crowded the trade is. High is "
                                     "fragile, not confident.",
                    "size_dial": cta.get("size_adjustment"),
                    "by_sector": cta.get("sector_bias") or {},
                },
                "large_speculators": {
                    "as_of": cot.get("as_of"),
                    "crowded_long": cot.get("crowded_long") or [],
                    "crowded_short": cot.get("crowded_short") or [],
                    "note": "CFTC data covering Tuesday, published Friday, so "
                            "always at least three days old. It cannot time "
                            "anything.",
                },
                "option_dealers": {
                    "available": gam.get("status") == "OK",
                    "regime": gam.get("regime"),
                    "means": {"POSITIVE": "dealers damp moves — rallies get "
                                          "sold, dips get bought",
                              "NEGATIVE": "dealers amplify moves — expect "
                                          "bigger swings"}.get(gam.get("regime")),
                    "detail": {k: {kk: v.get(kk) for kk in
                                   ("spot", "total_gex", "gamma_flip",
                                    "flip_distance_pct", "call_wall",
                                    "put_wall", "assumption")}
                               for k, v in (gam.get("underlyings") or {}).items()},
                    "why_not": gam.get("reason"),
                },
            },
            "volatility": {
                "vix": vol.get("vix"),
                "single_stock_vol": disp.get("single_stock_vol"),
                "gap": disp.get("spread"),
                "gap_means": "how much more the average stock moves than the "
                             "index. A wide gap means the index is hiding what "
                             "individual names are doing.",
                "gap_vs_history": disp.get("percentile"),
                "gap_change_20d": disp.get("spread_20d_change"),
                "state": disp.get("state"),
                "state_means": {
                    "ELEVATED_RISING": "wide and still growing — this is the "
                                       "version that warns",
                    "ELEVATED_EASING": "wide but shrinking — the stress is "
                                       "leaving, so downside bets would be late",
                }.get(disp.get("state")),
                "measured_from": disp.get("basis"),
                "implied_correlation": corr.get("implied_correlation"),
                "term_structure": (vol.get("term_structure") or {}).get("shape"),
            },
            "divergence": {
                "warnings_lit": div.get("weight"),
                "which": div.get("types_fired") or [],
                "note": "No single warning is a reason to sell. They matter "
                        "when several point the same way as breadth.",
            },
        },

        # Crown's own letter leads with what shifted and what is scheduled.
        # Both belong above the evidence, not buried under it.
        "what_changed": (crown.get("what_changed") or {}).get("changes") or [],
        "what_is_coming": [
            {k: e.get(k) for k in ("date", "day", "time_et", "event", "kind",
                                   "what_it_tests")}
            for e in ((crown.get("calendar") or {}).get("events") or [])],
        "key_levels": ((crown.get("key_levels") or {}).get("levels") or []),
        "how_to_read": HOW_TO_READ,
        "limits": _limits(crown, scen),
    }


# ── writing and publishing ───────────────────────────────────────────────

def publish_reading_copy(crown: dict | None = None,
                         scenarios: dict | None = None,
                         *, write: bool = True, upload: bool = True) -> dict:
    """Build the reading copy, write it locally, and put it on Drive.

    Falls back to the artifacts on disk when called without arguments, so it can
    be re-run on its own after a pipeline step failed without re-running the
    whole layer.
    """
    import json

    from src.data.paths import OUTPUT_DIR

    if crown is None:
        from .daily import load_crown
        crown = load_crown()
    if scenarios is None:
        from src.macro.scenarios import load_scenarios
        scenarios = load_scenarios()
    if not crown:
        return {"ok": False, "reason": "no Crown read to publish"}

    payload = build_llm_export(crown, scenarios)
    text = json.dumps(payload, indent=2, ensure_ascii=False)
    out = {"ok": True, "filename": ARTIFACT_NAME, "bytes": len(text.encode())}

    if write:
        try:
            OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
            (OUTPUT_DIR / ARTIFACT_NAME).write_text(text, encoding="utf-8")
        except Exception as exc:  # noqa: BLE001
            out["ok"] = False
            out["reason"] = f"local write failed: {exc}"
            return out

    if upload:
        try:
            from src.data.drive_sync import _upload_file
            res = _upload_file(ARTIFACT_NAME, text)
            out["drive"] = "ok" if res.get("ok") else f"failed: {res.get('reason')}"
        except Exception as exc:  # noqa: BLE001
            out["drive"] = f"failed: {exc}"
    return out
