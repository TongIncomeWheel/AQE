#!/usr/bin/env python3
"""Option-leg reconciliation and hedge derivation (D-89) — the half of the book the journal
never had.

WHY THIS EXISTS (PM, this session: "at times, to hedge the book, we might have a put spread or
an option structure as a macro hedge. What has happened in the past is the PTJ does not capture
this, and it gets confused because of the multiple portfolios being run. It pulls the wrong
option spreads, or it doesn't put it at all... this is easily identifiable by the underlying, by
the strike, and by the expiry date").

WHAT WAS ACTUALLY BROKEN (found before writing a line of this, D-89):
  1. `contracts/journal.schema.json` carried `hedge: {"type": ["object", "null"]}` — a stub with
     no fields and no required keys. Anything satisfied it, including nothing.
  2. NOTHING in the kernel ever wrote that key. Zero writers, checked across every tool. So it
     was null every single day, by construction, not by accident.
  3. `hedge_engine.assess_current_hedge()` reads that record and returns None the moment it is
     falsy or missing `upper`. So the hedge assessment's Phase 1 concluded "no hedge on record"
     EVERY morning and Phase 2 proposed a fresh structure — while the book already held one.
     That is the exact behaviour the PM described.
  4. No broker option pull existed anywhere. Post-market named `get_stock_positions` only.
  5. And the equity membership classifier (held_book_refresh.classify_aegis_status) keys on
     TICKER. Options break that instantly: SPY can host an Income Wheel leg and an Aegis macro
     put spread in the same account at the same moment. Worse, the equity exclusion list is
     ticker-keyed — rejecting a wheel leg on SPY would have permanently suppressed every future
     Aegis SPY hedge, silently. **That list is never consulted here (test_equity_exclusions_are_
     never_consulted asserts it), and option membership has its own contract-keyed store.**

THE FOUR PM RULINGS THIS IMPLEMENTS (D-89):
  - SEPARATE ARRAY. Option legs live in `option_positions[]`, never in `open_positions[]`.
    Every existing tool that walks open_positions assumes equity shape — sizing, stops,
    carry-forward, portfolio metrics. Mixing instruments would have broken all four on day one.
  - LEGS ARE TRUTH, STRUCTURE GROUPS THEM. Each leg is recorded exactly as the broker reports
    it; the structure is DERIVED from its legs and can be rebuilt at any time. A partial fill,
    an early assignment, or one leg closed alone therefore shows up as a structure that no
    longer reconciles, instead of a structure record quietly disagreeing with the broker.
  - STRUCTURE-LEVEL MEMBERSHIP. A leg is Aegis only if it belongs to a hedge structure the
    gatekeeper actually staged (matched on underlying + right + strike + expiry — the PM's own
    identity). The PM chose the tightest rule; its known weakness is a hedge placed by hand or
    rolled outside the system coming back unrecognised. That is closed by PERSISTENCE, not by
    loosening the rule: an unmatched structure is asked about ONCE, and the answer is kept
    forever in `data/persistent/option_membership.json`, keyed by contract.
  - HEDGE ONLY. Aegis's only option structure is the macro hedge; the Charter puts every other
    options book (the wheel, PMCC, Protege9) out of scope. Nothing here models a general option
    strategy, because none was asked for.

Deterministic (law 4) — no model, no network. OCC parsing is implemented locally rather than
imported from tools/calculators/alpaca_client.py on purpose: that module is a network client, and
importing it would drag a live HTTP dependency into a data-plane tool that must run offline.
Greeks are NOT fetched here — the orchestrator fetches them (Alpaca, 15-min delayed, the only
Greeks source per Charter §0.5) and passes them in, so this file stays pure.

Usage:
  python3 tools/option_book.py classify --journal today.json \
      --staged staged_hedges.json --membership data/persistent/option_membership.json [--out today.json]
  python3 tools/option_book.py derive-hedge --journal today.json [--out today.json]
  python3 tools/option_book.py confirm --journal today.json --structure-id SID \
      --membership data/persistent/option_membership.json [--out today.json]
  python3 tools/option_book.py reject --journal today.json --structure-id SID \
      --membership data/persistent/option_membership.json [--reason "..."] [--out today.json]
  python3 tools/option_book.py selftest
"""
import json
import argparse
import os
import re
import datetime as _dt

# OCC 21-char option symbol: ROOT(1-6) YYMMDD C|P STRIKE(8, thousandths)
_OCC_RE = re.compile(r"^([A-Z]{1,6})(\d{6})([CP])(\d{8})$")

RIGHTS = ("C", "P")


