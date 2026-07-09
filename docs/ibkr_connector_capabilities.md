# IBKR Connector — Full Capabilities Reference (Fixed Working Schemas)

> Complete reference for the **official Claude Interactive Brokers (IBKR) connector**.
> Every tool, field, enum, and constraint below is copied verbatim from the
> connector's published MCP tool schemas — treat this file as the source of truth for
> programming against the connector. All tool names are prefixed
> `mcp__Interactive_Brokers_IBKR__` (dropped in the tables for brevity).
>
> Companion doc: `docs/ibkr_connector_create_trade.md` (deep-dive on order creation).

---

## 0. Capability map

| Group | Tools | Mutating? |
|-------|-------|-----------|
| **Order instructions** | `create_order_instruction`, `get_order_instructions`, `delete_order_instruction`, `get_combo_identifier` | create/delete stage instructions (never live orders) |
| **Account & portfolio** | `get_account_summary`, `get_account_balances`, `get_account_positions`, `get_account_orders`, `get_account_trades`, `get_pa_allocation`, `get_pa_performance_all_periods` | read-only |
| **Market data** | `get_price_snapshot`, `get_price_history` | read-only |
| **Contract discovery** | `search_contracts`, `search_futures`, `get_option_parameters`, `get_option_data` | read-only |
| **Watchlists** | `get_watchlists`, `get_watchlist`, `create_watchlist`, `edit_watchlist`, `delete_watchlist` | create/edit/delete |
| **Research / themes** | `search_investment_topics`, `get_theme_details`, `get_company_themes`, `get_company_connections` | read-only |
| **Feedback** | `provide_customer_feedback` | submits feedback |

**Golden rules that hold across the whole connector:**

1. **No live-order placement.** The connector can only *stage* an instruction; a human
   submits it inside IBKR. There is no tool that places a live order autonomously.
2. **`contract_id_ex` / `contract_id` are internal identifiers** resolved from a lookup
   tool — never a raw ticker, never displayed to the user.
3. **ID chaining:** discovery → id → data/action. e.g.
   `search_contracts → underlying_contract_id → get_option_parameters → expiration id → get_option_data → contract_id_ex → create_order_instruction`.
4. Destructive tools (`delete_watchlist`, `delete_order_instruction`) require user
   confirmation first.

---

## 1. Order instructions

### 1.1 `create_order_instruction`
Stages an instruction (NOT a live order); returns a deep-link URL for the human to
review + submit in IBKR. Supports STK, FUT, single-leg OPT, single-leg FOP, and
OPT–OPT equity-option combos. **No** FOP/FUT/STK/mixed combos.

| Field | Type | Enum / format | Required | Notes |
|-------|------|---------------|----------|-------|
| `side` | string | `BUY` \| `SELL` | ✅ (only required) | |
| `contract_id_ex` | string | | ⚠️ effectively required | Full contract id; wins over `contract_id` |
| `contract_id` | integer | int64 | — | **deprecated** fallback |
| `quantity` | number | double | — | shares (STK) / contracts (FUT/OPT/FOP) |
| `order_type` | string | `MARKET` \| `LIMIT` | — | no STOP types |
| `limit_price` | number | double | — | with `LIMIT` |
| `time_in_force` | string | `DAY`\|`GTC`\|`OVT`\|`OND`\|`OPG` | — | defaults to system policy |

### 1.2 `get_order_instructions`
No args. Returns all saved instructions: id, description, `contract_id_ex`, side,
quantity, order type, limit price, time in force, creation time (ISO 8601), expiration.

### 1.3 `delete_order_instruction`
Deletes a staged instruction. Confirm with user first.

| Field | Type | Required |
|-------|------|----------|
| `id` | string | ✅ |

### 1.4 `get_combo_identifier`
Builds an OPT–OPT combo id **before** `create_order_instruction`. Equity-option legs
only (FOP/FUT/STK/mixed fail downstream). Returns `contract_id_ex` (pass to
`create_order_instruction`), `description`, `strategy_name`.

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `legs` | array of `{contract_id_ex: string, size: int32}` | ✅ | `size` > 0 = BUY leg, < 0 = SELL leg; `contract_id_ex` from `get_option_data` (OPT only) |

