# Crown in the daily run — and where the output goes

Three questions, answered in order: how it runs, what it writes, and what
survives a restart.

---

## 1 · The daily run already includes it

**No change to your command or your batch file.**

```
scripts\run_daily.bat          →  python -m src.pipeline.daily_orchestrator
```

Crown is **step 6f**, scenarios are **6g**, the reading copy is **6h**. All three
sit inside the same orchestrator, between the QS engine and the export build.
**The macro pack is step 8a-1** — it has to run after Step 8 has written
`aqe_daily_export.json` (SRM's sector grades and Thematic Rotation's basket
grades live there) and after Crown/scenarios have already written theirs, so
it sits later in the same run, not beside 6f-6h. In the cloud the same thing
happens automatically at **08:30 SGT Tue–Sat** through `daily_job.py`, with
the GitHub Action as a backstop.

You will see this in the run log:

```
[daily] Step 6f: Crown macro layer...
  status DEGRADED · heartbeat narrowing (conf 0.65) · family NARROWING_CONCENTRATED · size x1.00
[daily] Step 6g: Macro scenarios...
  leading DISPERSION_REGIME (100% of conditions) · runner-up REFLATION
[daily] Step 6h: Crown reading copy -> Drive...
  aqe_crown_macro.json: 14,066 bytes · Drive ok
...
[daily] Step 8a-1: Macro pack...
  Macro pack: OK (crown DEGRADED)
```

**The macro pack** (`docs/AQE_MACRO_PACK_PROPOSAL.md`, PM-signed 2026-08-13,
implementation in `src/macro/pack.py`) is a fifth, read-only module — it
does not change Crown, SRM, Macro Weather or Thematic Rotation, it reads
their finished output and adds exactly one new computation: whether each
sector's and theme's current grade agrees with what the leading scenario
implies for it. On `crown_status: EARLY_EXIT`/`UNAVAILABLE` its
`sector_read`/`thematic_read` are absent from the artifact entirely — same
discipline Crown itself uses, not smoothed into an empty list.

**Gamma is now ON in the daily run.** It was off while there was no working
open-interest feed. Each step is wrapped the same way QS is: a Crown failure
prints a warning and the pipeline carries on to build the export. It can never
take down the file your Longlist, Elder and held book ride on.

---

## 2 · What it writes, and which file an LLM should read

Three files, and they have different jobs. Reading the wrong one wastes context.

| File | Where | For | Size |
|---|---|---|---|
| **`aqe_crown_macro.json`** | `output/` **+ Drive** | **the committee and the AIC — read this one** | ~14 KB |
| `crown_macro.json` | `output/` only | the Streamlit page (carries the chart series) | ~250 KB |
| `macro_scenarios.json` | `output/` only | the scenario detail behind the summary | ~8 KB |

### `aqe_crown_macro.json` — the reading copy

It sits in the **same pinned Drive folder as `aqe_daily_export.json`**, so
wherever your committee already picks up the daily export, this is beside it.

The plain English comes **first and wraps everything below it**:

```json
{
  "what_this_is": "The Nick Crown macro layer: positioning, breadth and regime
                   read BEFORE any individual stock…",
  "status": "DEGRADED",
  "status_means": "it ran, but something was missing or on a substitute source",

  "read_me_first": {
    "headline": "A narrow market, calm on the surface but with single stocks
                 moving very differently underneath.",
    "why": [
      "A handful of big names are carrying the index — the average stock is
       falling behind.",
      "Single stocks are much more volatile than the index, but the gap is
       closing. It narrowed by 9.2 points over the last month…"
    ],
    "so_what": "Stay with the leaders. Keep the risk defined. Size at 1.00x
                your normal risk.",
    "what_would_change_it": [
      "If the S&P trades below 7,014.30 (9.9% away), trend funds start selling."
    ],
    "caveats": ["No dealer-positioning read today…"]
  },

  "the_call":      { "expression_family": …, "size_multiplier": …, "playbook": … },
  "how_current":   { "oldest_source": "2026-08-04", "oldest_source_days_behind": 6 },
  "scenario":      { "leading": …, "score_share_of_conditions": …, "evidence_for": [] },
  "readings":      { "breadth": …, "positioning": …, "volatility": …, "divergence": … },
  "flip_levels":   [ … sorted by nearness … ],
  "how_to_read":   { … what each block is, in the same plain words … },
  "limits":        [ … what was missing, and the four standing refusals … ]
}
```

**Four properties that make it usable by a model, each held by a test:**

1. **`read_me_first` is the whole reading.** A model that reads only that block
   has the answer. Everything below is evidence for checking a number.
2. **No chart series.** The runtime file carries 252 heartbeat bars and 504
   dispersion points; this one carries none. They buy a reader nothing the
   sentence has not already bought, and cost the context it needs. ~14 KB, about
   3,500 tokens — it fits in a prompt whole.
3. **It explains itself.** `how_to_read` describes every block, so nobody needs
   the kernel document to use the file.
4. **The limits travel with it.** A reader who does not know gamma was off, or
   that a market ran on a tracking fund, will over-trust what they are holding.

### `flip_levels` — the one actionable table

Flattened to a single list, **sorted by nearest first**, so nobody walks a nested
dict to find the trigger that matters:

```json
{ "market": "ZT", "name": "UST 2Y note",
  "price_now": 102.96, "flip_level": 103.65, "distance_pct": 0.67,
  "direction": "buy_above",
  "price_source": "yahoo_futures", "quotable_as_contract": true }
```

**`quotable_as_contract` is the field to respect.** When it is `false` the price
came from a tracking ETF: the direction is right, the level is the fund's, and
quoting it as a contract level would be quoting the wrong instrument.

---

## 3 · What survives a restart

All six pieces ride in the Daily Persist snapshot
(`aqe_state_snapshot.zip` on Drive):

| File | Why it must survive |
|---|---|
| `data/crown_cot.parquet` | The CFTC publishes once a week, so **this file IS the percentile window.** Lose it and every market reads "no history" instead of "crowded long" — a different answer wearing the same shape. |
| `data/crown_cboe.parquet` | The volatility complex and its percentile bands. |
| `output/crown_macro.json` | The page renders instantly instead of re-running the layer. |
| `output/macro_scenarios.json` | Scenario detail. |
| `output/aqe_crown_macro.json` | The reading copy, so it is there even if the Drive upload failed. |

`aqe_crown_macro.json` is also published to Drive on its own every run, so there
are two independent paths to it. The snapshot is the belt to that braces.

---

## Telling your AIC where to look

> The macro regime read is in **`aqe_crown_macro.json`**, in the same Drive
> folder as `aqe_daily_export.json`. Start with `read_me_first` — that is the
> whole reading. `flip_levels` is sorted nearest-first and is the actionable
> table; ignore any row where `quotable_as_contract` is false if you intend to
> quote a price. Check `limits` before trusting any of it, and `how_current` for
> how old the oldest input is. The layer produces a **family** of expressions and
> a **multiplier** on the PM's risk budget — never a ticker, never a size, never
> an order.