# ------------------------------------------------------------------ contract identity
# The PM's identity, stated verbatim: "easily identifiable by the underlying, by the strike, and
# by the expiry date" (+ the right, which distinguishes the two legs of a put spread from a call
# structure on the same strikes). Everything downstream keys on this and nothing else — never on
# ticker alone, which is what made the equity classifier unsafe for options.

def parse_occ(symbol):
    """Parse an OCC symbol into its four identifying parts. Returns None on anything that is not
    a well-formed OCC symbol — never a partially-filled guess."""
    m = _OCC_RE.match((symbol or "").strip().upper())
    if not m:
        return None
    root, yymmdd, right, strike8 = m.groups()
    return {
        "underlying": root,
        "expiry": "20%s-%s-%s" % (yymmdd[0:2], yymmdd[2:4], yymmdd[4:6]),
        "right": right,
        "strike": int(strike8) / 1000.0,
    }


def build_occ(underlying, expiry, right, strike):
    """Inverse of parse_occ. `expiry` is ISO (YYYY-MM-DD); `right` is C or P."""
    y, m, d = str(expiry).split("-")
    r = str(right).upper()[:1]
    if r not in RIGHTS:
        raise ValueError("right must be C or P, got %r" % (right,))
    return "%s%s%s%s%s%08d" % (str(underlying).upper(), y[2:], m, d, r,
                               int(round(float(strike) * 1000)))


def contract_key(leg):
    """The canonical identity of one option contract: UNDERLYING|RIGHT|STRIKE|EXPIRY.

    Built from the leg's explicit fields when present, falling back to parsing its OCC symbol.
    The strike is normalised to 3 decimals so 100, 100.0 and 100.000 are the SAME contract — a
    formatting difference between two brokers must never look like two different positions.
    Returns None if the leg cannot be identified at all, which callers treat as a flagged
    data problem, never as a silent skip."""
    u, r, s, e = (leg.get("underlying"), leg.get("right"),
                  leg.get("strike"), leg.get("expiry"))
    if not (u and r and s is not None and e):
        parsed = parse_occ(leg.get("occ_symbol"))
        if not parsed:
            return None
        u, r, s, e = (parsed["underlying"], parsed["right"],
                      parsed["strike"], parsed["expiry"])
    r = str(r).upper()[:1]
    if r not in RIGHTS:
        return None
    return "%s|%s|%.3f|%s" % (str(u).upper(), r, float(s), e)


def structure_id(legs):
    """A structure's id is derived from the contracts it is made of — sorted, so leg ORDER can
    never produce two ids for the same spread. Deriving rather than assigning means the id is
    reproducible from the broker pull alone: nothing has to remember it."""
    keys = sorted(k for k in (contract_key(l) for l in (legs or [])) if k)
    if not keys:
        return None
    return "OPT:" + "+".join(keys)


def _dte(expiry, as_of):
    """Calendar days to expiry, computed from the journal's own date — never from the wall
    clock, so a re-run of an old journal reproduces the same number."""
    try:
        e = _dt.date.fromisoformat(str(expiry))
        a = _dt.date.fromisoformat(str(as_of))
    except (TypeError, ValueError):
        return None
    return (e - a).days


# ------------------------------------------------------------------ flags (journal-level)
# Option flags reuse the journal's single review_flags list so the PM has ONE place to look, not
# a second parallel exception channel. The `ticker` field carries the UNDERLYING for an option
# flag, which is what a person actually scans for.

def _flag(journal, ticker, kind, detail, severity="medium"):
    flags = journal.setdefault("review_flags", [])
    for f in flags:
        if f.get("ticker") == ticker and f.get("type") == kind:
            f["detail"], f["severity"], f["since"] = detail, severity, journal.get("date")
            return
    flags.append({"ticker": ticker, "type": kind, "detail": detail, "severity": severity,
                  "since": journal.get("date")})


def _unflag(journal, ticker, kind):
    flags = journal.get("review_flags")
    if not flags:
        return
    journal["review_flags"] = [f for f in flags
                               if not (f.get("ticker") == ticker and f.get("type") == kind)]


# ------------------------------------------------------------------ persistent membership store
# ONE file, two possible verdicts, keyed by contract. Deliberately not two lists (an "adopted"
# list plus an "excluded" list): a contract has exactly one membership answer, and splitting that
# across two stores invites them to disagree.

def load_membership(path):
    """{contract_key: {decision: "aegis"|"not_aegis", since, reason, structure_id}}.
    A missing file is an empty store, never an error — nothing has been decided yet."""
    try:
        with open(path) as fh:
            return json.load(fh)
    except FileNotFoundError:
        return {}


def save_membership(path, store):
    d = os.path.dirname(path)
    if d:
        os.makedirs(d, exist_ok=True)
    with open(path, "w") as fh:
        json.dump(store, fh, indent=1)
    return store


