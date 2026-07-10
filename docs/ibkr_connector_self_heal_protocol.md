# IBKR Connector — Self-Heal Protocol (drop-in for CLAUDE.md / project instructions)

> Paste this block into the Aegis project instructions (claude.ai project → Instructions,
> and/or the repo CLAUDE.md). It tells any Claude session how to diagnose and work around
> the "IBKR tools not found" failure **instead of repeating toggle/reauth advice** — by
> discovering the connector's real registered namespace and calling under it. Derived from
> a live Claude Code session where the identical account/connector worked once the actual
> namespace was used.

---

## IBKR CONNECTOR TROUBLESHOOTING PROTOCOL

**Symptom:** IBKR tool calls return `Tool '<name>' not found` (e.g. `get_account_summary`,
`get_account_positions`, `get_price_snapshot`), often on every IBKR tool at once.

**Root cause (verified):** the IBKR connector's tools are registered under the connector's
**server id**, and that id may be an opaque **UUID** (e.g. `mcp__06ad11ab-…__get_account_summary`)
rather than the friendly prefix `mcp__Interactive_Brokers_IBKR__`. The registry shows the
connector "connected" under its display name, but the **callable tools live under the UUID
namespace**. A call keyed to the friendly name — or to the `mcp__Interactive_Brokers_IBKR__`
prefix documented in `ibkr_connector_capabilities.md` — misses, producing `Tool not found`
even though the tools are live. This is why reauth, per-chat toggle, new chat, new project,
and remove/re-add do **not** fix it: none of them change the namespace the caller is using.

**DO NOT** (these waste the user's time — they have already exhausted them):
- Do not tell the user to toggle the connector, reauthorize, start a new chat/project, or
  remove/re-add. Those do not address a namespace mismatch.
- Do not conclude "IBKR is down" from a `Tool not found` — that error is a *local registry
  lookup miss*, not a reply from IBKR's server. IBKR is almost certainly reachable.
- Do not fabricate or infer account/position/order data. If you cannot make a real call,
  fall back per the standing rule (Drive PTJ + FMP) and say so.

**SELF-HEAL SEQUENCE (run in order, stop at first success):**

1. **Discover the real namespace.** Enumerate the currently available tools / connector
   registry. Find every tool whose base name matches an IBKR tool (`get_account_summary`,
   `get_account_positions`, `search_contracts`, `create_order_instruction`, …) and read the
   **full registered name**, including its server-id prefix. The prefix may be the friendly
   `Interactive_Brokers_IBKR` OR a UUID like `06ad11ab-d72f-4691-…`.

2. **Call under the discovered prefix — not the friendly name.** Re-issue the tool call
   using the exact fully-qualified name from step 1 (e.g.
   `mcp__06ad11ab-…__get_account_summary`). Do not hardcode `mcp__Interactive_Brokers_IBKR__`;
   treat the prefix as whatever the registry actually reports this session.

3. **Verify with one cheap read** before any workflow: call the resolved
   `get_account_summary`. If it returns numbers, the connector is healthy — proceed.

4. **If step 1 finds no IBKR tools under ANY prefix** (the tool-discovery/search mechanism
   itself returns nothing or errors): this is a genuine session-wide **hydration failure**,
   not a namespace issue. Stop retrying. Fall back to Drive PTJ + FMP per standing rule,
   tell the user plainly it's an Anthropic-side connector-registration failure, and give
   them the escalation text below. Do not loop.

**ESCALATION TEXT (only after step 4):**
> "IBKR connector fails to hydrate in this chat: the registry shows it connected under
> `Interactive Brokers (IBKR)`, but no IBKR tools are callable under the friendly name or
> its UUID server id this session, and the tool-discovery mechanism returns nothing. The
> same account + connector work in Claude Code. This is a chat-surface connector-hydration
> bug (named-vs-UUID namespace), not a user-config issue."

---

## RELATED: `create_order_instruction` numeric fields

Same connector, separate gotcha. This tool fails validation with
`[/quantity: string found, number expected]` when numeric fields are sent as **quoted
strings**. Send `quantity` and `limit_price` (and the deprecated `contract_id`) as **bare,
unquoted JSON numerals** (`"quantity": 296`, not `"quantity": "296"`). Keep quotes only on
the string fields: `side`, `contract_id_ex`, `order_type`, `time_in_force`. This is a
client-side marshalling issue, not an IBKR or account problem.

---

## Note on the capabilities doc

`ibkr_connector_capabilities.md` documents tool names with the `mcp__Interactive_Brokers_IBKR__`
prefix for readability. **That prefix is not guaranteed** — the connector may register under
a UUID server id. Always resolve the live prefix (protocol step 1) before calling; use the
documented names only for the **base tool name and schema**, never as a fixed lookup key.
