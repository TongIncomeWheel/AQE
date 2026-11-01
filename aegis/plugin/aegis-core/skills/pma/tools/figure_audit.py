#!/usr/bin/env python3
"""figure_audit.py — did this seat read the packet, or did it invent the numbers?

WHY THIS EXISTS (PM ruling 2026-09-16). R2 asks every seat to prove it voted on the real packet by
returning a computed md5 of it. No seat has a hashing tool, so on 2026-09-15 all eleven returned
NOT_VERIFIED and substituted a quoted line. The PM's response was the right one: a tamper check is
overkill for a single-user system where AQE writes the file and the voices read it — nobody is
attacking the packet. The real exposure is different and worse:

    a seat that does not actually read the packet, and writes plausible numbers instead.

That is not hypothetical — it is the failure mode a language model has and a file does not. A md5
would never have caught it: a seat can hash a file correctly and still fabricate every figure in
its reasoning. This tool checks the thing that actually matters — every figure a seat cites must
be findable in the packet it was given.

WHAT IT DOES NOT DO, DELIBERATELY. It does not demand that every number match. Seats compute:
3x ATR for an unwatched loss, a sigma from a win rate and a sample size, a percentage from a ratio.
Those are correct work and they will not appear in the packet verbatim. A check that fires on
correct output every run is a check that gets waved through — the gate's own "support" ban was
exactly that mistake, made here it would be worse because the penalty is a rejected ballot. So:

  * ONLY QUOTED-FIELD CLAIMS are audited -- "ma50 218.30", "day_vol 1.37", "peg 7.47". Writing
    those asserts the row says so, and that is checkable. Derived arithmetic ("atr_pct 4.22%",
    "~5.05% on 3-ATR", "7-8% below the 32.00 entry") carries no served field name and is skipped.
  * The claim is checked against THAT TICKER's own section plus the shared header, not the whole
    packet -- 52 numbers, not 765.
  * A claim matches at the precision the seat wrote at, and percent-scaled either way (the export
    carries fcf_yld 0.0489, a seat legitimately writes 4.89%).

Everything left over is a number the seat put on the page that is in no way traceable to the data
it was handed. That is the report.

    python3 tools/figure_audit.py --form forms/r2/lynch.json --packet VOTE_PACKET.txt
    python3 tools/figure_audit.py --form <f> --packet <p> --json

Exit 0 clean, 1 if any untraceable figure is found, 2 on a usage error.
"""
import argparse, json, os, re, sys

# fields a seat writes prose into; these are what we audit
PROSE_FIELDS = ("reason", "opposing_case", "self_counter", "falsifier", "challenge_reply",
                "conviction_change", "o_a_note", "o_b_stop_honored", "o_c_invalidation",
                "shortfall_reason", "thesis", "entry_note")

SECTION = re.compile(r"(?m)^###\s+([A-Z][A-Z0-9.\-]*)")

# The served field names a packet row actually carries. A seat writing "ma50 218.30" is CLAIMING TO
# QUOTE one of these; that claim is checkable against the row it was given. A seat writing
# "atr_pct 4.22%" or "~5.05% (3-ATR)" is doing arithmetic on served values — legitimate work that
# by definition will not appear in the packet, and the thing that made the first two builds of this
# tool useless. Measured on the real 2026-09-15 ballots: auditing every decimal flagged 50 figures
# across 231 votes and every single one was correct derived work (thorp's ATR-as-percent, oneil's
# own 1.40 volume floor, a stop shown as "7-8% below the 32.00 entry"). Auditing only quoted-field
# claims targets the actual failure mode — asserting a served value the row does not carry.
FIELD_NAMES = ("structure", "sma_dist", "sma_distance_pct", "ma20", "ma50", "ma100", "ma200",
               "ma_20", "ma_50", "ma_100", "ma_200", "atr", "atr_14d", "day_vol", "flow", "energy",
               "elder", "elder_5d", "div", "rank", "sc_mom", "sc_momentum", "entry", "pe", "peg",
               "fwd_peg", "fcf_yld", "net_margin", "rev_g", "eps_g", "piotroski", "altman",
               "vcp_tightness_pct", "base_range_pct", "choch_state", "rs", "spy20", "downday",
               "rs_spy_20d", "cohort_n", "vol_30d_ann", "avg_vol_20d", "days_to_earnings")
# NOT AUDITED, deliberately: stop / risk / rr_tp1 / rr_tp2 / atr_fallback_stop / gap_loss_pct.
# The first four are bracket state, which R1 makes information-only and forbids as a basis for any
# vote -- auditing them protects nothing. And seats legitimately name THEIR OWN stop ("Stop 13.33,
# 2 ticks under ma20 13.35"), which is derived work, not a quote. gap_loss_pct is a seat's own
# coined metric, not a served field. Measured: these four names produced every remaining false
# positive on the real 2026-09-15 ballots.
QUOTED = re.compile(r"\b(" + "|".join(sorted(FIELD_NAMES, key=len, reverse=True)) +
                    r")\b[\s:=]+\$?(-?\d+\.\d+)", re.I)   # '=' added 2026-10-23: "field=value" was skipped