def record_decision(path, keys, decision, reason, since, sid=None):
    """Record the PM's answer for every contract in a structure at once — a structure is decided
    as a unit, so its legs can never end up with contradictory memberships."""
    store = load_membership(path)
    for k in keys:
        store[k] = {"decision": decision, "since": since, "reason": reason, "structure_id": sid}
    return save_membership(path, store)


# ------------------------------------------------------------------ membership classification

def _staged_structures(staged):
    """Normalise the gatekeeper's staged hedge orders into {structure_id: {contract_key: leg}}.
    Accepts either {"structures": [...]} or a bare list."""
    if isinstance(staged, dict):
        staged = staged.get("structures") or staged.get("staged") or []
    out = {}
    for st in staged or []:
        legs = st.get("legs") or []
        sid = st.get("structure_id") or structure_id(legs)
        if not sid:
            continue
        keyed = {}
        for l in legs:
            k = contract_key(l)
            if k:
                keyed[k] = l
        if keyed:
            out[sid] = keyed
    return out


def classify_option_status(journal, staged, membership):
    """Sort every option leg the brokers reported into Aegis / not-Aegis / undecided.

    Runs immediately after the option pull builds `option_positions`, before anything reads it.
    The rule the PM chose, applied in order:

      1. The leg belongs to a STAGED Aegis hedge structure (matched on the full contract key) ->
         confirmed, stamped with that structure's id. Silent, nothing to decide.
      2. The leg's contract has a recorded PM decision -> honoured. "aegis" confirms it silently
         (this is what stops a hand-placed or rolled hedge from being re-asked every morning);
         "not_aegis" DROPS the leg from the book entirely, silently, forever.
      3. Neither -> pending_review. The leg stays in the book (it is real capital and real risk)
         but is excluded from the hedge record until the PM rules, and it is flagged ONCE.

    A staged structure whose legs are only PARTIALLY present is a real event, not an error — one
    leg assigned, or one closed alone. Its present legs are confirmed (they are Aegis capital)
    and the gap is flagged high, because a half-spread's payoff is nothing like the spread's.

    NOTE THE ABSENCE: the ticker-keyed equity exclusion list is NEVER read here. Consulting it
    would let a rejected wheel leg on SPY suppress a future Aegis SPY hedge."""
    staged_map = _staged_structures(staged)
    key_to_sid = {}
    for sid, legs in staged_map.items():
        for k in legs:
            key_to_sid[k] = sid

    confirmed, dropped, pending, unidentifiable, remaining = [], [], [], [], []
    seen_by_sid = {}

    for leg in journal.get("option_positions", []) or []:
        key = contract_key(leg)
        under = leg.get("underlying") or (parse_occ(leg.get("occ_symbol")) or {}).get("underlying")
        if not key:
            # Cannot be identified at all — kept (never silently discarded) and flagged loudly.
            leg["aegis_status"] = "pending_review"
            unidentifiable.append(leg.get("occ_symbol"))
            remaining.append(leg)
            _flag(journal, under or "UNKNOWN", "option_unidentifiable",
                  "option leg %r carries no usable underlying/right/strike/expiry and no valid "
                  "OCC symbol — kept in the book but cannot be matched to any structure"
                  % (leg.get("occ_symbol"),), severity="high")
            continue

        leg["contract_key"] = key
        decided = membership.get(key) or {}

        if key in key_to_sid:
            sid = key_to_sid[key]
            leg["aegis_status"] = "confirmed"
            leg["structure_id"] = sid
            leg.setdefault("role", "hedge")
            confirmed.append(key)
            seen_by_sid.setdefault(sid, []).append(key)
            remaining.append(leg)
            _unflag(journal, under, "option_pending_review")
        elif decided.get("decision") == "aegis":
            leg["aegis_status"] = "confirmed"
            leg["structure_id"] = decided.get("structure_id") or structure_id([leg])
            leg.setdefault("role", "hedge")
            confirmed.append(key)
            seen_by_sid.setdefault(leg["structure_id"], []).append(key)
            remaining.append(leg)
            _unflag(journal, under, "option_pending_review")
        elif decided.get("decision") == "not_aegis":
            dropped.append(key)
            _unflag(journal, under, "option_pending_review")
        else:
            leg["aegis_status"] = "pending_review"
            leg["structure_id"] = leg.get("structure_id") or structure_id([leg])
            pending.append(key)
            remaining.append(leg)
            _flag(journal, under, "option_pending_review",
                  "option leg %s is not part of any staged Aegis hedge and has no recorded PM "
                  "decision — held in the book and risk-visible, but excluded from the hedge "
                  "record until the PM confirms or rejects it once at premarket" % key,
                  severity="medium")

    journal["option_positions"] = remaining

    incomplete = []
    for sid, legs in staged_map.items():
        found = set(seen_by_sid.get(sid, []))
        missing = [k for k in legs if k not in found]
        if found and missing:
            incomplete.append({"structure_id": sid, "missing": missing})
            under = missing[0].split("|")[0]
            _flag(journal, under, "option_structure_incomplete",
                  "staged hedge %s is only partially present at the broker — missing leg(s) %s. "
                  "A half-spread does not pay like the spread; treat its coverage as unknown "
                  "until reconciled" % (sid, ", ".join(missing)), severity="high")

    return {"confirmed": confirmed, "dropped_not_aegis": dropped, "pending_review": pending,
            "unidentifiable": unidentifiable, "incomplete_structures": incomplete}


