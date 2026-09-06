#!/usr/bin/env bash
#
# run_post_market.sh — the deterministic half of post-market, as ONE call.
# ---------------------------------------------------------------------------
# D-93. Everything between "the broker payloads are on disk" and "the gate is
# stamped" is deterministic: no model, no judgement, no network beyond the git
# push (constitution law 4). That whole span used to be a prose sequence in
# skills/post_market/SKILL.md, re-read and re-interpreted by a model every
# night, with the order of operations depending on the model getting it right
# again. This script IS that order. It cannot drift, it cannot skip a step
# because a context was long, and it returns one exit code.
#
# 2026-08-19 INCIDENT (D-99/D-100/D-101/D-102): a manual PTJ run on 2026-08-18
# never actually invoked this script — it called a subset of the underlying
# tools by hand, which is how four real defects shipped silently for weeks:
#   D-99  — dynCap was computed by journal_build.py's `build` BEFORE Aegis-
#           membership classification ran, so its unrealised-P&L component
#           summed over the full co-mingled broker book (Income Wheel,
#           Protege9, Ryan's personal names), not just Aegis holdings. Fixed:
#           tools/recompute_dyncap.py now runs as its own job right after
#           equity+option membership classify, before carry-forward.
#   D-100 — Tiger's get_filled_orders MCP tool silently drops stop-triggered
#           equity closes. Confirmed on AVAV: its 2026-08-18 stop-out never
#           appeared in get_filled_orders on the 08-18 OR 08-19 pull, despite
#           being present in get_transactions(symbol=AVAV) the whole time. The
#           loss was real at the broker and invisible in the book of record.
#           Fixed: tools/reconcile_vanished_positions.py is now a HARD GATE
#           right after the payload contract check — it diffs yesterday's
#           held tickers against today's broker pull, and HALTS (exit 2) if
#           any vanished ticker has no matching fill in the saved payload,
#           rather than letting journal_build quietly build a journal with
#           the position simply gone and nothing recorded.
#   D-101 — journal_build.py's `_date_only()` could not parse epoch-
#           millisecond timestamps (only ever exercised once D-100 produced
#           the first real closed_trade in this fund's history) and silently
#           produced garbage dates like "1787-05-98". Fixed in journal_build.py.
#   D-102 — archive_ledger.py's merge expects {exitDate, pnlUsd, ...} but
#           journal_build.py's closed_trades use {closed_date, realised_usd,
#           ...} — this script used to hand the raw extract straight to
#           archive_ledger.py, so any real close would have been archived
#           with pnlUsd defaulting to 0.0 and exitDate null. Fixed:
#           tools/journal_closed_to_archive_format.py converts the extract
#           before the merge step below.
#
# WHAT IT DOES NOT DO — the hard seams a shell script cannot cross:
#   * It does not call Tiger or IBKR. Those are MCP connectors, not CLIs. The
#     harness pulls both brokers and saves the raw payloads to
#     data/eod/<DATE>/broker_pull/ BEFORE calling this. That saved payload is
#     also the first time those responses have ever been retained — until now
#     nothing in the book of record could be re-derived or audited.
#   * It does not notify. The phone message is the session's own final reply
#     (D-75); a printed line is a draft, not a delivery.
#   * It does not place, size or arm anything. Nothing here is order-capable —
#     only staging-gatekeeper ever is (constitution law 1).
#   * If D-100's gate halts the run (an unexplained vanished position), it
#     does NOT try to self-heal by calling get_transactions — that is a live
#     MCP call this deterministic script cannot make. The orchestrating
#     Claude session must recover the fill and append it to
#     tiger_filled_orders.json, then re-run.
#   * If a git push is blocked by this session's own sandbox proxy (a real,
#     observed failure mode distinct from a bad token or network outage — see
#     git_sync.py's --check), this script does NOT attempt an MCP-based push
#     itself — a shell script cannot call an MCP tool — and, as of D-111
#     (2026-09-06), does NOT report this specific known signature as a
#     failure either: it is the routine, every-run shape of a push here, not
#     a finding, and treating it as one manufactured a false alarm every day.
#     The orchestrating Claude session ALWAYS completes the push via the
#     GitHub MCP connector's push_files tool, unconditionally (D-110) — this
#     is a mandatory follow-up regardless of what this script reports, not a
#     step gated on seeing a failure here. A push failure that does NOT match
#     the known sandbox-proxy signature is still reported as a real failure.
#
# NOTHING IS SCHEDULED. There is no task, cron or trigger that runs this. It
# is started by hand, every time.
#
#   usage:  scripts/run_post_market.sh <YYYY-MM-DD> [--pull DIR] [--rehearsal]
#
# --rehearsal runs every step for real against the real payloads, but writes the
# journal to data/eod/<DATE>/rehearsal/ instead of data/journal/, leaves the
# archive untouched, and turns both pushes into git_sync --dry-run. It proves
# the wiring without writing or shipping a book of record — which is what you
# want before the close, or the first time you run this after changing it.
#
# EXIT CODES — the same three-way grammar as phase_gate / aqe_coverage /
# artefact_check / journal_build:
#   0  every job passed. Gate stamped ok. (D-111, 2026-09-06: the routine sandbox
#      git-proxy push block no longer counts against this — it is expected on
#      every run here and self-heals via the mandatory GitHub-connector delivery
#      in the same session (D-110), so a run whose ONLY finding is that known
#      signature is a normal 0, not a 1. Don't mistake this for the push being
#      skipped or unverified — D-110's connector push + verify still runs, every
#      time, unconditionally; only the misleading "failure" label was removed.)
#   1  degraded but the book of record is sound — one broker only, a push that
#      failed for a reason OTHER than the known sandbox block, a later step
#      that failed. Gate stamped partial. PAGE.
#   2  halt. The journal could not be built or does not satisfy its contract,
#      or D-100's reconcile gate found an unexplained vanish, so nothing
#      downstream may run (ordering rule Arch-F9). Gate stamped fail BEFORE
#      exiting — a run that dies without stamping leaves tomorrow's Phase 0
#      waiting forever on something that is never coming. PAGE.
#
set -uo pipefail

