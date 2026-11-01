#!/usr/bin/env python3
"""canon_handoff.py — hand the READING out, keep the GATES here.

WHY THIS EXISTS
    canon_build.py assumes one operator does everything: chunk the text, extract it,
    diff it, author the spine, lock it. That assumption breaks the moment the person
    holding the texts is not the process running the gates.

    This tool splits the job at exactly that seam:

        EXTERNAL SYSTEM              THIS REPO
        ----------------            ----------------
        has the texts               has the voice cards
        does the READING            does the GATING
        produces a package    -->   canon_handoff.py import
                                    -> blindness gate
                                    -> seal (freeze gate)
                                    -> diff (direction gate)
                                    -> methods (paraphrase gate)
                                    -> PM spotcheck -> lock -> index

    Nothing about the trust model changes. The external system is treated as an
    UNTRUSTED PRODUCER: every artefact it returns is re-validated here against the
    same gates a local run would face, and any artefact that cannot pass is rejected
    rather than repaired. It cannot lock a voice; only the PM's signature does that.

THE THREE PHASES — RUN THEM IN DIFFERENT CONTEXTS, THIS IS THE WHOLE POINT

    PHASE A  BLIND EXTRACTION      the reader must never have seen the voice card,
                                   and must never have seen a sibling source's
                                   extract. Enforced on return by the blindness gate
                                   (8-gram overlap), so a violation is caught, not
                                   trusted away.
    PHASE B  SIGHTED DIFF + SPINE  now the card is allowed in. Direction is fixed:
                                   extract -> card. Never card -> extract.
    PHASE C  METHOD SECTIONS       layer 2, 1500-3000 words each, paraphrase only
                                   (this repo is public).

    Phase A and Phase B MUST be separate contexts/sessions in the external system.
    If one context does both, the blindness gate is meaningless — the reader will
    have seen the card before it read the book, which is the exact failure
    (confirmation-shopping) this entire chain exists to prevent.

COMMANDS
    canon_handoff.py brief <voice> --phase a [--source KEY]   write the job spec
    canon_handoff.py brief <voice> --phase b
    canon_handoff.py brief <voice> --phase c
    canon_handoff.py briefs                                   all voices, all phases
    canon_handoff.py import <voice> --package <dir>           ingest + run every gate
    canon_handoff.py status                                   what is back, what is not
"""
import argparse
import json
import os
import shutil
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import canon_build as cb  # noqa: E402  — single source of truth for gates and constants

ROOT = cb.ROOT
HANDOFF = os.path.join(ROOT, "canon", "handoff")
BRIEFS = os.path.join(HANDOFF, "briefs")


def ok(m):
    print(f"  ok  {m}")


def die(m):
    print(f"HANDOFF REJECTED — {m}", file=sys.stderr)
    sys.exit(1)


# ------------------------------------------------------------------ briefs