def mark_structure_confirmed(journal, sid, membership_path, reason="PM-confirmed Aegis hedge"):
    """PM confirmed a pending structure at premarket. Flips every leg of it to confirmed and
    records the answer per contract so it is never asked again — including after a broker
    re-report, a fresh checkout, or a roll that keeps the same contracts."""
    keys, under = [], None
    for leg in journal.get("option_positions", []) or []:
        if leg.get("structure_id") == sid:
            leg["aegis_status"] = "confirmed"
            leg.setdefault("role", "hedge")
            k = leg.get("contract_key") or contract_key(leg)
            if k:
                keys.append(k)
            under = under or leg.get("underlying")
    if not keys:
        return False
    _unflag(journal, under, "option_pending_review")
    record_decision(membership_path, keys, "aegis", reason, journal.get("date"), sid)
    return True


def mark_structure_rejected(journal, sid, membership_path, reason="PM-rejected, not an Aegis hedge"):
    """PM rejected a pending structure. Its legs leave the book entirely (they were never Aegis)
    and every contract is recorded as not_aegis, so the same wheel or PMCC leg is dropped
    silently every day after — never re-surfaced, never re-asked."""
    keys, kept, under = [], [], None
    for leg in journal.get("option_positions", []) or []:
        if leg.get("structure_id") == sid:
            k = leg.get("contract_key") or contract_key(leg)
            if k:
                keys.append(k)
            under = under or leg.get("underlying")
        else:
            kept.append(leg)
    if not keys:
        return False
    journal["option_positions"] = kept
    _unflag(journal, under, "option_pending_review")
    record_decision(membership_path, keys, "not_aegis", reason, journal.get("date"), sid)
    return True


# ------------------------------------------------------------------ hedge derivation