DATE="${1:-}"
if [[ -z "$DATE" || ! "$DATE" =~ ^[0-9]{4}-[0-9]{2}-[0-9]{2}$ ]]; then
  echo "usage: $0 <YYYY-MM-DD> [--pull DIR]" >&2
  exit 2
fi
shift

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT" || exit 2

PULL="data/eod/$DATE/broker_pull"
REHEARSAL=0
while [[ $# -gt 0 ]]; do
  case "$1" in
    --pull) PULL="$2"; shift 2 ;;
    --rehearsal) REHEARSAL=1; shift ;;
    *) echo "unknown argument: $1" >&2; exit 2 ;;
  esac
done

EOD="data/eod/$DATE"
JOURNAL="data/journal/aegis_journal_$DATE.json"
ALLOCATED="${AEGIS_ALLOCATED_CAPITAL:-75000}"
# OUT is where THIS RUN's own artefacts land — its log, its summary, the closed-trade
# extract, the git_sync receipts. A rehearsal moves all of them under rehearsal/ so the
# live shelf is left exactly as the last real run left it.
OUT="$EOD"
PUSH_ARG=()
if (( REHEARSAL )); then
  OUT="$EOD/rehearsal"
  JOURNAL="$OUT/aegis_journal_$DATE.json"
  PUSH_ARG=(--dry-run)
fi
ARCHIVE="data/persistent/aegis_trade_journal_ARCHIVE_master.json"
EXCLUSIONS="data/persistent/non_aegis_exclusions.json"
MEMBERSHIP="data/persistent/option_membership.json"
EQUITY_MEMBERSHIP="data/persistent/aegis_membership.json"
STAGED="$EOD/staged_orders.json"
LOG="$OUT/post_market_run.log"
SUMMARY="$OUT/post_market_run.json"
mkdir -p "$EOD" "$OUT" data/journal

WORST=0          # highest exit code any step reached
RESULTS=()       # "name|status|detail" per job, for the closing checklist

