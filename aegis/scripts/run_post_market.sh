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
#   0  every job passed. Gate stamped ok.
#   1  degraded but the book of record is sound — one broker only, a push that
#      did not land, a later step that failed. Gate stamped partial. PAGE.
#   2  halt. The journal could not be built or does not satisfy its contract,
#      so nothing downstream may run (ordering rule Arch-F9). Gate stamped
#      fail BEFORE exiting — a run that dies without stamping leaves tomorrow's
#      Phase 0 waiting forever on something that is never coming. PAGE.
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
# OUT is where THIS RUN's own artefacts land — its log, its summary, the closed-trade
# extract, the git_sync receipts. A rehearsal moves all of them under rehearsal/ so the
# live shelf is left exactly as the last real run left it. The first rehearsal (28 Jul)
# redirected only the journal and wrote six side artefacts into the live day folder,
# overwriting that day's real flow audit. A rehearsal that mutates the live shelf is not
# a rehearsal.
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
STAGED="$EOD/staged_orders.json"
LOG="$OUT/post_market_run.log"
SUMMARY="$OUT/post_market_run.json"
mkdir -p "$EOD" "$OUT" data/journal

WORST=0          # highest exit code any step reached
RESULTS=()       # "name|status|detail" per job, for the closing checklist

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
  # A rehearsal must NEVER stamp. The stamp is the one thing tomorrow's Phase 0 reads;
  # stamping it from a run that wrote no book of record would green-light the next phase
  # against a journal that does not exist.
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
say "POST-MARKET $DATE   (deterministic batch, D-93)"
say "started $(date -u '+%Y-%m-%dT%H:%M:%SZ') UTC / $(TZ=Asia/Singapore date '+%Y-%m-%d %H:%M') SGT"
say "repo: $ROOT"
say "==============================================="

# --------------------------------------------------------------- 0. inputs
# The payload directory is this script's entire input contract. If the harness
# did not save the pulls, say so here rather than building a book out of
# nothing and calling it the record.
if [[ ! -d "$PULL" ]]; then
  record "broker payloads" FAIL "$PULL does not exist"
  say "No broker payloads at $PULL — the harness must pull Tiger and IBKR and save"
  say "them there before this script runs. Nothing was built."
  finish 2 "broker payload directory missing"
fi
PAYLOADS=$(find "$PULL" -maxdepth 1 -name '*.json' | wc -l | tr -d ' ')
record "broker payloads" pass "$PAYLOADS file(s) in $PULL"
say "$PAYLOADS payload file(s) found in $PULL"

# --------------------------------------------------------------- 1. preflight
# Non-fatal on purpose (post_market step 1): the journal still writes without a
# push credential. But a run that cannot push is degraded, not clean — this is
# now the only book of record there is.
step "preflight" 0 python3 tools/preflight.py || worse 1

# --------------------------------------------------------------- 2. journal
# Operation 1: reconcile both payloads into the book. Exit 1 = one broker only
# (PARTIAL_SOURCES — a real book, page anyway). Exit 2 = no book could be
# built, or a row could not be mapped; halt.
step "journal build" 1 python3 tools/journal_build.py build --date "$DATE" --pull "$PULL" \
     --out "$JOURNAL"

# --------------------------------------------------------- 3. Aegis membership
# Operations 1a/1b/1c/2. Each mutates the journal in place. These are fatal:
# the file they leave behind IS the book, and a half-classified book is worse
# than none — an unclassified fill is another strategy's position sitting in
# Aegis's risk numbers.
STAGED_ARG=()
if [[ -f "$STAGED" ]]; then
  STAGED_ARG=(--staged "$STAGED")
  say "staged-orders list: $STAGED"
else
  say "no staged-orders list at $STAGED — every unmatched fill lands as pending_review,"
  say "which is the designed behaviour, not a fault."
fi

step "equity membership" 1 python3 tools/held_book_refresh.py classify \
     --journal "$JOURNAL" --exclusions "$EXCLUSIONS" "${STAGED_ARG[@]}"

step "option membership" 1 python3 tools/option_book.py classify \
     --journal "$JOURNAL" --membership "$MEMBERSHIP" "${STAGED_ARG[@]}"

# derive-hedge is the ONLY writer of the `hedge` record. journal_build carries
# a prior record but never edits one, and quarantines a malformed one — this is
# the step entitled to rebuild it from the confirmed legs.
step "hedge derivation" 1 python3 tools/option_book.py derive-hedge --journal "$JOURNAL"