def derive_hedge(journal):
    """Rebuild `journal["hedge"]` from the CONFIRMED option legs — the structure is derived, never
    stored as independent truth, so it can never quietly disagree with the broker.

    Recognises the macro put spread the Aegis book actually uses: two puts, same underlying, same
    expiry, one long and one short. `upper` is the long (bought, higher-strike) put and `lower`
    the short (sold) put, which is the convention tools/calculators/hedge_engine.py already reads.

    Emits exactly the keys hedge_engine.assess_current_hedge() consumes — upper, lower,
    contracts, dte, iv — alongside the identity it never had (underlying, expiry, per-leg
    contract keys, structure id). `iv` is OMITTED rather than set to None when the legs carry no
    implied vol, because hedge_engine reads it with a 0.20 default: a present-but-null key would
    crash the coverage math, while an absent one degrades to the documented default.

    GREEKS ARE NOT THIS TOOL'S JOB (D-90, PM ruling). The journal is a book of record — what is
    held, at what strikes, to what expiry, in what size. Greeks and IV are ANALYTICS, they are
    only available from Alpaca (15-min delayed; neither broker serves them at contract level),
    and they are consumed in exactly one place: premarket's hedge-coverage assessment. So they
    are pulled at the point of use, not at journal-write, and their ABSENCE here is normal and
    is NOT flagged — flagging it would fire a review flag on every journal ever written, which
    is flag fatigue, not risk management. `has_iv` in the return value tells the caller whether
    the record carries measured vol; premarket enriches and flags if its own pull fails.

    No confirmed structure -> hedge is set to None, honestly. That is a book with no hedge, and
    it is different from the old permanent null, which was a book whose hedge was never looked
    for."""
    as_of = journal.get("date")
    legs_present = journal.get("option_positions") or []
    prior = journal.get("hedge")

    # A hedge must never vanish from the record because a PULL failed. An EMPTY option book is
    # ambiguous — it means either "the book genuinely holds no options" or "the broker call
    # returned nothing" — and those are indistinguishable from here. So when the book is empty
    # and a hedge was on record yesterday, the prior record is KEPT and marked stale, loudly,
    # rather than nulled. A book that HAS legs but none confirmed is not ambiguous: that is a
    # real answer and it does null. (An option book that is genuinely empty for good clears on
    # the PM's acknowledgement of the flag, not silently.)
    if not legs_present and prior:
        prior["stale"] = True
        prior["stale_since"] = prior.get("stale_since") or as_of
        _flag(journal, prior.get("underlying") or "PORTFOLIO", "hedge_book_empty",
              "the option book came back EMPTY while hedge %s was on record. That is either a "
              "closed hedge or a failed pull, and the two are indistinguishable from the data — "
              "so the prior record is KEPT and marked stale rather than nulled. Confirm at the "
              "broker: if the hedge really is closed, reject the structure to clear this."
              % prior.get("structure_id"), severity="high")
        return {"hedge": prior.get("structure_id"), "structures_found": 0, "stale": True,
                "note": "option book empty — prior hedge retained as stale, not nulled"}

    by_sid = {}
    for leg in legs_present:
        if leg.get("aegis_status") != "confirmed":
            continue
        by_sid.setdefault(leg.get("structure_id"), []).append(leg)

    candidates = []
    for sid, legs in by_sid.items():
        puts = [l for l in legs if str(l.get("right", "")).upper()[:1] == "P"]
        if len(puts) != 2:
            continue
        longs = [l for l in puts if float(l.get("qty", 0) or 0) > 0]
        shorts = [l for l in puts if float(l.get("qty", 0) or 0) < 0]
        if len(longs) != 1 or len(shorts) != 1:
            continue
        lo, sh = longs[0], shorts[0]
        if lo.get("underlying") != sh.get("underlying") or lo.get("expiry") != sh.get("expiry"):
            continue
        if float(lo.get("strike", 0)) <= float(sh.get("strike", 0)):
            continue  # a long put BELOW the short one is not a protective debit spread
        ivs = [float(l["iv"]) for l in (lo, sh) if l.get("iv") is not None]
        rec = {
            "structure_id": sid,
            "kind": "put_debit_spread",
            "underlying": lo.get("underlying"),
            "expiry": lo.get("expiry"),
            "dte": _dte(lo.get("expiry"), as_of),
            "upper": float(lo.get("strike")),
            "lower": float(sh.get("strike")),
            "contracts": int(abs(float(lo.get("qty", 0) or 0))),
            "legs": [lo.get("contract_key") or contract_key(lo),
                     sh.get("contract_key") or contract_key(sh)],
            "as_of": as_of,
            "greeks_as_of": lo.get("greeks_as_of") or sh.get("greeks_as_of"),
            "source": "derived from confirmed option_positions (D-89)",
        }
        if ivs:
            rec["iv"] = round(sum(ivs) / len(ivs), 4)
        candidates.append(rec)

    if not candidates:
        journal["hedge"] = None
        return {"hedge": None, "structures_found": 0,
                "note": "no confirmed Aegis option structure in the book"}

    # Nearest expiry is the live hedge — it is the one actually covering the book right now.
    candidates.sort(key=lambda c: (c["dte"] if c["dte"] is not None else 10 ** 6))
    chosen = candidates[0]
    journal["hedge"] = chosen

    # No hedge_iv_missing flag here, deliberately (D-90). Missing IV at journal-write is the
    # NORMAL state, not an exception: Greeks come from Alpaca at the point of use in premarket,
    # not from the broker pull that builds this file. A flag that fires every single day teaches
    # the PM to ignore flags. Any stale flag written by the earlier behaviour is cleared.
    _unflag(journal, chosen["underlying"], "hedge_iv_missing")

    if len(candidates) > 1:
        _flag(journal, chosen["underlying"], "multiple_hedge_structures",
              "%d confirmed hedge structures are open; the nearest-expiry one (%s, %s dte) is "
              "recorded as THE hedge and the coverage math sees only that one. Others: %s"
              % (len(candidates), chosen["structure_id"], chosen["dte"],
                 ", ".join(c["structure_id"] for c in candidates[1:])), severity="high")

    return {"hedge": chosen["structure_id"], "structures_found": len(candidates),
            "dte": chosen["dte"], "has_iv": "iv" in chosen}


# --------------------------------------------------------------------------- CLI
def _load(path):
    with open(path) as fh:
        return json.load(fh)


def _write(journal, args):
    out = args.out or args.journal
    with open(out, "w") as fh:
        json.dump(journal, fh, indent=1)
    return out


def cmd_classify(args):
    journal = _load(args.journal)
    staged = _load(args.staged) if args.staged else []
    membership = load_membership(args.membership)
    report = classify_option_status(journal, staged, membership)
    print(json.dumps({"op": "classify", "out": _write(journal, args), **report}, indent=1))