# D-111: the exact, byte-for-byte signature of the sandbox git-proxy blocking a native push —
# every run here hits this, every time, and it always self-heals via the GitHub connector (D-110,
# mandatory regardless of this script's own exit code). Matched against git_sync.py's own JSON
# output so the two push jobs below can tell this ROUTINE, expected condition apart from a real,
# unrecognized push failure that still deserves to page.
GIT_PROXY_BLOCK_SIGNATURE='access denied by the git proxy'

say() { printf '%s\n' "$*" | tee -a "$LOG"; }

record() { RESULTS+=("$1|$2|${3:-}"); }

# Escalate the run's verdict. A step never lowers it: partial then ok is still
# partial, and a halt is final.
worse() { (( $1 > WORST )) && WORST=$1; return 0; }

# Stamp the gate and leave. Called on EVERY exit path, including the halts —
# stamping is what makes the failure visible to tomorrow rather than silent.
finish() {
  local code="$1" note="$2" status
  case "$code" in
    0) status=ok ;;
    1) status=partial ;;
    *) status=fail ;;
  esac
  if (( REHEARSAL )); then
    record "gate stamped" skipped "rehearsal — would have been $status"
  else
    local stamp_out stamp_rc
    stamp_out="$(python3 tools/phase_gate.py stamp --phase post_market --status "$status" \
                   --journal-date "$DATE" --note "$note" 2>&1)"
    stamp_rc=$?
    if (( stamp_rc == 0 )); then
      record "gate stamped" pass "$status"
    else
      record "gate stamped" FAIL "$stamp_out"
      code=2
    fi
  fi
  say ""
  say "POST-MARKET $DATE — exit $code (gate: $status)"
  say "-----------------------------------------------"
  local line name st detail
  for line in "${RESULTS[@]}"; do
    name="${line%%|*}"; st="${line#*|}"; detail="${st#*|}"; st="${st%%|*}"
    printf '  %-24s %s%s\n' "$name" "$st" "${detail:+  — $detail}" | tee -a "$LOG"
  done
  {
    printf '{\n "date": "%s",\n "exit_code": %s,\n "gate_status": "%s",\n' "$DATE" "$code" "$status"
    printf ' "note": "%s",\n "jobs": [\n' "${note//\"/\'}"
    local first=1
    for line in "${RESULTS[@]}"; do
      name="${line%%|*}"; st="${line#*|}"; detail="${st#*|}"; st="${st%%|*}"
      (( first )) || printf ',\n'; first=0
      printf '  {"job": "%s", "status": "%s", "detail": "%s"}' \
             "$name" "$st" "${detail//\"/\'}"
    done
    printf '\n ]\n}\n'
  } > "$SUMMARY"
  say ""
  say "log:     $LOG"
  say "summary: $SUMMARY"
  exit "$code"
}

# Run one deterministic tool. fatal=1 means its failure halts the run.
step() {
  local name="$1" fatal="$2"; shift 2
  say ""
  say "--- $name"
  local out rc
  out="$("$@" 2>&1)"; rc=$?
  printf '%s\n' "$out" | tee -a "$LOG" >/dev/null
  printf '%s\n' "$out" | sed 's/^/    /'
  if (( rc == 0 )); then
    record "$name" pass
  elif (( rc == 1 && fatal == 0 )); then
    record "$name" DEGRADED "exit 1"
    worse 1
  else
    record "$name" FAIL "exit $rc"
    if (( fatal )); then
      say ""
      say "HALT: $name returned $rc and nothing downstream of it may run (Arch-F9)."
      finish 2 "$name failed with exit $rc"
    fi
    worse 1
  fi
  return $rc
}

say "==============================================="
say "POST-MARKET $DATE   (deterministic batch, D-93 + D-99/D-100/D-101/D-102 fixes)"
say "started $(date -u '+%Y-%m-%dT%H:%M:%SZ') UTC / $(TZ=Asia/Singapore date '+%Y-%m-%d %H:%M') SGT"
say "repo: $ROOT"
say "==============================================="