# --prior is the most recent journal before today. Resolved by journal_build's own
# _latest_prior so there is exactly one answer to "which journal came before this one" —
# omitting it silently carries nothing forward, which reads identically to having nothing
# to carry.
PRIOR="$(python3 tools/journal_build.py prior --date "$DATE")"
PRIOR_ARG=()
if [[ -n "$PRIOR" ]]; then
  PRIOR_ARG=(--prior "$PRIOR")
  say "prior journal: $PRIOR"
else
  say "no prior journal exists — nothing to carry forward (first run, not a fault)"
fi
step "carry-forward" 1 python3 tools/held_book_refresh.py carry-forward \
     --journal "$JOURNAL" "${PRIOR_ARG[@]}"

# --------------------------------------------------------------- 4. verify
# Four tools have now rewritten the file journal_build validated. Read it back
# off disk and re-check the contract. Fatal — Arch-F9.
step "journal verified" 1 python3 tools/journal_build.py verify --date "$DATE" --journal "$JOURNAL"

# --------------------------------------------------------------- 5. push #1
# The book of record reaches GitHub the moment it is sound, before the later
# steps get a chance to fail. Every run is a fresh clone in a fresh session; a
# file that only ever reached local disk is invisible to tomorrow forever.
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
  else
    record "GitHub push (journal)" FAIL "committed locally, not pushed"
    say "    committed locally but NOT pushed — see $OUT/git_sync_result.json"
    worse 1
  fi
else
  record "GitHub push (journal)" FAIL "git_sync errored"
  worse 1
fi
sed 's/^/    /' "$OUT/git_sync_result.json" | head -20

# --------------------------------------------------------------- 6. metrics
# Not fatal: a journal without metrics is still a true book, and the failure is
# named in the checklist rather than taking the record down with it.
step "portfolio metrics" 0 python3 tools/portfolio_metrics.py compute --journal "$JOURNAL"

# --------------------------------------------------------------- 7. archive
say ""
say "--- archive ledger"
CLOSED_TMP="$OUT/closed_trades_$DATE.json"
# The extract is written ONLY when there is something to extract. An empty [] on the
# shelf is worse than no file: it gets committed, and a later reader cannot tell "we
# closed nothing today" from "the extract ran before the closes were booked".
CLOSED_N=$(python3 - "$JOURNAL" "$CLOSED_TMP" <<'PY'
import json, os, sys
closed = json.load(open(sys.argv[1])).get("closed_trades") or []
if closed:
    json.dump(closed, open(sys.argv[2], "w"), indent=1)
elif os.path.exists(sys.argv[2]):
    os.remove(sys.argv[2])          # a stale extract from an earlier run of the same day
print(len(closed))
PY
)
CLOSED_N="${CLOSED_N:-0}"
say "    $CLOSED_N closed trade(s) today"
if (( CLOSED_N == 0 )); then
  record "archive ledger" skipped "no closed trades today"
  say "    no closed trades — archive untouched (the tool's own no_op rule)"
elif [[ ! -f "$ARCHIVE" ]]; then
  # Closed trades with nowhere to file them is a real gap, not a quiet skip.
  record "archive ledger" FAIL "$CLOSED_N closed trade(s) but $ARCHIVE does not exist"
  say "    $CLOSED_N closed trade(s) and no archive file at $ARCHIVE — NOT filed."
  worse 1
else
  ARCH_TMP="$OUT/archive_merged_$DATE.json"
  if python3 tools/archive_ledger.py merge --archive "$ARCHIVE" --closed "$CLOSED_TMP" \
       --today "$DATE" --out "$ARCH_TMP" 2>&1 | tee -a "$LOG" | sed 's/^/    /'; then
    # The integrity gate lives inside the tool (it raises if the per-day sums
    # don't reconcile to YTD). Only a clean merge is allowed to overwrite.
    if (( REHEARSAL )); then
      record "archive ledger" skipped "rehearsal — merge computed, archive not overwritten"
      say "    rehearsal: merge succeeded, archive left untouched ($ARCH_TMP kept)"
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

# --------------------------------------------------------------- 8. flow audit
# daily_flow_audit.py writes to data/eod/<DATE>/ with no --out — the path is baked in,
# because the audit's whole job is to reconstruct that day's shelf in place. Rather than
# widen that tool's interface for the sake of a rehearsal, a rehearsal stashes whatever
# is already there, lets the audit write, moves the fresh pair into rehearsal/, and puts
# the originals back. Net effect on the live shelf: nothing.
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
# The hole this closes: git_sync used to run once, in step 2, BEFORE metrics,
# the archive append and the audit existed. A fresh clone therefore read a
# journal with an empty `metrics` key until the following day's run overwrote
# it. Both pushes stay — the first protects the book, the second ships the rest
# of the same run.
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
  else
    record "GitHub push (final)" FAIL "committed locally, not pushed"
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
