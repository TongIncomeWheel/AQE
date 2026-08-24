# Crown DEGRADED — root cause and exact fix
**Found on the 2026-08-24 premarket run. PM action required (I cannot apply items 1 and 3 myself).**

Crown published `status: DEGRADED` with `option_dealers.available: false` and
`economic calendar unavailable`. Neither is a market condition. Three separate
config faults, listed in priority order.

---

## 1. Alpaca keys are never handed to the job — AND the names do not match

`src/options/providers/alpaca.py:107` reads:

```python
kid = os.environ.get("ALPACA_API_KEY_ID")
sec = os.environ.get("ALPACA_API_SECRET_KEY")
if not kid or not sec:
    raise RuntimeError("Alpaca keys missing: ...")
```

Two problems stack on top of each other.

**a) The daily job never passes them.** `.github/workflows/daily-run.yml` sets only
`FMP_API_KEY`, three `GOOGLE_OAUTH_*` secrets and `GITHUB_TOKEN`. No Alpaca, no Tiger.
So both the primary and the fallback open-interest source die and Crown loses gamma.

**b) The names differ between the two halves of this repo.**

| Where | Variable names used |
|---|---|
| `src/options/config.py:55-56` (AQE / Crown) | `ALPACA_API_KEY_ID` · `ALPACA_API_SECRET_KEY` |
| `aegis/config/env.example` + `aegis/tools/calculators/alpaca_client.py` | `ALPACA_API_KEY` · `ALPACA_SECRET_KEY` |

**These are not interchangeable.** If the keys are already stored under the short
names, Crown will still see nothing. Set the repo/Space secrets under the LONG names.

### Patch for `.github/workflows/daily-run.yml`

Add these five lines to the `env:` block at line 41, after `GITHUB_TOKEN`:

```yaml
          ALPACA_API_KEY_ID: ${{ secrets.ALPACA_API_KEY_ID }}
          ALPACA_API_SECRET_KEY: ${{ secrets.ALPACA_API_SECRET_KEY }}
          TIGER_ID: ${{ secrets.TIGER_ID }}
          TIGER_ACCOUNT: ${{ secrets.TIGER_ACCOUNT }}
          TIGER_PRIVATE_KEY: ${{ secrets.TIGER_PRIVATE_KEY }}
```

> The GitHub App token used by the premarket session **cannot write
> `.github/workflows/**`** — it lacks the `workflows` permission (403). Paste the
> five lines by hand, or grant that permission and I will push it next run.

### THE MORE IMPORTANT HALF: this workflow is only the backstop

Per the header comment in that same file, the **primary** daily run is the
**HF Space at 08:30 SGT (Tue–Sat)**; this workflow only fires an hour later and
only if the Space did not already run. **Today's Crown came from the Space.**

So the same five secrets must be set in **HF Space → Settings → Variables and
secrets**, exactly as `FMP_API_KEY` already is (see `CLAUDE.md:16` — the standing
rule is that every secret lives in BOTH places and both are updated on rotation).

**Fixing only the GitHub workflow will not fix tomorrow's Crown.**

---

## 2. SECURITY — live Alpaca keys are hardcoded in a tracked file

`aegis/tools/calculators/alpaca_client.py:27-28` carries a real key id and secret as
literal default arguments to `os.environ.get(...)`. They are committed, they are in
git history, and `aegis/INTAKE/README.md:4` already flagged them for rotation
("**rotate these — the old skill file had them hardcoded**"). They were not rotated.

**Rotate them at Alpaca now**, replace the defaults with `None`, and let the call
fail loudly instead of silently authenticating with a repo-visible credential.
Rotating also means the value you put into the Space/Actions secrets in item 1
should be the NEW key, not the one in that file.

---

## 3. FMP economic calendar — the code is right, the key is not

`src/macro/crown/calendar.py:179` calls
`https://financialmodelingprep.com/stable/economics-calendar`.

**That URL is correct and the endpoint works.** Called through the FMP connector on
2026-08-24 it returned **450 events** for 24–28 Aug, including four US high-impact
prints. So the `HTTP 404` in Crown's `limits` is not a bad URL and not a dead
endpoint — it is the `FMP_API_KEY` that the daily job uses: expired, or on a plan
that gates this endpoint. FMP's `/stable` route answers 404 rather than 403 for
plan-gated endpoints, which is why the failure looks like a broken path.
`fetch_macro_events` already anticipates this — it carries a
`"it may be plan-gated"` branch.

Corroborating signal: `mcp__FMP__quote` returns ACCESS DENIED on the Starter plan.

**Action:** confirm the plan covers `economics-calendar`, or rotate/replace
`FMP_API_KEY` in **both** GitHub Actions secrets and HF Space secrets.

### What the 404 cost on 2026-08-24

Crown ran with no calendar, so nothing in that morning's brief knew this was coming:

| Date | US high-impact print | Prev | Est |
|---|---|---|---|
| **Wed 26 Aug** | **Core PCE Price Index MoM (Jul)** | 0.1 | **0.2** |
| Wed 26 Aug | Durable Goods Orders MoM (Jul) | 0.3 | 0.7 |
| Wed 26 Aug | Personal Income MoM (Jul) | 0.2 | 0.3 |
| Tue 25 Aug | CB Consumer Confidence (Aug) | 90.8 | 90.3 |

---

## 4. NOT a fault — retracted from the 2026-08-24 brief

That brief listed "positioning as-of 2026-08-18 (6 days behind), volatility as-of
2026-08-21 (3 days)" as a degradation. **That was wrong and has been struck.**

Crown states the convention in its own payload:

> *"CFTC data covering Tuesday, published Friday, so always at least three days old.
> It cannot time anything."*

2026-08-18 was a Tuesday — the CFTC reporting date, exactly as designed. 2026-08-21
was the Friday close, the last completed session before Monday 2026-08-24. Normal
cadence, not staleness. Only items 1 and 3 above are real degradations.

---

## Checklist

- [ ] Rotate the Alpaca keys exposed in `aegis/tools/calculators/alpaca_client.py:27-28`
- [ ] Add `ALPACA_API_KEY_ID` + `ALPACA_API_SECRET_KEY` (long names) to **HF Space secrets**
- [ ] Add the same two to **GitHub Actions repo secrets**
- [ ] Paste the five-line `env:` patch into `.github/workflows/daily-run.yml`
- [ ] Add `TIGER_ID` / `TIGER_ACCOUNT` / `TIGER_PRIVATE_KEY` in both places (fallback path)
- [ ] Confirm the FMP plan covers `economics-calendar`, or rotate `FMP_API_KEY` in both places
- [ ] Next run: confirm Crown prints `status: OK` and `option_dealers.available: true`