# --------------------------------------------------------------- 0. inputs
if [[ ! -d "$PULL" ]]; then
  record "broker payloads" FAIL "$PULL does not exist"
  say "No broker payloads at $PULL — the harness must pull Tiger and save"
  say "them there before this script runs. Nothing was built."
  finish 2 "broker payload directory missing"
fi
PAYLOADS=$(find "$PULL" -maxdepth 1 -name '*.json' | wc -l | tr -d ' ')
record "broker payloads" pass "$PAYLOADS file(s) in $PULL"
say "$PAYLOADS payload file(s) found in $PULL"

# --------------------------------------------------------- 0.5 (D-100) reconcile
# HARD GATE: diff yesterday's held equity tickers against today's stock_positions pull.
# Any ticker that vanished with NO matching fill in tiger_filled_orders.json halts the run —
# get_filled_orders is known to silently drop stop-triggered equity closes, and a vanished
# position with nothing recorded is a real, capital-affecting event, not a data nicety.
PRIOR="$(python3 tools/journal_build.py prior --date "$DATE")"
if [[ -n "$PRIOR" ]] && [[ -f "$PRIOR" ]] && [[ -f "$PULL/tiger_stock_positions.json" ]] && [[ -f "$PULL/tiger_filled_orders.json" ]]; then
  RECON_OUT="$(python3 tools/reconcile_vanished_positions.py --prior "$PRIOR" \
    --stock-positions "$PULL/tiger_stock_positions.json" \
    --filled-orders "$PULL/tiger_filled_orders.json" 2>&1)"
  RECON_RC=$?
  printf '%s\n' "$RECON_OUT" | sed 's/^/    /'
  if (( RECON_RC != 0 )); then
    record "reconcile vanished positions (D-100)" FAIL "unexplained vanish — see output above"
    say ""
    say "HALT: a position vanished from the broker book with no matching fill on file."
    say "Recover the missing fill (get_transactions per ticker, live MCP call — the"
    say "orchestrating Claude session must do this, not this script) and append it to"
    say "$PULL/tiger_filled_orders.json before re-running."
    finish 2 "D-100 reconcile gate: unexplained vanished position"
  fi
  record "reconcile vanished positions (D-100)" pass
else
  record "reconcile vanished positions (D-100)" skipped "no prior journal or incomplete payload — nothing to reconcile"
fi

# --------------------------------------------------------------- 1. preflight
step "preflight" 0 python3 tools/preflight.py || worse 1

# --------------------------------------------------------------- 2. journal
step "journal build" 1 python3 tools/journal_build.py build --date "$DATE" --pull "$PULL" \
     --allocated "$ALLOCATED" --out "$JOURNAL"

# --------------------------------------------------------- 3. Aegis membership
STAGED_ARG=()
if [[ -f "$STAGED" ]]; then
  STAGED_ARG=(--staged "$STAGED")
  say "staged-orders list: $STAGED"
elif [[ -f "$EQUITY_MEMBERSHIP" ]]; then
  STAGED_ARG=(--staged "$EQUITY_MEMBERSHIP")
  say "known continuing AEGIS membership: $EQUITY_MEMBERSHIP (so confirmed holdings don't re-flag every day)"
else
  say "no staged-orders list and no known-membership file — every unmatched fill is AUTO-INCLUDED"
  say "as confirmed (D-106), flagged auto_included_unrecognized. The PM's only lever is reject."
fi

# D-106: persist today's auto-includes onto the membership file so tomorrow's classify matches
# them under --staged and confirms silently instead of re-flagging every day. A rehearsal run
# points this at a throwaway copy under $OUT instead of the live file — it still shows what
# WOULD be added (in the job's own JSON output) without mutating the live shelf.
MEMBERSHIP_FOR_CLASSIFY="$EQUITY_MEMBERSHIP"
if (( REHEARSAL )); then
  MEMBERSHIP_FOR_CLASSIFY="$OUT/aegis_membership_rehearsal.json"
  [[ -f "$EQUITY_MEMBERSHIP" ]] && cp -p "$EQUITY_MEMBERSHIP" "$MEMBERSHIP_FOR_CLASSIFY"