---

## 2. Account & portfolio (all read-only)

### 2.1 `get_account_summary` — no args
Account-level metrics: net liquidation value, equity with loan value, available funds,
buying power, initial & maintenance margin, day-trading status, etc.

### 2.2 `get_account_balances` — no args
Cash balances and market values broken down **per currency** (one entry per currency).

### 2.3 `get_account_positions` — no args
All open positions: quantity, price, market value, P&L, cost basis.

### 2.4 `get_account_orders` — no args
Live orders: order ID, symbol, side, order type, status, quantity, price, fill info.

### 2.5 `get_account_trades`
Executed-trade snapshot over a period. Each: trade ID, symbol, side, size, price,
commission, trade time. **All boundaries are UTC.**

| Field | Enum | Required | Default |
|-------|------|----------|---------|
| `period` | `TODAY`, `DAYS_7`, `DAYS_30`, `DAYS_60`, `DAYS_90`, `MONTH_TO_DATE`, `YEAR_TO_DATE`, `LAST_QUARTER`, `TWO_QUARTERS_AGO`, `THREE_QUARTERS_AGO`, `FOUR_QUARTERS_AGO` | — | `TODAY` |

### 2.6 `get_pa_allocation`
Portfolio NAV broken down along one dimension into long / short buckets (each `total` +
`items[]` with id, name, nav, weight). `short_positions` present only when shorts exist —
null-check it. Weights sum to 1.0 within each bucket. Long-side denominator is
category-dependent (do not assume a common base).

| Field | Type / Enum | Required | Notes |
|-------|-------------|----------|-------|
| `type` | `FINANCIAL_INSTRUMENT`\|`ASSET_CLASS`\|`SECTOR`\|`REGION`\|`COUNTRY`\|`ALL` | ✅ | `ALL` returns every dimension in one call |
| `currency` | string | — | default USD; **non-base currency silently switches to prior trading day, not live** |
| `date` | string yyyymmdd | — | omit for live; must be ≥ account inception |

### 2.7 `get_pa_performance_all_periods` — no args
Performance time series for every window (1D, 7D, MTD, 1M, YTD, 1Y). `cps`, `nav`,
`dates` are parallel arrays. `cps` = cumulative return **as fractions** (−0.106 = −10.6%).
`portfolio_measure` = `TWR` or `MWR`. Accounts <1yr: 1Y == YTD.

---

## 3. Market data (read-only)

### 3.1 `get_price_snapshot`
Real-time snapshot (live or delayed per the account's subscription; frozen not
supported). Default fields `['last','bid_ask']`. **Response keys are hyphenated**
(`option_midpoint_iv` → `option-midpoint-iv`).

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `contract_id` | int64 | ✅ | |
| `exchange` | string | — | Optional for SMART-eligible (US stocks/ETFs/equity options). **Mandatory for FUT/FOP** — pass native exchange (CME, CBOT, NYMEX, COMEX, EUREX…) or response is empty |
| `market_data_names` | array of enum | — | see below |

`market_data_names` enum (request underscored, read hyphenated): `bid_ask`, `last`,
`change`, `prior_close`, `plprice`, `dividend_yield`, `volume`, `option_volume`,
`option_open_interest`, `future_open_interest`, `option_midpoint_iv`,
`underlying_today_option_volume`, `underlying_avg_option_volume`, `misc_statistics`,
`avg_90d_usd_volume`, `implied_volatility_percentile`, `implied_vol_underlying`,
`implied_vol`, `historical_vol`, `year_to_date_change`, `bond_yield`,
`cumulative_perf_1d/1w/1m/ytd/1y/3y/5y`, `total_net_assets`, `open`, `low`, `high`,
`perpetual_futures_funding_rate`.

### 3.2 `get_price_history`
Historical OHLCV bars. **Provide `period` OR `step_count`, never both.**