BRIEF_A = """# PHASE A — BLIND EXTRACTION · {voice} · {title}

**Run this in a context that has never seen, and will never be shown, the Aegis voice
card for `{voice}`.** If the same session later runs Phase B, discard this work and
start again — a reader who knows the conclusion finds the conclusion.

Do not read another source for this same voice in this context either. `{voice}` has
{n_sources} source(s) and each one is read blind of the others; they meet for the first
time at the diff, in Phase B.

## The text
| field | value |
|---|---|
| voice | `{voice}` |
| source key | `{skey}` |
| title | {title} |
| author | {author} |
| year | {year} |
| citation code | `{code}` |
| weight | {weight} |
| kind | {kind} |
{note}

## Step 1 — chunk it

Split the text into chunks of about **{words} words**, breaking only at page boundaries,
and prefix every page's text with a marker on its own line:

    [p.417]
    ...the text of page 417...

Page markers are not decoration. Every extracted record must carry a real page number,
because a canon line without a page is not citable and will be rejected here.

Number the chunks `0001`, `0002`, ... and write `chunk_manifest.json`:

```json
{{"voice": "{voice}", "source": "{skey}", "pdf_sha256": "<sha256 of the source file>",
 "chunk_words_target": {words},
 "chunks": [{{"chunk": "0001", "pages": [1, 9], "words": 1183, "sha256": "<sha256 of the chunk text>"}}]}}
```

Return the manifest. **Do not return the chunk text itself** — this repo is public and
the chunks are the book. They stay on your side.

## Step 2 — extract, one chunk at a time

For each chunk, run the prompt below **verbatim** with `{{chunk}}` replaced by the chunk
id and the chunk text appended. Save the exact prompt text you used to
`prompts/{skey}-<chunk>.md`, and return those too — they are re-checked here for n-gram
overlap against the voice card. That check is why the prompts are part of the package
and not an afterthought.

Append every record from every chunk to a single `extract.jsonl`, ids running
`{skey}#001`, `{skey}#002`, ... across the whole source without restarting per chunk.

---

{prompt}

---

## What gets rejected on return

| rejected because | fix |
|---|---|
| a record is missing `id`/`source`/`chunk`/`page`/`quote`/`principle`/`operational`/`kind` | all eight are required |
| `id` not namespaced `{skey}#NNN`, or duplicated | provenance must be unambiguous |
| `chunk` not in the manifest | the record cites a chunk that does not exist |
| `kind` outside rule/observation/caution/definition | fixed vocabulary |
| `page` missing, zero, or not an integer | never guess a page; drop the record instead |
| `quote` longer than {maxq} words | quote the {maxq} that carry the claim, rest goes in `principle` |
| your prompt shares 8-gram text with the voice card | the reader was not blind — the whole extract is void |

## Completeness, not selection

Do not rank, do not pick "the important ones", do not skip a chapter because it repeats
an earlier one. A chunk with nothing operational in it yields no records and that is a
correct outcome. Under-extraction is the failure mode that is invisible later: a
principle that was never recorded cannot be missed at the diff, because nothing points
at the hole.
"""

BRIEF_B = """# PHASE B — SIGHTED DIFF + SPINE · {voice}

**This is a different context from Phase A.** The card is allowed in here, and only
here, and only after every source has been extracted and sealed.

Sources for `{voice}`: {srclist}

## The card as it stands today

This is the existing voice card. It was written from LLM recall, not from the texts.
Treat it as a HYPOTHESIS to be tested, never as a target to be confirmed.

```
{card}
```

## Step 1 — diff.json

Direction is fixed and one-way: **extract -> card**. You read what the books actually
say and ask what the card got right, what it missed, and what it made up. You never
start from a card line and hunt for a quote that agrees with it.

Write `diff.json`:

```json
{{"voice": "{voice}",
 "extract_sha": {{ "<source_key>": "<the sealed sha, supplied to you after seal>" }},
 "direction": "extract -> card (never the reverse)",
 "book_supports_card": [{{"extract_id": "{ex}#014", "card_line": "<the line>", "note": "<how it supports it>"}}],
 "book_missing_from_card": [{{"extract_id": "{ex}#087", "note": "<what the book says that the card never mentions>"}}],
 "card_unsupported_by_book": [{{"card_line": "<the line>", "searched_sources": {srckeys},
                               "note": "<what you looked for and did not find>"}}],
 "cross_source": [{{"extract_ids": ["a#1", "b#7"], "relation": "agrees|refines|supersedes|unique",
                    "superseded_by": "b#7", "note": "<what the later text does to the earlier>"}}]}}
```

Four buckets, and the asymmetry between them is deliberate:

- **book_supports_card** — the card was right. Cheap. Expect most of the card here.
- **book_missing_from_card** — the book says something operational the card never
  carried. This is a FINDING, and it is the reason the exercise is worth doing. A diff
  with an empty `book_missing_from_card` almost certainly means the reader was
  confirming, not reading.
- **card_unsupported_by_book** — the card asserts something no source supports. This is
  a DEFECT, and it only counts if you searched **every** source and all of them are
  silent. `searched_sources` must list all of them or the entry is rejected here. A
  card line is not a defect merely because the one book you happened to open is quiet.
- **cross_source** — where two texts touch the same ground. `supersedes` never deletes
  the earlier line; it marks it and names what replaced it, because the older method
  is often the one that still works.

## Step 2 — principles.yaml (LAYER 1, the spine)

{pmin}-{pmax} lines. Fewer is a bumper sticker; more is the book. Authored **from the
diff**, not from the card — if a card line survives, it survives because an extract id
carries it.

```yaml
principles:
  - id: C1                       # C1..C99; the voice cites these ids at runtime
    text: "<one line the voice can actually apply>"
    status: verified             # verified | pm_override | unsourced_retained
    cite:
      - {{code: {code}, page: 112, extract_id: "{ex}#014"}}
    relation: refines            # optional: agrees|refines|supersedes|unique
    supersedes: C7               # required when relation is 'supersedes'
recognisers:
  - id: R1
    if: "<the author's own if-condition, in field terms>"
    then: "<what the author says that means>"
    fields: [sc_momentum, rvol]  # must be on this voice's data menu
```

`status: verified` requires a citation with a page and a real extract id. `status:
unsourced_retained` is for a card line you judge worth keeping although no text
supports it — it carries NO citation and it is counted and shown, so the PM can see
exactly how much of the voice is still hearsay. That visibility is the point; do not
use `verified` to make the count look better.

Recognisers are the author's own if-then tests, expressed against fields the system
actually computes. A recogniser that needs a field we do not have is not a recogniser,
it is a wish — leave it out and note it in the diff instead.

## Do not

- Do not touch the extract. It is sealed and hashed; any edit breaks every downstream
  artefact by design.
- Do not write the `extract_sha` values from memory. They are supplied to you after
  `seal` runs on this side, and they are re-checked on import.
- Do not smooth a contradiction between two sources. Record it as `conflicted` in
  `cross_source` and let the desk deal with it. Two authors disagreeing is information.
"""