def cmd_derive_hedge(args):
    journal = _load(args.journal)
    report = derive_hedge(journal)
    print(json.dumps({"op": "derive-hedge", "out": _write(journal, args), **report}, indent=1))


def cmd_confirm(args):
    journal = _load(args.journal)
    ok = mark_structure_confirmed(journal, args.structure_id, args.membership,
                                  args.reason or "PM-confirmed Aegis hedge")
    print(json.dumps({"op": "confirm", "out": _write(journal, args),
                      "structure_id": args.structure_id, "found": ok,
                      "note": "run derive-hedge next so the hedge record reflects this"}, indent=1))


def cmd_reject(args):
    journal = _load(args.journal)
    ok = mark_structure_rejected(journal, args.structure_id, args.membership,
                                 args.reason or "PM-rejected, not an Aegis hedge")
    print(json.dumps({"op": "reject", "out": _write(journal, args),
                      "structure_id": args.structure_id, "found": ok,
                      "note": "run derive-hedge next so the hedge record reflects this"}, indent=1))


def selftest(_args=None):
    import tempfile
    mpath = os.path.join(tempfile.mkdtemp(), "option_membership.json")

    # --- contract identity -------------------------------------------------------------
    p = parse_occ("SPY260918P00580000")
    assert p == {"underlying": "SPY", "expiry": "2026-09-18", "right": "P", "strike": 580.0}, p
    assert build_occ("SPY", "2026-09-18", "P", 580) == "SPY260918P00580000"
    assert parse_occ("not-an-occ-symbol") is None, "a malformed symbol must parse to None, never a guess"
    # the same contract written two ways must produce ONE key
    assert contract_key({"underlying": "SPY", "right": "P", "strike": 580, "expiry": "2026-09-18"}) == \
           contract_key({"occ_symbol": "SPY260918P00580000"}), \
           "explicit fields and an OCC symbol must resolve to the same contract key"
    assert contract_key({"underlying": "SPY", "right": "P", "strike": 580.0, "expiry": "2026-09-18"}) == \
           contract_key({"underlying": "spy", "right": "p", "strike": 580.000, "expiry": "2026-09-18"}), \
           "case and strike formatting must not create two contracts out of one"

    long_put = {"occ_symbol": "SPY260918P00580000", "underlying": "SPY", "right": "P",
                "strike": 580.0, "expiry": "2026-09-18", "qty": 10, "entry": 12.40,
                "broker": "ibkr", "iv": 0.22, "greeks_as_of": "2026-07-28T09:45:00Z"}
    short_put = {"occ_symbol": "SPY260918P00550000", "underlying": "SPY", "right": "P",
                 "strike": 550.0, "expiry": "2026-09-18", "qty": -10, "entry": 6.10,
                 "broker": "ibkr", "iv": 0.24, "greeks_as_of": "2026-07-28T09:45:00Z"}
    # a wheel leg on the SAME underlying — the exact collision that made ticker-keying unsafe
    wheel_put = {"occ_symbol": "SPY260821P00600000", "underlying": "SPY", "right": "P",
                 "strike": 600.0, "expiry": "2026-08-21", "qty": -3, "entry": 8.00,
                 "broker": "tiger"}

    sid = structure_id([long_put, short_put])
    assert sid == structure_id([short_put, long_put]), "leg order must not change the structure id"

    journal = {"date": "2026-07-28", "dyncap": {"value": 66699, "one_r": 667},
               "open_positions": [], "closed_trades": [], "metrics": {},
               "option_positions": [dict(long_put), dict(short_put), dict(wheel_put)]}
    staged = {"structures": [{"structure_id": sid, "legs": [long_put, short_put]}]}

    r = classify_option_status(journal, staged, load_membership(mpath))
    assert len(r["confirmed"]) == 2, r
    assert len(r["pending_review"]) == 1, r
    assert r["incomplete_structures"] == [], r
    wheel_row = [l for l in journal["option_positions"] if l["strike"] == 600.0][0]
    assert wheel_row["aegis_status"] == "pending_review"
    assert all(l["aegis_status"] == "confirmed" for l in journal["option_positions"]
               if l["expiry"] == "2026-09-18")
    assert {f["type"] for f in journal["review_flags"]} == {"option_pending_review"}, journal["review_flags"]

    # --- hedge derivation --------------------------------------------------------------
    h = derive_hedge(journal)
    hedge = journal["hedge"]
    assert hedge is not None, "a confirmed put spread MUST produce a hedge record"
    assert hedge["upper"] == 580.0 and hedge["lower"] == 550.0, hedge
    assert hedge["contracts"] == 10 and hedge["underlying"] == "SPY", hedge
    assert hedge["dte"] == 52, hedge          # 2026-07-28 -> 2026-09-18
    assert hedge["iv"] == 0.23, hedge          # average of the two legs
    assert hedge["kind"] == "put_debit_spread"
    assert len(hedge["legs"]) == 2 and all("|" in k for k in hedge["legs"])
    assert h["structures_found"] == 1, h
    # the wheel leg is pending, so it must NOT have leaked into the hedge
    assert "600.000" not in "".join(hedge["legs"]), "a pending leg must never enter the hedge record"

    # the record must satisfy what hedge_engine.assess_current_hedge actually reads
    for k in ("upper", "lower", "contracts", "dte", "iv"):
        assert k in hedge, "hedge_engine reads %r — it must be present" % k
    assert hedge.get("upper"), "assess_current_hedge returns None on a falsy `upper` — the exact silent failure this fixes"

    # --- PM rejects the wheel leg; it must never come back ------------------------------
    wheel_sid = wheel_row["structure_id"]
    assert mark_structure_rejected(journal, wheel_sid, mpath, reason="Income Wheel, not Aegis")
    assert all(l["strike"] != 600.0 for l in journal["option_positions"]), \
        "a rejected structure's legs must leave the book entirely"
    assert not [f for f in journal["review_flags"] if f["type"] == "option_pending_review"]

    journal["option_positions"].append(dict(wheel_put))   # broker reports it again tomorrow
    r2 = classify_option_status(journal, staged, load_membership(mpath))
    assert len(r2["dropped_not_aegis"]) == 1, r2
    assert r2["pending_review"] == [], "a rejected contract must be dropped silently, never re-asked"

    # --- the equity exclusion list is never consulted -----------------------------------
    # Rejecting a wheel leg on SPY must NOT suppress a future Aegis SPY hedge. The Aegis SPY
    # spread above is still confirmed even though a SPY option was just rejected.
    r3 = classify_option_status(journal, staged, load_membership(mpath))
    assert len(r3["confirmed"]) == 2, \
        "rejecting one SPY contract must never suppress a different SPY contract — this is the " \
        "landmine ticker-keyed exclusions would have created"

    # --- a hand-placed hedge is asked about ONCE ----------------------------------------
    hand = {"occ_symbol": "QQQ261218P00500000", "underlying": "QQQ", "right": "P",
            "strike": 500.0, "expiry": "2026-12-18", "qty": 5, "entry": 15.0, "broker": "ibkr"}
    hand2 = {"occ_symbol": "QQQ261218P00470000", "underlying": "QQQ", "right": "P",
             "strike": 470.0, "expiry": "2026-12-18", "qty": -5, "entry": 9.0, "broker": "ibkr"}
    hand_sid = structure_id([hand, hand2])
    for leg in (hand, hand2):
        leg["structure_id"] = hand_sid
        journal["option_positions"].append(dict(leg))
    r4 = classify_option_status(journal, staged, load_membership(mpath))
    assert len(r4["pending_review"]) == 2, r4
    assert mark_structure_confirmed(journal, hand_sid, mpath, reason="hand-placed macro hedge")
    r5 = classify_option_status(journal, staged, load_membership(mpath))
    assert r5["pending_review"] == [], "a confirmed hand-placed hedge must never be re-asked"
    assert len(r5["confirmed"]) == 4, r5

    # two live structures now -> nearest expiry wins, the other is flagged, not hidden
    h2 = derive_hedge(journal)
    assert h2["structures_found"] == 2, h2
    assert journal["hedge"]["underlying"] == "SPY", "nearest expiry (Sep) must be the live hedge"
    assert [f for f in journal["review_flags"] if f["type"] == "multiple_hedge_structures"], \
        "a second open structure must be flagged, never silently ignored"

    # --- partial structure at the broker ------------------------------------------------
    j2 = {"date": "2026-07-28", "option_positions": [dict(long_put)]}   # short leg assigned away
    r6 = classify_option_status(j2, staged, {})
    assert len(r6["incomplete_structures"]) == 1, r6
    assert [f for f in j2["review_flags"] if f["type"] == "option_structure_incomplete"]
    h3 = derive_hedge(j2)
    assert j2["hedge"] is None, "a half-spread must NOT be recorded as a hedge"
    assert h3["structures_found"] == 0

    # --- missing implied vol degrades honestly ------------------------------------------
    j3 = {"date": "2026-07-28", "option_positions": [
        {k: v for k, v in long_put.items() if k != "iv"},
        {k: v for k, v in short_put.items() if k != "iv"}]}
    classify_option_status(j3, staged, {})
    derive_hedge(j3)
    assert "iv" not in j3["hedge"], \
        "with no measured IV the key must be ABSENT (hedge_engine's 0.20 default applies), " \
        "never present-and-null, which would crash the coverage math"
    assert not [f for f in j3.get("review_flags", []) if f["type"] == "hedge_iv_missing"], \
        "D-90: missing IV at journal-write is NORMAL (Greeks are pulled at point of use in " \
        "premarket, not here) and must not raise a flag that would fire every single day"

    # --- an unidentifiable leg is kept and flagged, never dropped -----------------------
    j4 = {"date": "2026-07-28", "option_positions": [{"occ_symbol": "GARBAGE", "qty": 1}]}
    r7 = classify_option_status(j4, staged, {})
    assert r7["unidentifiable"] == ["GARBAGE"], r7
    assert len(j4["option_positions"]) == 1, "an unparseable leg is real capital — never discarded"
    assert [f for f in j4["review_flags"] if f["type"] == "option_unidentifiable"]

    # --- no options at all ---------------------------------------------------------------
    j5 = {"date": "2026-07-28", "option_positions": []}
    classify_option_status(j5, staged, {})
    assert derive_hedge(j5)["hedge"] is None and j5["hedge"] is None

    # --- an EMPTY book must never silently erase a hedge that was on record --------------
    # This is the failure the whole path exists to stop: a broker pull returning nothing looks
    # exactly like a closed hedge, so it is retained-and-flagged, never nulled.
    j6 = {"date": "2026-07-29", "option_positions": [],
          "hedge": {"structure_id": "OPT:SPY|P|550.000|2026-09-18+SPY|P|580.000|2026-09-18",
                    "kind": "put_debit_spread", "underlying": "SPY", "upper": 580.0,
                    "lower": 550.0, "contracts": 10, "dte": 51}}
    r8 = derive_hedge(j6)
    assert j6["hedge"] is not None, "a failed/empty option pull must NOT null a live hedge record"
    assert j6["hedge"]["stale"] is True and j6["hedge"]["stale_since"] == "2026-07-29"
    assert r8["stale"] is True and r8["structures_found"] == 0
    assert [f for f in j6["review_flags"] if f["type"] == "hedge_book_empty"
            and f["severity"] == "high"], "an empty book over a live hedge is a HIGH flag"
    # but a book that HAS legs and simply confirms none of them is a real answer -> null
    j7 = {"date": "2026-07-29", "hedge": dict(j6["hedge"]),
          "option_positions": [{"underlying": "TSLA", "right": "P", "strike": 200,
                                "expiry": "2026-08-21", "qty": -1,
                                "aegis_status": "pending_review"}]}
    assert derive_hedge(j7)["hedge"] is None and j7["hedge"] is None, \
        "legs present but none confirmed is unambiguous — that genuinely is no hedge"

    print("option_book selftest OK — contracts identify on underlying/right/strike/expiry (one "
          "key however the broker spells it); a staged spread confirms silently while a wheel leg "
          "on the SAME underlying goes to pending_review; rejecting that wheel leg never suppresses "
          "the Aegis SPY hedge; a hand-placed hedge is asked about once and remembered forever; the "
          "hedge record is DERIVED from confirmed legs and carries exactly the keys hedge_engine "
          "reads; a half-spread, a missing IV, an unparseable leg and an empty book each degrade "
          "honestly and loudly instead of silently.")


