# M&A flag: a pending merger / acquisition / buyout is flagged wherever the name is picked (SPEC, 5 Nov 2026)

PM 2026-11-04 (relayed by the conductor). **Evidence:** ROKU, our only "agreed outright" ADVANCE on 4 Nov, has a definitive agreement for
Fox Corp to acquire it (announced 15 Jun 2026, ~$22B cash and stock; shareholders approved 14 Oct; close expected H1 2027; Roku's own
2 Nov release: "In light of the pending transaction, Roku will not host an earnings call"). A deal-pinned stock trades on the deal
spread, not momentum, so flow / energy / structure mean little, and the committee never saw it.

## 1. Data source (checked on our plan, 4 Nov)
| Source | Verdict |
|---|---|
| FMP `latest-mergers-acquisitions` | Works, but lists **SEC S-4 filings only** (stock-for-stock registrations): a cash deal like Fox/Roku does not appear. **Not used.** |
| FMP `news/stock` (per ticker, 120 days) | Works. ROKU returns the Business Wire release, Deadline "Shareholders approve Fox's $22 billion Roku acquisition", Wedbush "close in H1 2027". **This is the source.** |
| FMP profile | One call, only for the few flagged tickers, to read the company's short name for the target / buyer role. |

## 2. Fields (every row of `daily_list` and `held_positions`; nightly export)
* `ma_status`: `NONE` / `PENDING_TARGET` / `PENDING_ACQUIRER` / `PENDING_UNCLEAR` / `UNKNOWN`.
  **`UNKNOWN` = the scan failed for this ticker and is never shown as clean.** `PENDING_UNCLEAR` = a pending deal is in its news but the
  role could not be read.
* `ma_note`: the matched sentence + its date ("...a definitive agreement under which FOX will acquire Roku. (2026-11-02)").
* `ma_evidence`: `{headline, date, url, terms[], n_deal_items}`, so every flag can be audited in ten seconds.
* Top level: `ma_scan {scan_status ok|partial|failed, asof, n_scanned, n_failed, n_flagged, failed[]}`, `ma_pending [tickers]`, and
  `data_quality.ma_scan`. More than 10% failed = `partial`; all failed = `failed` (loud banner on the Cards, never an empty list).
* Rule (code, `src/data/ma_flag.py`): deal terms ("definitive agreement", "pending merger / acquisition / transaction", "will / to acquire",
  "to be acquired", "tender offer", "take-private", "buyout", "shareholders approve the merger", ...) in a headline or summary within 120
  days; a newer "completes the acquisition / merger" item clears it. Investor-filing noise ("Acquires 29,656 Shares of ...") never matches.
  Role: the company's own short name is read around the deal verb ("FOX will acquire **Roku**" = target; "**Fox** to acquire" = buyer).
* Cost: one FMP call per ticker per day (~260 + held, ~3.5 min at 80 calls/min), cached per ticker per day in `data/ma_flags.json`.

## 3. Where the flag shows (built)
1. Voice packets: `ma_status` + `ma_note` on the menus of the seven deciders (the seats SEE it).
2. Cards: red pill "M&A PENDING · being acquired" on the ADVANCE card, the HOLD row, the PASS row, the Top-20 table and the Detect-lens table,
   plus a sentence on the card ("A stock with a pending takeover trades on the deal spread...") and a page banner if the scan was not ok.
3. Alert cards (every digest card): headline "· 🔴 M&A PENDING (being acquired)" and a first line with the matched sentence.
4. The brief and the conductor's v3 lists tables read the same export field (their render is the conductor's; the field is there).

## 4. Committee rule: SIGNED by the PM 2026-11-04 (ruling R44), built
* A slated ticket with `ma_status == PENDING_TARGET` is **excluded from ADVANCE by code** in `ratify-count` (not a voice judgment): status
  `DEAL_PINNED`, verdict `PASS`, whatever the vote; WATCH is excluded too ("never a buy card"). It carries the M&A line and the verdict it
  would have had, and is not eligible for the committee rationale.
* Cards: own small section **"Deal-pinned, not a momentum pick"** with the M&A line; never a buy card; the lists tables show the red pill.
* Alerts: **no buy trigger is armed** for it, committee row or AQE-list row alike: one label-only card "DEAL-PINNED, no buy trigger". A HELD
  position keeps its stop / exit cards.
* `PENDING_ACQUIRER` and `PENDING_UNCLEAR` are flag-only (pill, line), no exclusion.
* Safety: if the export carries no `ma_status` (older export) or is missing, the exclusion is NOT applied and `ratify-count` prints that
  loudly; a missing scan never reads as a clean name.

## 5. Dry-run on the 4 Nov export
Run by `.github/workflows/ma-flag-dryrun.yml` (needs the FMP secret; the sandbox has no key). To be appended here with every flagged row
and its matched sentence once the workflow is on main and run.