BRIEF_C = """# PHASE C — METHOD SECTIONS · {voice}

Layer 2 exists because a principle is a spine and a spine cannot be followed. "Cut your
losses short" is not a method — it is the *title* of a method. This layer is the
author's actual procedure, at the length it takes to be executable.

One file per method: `methods/<method_id>.md`.

```markdown
---
method_id: base_breakout
steps: [2, 3]        # which checklist steps on the voice card this method serves
cite:
  - {{code: {code}, page: 143}}
---

## Preconditions
<what must already be true before this method is even applicable>

## Sequence
<the actual procedure, in order, with the author's own thresholds where given>

## Exceptions
<the cases where the author says to do something different>

## Invalidators
<what tells you the setup has failed — the author's own abort conditions>
```

## Hard requirements

| requirement | why |
|---|---|
| {wmin}-{wmax} words of body | below {wmin} it is a summary again, which is the thing this layer exists to prevent; above {wmax} it is becoming the book |
| all four headings present | a method without invalidators is a recipe with no way to be wrong |
| `steps` maps to real checklist step numbers | the orchestrator injects methods by step, deterministically — a method that serves no step is never retrieved |
| **no verbatim run longer than {mpara} words from the extract** | these files are COMMITTED to a public repo; they must be paraphrase with page citation, never transcription |

That last one is checked mechanically on import against every quote in the extract, and
it is not negotiable regardless of how well a passage is written.

## How these get used at runtime

Pass 1 screens the whole universe on principles and recognisers only. Pass 2 takes the
3-5 finalists and the orchestrator injects the method sections keyed to the checklist
steps that actually fired — a lookup in `contracts/canon_index.json`, not a search. The
voice never goes looking for its own methods, because looking would require tools, and
tools would destroy the isolation the whole committee design rests on.

Write these for the methods that carry real weight. Two or three good ones beat ten
thin ones; a voice with no method sections still works, it just runs on the spine alone.
"""


def _brief_a(vkey, src):
    n = len(cb.voice_sources(vkey))
    prompt = cb.EXTRACTOR_PROMPT.format(title=src["title"], author=src["author"],
                                        year=src.get("year", "n.d."), source=src["key"],
                                        chunk="{chunk}", chunk_text="{chunk_text}")
    note = ""
    if src.get("note"):
        note = f"\n> **Note from the registry:** {src['note']}\n"
    if src.get("kind") == "system_source":
        note += ("\n> This source is not a book — it is our own field dictionary. "
                 "Chunking is done on this side by `canon_build.py chunk-system`; you only "
                 "need Phase B and C for this voice.\n")
    return BRIEF_A.format(voice=vkey, skey=src["key"], title=src["title"],
                          author=src["author"], year=src.get("year", "n.d."),
                          code=src["code"], weight=src.get("weight", "—"),
                          kind=src.get("kind", "book"), n_sources=n, note=note,
                          words=1200, prompt=prompt, maxq=cb.MAX_QUOTE_WORDS)


