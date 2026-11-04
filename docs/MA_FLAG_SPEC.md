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

## 4. Proposed committee rule (PM decides; NOT built)
| Option | What happens to a `PENDING_TARGET` | Cost |
|---|---|---|
| **A. Flag only** (shipped) | Seats see it, the card shows it; the committee may still ADVANCE it | A seat can still vote a deal-pinned stock a momentum buy |
| **B. Flag + explicit M&A line (recommended)** | A `PENDING_TARGET` can only be slated if the rationale carries an explicit "M&A: ..." clause (verbatim from a seat's filed form); otherwise code caps it at HOLD-FOR-CONDITIONS | Small: one check in the slate step |
| **C. Auto-exclude** | `PENDING_TARGET` is removed from the slate; shown only as a flagged PASS row | A deal-arb idea can never be a pick, even deliberately |
I recommend **B**: it keeps the PM's discretion and makes the committee say what it is buying (the spread), not a momentum story.

## 5. Dry-run on the 4 Nov export
Run by `.github/workflows/ma-flag-dryrun.yml` (needs the FMP secret; the sandbox has no key). To be appended here with every flagged row
and its matched sentence once the workflow is on main and run.
