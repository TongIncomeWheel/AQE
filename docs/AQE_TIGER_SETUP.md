# Switching on Tiger (for the gamma map)

**What this gets you.** Dealer gamma on the Crown Macro page — the flip level,
the call and put walls, and whether the tape is pinned or unstable. Tiger is the
**fallback**; AQE tries Alpaca first and only reaches for Tiger if Alpaca does
not return open interest.

**Try Alpaca first.** The gamma failure was a bug on our side — the fetch was
asking Alpaca's *market-data* host for open interest, which does not serve it.
That is fixed and points at the trading host now. If Alpaca works you do not
need any of this.

> 🔧 Crown Macro page → **Gamma trial run** → *Run gamma diagnostic*.
> If steps 1–4 come back green, stop here. You are done.

---

## The three values, and where each one comes from

Everything is on Tiger's developer portal: <https://quant.itigerup.com/openapi/>
(Chinese portal: <https://www.laohu8.com/openapi/>). Log in with your normal
Tiger account.

| Secret name | What it is | Where to find it |
|---|---|---|
| `TIGER_ID` | Your developer ID — a number, roughly 8 digits | Developer portal → **配置管理 / Configuration**, shown as **tiger_id** |
| `TIGER_ACCOUNT` | The trading account number | Same page, shown as **账户 / Account**. Use the **live** account, not the paper one, unless you want paper data |
| `TIGER_PRIVATE_KEY` | The RSA private key you generated when you enabled API access | The `.pem` file you downloaded. Tiger never stores it — if you cannot find it, regenerate the key pair on that page and re-upload the public half |

⚠️ **The private key is a credential, exactly like a password.** Anyone holding
it can act on your Tiger account. Do not paste it into chat, email or a
document. It goes into the secrets box and nowhere else.

---

## Where to put them

**HuggingFace Space → Settings → Variables and secrets → New secret.**

1. Open <https://huggingface.co/spaces/AQE-Aegis/aqe>
2. **Settings** tab (top right)
3. Scroll to **Variables and secrets**
4. **New secret** — three times, once per row below

| Name | Value |
|---|---|
| `TIGER_ID` | the number, nothing else |
| `TIGER_ACCOUNT` | the account number, nothing else |
| `TIGER_PRIVATE_KEY` | the whole contents of the `.pem` file |

Use **Secret**, not *Variable*. Variables are visible in the build log; secrets
are not.

The Space restarts itself after you add them. Give it a minute.

### The private key — paste it however it comes

Open the `.pem` file in Notepad and copy **everything**, including the
`-----BEGIN RSA PRIVATE KEY-----` and `-----END RSA PRIVATE KEY-----` lines.
Paste the lot into the value box.

You do not need to reformat it. AQE normalises it on the way in and accepts:

- the full PEM with real line breaks (what the file looks like)
- the same thing collapsed to one line with `\n` in it (what some forms do to it)
- just the base64 body with the header and footer already removed
- `-----BEGIN PRIVATE KEY-----` style headers as well as `RSA PRIVATE KEY`

That leniency exists deliberately. The SDK wants **only the base64 body** — hand
it a full PEM block and it fails with an opaque signature error rather than
anything that tells you what went wrong. Six tests cover the paste formats so
you get one shot at this instead of a debugging session.

---

## Confirm it worked

Crown Macro page → **🔧 Gamma trial run** → *Run gamma diagnostic*.

- **Step 5 · Tiger fallback** should read **READY**
- If it still says *not configured*, the row tells you which of the three
  secrets is missing — that text is generated from what the app can actually
  see, so it is not a guess

Then tick **Include gamma** at the top and press **Run Crown layer**.

---

## If it does not work

| What the diagnostic says | What it means |
|---|---|
| `secret TIGER_ID not set` | The Space has not restarted yet, or the name has a typo. It is case-sensitive |
| `tigeropen not installed` | The Space is on an older build. Push any commit to trigger a rebuild |
| `Tiger chain fetch failed: ... signature ...` | The private key is wrong or does not match the public key uploaded to Tiger. Regenerate the pair |
| `Tiger chain fetch failed: ... permission ...` | The account has no US options market-data entitlement |
| `chain rows returned but none carried open interest` | Tiger answered but the rows were unusable. Send me that message |

---

## What Tiger is and is not used for here

**Used for:** option open interest and chains, so the gamma map can be built.

**Not used for:** anything else. It places no orders, reads no positions and
touches nothing in the daily pipeline. If the credentials are absent the layer
carries on exactly as it does today — gamma simply reports unavailable, which it
already does.

`is_configured()` returns False unless all three secrets *and* the SDK are
present, so a half-finished setup cannot half-work.