| Field | Type / Enum | Required | Notes |
|-------|-------------|----------|-------|
| `contract_id` | int64 | ✅ | |
| `security_type` | `STK`,`OPT`,`FUT`,`FOP`,`CASH`,`WAR`,`BOND`,`CFD`,`FUND`,`IND`,`CRYPTO`,`CMDTY`,`IOPT` | ✅ | |
| `step` | `THIRTY_SECS`,`ONE_MIN`,`TWO_MINS`,`FIVE_MINS`,`TEN_MINS`,`FIFTEEN_MINS`,`THIRTY_MINS`,`ONE_HOUR`,`TWO_HOURS`,`FOUR_HOURS`,`ONE_DAY`,`ONE_WEEK`,`ONE_MONTH` | ✅ | bar size |
| `outside_rth` | boolean | ✅ | include pre/post-market |
| `period` | `ONE_DAY`…`FIVE_YEARS` (see enum) | one-of | mutually exclusive with `step_count` |
| `step_count` | int32 | one-of | number of bars; mutually exclusive with `period` |
| `exchange` | string | — | omit → SMART |
| `include_corporate_actions` | boolean | — | |

`period` enum: `ONE_DAY`, `TWO_DAYS`, `THREE_DAYS`, `ONE_WEEK`, `TWO_WEEKS`,
`ONE_MONTH`, `THREE_MONTHS`, `SIX_MONTHS`, `ONE_YEAR`, `TWO_YEARS`, `FIVE_YEARS`.

> For options: pass `security_type="OPT"` + the `exchange` from the `get_option_data`
> row; use the numeric `call_contract_id`/`put_contract_id` as `contract_id`.

---

## 4. Contract discovery (read-only — the id-resolution chain)

### 4.1 `search_contracts`
Resolve name/ticker/keyword → instruments with `contract_id`, exchanges, symbols, and a
`sections` array (available security types: STK, OPT, FUT…). **Call this first** to get
`underlying_contract_id` for everything downstream.

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `query` | string | ✅ | ticker / company / keyword |
| `language` | enum (ar, cs_CZ, de_DE, en_US, es_ES, …, zh_TW) | — | omit if not in list |

> Selection for options: match `symbol` EXACTLY (AAPL ≠ AAPU); OPT-in-sections is
> necessary but not sufficient. Disambiguate multiple exact matches via `description` /
> `country_code` (prefer US primary listing). Use that row's `underlying_contract_id`.

### 4.2 `search_futures`
Futures term structure (full expiry ladder). Returns `contracts[]` with
`contract_id_ex`, numeric `contract_id`, `exchange`, `contract_month` (YYYYMM),
`last_trading_date` (YYYYMMDD), `symbol`. **Not expiry-ordered — sort by
`contract_month` yourself; earliest non-expired = front month.** `symbol` is identical
per expiry — never display it; identify by `contract_month`/`last_trading_date`.
`contract_id_ex` → `create_order_instruction` only (not valid as combo legs).

| Field | Type | Required | Default |
|-------|------|----------|---------|
| `underlying_contract_id` | int64 | ✅ | from `search_contracts` (row where symbol==root & sections include FUT) |
| `include_expired` | boolean | — | false |
| `representative_only` | boolean | — | true (single most-liquid contract per expiry) |

### 4.3 `get_option_parameters`
Available option expirations + exchange list for an underlying. Returns `exchanges[]`,
`current_exchange`, `expirations[]` (`id`, `date` YYYYMMDD, `regular` bool,
`trading_class`), `current_expiration`. **Key on `id`, never on `date` alone**
(one date can carry multiple distinct `trading_class` contracts).

| Field | Type / Enum | Required | Default |
|-------|-------------|----------|---------|
| `underlying_contract_id` | int64 | ✅ | from `search_contracts` |
| `option_sec_type` | `OPT` \| `FOP` | — | `OPT` |
| `option_exchange` | string | — | default exchange auto-picked |

