"""Generate the AQE data taxonomy from the code that actually emits the fields.

A hand-written field list is wrong the day after it is written. This reads the
authoritative sources instead and regenerates `docs/AQE_DATA_TAXONOMY.md`:

  * `drive_sync._FIELD_SCHEMA` / `_FIELD_GLOSSARY` — the export's own
    self-description, the same dicts that ship inside the daily JSON
  * `agentic_dictionary.FIELD_ENUMS` / `GLOSSARY_FILL` — the agentic layer that
    completes the glossary and enumerates every categorical field
  * `lens_consensus.LENS_GLOSSARY` and `LENSES`
  * `qs_spec`, `signal_radar`, `github_sync.DAILY_ARTIFACTS` — the frozen
    constants and the artifact list
  * a live `aqe_daily_export.json` when one is on disk, for the fields the
    static sources do not name

Every row records WHERE its definition came from, so a field documented only by
a sample file is visibly weaker evidence than one documented by the glossary.

Run:  python -m scripts.build_data_taxonomy
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "AQE_DATA_TAXONOMY.md"
SGT = ZoneInfo("Asia/Singapore")

# Where a field belongs in the reading order. First match wins, so order matters.
GROUPS: list[tuple[str, tuple[str, ...]]] = [
    ("Identity and rank", ("rank", "ticker", "source", "entry", "held",
                           "on_longlist", "on_elder", "on_qs", "in_ledger")),
    ("Composite scores", ("sc_momentum", "sc_momentum_raw", "sc_position",
                          "ptrs", "pipe_rank", "pipe_tier", "floor",
                          "sc_m_gates", "sc_m_gate_detail", "sc_p_gates",
                          "sc_p_gate_detail")),
    ("The five engines", ("flow", "energy", "structure", "mp", "elder",
                          "mp_state", "elder_5d", "elder_pattern",
                          "elder_context", "bq", "k39")),
    ("Structural bracket", ("bracket", "malformed_bracket", "atr_caution")),
    ("Levels and moving averages", ("ma_", "fib_", "last_pivot_high",
                                    "sma_distance_pct")),
    ("Volatility and relative strength", ("atr_14d", "vol_30d_ann", "beta_",
                                          "rvol", "rs_", "day_vol")),
    ("DETECT layer", ("structure_shift", "div_", "pin_bar", "inside_bar",
                      "pib_pattern", "choch_", "knn_", "mp_accel")),
    ("Signal Radar", ("runner_", "mover_subtype", "premove_")),
    ("Chart patterns", ("pattern", "candle_")),
    ("Lens consensus", ("lens",)),
    ("Quiet Strength", ("qs",)),
    ("Sector and thematic", ("gics_", "sector_", "thematic_")),
    ("Held-position health", ("hl_", "live_px", "unreal_usd")),
    ("FIP", ("fip_",)),
    ("Schema vocabulary", ("role", "side", "unit", "_convention",
                           "_decision_framework")),
    ("Engine subcomponents", ("subcomponents",)),
    ("Retired — documented, no longer emitted", ("atr_quarter",)),
]

# Fields the glossary still describes but the export no longer emits. Keeping
# the definition is right — an old file still has to be readable — but a reader
# must not shop from this list expecting today's export to carry them.
RETIRED = {
    "atr_quarter_stop": "mechanical stop, retired in favour of bracket.stop",
    "atr_quarter_risk_pct": "companion to atr_quarter_stop, retired with it",
}

BLOCKS = {
    "date": "Scan date, US market close.",
    "exported_at": "When this file was written (SGT).",
    "market": "One-line market descriptor.",
    "regime": "VIX bucket + Hurst regime detection, and the size ceiling it implies.",
    "intermarket": "Cross-asset context read.",
    "srm": "Sector Rotation Model — one row per GICS sector, graded.",
    "srm_signals": "Sector-level signals derived from the SRM grid.",
    "macro_weather": "The 7-instrument cross-asset direction read (TLT/UUP/HYG/IWM/GLD/CPER/USO).",
    "regime_stop_pct_ceiling": "Regime-implied ceiling on stop width, in percent.",
    "spy_roc_20d": "SPY 20-day rate of change — the benchmark move.",
    "thematic_baskets": "The 35 thematic baskets with grades and RRG position.",
    "sector_map_version": "Version stamp of the GICS sector map in force.",
    "sector_map_gaps": "Tickers the sector map could not classify. Empty is the goal.",
    "field_schema": "The export describing its own field types.",
    "field_schema_enums": "Every permitted value for each categorical field.",
    "field_glossary": "The export describing what each field means.",
    "held_positions_status": "live / cache_fallback / unknown — whether this run's PTJ fetch was genuinely fresh.",
    "held_positions": "The PM's live book, as read from the trade journal.",
    "held_book": "Portfolio hedge layer — beta-adjusted exposure, gap scenarios, sector weights.",
    "daily_list": "THE list. Every scored ticker with the full field set. Membership of Longlist / Elder / QS / ledger is a flag on the row, never a separate list.",
    "lens_ranking": "The same names ordered by how many lenses agree. A reading order, not a verdict.",
    "summary": "Counts and headline figures for the run.",
    "signal_radar": "Radar tag totals across the scored universe.",
    "data_quality": "Records carrying a null core field despite being scored. The loud-failure guard.",
    "_radar_pool": "Internal radar pool sample. Diagnostic, not a read.",
}


def _group_for(name: str) -> str:
    for label, prefixes in GROUPS:
        for p in prefixes:
            if name == p or name.startswith(p):
                return label
    return "Other"


def collect() -> dict:
    from src.data import drive_sync as D
    from src.data import github_sync as GH
    from src.engines import agentic_dictionary as AD
    from src.engines import lens_consensus as LC

    fields: dict[str, dict] = {}

    def add(name, *, kind=None, desc=None, enum=None, src=None):
        row = fields.setdefault(name, {"name": name, "kind": None, "desc": None,
                                       "enum": None, "sources": []})
        row["kind"] = row["kind"] or kind
        row["desc"] = row["desc"] or desc
        row["enum"] = row["enum"] or enum
        if src and src not in row["sources"]:
            row["sources"].append(src)

    for k, v in D._FIELD_SCHEMA.items():
        add(k, kind=str(v), src="export field_schema")
    for k, v in D._FIELD_GLOSSARY.items():
        add(k, desc=str(v), src="export field_glossary")
    for k, v in AD.GLOSSARY_FILL.items():
        add(k, desc=str(v), src="agentic glossary")
    for k, v in {**D._FIELD_SCHEMA_ENUMS, **AD.FIELD_ENUMS}.items():
        add(k, enum=list(v), src="enum set")
    for k, v in LC.LENS_GLOSSARY.items():
        add(k, desc=str(v), src="lens glossary")

    sample_path = ROOT / "aegis" / "output" / "aqe_daily_export.json"
    sample_meta = {}
    if sample_path.exists():
        try:
            ex = json.loads(sample_path.read_text(encoding="utf-8"))
            sample_meta = {"date": ex.get("date"),
                           "records": len(ex.get("daily_list") or []),
                           "path": str(sample_path.relative_to(ROOT))}
            for rec in (ex.get("daily_list") or [])[:50]:
                for k, v in rec.items():
                    add(k, kind=type(v).__name__ if v is not None else None,
                        src="observed in export")
        except Exception:  # noqa: BLE001
            pass

    return {"fields": fields, "sample": sample_meta,
            "lenses": list(LC.LENSES), "artifacts": list(GH.DAILY_ARTIFACTS),
            "subcomponents": AD.SUBCOMPONENT_DOCS,
            "folder": GH.OUTPUT_DIR_IN_REPO}


def render(data: dict) -> str:
    fields = data["fields"]
    by_group: dict[str, list] = {}
    for row in fields.values():
        by_group.setdefault(_group_for(row["name"]), []).append(row)

    order = [g for g, _ in GROUPS] + ["Other"]
    now = datetime.now(SGT).strftime("%Y-%m-%d %H:%M SGT")

    L = [
        "# AQE Data Taxonomy",
        "",
        "**Every data point AQE computes and every place it lands.**",
        "",
        f"Generated {now} by `scripts/build_data_taxonomy.py`. Do not hand-edit —",
        "regenerate it. Each row records where its definition came from, so a field",
        "known only from a sample file is visibly weaker evidence than one carried by",
        "the export's own glossary.",
        "",
        f"**{len(fields)} distinct fields** across "
        f"{len([g for g in by_group if by_group[g]])} groups.",
        "",
        "---",
        "",
        "## 1 · Where the data lands",
        "",
        f"One destination: **`{data['folder']}/`** in this repository. "
        "One copy of each file, overwritten in place, no dated filenames.",
        "",
        "| Artifact | What it carries |",
        "|---|---|",
    ]
    art_desc = {
        "aqe_daily_export.json": "The committee's read — every block in section 2.",
        "aqe_crown_macro.json": "Crown macro reading copy: plain English first, series stripped.",
        "crown_macro.json": "Crown runtime record, with the chart series.",
        "macro_scenarios.json": "The Crown x Macro Weather merge point — 7 ranked scenarios.",
        "qs_daily.json": "Quiet Strength standalone artifact.",
        "shortlist.json": "The pre-export shortlist.",
        "held_positions.json": "The PM's live book as read from the journal.",
        "aqe_sector_map.json": "GICS sector map, rich form.",
        "options_scan.json": "Universe CSP theta sweep.",
        "aqe_last_run.json": "Run marker the status bar reads.",
        "aqe_snapshot_meta.json": "When the runtime state snapshot was last written.",
    }
    for a in data["artifacts"]:
        L.append(f"| `{a}` | {art_desc.get(a, '—')} |")
    L += [
        "",
        "The heavy runtime state (`panel_daily`, `ma_panel`, `scores_daily`, `aqe.db`)",
        "is **not** in this folder. It rides in a GitHub release asset on the",
        "`state-snapshot` tag, because a daily binary of that size committed to the",
        "repo would grow git history permanently. See `docs/AQE_GITHUB_AS_STORE.md`.",
        "",
        "---",
        "",
        "## 2 · Export structure — the 25 top-level blocks",
        "",
        "| Block | What it is |",
        "|---|---|",
    ]
    for k, v in BLOCKS.items():
        L.append(f"| `{k}` | {v} |")

    L += [
        "",
        "### The one-list rule",
        "",
        "`daily_list` is the single list every surface reads. Longlist, Elder, QS,",
        "ledger and held are **flags on the row** (`on_longlist`, `on_elder`, `on_qs`,",
        "`in_ledger`, `held`), never parallel lists. Every row carries the identical",
        "AQE block from the same builder, so levels cannot disagree between lists.",
        "",
        "An **absent** `qs` key means QS could not evaluate that name. That is not the",
        "same as a poor QS score, and the two must not be read alike.",
        "",
        "---",
        "",
        "## 3 · Every field, by group",
        "",
    ]

    for group in order:
        rows = sorted(by_group.get(group, []), key=lambda r: r["name"])
        if not rows:
            continue
        L += [f"### {group} — {len(rows)} fields", "",
              "| Field | Type | Values | Meaning | Documented by |", "|---|---|---|---|---|"]
        for r in rows:
            enum = ("`" + "` · `".join(str(x) for x in r["enum"]) + "`") if r["enum"] else ""
            desc = (r["desc"] or "").replace("\n", " ").replace("|", "\\|")
            if len(desc) > 400:
                desc = desc[:397] + "…"
            if r["name"] in RETIRED:
                desc = f"**RETIRED** ({RETIRED[r['name']]}). {desc}"
            kind = f"`{r['kind']}`" if r["kind"] else ""
            L.append(f"| `{r['name']}` | {kind} | {enum} | {desc} | "
                     f"{', '.join(r['sources'])} |")
        L.append("")

    L += ["---", "", "## 4 · Engine subcomponents", "",
          "Each engine also exports its own breakdown under `subcomponents`, so a",
          "score can always be taken apart into the parts that made it.", ""]
    for grp, doc in (data["subcomponents"] or {}).items():
        L += [f"**`subcomponents.{grp}`** — {str(doc).strip()}", ""]

    L += ["---", "", "## 5 · The lens set", "",
          "Six lenses count toward the consensus; `extension` is present and",
          "**always null** by ruling, because the voices disagree on what extension",
          "means, so AQE prints the numbers and makes no call.", "",
          "Counting lenses: " + ", ".join(f"`{x}`" for x in data["lenses"]), ""]

    if data["sample"]:
        s = data["sample"]
        L += ["---", "", "## 6 · Provenance of this run", "",
              f"Static sources: the export's own `field_schema` / `field_glossary`,",
              f"the agentic dictionary, the enum sets and the lens glossary — all read",
              f"from code at generation time.", "",
              f"Sample file: `{s.get('path')}` — {s.get('records')} records, "
              f"scan date {s.get('date')}. Fields marked *observed in export* and",
              "nothing else are known only from that sample; if it is stale, they are",
              "the rows most likely to be out of date.", ""]

    return "\n".join(L) + "\n"


def main() -> None:
    data = collect()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(render(data), encoding="utf-8")
    print(f"wrote {OUT.relative_to(ROOT)} — {len(data['fields'])} fields")


if __name__ == "__main__":
    main()
