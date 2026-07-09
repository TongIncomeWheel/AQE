# IBKR Connector — Create-Trade Capability (Fixed Working Schema)

> Reference spec for the **official Claude Interactive Brokers (IBKR) connector**
> create-trade path. Every field, enum, and workflow step below is copied verbatim
> from the connector's published tool schemas — treat this file as the source of
> truth for the schema IBKR needs to process instructions.

---

## 0. The one thing to internalise

`create_order_instruction` **does NOT place a trade.**

> *"Creates a new instruction. An instruction is not a live order. The returned URL
> deep-links to the instruction in the IBKR platforms where a user can review and
> submit it. After submission, the instruction is converted into a live order."*

- The call **stages** a fully-specified instruction and returns a **deep-link URL**.
- A **human** opens that URL in IBKR (mobile / desktop / web), reviews, and submits.
- Only on submission does IBKR convert the instruction → live order.
- There is **no autonomous execution** — enforced by the connector.

---

## 1. Tool surface

| Tool | Purpose | Args | Mutates? |
|------|---------|------|----------|
| `mcp__Interactive_Brokers_IBKR__create_order_instruction` | Stage a new instruction, return deep-link | see §2 | creates instruction (not order) |
| `mcp__Interactive_Brokers_IBKR__get_order_instructions` | List all saved instructions | none | no |
| `mcp__Interactive_Brokers_IBKR__delete_order_instruction` | Delete a staged instruction | `id` (string) | deletes instruction |

There is **no edit tool**. To change a staged instruction: `delete` + recreate.

Contract-resolution lookups (read-only, used to obtain `contract_id_ex`):

| Instrument | Lookup tool | Field to read | Format returned |
|------------|-------------|---------------|-----------------|
| STK | `search_contracts` | `underlying_contract_id` (stringify) | plain int string, e.g. `"8314"` |
| FUT | `search_futures` | `contract_id_ex` (verbatim) | `@EXCHANGE`-suffixed, e.g. `"12345@CME"` |
| OPT / FOP | `get_option_data` | `call_contract_id_ex` / `put_contract_id_ex` (verbatim) | `@EXCHANGE`-suffixed, e.g. `"722271932@CBOE"` |
| Combo / spread | `get_combo_identifier` | `contract_id_ex` (verbatim) | connector-issued combo id |

---

## 2. `create_order_instruction` — fixed schema

### 2.1 Field table

| Field | Type | Enum / format | Required | Notes |
|-------|------|---------------|----------|-------|
| `side` | string | `BUY` \| `SELL` | ✅ **(only schema-required field)** | Trade direction |
| `contract_id_ex` | string | free string | ⚠️ *effectively required* | Full contract id. Optional **only** if deprecated `contract_id` is supplied. Takes precedence over `contract_id`. |
| `contract_id` | integer | int64 | — | **DEPRECATED** backward-compat fallback. Use `contract_id_ex`. |
| `quantity` | number | double | — | Shares (STK) or contracts (FUT/OPT/FOP) |
| `order_type` | string | `MARKET` \| `LIMIT` | — | Only these two. **No STOP / STOP_LIMIT.** |
| `limit_price` | number | double | — | Used with `order_type=LIMIT` |
| `time_in_force` | string | `DAY` \| `GTC` \| `OVT` \| `OND` \| `OPG` | — | Defaults to system policy if omitted |

> **Programming note:** the JSON Schema marks *only* `side` as `required`. In
> practice a usable instruction needs `side` + (`contract_id_ex` or `contract_id`)
> + `quantity` + `order_type` (+ `limit_price` when `LIMIT`). Validate these
> yourself; the connector will not reject a partial instruction on schema grounds.

### 2.2 `contract_id_ex` — per-instrument construction

`contract_id_ex` is **not a ticker symbol**. It must be resolved first (see §1) and
the exact form differs by instrument:

- **STK** → stringify `underlying_contract_id` from `search_contracts` (e.g. `"8314"`).
- **FUT** → `contract_id_ex` from `search_futures` verbatim (e.g. `"12345@CME"`).
- **OPT / FOP** → `call_contract_id_ex` / `put_contract_id_ex` from `get_option_data` verbatim (e.g. `"722271932@CBOE"`).
- **Combo / spread** → `contract_id_ex` from `get_combo_identifier` verbatim.

The deprecated `contract_id` (int64) is accepted as a fallback; when both are
supplied, `contract_id_ex` wins.

### 2.3 `time_in_force` enum semantics

