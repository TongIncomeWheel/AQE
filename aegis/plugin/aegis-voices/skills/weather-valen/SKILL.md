---
name: weather-valen
description: READING CARD, not a voice — how the PMA reads AQE's Valen dashboard (aqe_valen_dashboard.json) and the export's Valen rows (setups, U&R) for the Daily Weather, the house setups and the no-buy list. Valen never had a voice file; this card makes his rules persistent (PM memory, extracted 2026-11-01). Loaded by the brief-writer at WRITE and by the Cards renderer. Stance is a READING, never a size. Source of truth: ../weather_spec_2026-11-01.md §3.
---
# WEATHER — VALEN: the VIV System weather, house setups, no-buy list

**I am a reading source, not a seat.** The PM's target model for the daily report (PM 2026-10-23: "I want to see it take
space"). Book: *The VIV System: 21 Building Blocks to Profitability* (v1.3, Sep 2026). AQE ports three parts: **Part 1 the
weather** (check the market first; one word sets how hard to push; never picks the stock), **Part 3 the house** (five measured
setups graded against his own checklists), **the no-buy list** (one yes means no). His order: stance → headline → groups → charts. "Never before."
Full specification: `aegis-voices/skills/weather_spec_2026-11-01.md` §3; this card is the operating cut.

## Function (plain rules)
| Piece | Rule |
|---|---|
| Stance | RISK ON / NEUTRAL / RISK OFF + one line why. Changes on rules, "never on a feeling, never on one session" |
| Trend regime | SPY daily buy (above 10- and 20-day, 10 above 20), weekly buy, above a rising 5-day. All yes UPTREND · all no DOWNTREND · mixed **CHOP** ("chop is where breakouts get sold") |
| Extension | SPY/QQQ distance from the 50-day in ATRs (~6 extreme for an index). VIX/VIX3M: < 0.82 calm, > 1.00 stress |
| Checklist | Net new highs (8d vs 20d), today's 4% count, 5-day count ≥ 1.00, month 25% count. "More yes, more size." Net new highs alone decides how open trades are managed |
| Instruments | 5- and 10-day 4% ratios (0.50 / 1.00 / 2.00), T2108 (< 20 washed out, > 80 overheated, > 50 for risk-on), big movers |
| What would change it | To positive: T2108 > 50, monthly risers > 350, 5-day count > 1.00. To negative: 5-day count < 0.70. Items already met are hidden |
| Groups and rotation | Themes on 1 week and 1 month; thrust = week − month; % off 52-week high. Leading = strong and near highs; Off the floor = 15–25% below highs, a lesser bounce |
| Five setups | VCP · high tight flag (only) · undercut-and-rally · episodic pivot + delayed EP · parabolic as a **long-only risk warning** |
| Other U&R supports | Gaps, trendlines, EMA9/EMA21, the swing low (PM 2026-10-08: "keep it simple") |
| No-buy list | Stretched (ATR-extended), earnings within 5 sessions, below the 200-day, … Flags per name, ⛔ on the card |

**U&R in the export (PM 2026-10-12):** `MET` = a support was undercut by a shallow dip and the last completed day closed back above it (the reclaim day); `SETUP` = undercut within 3 sessions, still under; `NA` = too little history, never a silent NO. The live alert uses the same rules.

## AQE data points
`aqe_valen_dashboard.json`: `read_me_first` (headline, because[], so_what = handbook doctrine, watch_for[], caveats, as_of) · `stance` (word, status, reason) · `regime` · `trend[]` (SPY/QQQ daily/weekly/5d signals) · `extension[]` · `breadth[]` (label, section, kind, value, display) · `gex` (regime, light, flip, walls, flip_distance_pct) · `crown_cockpit` · `history[]` (now / 5d / 1mo) · `neighbourhood[]` · `theme_leaders[]`, `rotation[]` · `selection` (relative_strength[], funnel, no_buy_list[]) · `house.setups[]` (grades: setup, status, pivot, stop, checks[]) · `execution` · `management.held_facts[]`.
On every `daily_list` / `held_positions` row: `setups[]`, `unr_status`, `unr_note`, `unr_as_of`, `unr_level`; top-level `unr_summary`.

## Guardrails (each one binding)
**Stance is a reading, never a size** — AQE exports the word; the handbook's sizing line is printed as *quoted doctrine*, "not an Aegis rule" · sizing stays the PM's (1R = $620, PM 2026-10-27) · population stated on every breadth read (AQE's ~800-stock panel, not the whole market) · the "350 monthly risers" flip is a whole-market number, never cited as reachable · **no levels to the voices** (the vote packet carries setup status and checklist pass counts only; pivots and stops never reach a voice) · missing = declared gap, in the packet and the Cards alike · U&R is one setup, not his entry rule: show only when MET or forming; **say nothing on NO or NA** · thresholds already met are dropped from "what would change it" · parabolic = warning only, never a short · reserved seats: up to 3 U&R-MET Longlist/Elder names no voice nominated are seated — "in the room on a reserved reclaim seat; no voice nominated it" · data is measured, not tuned (handbook thresholds with page cites; AQE's own measurements labelled AQE's).

## Writing style
First-person, short, rule-led, as in the handbook: "If the market check is not green, do not push." "One yes means no."
Quote the handbook as **doctrine**, never as an Aegis rule. Use his words: stance, chop, in-theme, leading vs off the floor,
reclaim day, washed out / overheated. Every figure with what it means for a momentum book today ("Read: …"). Never write
"Valen U&R NO" — silence is the correct output.

## Where I appear
Cards header `stance_pill` ("NEUTRAL · HALF SIZE" — stance + doctrine); Part 1 blocks 1 situational awareness, 2 GEX light,
5 direction of the wind (gauges, checklist, instruments), 6 weather turning, 7 theme leaders and rotation, 8 strong stocks
riding a group turn, the house-setups line; a Valen row on every ADVANCE card (setups, U&R words, ⛔); vote packet VALEN
block (no levels); brief §1A and the two §0 columns; RANK reserved seats. `cards_text.json → weather.{stance, gex, checklist,
turning, themes, groups}` — one "Read:" paragraph each (spec §4).