fi

# held_book_refresh.load_exclusions / option_book.load_membership both already treat a missing
# file as an empty store (FileNotFoundError -> {}) — no need to pre-create either path, which
# matters in --rehearsal: writing a fresh persistent file on a rehearsal run would itself be a
# live-shelf mutation, exactly what --rehearsal promises not to do.
step "equity membership" 1 python3 tools/held_book_refresh.py classify \
     --journal "$JOURNAL" --exclusions "$EXCLUSIONS" "${STAGED_ARG[@]}" \
     --membership "$MEMBERSHIP_FOR_CLASSIFY" --out "$JOURNAL"

step "option membership" 1 python3 tools/option_book.py classify \
     --journal "$JOURNAL" --membership "$MEMBERSHIP" "${STAGED_ARG[@]}" --out "$JOURNAL"

# --------------------------------------------------------- 3.5 (D-99) dynCap
# HARD FIX: journal_build's own dynCap (job 2 above) was computed BEFORE this classify step —
# its unrealised-P&L sum still included every co-mingled broker holding. Recompute now, over the
# post-classification (Aegis-only) open_positions, sourcing realised P&L from the archive ledger
# (idempotent — see tools/recompute_dyncap.py's own docstring for why a running counter broke).
step "recompute dynCap (D-99)" 1 python3 tools/recompute_dyncap.py \
     --journal "$JOURNAL" --allocated "$ALLOCATED" --one-r-pct 1.5 --out "$JOURNAL"

step "hedge derivation" 1 python3 tools/option_book.py derive-hedge --journal "$JOURNAL" --out "$JOURNAL"

PRIOR_ARG=()
if [[ -n "$PRIOR" ]]; then
  PRIOR_ARG=(--prior "$PRIOR")
  say "prior journal: $PRIOR"
else
  say "no prior journal exists — nothing to carry forward (first run, not a fault)"
fi
step "carry-forward" 1 python3 tools/held_book_refresh.py carry-forward \
     --journal "$JOURNAL" "${PRIOR_ARG[@]}" --out "$JOURNAL"

# --------------------------------------------------------------- 4. verify
step "journal verified" 1 python3 tools/journal_build.py verify --date "$DATE" --journal "$JOURNAL"

# --------------------------------------------------------------- 5. push #1
# D-111 (PM ruling 2026-09-06 — "why even show the fail which is useless, inaccurate... remove it
# to avoid false alarms"). The sandbox git proxy blocking a native push with this EXACT signature
# is not a finding — it is the normal, 100%-of-runs shape of every push in this environment, and
# it self-heals every time via the GitHub connector (D-110, mandatory, unconditional, runs
# regardless of what this script reports). Recording it as "FAIL" and degrading the run to
# "partial" was itself the bug: it manufactured a page-worthy-looking alarm out of a routine,
# always-expected, always-fixed event, and trained everyone reading the log to ignore red text —
# which is exactly how the REAL 2026-09-04 gap (a push that landed but never got re-stamped) went
# unnoticed. Only an UNRECOGNIZED push failure — one that doesn't match this known signature —
# still counts as a real finding and still degrades the run.
say ""
say "--- push (book of record)"
if python3 tools/git_sync.py -m "post-market $DATE: journal" "${PUSH_ARG[@]}" \
     > "$OUT/git_sync_result.json" 2>&1; then
  if (( REHEARSAL )); then
    record "GitHub push (journal)" skipped "rehearsal — dry run"
    say "    rehearsal: dry run, nothing pushed"
  elif grep -q '"pushed": true' "$OUT/git_sync_result.json"; then
    record "GitHub push (journal)" pass
    say "    pushed"
  elif grep -q "$GIT_PROXY_BLOCK_SIGNATURE" "$OUT/git_sync_result.json"; then
    record "GitHub push (journal)" expected "sandbox git-proxy block (every run, not a fault) — GitHub connector delivers this next"
    say "    committed locally — native push blocked by the sandbox git proxy, exactly as every"
    say "    run here. This is expected, not a fault, and does not affect the verdict. The"
    say "    connector delivery + verify (D-110) is mandatory and runs next regardless."
  else
    record "GitHub push (journal)" FAIL "committed locally, not pushed — reason does not match the known sandbox block"
    say "    committed locally but NOT pushed, for a reason that is NOT the routine sandbox"
    say "    git-proxy block — this IS a real finding. See $OUT/git_sync_result.json and page."
    worse 1
  fi