| Value | Meaning |
|-------|---------|
| `DAY` | Valid only for the current trading day; cancelled if unfilled at session end |
| `GTC` | Good-Till-Cancelled; active until filled or explicitly cancelled |
| `OVT` | Overnight; executed during the overnight session after regular close |
| `OND` | Overnight-Next-Day; overnight session, carries into next day if unfilled |
| `OPG` | At-The-Opening; executed at the next trading day's opening auction |

Omit the field to accept IBKR's system-default time-in-force policy.

### 2.4 Instrument coverage

**Supported:** STK, FUT, single-leg OPT, single-leg FOP, and **OPT–OPT** equity-option
combos/spreads.

**NOT supported:** FOP, FUT, STK combos, or any mixed-type combo. Combo/spread support
is equity-option (OPT) legs only.

### 2.5 Canonical JSON payloads

Stock, limit order:

```json
{
  "side": "BUY",
  "contract_id_ex": "8314",
  "quantity": 100,
  "order_type": "LIMIT",
  "limit_price": 187.50,
  "time_in_force": "DAY"
}
```

Stock, market order:

```json
{
  "side": "BUY",
  "contract_id_ex": "8314",
  "quantity": 100,
  "order_type": "MARKET",
  "time_in_force": "DAY"
}
```

Single-leg option, limit (exchange-suffixed id from `get_option_data`, verbatim):

```json
{
  "side": "BUY",
  "contract_id_ex": "722271932@CBOE",
  "quantity": 1,
  "order_type": "LIMIT",
  "limit_price": 3.20,
  "time_in_force": "GTC"
}
```

Sell to close (option), GTC:

```json
{
  "side": "SELL",
  "contract_id_ex": "722271932@CBOE",
  "quantity": 1,
  "order_type": "LIMIT",
  "limit_price": 5.00,
  "time_in_force": "GTC"
}
```

---

## 3. Workflow (two-step for STK)

```
1. Resolve contract id
   search_contracts(symbol) ─▶ underlying_contract_id ─▶ stringify ─▶ contract_id_ex
   (FUT: search_futures · OPT/FOP: get_option_data · combo: get_combo_identifier)

2. Stage instruction
   create_order_instruction({ side, contract_id_ex, quantity, order_type, limit_price?, time_in_force? })
   ─▶ returns deep-link URL

3. Human reviews + submits in IBKR  ─▶ instruction becomes a live order

Lifecycle:  get_order_instructions()  ·  delete_order_instruction(id)   (no edit — delete+recreate)
```

---

## 4. Capability limits (design around these)

- **Single-leg only.** No native stop-loss, take-profit, or attached/OCO bracket.
- **No STOP order types** — only `MARKET` and `LIMIT`.
- **No edit** — delete + recreate.
- **Instruction ≠ order** — always ends at a human review screen. Report a call as
  "staged, pending review in IBKR," never as "placed."
- **`contract_id_ex` is not a ticker** — resolve it first; format is instrument-specific.

---

## 5. Machine-readable schema block (drop-in)

```json
{
  "name": "create_order_instruction",
  "required": ["side"],
  "effective_required": ["side", "contract_id_ex", "quantity", "order_type"],
  "fields": {
    "side":          { "type": "string", "enum": ["BUY", "SELL"] },
    "contract_id_ex":{ "type": "string", "note": "resolve via lookup; STK=int string, FUT/OPT/FOP/combo=@EXCHANGE-suffixed" },
    "contract_id":   { "type": "integer", "format": "int64", "deprecated": true },
    "quantity":      { "type": "number", "format": "double", "unit": "shares(STK) | contracts(FUT/OPT/FOP)" },
    "order_type":    { "type": "string", "enum": ["MARKET", "LIMIT"] },
    "limit_price":   { "type": "number", "format": "double", "when": "order_type == LIMIT" },
    "time_in_force": { "type": "string", "enum": ["DAY", "GTC", "OVT", "OND", "OPG"], "default": "system_policy" }
  },
  "instruments_supported": ["STK", "FUT", "OPT", "FOP", "OPT_OPT_COMBO"],
  "instruments_unsupported": ["FOP_COMBO", "FUT_COMBO", "STK_COMBO", "MIXED_COMBO"],
  "returns": "deep_link_url",
  "semantics": "instruction_not_order__human_must_submit",
  "companion_tools": {
    "list": "get_order_instructions",
    "delete": "delete_order_instruction(id: string)",
    "edit": null
  },
  "no_bracket": true,
  "no_stop_order_type": true,
  "no_edit": true
}
```
