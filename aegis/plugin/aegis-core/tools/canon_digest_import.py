#!/usr/bin/env python3
"""canon_digest_import.py — import a PM-VERIFIED DIGEST as a canon source.

WHY THIS EXISTS (2026-08-06)
    The normal chain is  pdf -> chunk -> extractor prompt -> extract.jsonl.  That chain
    exists because an LLM reading a book unsupervised will drift, so every line must
    carry a page and be spot-checked against the physical text.

    A DIGEST is a different animal.  It is a rules document that someone ELSE'S model
    produced from the book and that the PM has already read and confirmed.  Re-running
    our own extractor over it would re-summarise a summary — it would burn tokens to
    make the material WORSE, and it would invent page numbers that were already lost.

    So a digest is imported, not extracted.  This tool is deterministic: it splits the
    digest into one record per stated rule, keyed to the digest's own section headings,
    and writes the same extract.jsonl / extract.sha256 pair the rest of the chain
    consumes.  No model runs here (constitution law 4).

WHAT A DIGEST CAN AND CANNOT DO
    It CAN ground a voice: the rules, thresholds and procedures are all present.
    It CANNOT be page-cited to the book.  `page` is the digest's own PART number and
    `kind` is 'digest_rule', never 'quote'.  A principle built on a digest is therefore
    honest about its provenance, and `sources.yaml` must record kind: pm_digest so the
    lock, the diff and every downstream reader can see it.

CHANGING THIS TOOL BREAKS SEALED SOURCES — READ BEFORE EDITING parse()
    extract.sha256 is a hash of the OUTPUT of this file.  Any change to parse() or
    its filters changes that hash for every source, including ones already locked.
    A voice's diff.json carries the sha it was built against, and cmd_lock's FREEZE
    GATE compares the two — so a silent re-import of a sealed source will not
    corrupt the canon, it will HALT the lock, loudly.  That is the design.

    But halting is not the remedy.  If you change this tool and re-import a source
    that is already sealed (today that is oneil/canslim_kb_v2, whose sha is
    committed and referenced), you MUST walk the whole chain for that voice again:
        re-import  ->  canon_build.py diff  ->  spotcheck  ->  lock --sign "<PM>"
    A re-lock needs the PM's signature.  So: do not re-import a sealed source as a
    side effect of a tool tweak.  Change the tool, then decide per voice whether
    that voice is being re-grounded, and if it is, take it through all four steps.

USAGE
    python3 tools/canon_digest_import.py <voice> <source_key>
        reads   canon/<voice>/<source_key>/chunks/*.md
        writes  canon/<voice>/<source_key>/extract.jsonl   (gitignored)
                canon/<voice>/<source_key>/extract.sha256  (committed)
"""

import hashlib
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

ROMAN = {"I": 1, "II": 2, "III": 3, "IV": 4, "V": 5, "VI": 6, "VII": 7,
         "VIII": 8, "IX": 9, "X": 10}

PART_RE = re.compile(r"^#{1,3}\s*.*?PART\s+([IVX]+)\b[:\s]*(.*)$", re.I)
HEAD_RE = re.compile(r"^(#{1,6})\s+(.*)$")
# a stated rule: numbered item, lettered item, or bullet
ITEM_RE = re.compile(r"^\s{0,6}(?:[-*+]|\d{1,2}[.)]|[a-z][.)])\s+(.+)$")
REFS_RE = re.compile(r"\[(\d+(?:\s*,\s*\d+)*)\]")
FENCE_RE = re.compile(r"^\s*```")


TERMINAL = (".", "!", "?")
STATEMENT_MIN_WORDS = 12


def _is_statement(raw_body, txt):
    """Does this loose (unbulleted) paragraph read as a STATED RULE?

    The old test was a hard-coded opener whitelist — ('The ', 'This ', 'If ', 'A ',
    'When ', 'To ').  That is arbitrary: it kept "The trend line frames the angle..."
    and silently dropped "Trades represent a study in Force..." for no reason a
    reader could defend.  Dropping a rule because of its first word is a defect.

    The honest test is shape, not vocabulary: a rule is a COMPLETE SENTENCE of
    substance.  COMPLETE = the source line ends in terminal punctuation, so a
    wrapped fragment or a running header is not mistaken for a finished thought.
    SUBSTANCE = at least STATEMENT_MIN_WORDS words.  Both must hold.

    Note it reads RAW_BODY for the punctuation test, because clean() strips the
    trailing '.;:' — by the time we hold `txt` the evidence is already gone."""
    if len(txt.split()) < STATEMENT_MIN_WORDS:
        return False
    return raw_body.rstrip().endswith(TERMINAL)