def _brief_b(vkey):
    srcs = cb.voice_sources(vkey)
    keys = [s["key"] for s in srcs]
    card = cb.read_card(vkey)
    return BRIEF_B.format(
        voice=vkey, card=card.strip(),
        srclist=", ".join(f"`{s['key']}` ({s['code']}, {s['author']} {s.get('year','')})" for s in srcs),
        srckeys=json.dumps(keys), ex=keys[0], code=srcs[0]["code"],
        pmin=cb.PRINCIPLES_MIN, pmax=cb.PRINCIPLES_MAX)


def _brief_c(vkey):
    srcs = cb.voice_sources(vkey)
    return BRIEF_C.format(voice=vkey, code=srcs[0]["code"],
                          wmin=cb.METHOD_MIN_WORDS, wmax=cb.METHOD_MAX_WORDS,
                          mpara=cb.MAX_PARAPHRASE_RUN)


def cmd_brief(a):
    os.makedirs(BRIEFS, exist_ok=True)
    written = []
    phases = [a.phase] if a.phase else ["a", "b", "c"]
    for ph in phases:
        if ph == "a":
            for s in cb.voice_sources(a.voice):
                if a.source and s["key"] != a.source:
                    continue
                p = os.path.join(BRIEFS, f"{a.voice}-A-{s['key']}.md")
                open(p, "w").write(_brief_a(a.voice, s))
                written.append(p)
        elif ph == "b":
            p = os.path.join(BRIEFS, f"{a.voice}-B-diff-and-spine.md")
            open(p, "w").write(_brief_b(a.voice))
            written.append(p)
        else:
            p = os.path.join(BRIEFS, f"{a.voice}-C-methods.md")
            open(p, "w").write(_brief_c(a.voice))
            written.append(p)
    for p in written:
        print(f"  {os.path.relpath(p, ROOT)}")
    print(f"{len(written)} brief(s) written.")
    if any("-B-" in p for p in written):
        print("  NOTE: the -B- brief CONTAINS THE VOICE CARD. Never send it to the context "
              "that runs Phase A.")


def cmd_briefs(a):
    reg = cb.load_registry()
    for vkey in sorted(reg.get("voices") or {}):
        cmd_brief(argparse.Namespace(voice=vkey, phase=None, source=None))


# ------------------------------------------------------------------ import

def _run(args):
    r = subprocess.run([sys.executable, os.path.join(ROOT, "tools", "canon_build.py")] + args,
                       capture_output=True, text=True)
    return r.returncode, (r.stdout + r.stderr).strip()