### 4.4 `get_option_data`
Option chain for **one expiration** — a row per strike: `strike`,
`call_contract_id_ex`, `call_contract_id`, `call_description`, `put_contract_id_ex`,
`put_contract_id`, `put_description`; top-level `currency` + `exchange`. **Structure
only — no prices/IV/OI/volume** (use `get_price_snapshot` with the numeric id + exchange
for those). Always bound the strike range (≥5 strikes each side of spot).

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `expiration_id` | string | ✅ | verbatim from `get_option_parameters` `expirations[].id` — never construct |
| `min_strike` | double | — | lower bound |
| `max_strike` | double | — | upper bound |

---

## 5. Watchlists

### 5.1 `get_watchlists` — no args
All watchlists with `id`, `name`, `hash`. Empty list if none.

### 5.2 `get_watchlist`
One watchlist's `name`, `hash`, and `instruments[]` (`contract_id_ex` +
`contract_description`). `contract_id_ex` here is pass-back-verbatim to create/edit.

| Field | Type | Required |
|-------|------|----------|
| `id` | string | ✅ (resolve via `get_watchlists`) |

### 5.3 `create_watchlist`
New watchlist. Returns new `id` + `hash`.

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `name` | string | ✅ | non-blank |
| `instruments` | string[] | ✅ | `contract_id_ex` values (STK int string / FUT/OPT/FOP suffixed) |

### 5.4 `edit_watchlist`
**Full-replace semantics** — submitted list becomes the entire new content. To add/remove:
`get_watchlist` → modify → `edit_watchlist`. All three fields required (source current
`name` from `get_watchlist` if not renaming).

| Field | Type | Required |
|-------|------|----------|
| `id` | string | ✅ |
| `name` | string | ✅ |
| `instruments` | string[] | ✅ (complete replacement list) |

### 5.5 `delete_watchlist`
Permanent + irreversible. Confirm with user first; resolve `id` via `get_watchlists`.

| Field | Type | Required |
|-------|------|----------|
| `id` | string | ✅ |

---

## 6. Research / themes (read-only)

### 6.1 `search_investment_topics`
Sector/industry/trend/topic search → `{key, name}` pairs. Pass `key` to
`get_theme_details`. **Use short, broad, singular keywords** ('battery' not 'batteries';
'robot' not 'robotics companies'); retry singular/synonym if empty. Never construct keys.

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `query` | string | ✅ | single singular noun works best |
| `max` | int32 | — | 3–5 for closest matches |

### 6.2 `get_theme_details`
Full topic profile: description, companies ranked by relevance (rank 1 = most central,
NOT market-cap weighted), optionally ETFs/funds. Each company carries a `contract_id`
usable in `get_company_themes`/`get_company_connections`. Paginate via `offset` + `total_count`.

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `key` | string | ✅ | verbatim from `search_investment_topics` |
| `max` | int32 | — | companies in rank order |
| `max_funds` | int32 | — | default 0; >0 only when user asks about funds/ETFs |
| `offset` | int32 | — | pagination |

### 6.3 `get_company_themes`
For a company → its sectors/trends/industries + top peers ranked by relevance. The
lightweight choice when you only need sectors/trends + peers.

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `contract_id` | int32 | ✅ | from `search_contracts`/`get_theme_details` |
| `max_themes` | int32 | — | |
| `max_companies` | int32 | — | peers per theme |

### 6.4 `get_company_connections`
Broader profile: competitors, products, geography (countries/regions), + themes with
supporting evidence. Use over `get_company_themes` when you need products/geography or
WHY a connection exists.

| Field | Type / Enum | Required | Notes |
|-------|-------------|----------|-------|
| `contract_id` | int32 | ✅ | |
| `link_types` | enum[] (`company_theme`, `company_product`, `company_country`, `company_region`, `company_competitor`, `theme_company`, `fund_theme`, `theme_fund`) | — | omit for all; `['company_theme']` = themes only |
| `include` | enum[] (`link_info`, `company_info`) | — | `link_info` adds evidence; `company_info` adds the company profile |
| `max` | int32 | — | connections per group |