def main(argv=None):
    ap = argparse.ArgumentParser(
        description="Option-leg reconciliation and hedge derivation (D-89, deterministic)")
    sub = ap.add_subparsers(dest="cmd", required=True)

    cl = sub.add_parser("classify")
    cl.add_argument("--journal", required=True)
    cl.add_argument("--staged", help="JSON: staged Aegis hedge structures from the gatekeeper")
    cl.add_argument("--membership", required=True)
    cl.add_argument("--out")

    dh = sub.add_parser("derive-hedge")
    dh.add_argument("--journal", required=True)
    dh.add_argument("--out")

    co = sub.add_parser("confirm")
    co.add_argument("--journal", required=True)
    co.add_argument("--structure-id", required=True, dest="structure_id")
    co.add_argument("--membership", required=True)
    co.add_argument("--reason")
    co.add_argument("--out")

    rj = sub.add_parser("reject")
    rj.add_argument("--journal", required=True)
    rj.add_argument("--structure-id", required=True, dest="structure_id")
    rj.add_argument("--membership", required=True)
    rj.add_argument("--reason")
    rj.add_argument("--out")

    sub.add_parser("selftest")

    a = ap.parse_args(argv)
    {"selftest": lambda _: selftest(),
     "classify": cmd_classify,
     "derive-hedge": cmd_derive_hedge,
     "confirm": cmd_confirm,
     "reject": cmd_reject}[a.cmd](a)


if __name__ == "__main__":
    main()