def clean(s):
    """Drop the digest's own bracket refs and markdown emphasis; keep the words."""
    s = REFS_RE.sub("", s)
    s = re.sub(r"\*\*|__|\*|`", "", s)
    s = re.sub(r"\$\$?", "", s)
    s = re.sub(r"\s{2,}", " ", s)
    return s.strip(" .;:").strip()


def parse(text):
    """One record per stated rule. Fenced code and ASCII diagrams are skipped — they
    are illustration, and a record that is half a box-drawing is not a rule."""
    part, part_title, head = 0, "", ""
    in_fence = False
    out = []
    for raw in text.splitlines():
        if FENCE_RE.match(raw):
            in_fence = not in_fence
            continue
        if in_fence or not raw.strip():
            continue

        m = PART_RE.match(raw)
        if m:
            part = ROMAN.get(m.group(1).upper(), part)
            part_title = clean(m.group(2))
            head = part_title
            continue
        m = HEAD_RE.match(raw)
        if m:
            head = clean(m.group(2))
            continue

        m = ITEM_RE.match(raw)
        body = m.group(1) if m else raw
        txt = clean(body)
        if len(txt.split()) < 6:          # a fragment is not a rule
            continue
        if not m and not _is_statement(body, txt):
            continue                      # loose prose only when it reads as a statement
        if part == 0:
            # Anything before the first PART heading is the digest's own front
            # matter — "this handbook converts...", a scope note, a title blurb.
            # It is a description OF the rules, not a rule, and it has no PART to
            # key `page` to, so a principle citing it could never be located.
            # Front matter is skipped, not imported with a fictional page 0.
            continue
        refs = sorted({int(x) for grp in REFS_RE.findall(raw)
                       for x in re.split(r"\s*,\s*", grp)})
        out.append({"section": head or part_title, "part": part,
                    "text": txt, "src_refs": refs})
    return out


def main():
    if len(sys.argv) != 3:
        sys.exit(__doc__.strip().splitlines()[-4].strip())
    voice, skey = sys.argv[1], sys.argv[2]
    sdir = os.path.join(ROOT, "canon", voice, skey)
    cdir = os.path.join(sdir, "chunks")
    if not os.path.isdir(cdir):
        sys.exit(f"no {cdir} — put the digest markdown there first")

    text = ""
    for f in sorted(os.listdir(cdir)):
        if f.endswith((".md", ".txt")):
            text += open(os.path.join(cdir, f)).read() + "\n"
    if not text.strip():
        sys.exit(f"no digest text found under {cdir}")

    recs = parse(text)
    if len(recs) < 30:
        sys.exit(f"only {len(recs)} rules parsed — that is too thin to ground a voice; "
                 "check the digest's heading/list structure")

    p = os.path.join(sdir, "extract.jsonl")
    with open(p, "w") as fh:
        for i, r in enumerate(recs, 1):
            fh.write(json.dumps({
                "id": f"{skey}#{i:03d}",
                "source": skey,
                "chunk": "digest",
                "page": r["part"],              # the digest's PART number, not a book page
                "section": r["section"],
                "quote": r["text"],             # the DIGEST's words, never the book's
                "principle": r["text"],
                "operational": r["text"],
                "kind": "digest_rule",
                "digest_refs": r["src_refs"],   # the digest's own internal ref numbers
                "extractor_confidence": None,   # no extractor ran — this is an import
            }, ensure_ascii=False) + "\n")

    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for blk in iter(lambda: fh.read(65536), b""):
            h.update(blk)
    sha = h.hexdigest()
    open(os.path.join(sdir, "extract.sha256"), "w").write(sha + "\n")

    parts = {}
    for r in recs:
        parts[r["part"]] = parts.get(r["part"], 0) + 1
    print(f"imported {len(recs)} digest rules -> {p}")
    print("  per part: " + ", ".join(f"{k}:{v}" for k, v in sorted(parts.items())))
    print(f"  extract.sha256 = {sha}")


if __name__ == "__main__":
    main()