def cmd_import(a):
    pkg = os.path.abspath(a.package)
    if not os.path.isdir(pkg):
        die(f"no package directory at {pkg}")
    mpath = os.path.join(pkg, "package.json")
    if not os.path.isfile(mpath):
        die("package.json is missing — a package must declare what it is and who made it "
            "(voice, produced_by, produced_at, sources)")
    man = json.load(open(mpath))
    vkey = man.get("voice")
    if vkey != a.voice:
        die(f"package.json declares voice '{vkey}' but you asked to import '{a.voice}'")
    known = {s["key"] for s in cb.voice_sources(vkey)}
    got = list(man.get("sources") or [])
    unknown = [s for s in got if s not in known]
    if unknown:
        die(f"package carries source(s) {unknown} which are not registered for {vkey} in "
            f"canon/sources.yaml (have: {sorted(known)}). Register the source first — an "
            "unregistered source has no rights record, and rights are checked before reading.")
    if not man.get("produced_by"):
        die("package.json has no 'produced_by' — an untrusted producer must at least be named")

    print(f"IMPORT {vkey} — package by {man['produced_by']} ({man.get('produced_at','no date')})")
    print(f"  sources declared: {', '.join(got)}\n")

    # ---- per source: blindness gate FIRST, then install, then seal ----
    for skey in got:
        sd = os.path.join(pkg, skey)
        if not os.path.isdir(sd):
            die(f"package.json declares source '{skey}' but there is no {skey}/ directory")
        ex = os.path.join(sd, "extract.jsonl")
        cm = os.path.join(sd, "chunk_manifest.json")
        for f in (ex, cm):
            if not os.path.isfile(f):
                die(f"{skey}/: missing {os.path.basename(f)}")

        print(f"[{skey}] blindness gate")
        pd = os.path.join(sd, "prompts")
        prompts = sorted(glob_md(pd))
        if not prompts and not a.no_prompts:
            die(f"{skey}/prompts/ is empty. The prompts the reader actually used ARE the "
                "evidence of blindness — without them 'it was blind' is a claim, not a "
                "check. Return them, or re-run with --no-prompts to record the gate as "
                "UNVERIFIED (it will be stamped in the import receipt and the PM sees it).")
        for p in prompts:
            # dies on overlap with the card or with an already-installed sibling extract
            cb._blindness_gate(vkey, open(p).read(), skey, quiet=True)
        if prompts:
            ok(f"{len(prompts)} prompt(s) share no {cb.BLIND_NGRAM}-gram with the card "
               f"or with sibling extracts")
        else:
            print(f"  !!  blindness gate UNVERIFIED for {skey} — no prompts supplied")

        dest = cb.sdir(vkey, skey)
        os.makedirs(dest, exist_ok=True)
        shutil.copy(cm, os.path.join(dest, "chunk_manifest.json"))
        shutil.copy(ex, os.path.join(dest, "extract.jsonl"))
        if prompts:
            pdest = os.path.join(cb.vdir(vkey), "prompts")
            os.makedirs(pdest, exist_ok=True)
            for p in prompts:
                shutil.copy(p, os.path.join(pdest, f"{skey}-{os.path.basename(p)}"))

        print(f"[{skey}] seal (record schema + freeze gate)")
        rc, out = _run(["seal", vkey, skey])
        if rc:
            die(f"seal rejected {skey}:\n{out}")
        print("      " + out.replace("\n", "\n      "))

    # ---- diff ----
    dsrc = os.path.join(pkg, "diff.json")
    if os.path.isfile(dsrc):
        print("\n[diff] direction gate + freeze gate")
        # Install, then validate, then ROLL BACK on failure. A rejected artefact must not
        # be left on disk looking installed — a half-applied import is worse than none.
        ddest = os.path.join(cb.vdir(vkey), "diff.json")
        prev = open(ddest, "rb").read() if os.path.isfile(ddest) else None
        shutil.copy(dsrc, ddest)
        rc, out = _run(["diff", vkey])
        if rc:
            if prev is None:
                os.remove(ddest)
            else:
                open(ddest, "wb").write(prev)
            die("diff rejected (rolled back — nothing installed):\n" + out)
        print("      " + out.replace("\n", "\n      "))
    else:
        print("\n[diff] absent — Phase B not returned yet")

    # ---- principles + methods ----
    psrc = os.path.join(pkg, "principles.yaml")
    if os.path.isfile(psrc):
        shutil.copy(psrc, os.path.join(cb.vdir(vkey), "principles.yaml"))
        ok("principles.yaml installed (validated at lock, not here — lock is the gate)")
    msrc = os.path.join(pkg, "methods")
    incoming = sorted(f for f in os.listdir(msrc) if f.endswith(".md")) if os.path.isdir(msrc) else []
    if incoming:
        mdest = os.path.join(cb.vdir(vkey), "methods")
        os.makedirs(mdest, exist_ok=True)
        prev = {f: open(os.path.join(mdest, f), "rb").read()
                for f in os.listdir(mdest) if f.endswith(".md")}
        for f in incoming:
            shutil.copy(os.path.join(msrc, f), os.path.join(mdest, f))
        print(f"\n[methods] paraphrase gate on {len(incoming)} file(s)")
        rc, out = _run(["methods", vkey])
        if rc:
            for f in incoming:
                os.remove(os.path.join(mdest, f))
            for f, b in prev.items():
                open(os.path.join(mdest, f), "wb").write(b)
            die("method sections rejected (rolled back — nothing installed):\n" + out)
        print("      " + out.replace("\n", "\n      "))

    receipt = {
        "voice": vkey,
        "produced_by": man["produced_by"],
        "produced_at": man.get("produced_at"),
        "sources": got,
        "blindness_gate": "verified" if not a.no_prompts else "UNVERIFIED — no prompts supplied",
        "extract_sha": cb._extract_shas(vkey),
        "phases_returned": [p for p, c in (("A", True),
                                           ("B", os.path.isfile(dsrc)),
                                           ("C", os.path.isdir(msrc))) if c],
    }
    rp = os.path.join(cb.vdir(vkey), "import_receipt.json")
    json.dump(receipt, open(rp, "w"), indent=1)

    print(f"\nPACKAGE ACCEPTED — receipt at {os.path.relpath(rp, ROOT)}")
    print("\nIT IS NOT LOCKED. What is still on YOU, not on them:")
    for skey in got:
        print(f"  python3 tools/canon_build.py spotcheck {vkey} {skey}")
        print(f"      → open the physical text to the {cb.SPOTCHECK_N} pages it prints and "
              "confirm each quote is there and says what the record says")
        print(f"  python3 tools/canon_build.py spotcheck {vkey} {skey} --confirm N --by \"<you>\"")
    print(f"  python3 tools/canon_build.py lock {vkey} --sign \"<PM name>\"")
    print("  python3 tools/canon_build.py index && python3 tools/canon_build.py verify")
    print("\nThe hash chain proves the reader never saw the card. It does not prove the reader "
          "read the page correctly. Only you, with the text open, proves that.")