else
  record "GitHub push (journal)" FAIL "git_sync errored"
  worse 1
fi
sed 's/^/    /' "$OUT/git_sync_result.json" | head -20

# --------------------------------------------------------------- 6. metrics
step "portfolio metrics" 0 python3 tools/portfolio_metrics.py compute --journal "$JOURNAL" --out "$JOURNAL"

# --------------------------------------------------------------- 7. archive
say ""
say "--- archive ledger"
ARCHIVE_FOR_BRIEF="$ARCHIVE"   # D-108: which archive file overnight_brief.py reads below
CLOSED_TMP="$OUT/closed_trades_$DATE.json"
ARCHIVE_FMT_TMP="$OUT/closed_trades_archive_format_$DATE.json"
CLOSED_N=$(python3 - "$JOURNAL" "$CLOSED_TMP" <<'PY'
import json, os, sys
closed = json.load(open(sys.argv[1])).get("closed_trades") or []
if closed:
    json.dump(closed, open(sys.argv[2], "w"), indent=1)
elif os.path.exists(sys.argv[2]):
    os.remove(sys.argv[2])
print(len(closed))
PY
)
CLOSED_N="${CLOSED_N:-0}"
say "    $CLOSED_N closed trade(s) today"
if (( CLOSED_N == 0 )); then
  record "archive ledger" skipped "no closed trades today"
  say "    no closed trades — archive untouched (the tool's own no_op rule)"
else
  # D-102 FIX: journal_build's closed_trades schema ({closed_date, realised_usd, ...}) does not
  # match archive_ledger.py's expected input ({exitDate, pnlUsd, ...}) — convert first, or every
  # real close gets archived with pnlUsd=0.0 and exitDate=null.
  python3 tools/journal_closed_to_archive_format.py --journal "$JOURNAL" --out "$ARCHIVE_FMT_TMP" | sed 's/^/    /'
  # A missing archive is seeded from an in-memory empty store, NEVER by writing to $ARCHIVE
  # directly — doing that unconditionally would itself mutate the live shelf on a rehearsal run.
  ARCHIVE_READ="$ARCHIVE"
  if [[ ! -f "$ARCHIVE" ]]; then
    ARCHIVE_READ="$OUT/empty_archive_seed.json"
    echo '{"archive_meta": {}, "closed_trades_ledger": []}' > "$ARCHIVE_READ"
    say "    no archive on disk yet — merging against an empty seed (first-ever close in this fund's history)"
  fi
  ARCH_TMP="$OUT/archive_merged_$DATE.json"
  if python3 tools/archive_ledger.py merge --archive "$ARCHIVE_READ" --closed "$ARCHIVE_FMT_TMP" \
       --today "$DATE" --out "$ARCH_TMP" 2>&1 | tee -a "$LOG" | sed 's/^/    /'; then
    if (( REHEARSAL )); then
      record "archive ledger" skipped "rehearsal — merge computed, archive not overwritten"
      say "    rehearsal: merge succeeded, archive left untouched ($ARCH_TMP kept)"
      ARCHIVE_FOR_BRIEF="$ARCH_TMP"   # today's true rollups, without touching the live shelf
    else
      mv "$ARCH_TMP" "$ARCHIVE"
      record "archive ledger" pass "$CLOSED_N trade(s) filed"
    fi
  else
    record "archive ledger" FAIL "merge failed — archive left untouched"
    rm -f "$ARCH_TMP"
    worse 1
  fi
fi