---

## 7. Feedback

### 7.1 `provide_customer_feedback`
Submit a feature request / feedback when the user wants functionality IBKR tools don't
offer, or expresses sentiment/issues. **Show the exact `feedback_text` and get
confirmation before calling.**

| Field | Type | Required |
|-------|------|----------|
| `feedback_text` | string | ✅ |

---

## 8. Common id-chaining recipes

```
Stock quote:        search_contracts → underlying_contract_id → get_price_snapshot
Stock history:      search_contracts → underlying_contract_id → get_price_history(security_type=STK)
Stock order:        search_contracts → underlying_contract_id(str) → create_order_instruction
Futures order:      search_contracts → underlying_contract_id → search_futures → contract_id_ex → create_order_instruction
Single option:      search_contracts → get_option_parameters → get_option_data → call/put_contract_id_ex → create_order_instruction
Option spread:      …get_option_data → legs[] → get_combo_identifier → contract_id_ex → create_order_instruction
Option price/greeks: …get_option_data → numeric call/put_contract_id + exchange → get_price_snapshot
Theme drilldown:    search_investment_topics → key → get_theme_details → contract_id → get_company_themes/connections
Edit watchlist:     get_watchlists → id → get_watchlist → modify → edit_watchlist (full replace)
```

---

## 9. Machine-readable capability index (drop-in)

```json
{
  "connector": "Interactive_Brokers_IBKR",
  "prefix": "mcp__Interactive_Brokers_IBKR__",
  "invariants": {
    "no_live_order_placement": true,
    "instruction_requires_human_submit": true,
    "ids_are_internal_not_ticker": true,
    "destructive_tools_need_confirmation": ["delete_watchlist", "delete_order_instruction"]
  },
  "tools": {
    "create_order_instruction": { "mutating": true, "required": ["side"], "returns": "deep_link_url" },
    "get_order_instructions":   { "mutating": false, "args": [] },
    "delete_order_instruction": { "mutating": true, "required": ["id"] },
    "get_combo_identifier":     { "mutating": false, "required": ["legs"], "note": "OPT-OPT only" },
    "get_account_summary":      { "mutating": false, "args": [] },
    "get_account_balances":     { "mutating": false, "args": [] },
    "get_account_positions":    { "mutating": false, "args": [] },
    "get_account_orders":       { "mutating": false, "args": [] },
    "get_account_trades":       { "mutating": false, "optional": ["period"], "default_period": "TODAY" },
    "get_pa_allocation":        { "mutating": false, "required": ["type"] },
    "get_pa_performance_all_periods": { "mutating": false, "args": [] },
    "get_price_snapshot":       { "mutating": false, "required": ["contract_id"] },
    "get_price_history":        { "mutating": false, "required": ["contract_id","security_type","step","outside_rth"], "one_of": ["period","step_count"] },
    "search_contracts":         { "mutating": false, "required": ["query"] },
    "search_futures":           { "mutating": false, "required": ["underlying_contract_id"] },
    "get_option_parameters":    { "mutating": false, "required": ["underlying_contract_id"] },
    "get_option_data":          { "mutating": false, "required": ["expiration_id"] },
    "get_watchlists":           { "mutating": false, "args": [] },
    "get_watchlist":            { "mutating": false, "required": ["id"] },
    "create_watchlist":         { "mutating": true, "required": ["name","instruments"] },
    "edit_watchlist":           { "mutating": true, "required": ["id","name","instruments"], "note": "full-replace" },
    "delete_watchlist":         { "mutating": true, "required": ["id"], "note": "irreversible" },
    "search_investment_topics": { "mutating": false, "required": ["query"] },
    "get_theme_details":        { "mutating": false, "required": ["key"] },
    "get_company_themes":       { "mutating": false, "required": ["contract_id"] },
    "get_company_connections":  { "mutating": false, "required": ["contract_id"] },
    "provide_customer_feedback":{ "mutating": true, "required": ["feedback_text"], "note": "confirm text first" }
  }
}
```