def _floats(text):
    out = set()
    for m in re.finditer(r"-?\d+(?:\.\d+)?", text):
        try:
            out.add(float(m.group(0)))
        except ValueError:
            pass
    return out


def packet_index(text):
    """Split the packet into per-ticker sections plus the shared header/macro region.

    SCOPE IS THE WHOLE POINT. The first build of this tool matched a cited figure against every
    number anywhere in the packet. Measured on the real 2026-09-15 packet that is 765 distinct
    numbers, and with percent-scaling and multiples on top, deliberately fabricated figures still
    matched something — the check reported a clean bill on a ballot whose numbers had been
    replaced wholesale. A test that cannot fail is not a test. A seat reasoning about KR should be
    citing KR's row, and KR's section carries 52 numbers, not 765.
    """
    bounds = [(m.group(1), m.start()) for m in SECTION.finditer(text)]
    shared = _floats(text[:bounds[0][1]]) if bounds else _floats(text)
    per = {}
    for i, (tic, start) in enumerate(bounds):
        end = bounds[i + 1][1] if i + 1 < len(bounds) else len(text)
        per.setdefault(tic, set()).update(_floats(text[start:end]))
    return per, shared


def _precision(literal):
    return len(literal.split(".")[1]) if "." in literal else 0


def traceable(literal, x, vals):
    """Findable in scope, at the precision the seat actually wrote at.

    No 0-decimal sweep: rounding 187.43 to 187 matches any packet value in a whole unit and was
    how the first build swallowed fabricated prices. Percent scaling stays — the export carries
    fcf_yld as 0.0489 and a seat legitimately writes 4.89%.
    """
    dp = _precision(literal)
    for v in vals:
        if round(v, dp) == round(x, dp):
            return True
        if v != 0 and (round(v * 100, dp) == round(x, dp) or round(v / 100, dp) == round(x, dp)):
            return True
        if round(abs(v), dp) == round(abs(x), dp):     # a loss quoted positive
            return True
    return False


def audit(form, packet_text, counts=None):
    """Findings list. Pass counts={} to also learn how many claims were actually examined.

    COVERAGE IS PART OF THE RESULT. This tool can only audit a figure a seat presents as a served
    field. A ballot that reasons in pure prose offers nothing to check, and would come back "OK" --
    which would mean "nothing was verified", not "nothing was wrong". The caller is told the
    difference so a clean result can never be mistaken for a clean bill on an unauditable ballot.
    """
    per, shared = packet_index(packet_text)
    findings = []
    examined = 0
    votes = form.get("votes") or form.get("nominations") or []
    for i, v in enumerate(votes):
        if not isinstance(v, dict):
            continue
        tic = v.get("ticker", f"[{i}]")
        scope = set(shared) | per.get(tic, set())
        if tic not in per:
            continue          # no section for this name — cannot audit, never invent a failure
        for f in PROSE_FIELDS:
            s = v.get(f)
            if not isinstance(s, str):
                continue
            for m in QUOTED.finditer(s):
                field_claimed, lit = m.group(1), m.group(2)
                examined += 1
                try:
                    x = float(lit)
                except ValueError:
                    continue
                if not traceable(lit, x, scope):
                    findings.append({"ticker": tic, "field": f, "claimed": field_claimed,
                                     "figure": lit,
                                     "context": s[max(0, m.start() - 45):m.end() + 45].strip()})
    if counts is not None:
        counts["examined"] = examined
        counts["votes"] = len(votes)
    return findings


def main():
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--form", required=True, help="a seat's ballot (round-1 or round-2 form)")
    p.add_argument("--packet", required=True, help="the packet that seat was given")
    p.add_argument("--json", action="store_true")
    a = p.parse_args()
    for path in (a.form, a.packet):
        if not os.path.exists(path):
            print(f"figure_audit: no such file: {path}", file=sys.stderr)
            return 2
    try:
        form = json.load(open(a.form))
    except json.JSONDecodeError as e:
        print(f"figure_audit: form is not valid JSON: {e}", file=sys.stderr)
        return 2
    counts = {}
    findings = audit(form, open(a.packet, encoding="utf-8", errors="replace").read(), counts)
    voice = form.get("voice", "?")
    if a.json:
        print(json.dumps({"voice": voice, "untraceable": findings,
                          "claims_examined": counts.get("examined", 0),
                          "votes": counts.get("votes", 0),
                          "result": "REJECT" if findings else "OK"}, indent=1))
    else:
        if not findings:
            n = counts.get("examined", 0)
            if n == 0:
                print(f"figure_audit: {voice} — NO auditable field claims in this ballot. Nothing "
                      f"was verified; this is not a clean bill. A seat that cites no served field "
                      f"offers nothing to check against the row it was given.")
            else:
                print(f"figure_audit: {voice} — {n} field claim(s) checked across "
                      f"{counts.get('votes', 0)} votes; every one traces to the packet row. OK")
        else:
            print(f"figure_audit: {voice} — {len(findings)} figure(s) cite data that is NOT in the "
                  f"packet this seat was given:")
            for f in findings:
                print(f"  {f['ticker']:6} claims {f['claimed']}={f['figure']}"
                      f"   ...{f['context']}...")
    return 1 if findings else 0


if __name__ == "__main__":
    sys.exit(main())