# ----------------------------------------------------- 7.5 (D-108) overnight brief
# PM ruling 2026-09-06: PTJ ran clean but nothing assembled "what changed overnight, what's my
# open risk, what's my realised MTD/WTD/YTD, what's my book beta/exposure" into one place — the
# PM was reconstructing it from memory or the broker screen. Pure read+assemble over what every
# job above this point already produced: today's journal (membership-classified, dynCap-recomputed,
# metrics-computed), the prior day's journal (for the overnight diff), and the archive ledger (for
# the realised rollups, WTD added by D-107). No new broker calls, no judgement (law 4).
BRIEF="$OUT/overnight_brief_$DATE.json"
BRIEF_ARGS=(--journal "$JOURNAL" --out "$BRIEF")
if [[ -n "$PRIOR" ]]; then
  BRIEF_ARGS+=(--prior "$PRIOR")
fi
if [[ -f "$ARCHIVE_FOR_BRIEF" ]]; then
  BRIEF_ARGS+=(--archive "$ARCHIVE_FOR_BRIEF")
else
  say "    no archive on disk yet — overnight brief will show all-zero realised P&L (true, not a fault)"
fi
step "overnight brief (D-108)" 0 python3 tools/overnight_brief.py build "${BRIEF_ARGS[@]}"

# --------------------------------------------------------------- 8. flow audit
FA_JSON="$EOD/flow_audit_$DATE.json"
FA_HTML="$EOD/flow_audit_$DATE.html"
if (( REHEARSAL )); then
  for f in "$FA_JSON" "$FA_HTML"; do [[ -f "$f" ]] && cp -p "$f" "$f.prerehearsal"; done
fi
step "flow audit" 0 python3 tools/daily_flow_audit.py "$DATE" --render
if (( REHEARSAL )); then
  for f in "$FA_JSON" "$FA_HTML"; do
    [[ -f "$f" ]] && mv "$f" "$OUT/$(basename "$f")"
    [[ -f "$f.prerehearsal" ]] && mv "$f.prerehearsal" "$f"
  done
  say "    rehearsal: audit written to $OUT, live shelf restored"
fi

# --------------------------------------------------------------- 9. push #2
say ""
say "--- push (metrics, archive, audit)"
if python3 tools/git_sync.py -m "post-market $DATE: metrics, archive, audit" "${PUSH_ARG[@]}" \
     > "$OUT/git_sync_result_final.json" 2>&1; then
  if (( REHEARSAL )); then
    record "GitHub push (final)" skipped "rehearsal — dry run"
    say "    rehearsal: dry run, nothing pushed"
  elif grep -q '"pushed": true' "$OUT/git_sync_result_final.json"; then
    record "GitHub push (final)" pass
    say "    pushed"
  elif grep -q '"reason": "nothing to commit' "$OUT/git_sync_result_final.json" 2>/dev/null; then
    record "GitHub push (final)" pass "nothing new to push"
    say "    nothing new since the first push"
  elif grep -q "$GIT_PROXY_BLOCK_SIGNATURE" "$OUT/git_sync_result_final.json"; then
    # D-111 — see push #1's comment. Same routine, expected, self-healing condition.
    record "GitHub push (final)" expected "sandbox git-proxy block (every run, not a fault) — GitHub connector delivers this next"
    say "    committed locally — native push blocked by the sandbox git proxy, as expected."
  else
    record "GitHub push (final)" FAIL "committed locally, not pushed — reason does not match the known sandbox block"
    say "    committed locally but NOT pushed, for a reason that is NOT the routine sandbox"
    say "    git-proxy block — this IS a real finding. See $OUT/git_sync_result_final.json and page."
    worse 1
  fi
else
  record "GitHub push (final)" FAIL "git_sync errored"
  worse 1
fi
sed 's/^/    /' "$OUT/git_sync_result_final.json" | head -20

# --------------------------------------------------------------- 10. verdict
NOTE="deterministic batch: all jobs passed"
(( WORST == 1 )) && NOTE="deterministic batch completed degraded — see $SUMMARY"
finish "$WORST" "$NOTE"