def glob_md(d):
    if not os.path.isdir(d):
        return []
    return [os.path.join(d, f) for f in os.listdir(d) if f.endswith((".md", ".txt"))]


# ------------------------------------------------------------------ status

def cmd_status(a):
    reg = cb.load_registry()
    print(f"{'voice':16s} {'sources':9s} {'extracted':10s} {'diff':6s} {'spine':6s} "
          f"{'methods':8s} {'spot':6s} {'lock':6s} producer")
    print("-" * 96)
    for vkey in sorted(reg.get("voices") or {}):
        srcs = cb.voice_sources(vkey)
        vd = cb.vdir(vkey)
        n_ex = sum(1 for s in srcs
                   if os.path.isfile(os.path.join(cb.sdir(vkey, s["key"]), "extract.sha256")))
        rp = os.path.join(vd, "import_receipt.json")
        who = json.load(open(rp))["produced_by"] if os.path.isfile(rp) else "—"
        sc = os.path.join(vd, "spotcheck.json")
        spot = "—"
        if os.path.isfile(sc):
            d = json.load(open(sc))
            spot = f"{d.get('confirmed',0)}/{d.get('sampled',0)}"
        n_m = len(cb._method_files(vkey))
        cols = [
            f"{vkey:16s}",
            f"{len(srcs):<9d}",
            f"{f'{n_ex}/{len(srcs)}':<10s}",
            f"{'yes' if os.path.isfile(os.path.join(vd, 'diff.json')) else '-':6s}",
            f"{'yes' if os.path.isfile(os.path.join(vd, 'principles.yaml')) else '-':6s}",
            f"{n_m:<8d}",
            f"{spot:6s}",
            f"{'LOCKED' if os.path.isfile(os.path.join(vd, 'canon.lock.yaml')) else '-':6s}",
            who,
        ]
        print(" ".join(cols))


def main():
    ap = argparse.ArgumentParser(prog="canon_handoff.py", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("brief", help="write the job spec for the external system")
    p.add_argument("voice")
    p.add_argument("--phase", choices=["a", "b", "c"])
    p.add_argument("--source")
    p.set_defaults(fn=cmd_brief)

    p = sub.add_parser("briefs", help="write every brief for every voice")
    p.set_defaults(fn=cmd_briefs)

    p = sub.add_parser("import", help="ingest a returned package and run every gate")
    p.add_argument("voice")
    p.add_argument("--package", required=True)
    p.add_argument("--no-prompts", action="store_true",
                   help="accept a package with no extractor prompts; the blindness gate is "
                        "then recorded UNVERIFIED in the import receipt")
    p.set_defaults(fn=cmd_import)

    p = sub.add_parser("status", help="what is back and what is still outstanding")
    p.set_defaults(fn=cmd_status)

    a = ap.parse_args()
    a.fn(a)


if __name__ == "__main__":
    main()
