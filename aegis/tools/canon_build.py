#!/usr/bin/env python3
"""canon_build.py — BUILD-TIME grounding of the voices.

WHY THIS EXISTS
    A voice agent compiles with `tools: []`. It has no network, no retrieval, no memory
    at spawn. Every word of source material a voice will ever have must therefore be
    INSIDE its compiled file. Grounding is a build problem, not a RAG problem.

THE CHAIN (each step's output is hashed into the next; break one link and the build fails)

    sources.yaml
      → chunk      pages → chunks/NNNN.txt        (gitignored — copyright)
      → prompt     the extractor prompt, written to disk and BLINDNESS-GATED
      → seal       extract.jsonl validated, extract.sha256 written        (sha committed)
      → diff       extract vs card, direction-gated, spans ALL sources    (committed)
      → spotcheck  5 records per source, PM-confirmed — a GATE on lock    (committed)
      → lock       principles.yaml + methods/ + recognisers → canon.lock.yaml (committed)
      → index      contracts/canon_index.json for the orchestrator        (generated)

THE FOUR LAYERS (canon §4c — the anti-over-summarisation store)
    1 principles   15–25 page-cited lines. The spine. Compiled into every voice, always.
    2 methods      1,500–3,000 words per method section — preconditions, sequence,
                   exceptions, invalidators. NOT compiled at pass 1; injected by the
                   orchestrator at deep-dive, keyed to whichever checklist steps fired.
    3 recognisers  the author's own if-then tests, rewritten against fields we actually
                   have. Compiled into every voice, always.
    4 archive      extract.jsonl on disk. Audit and deep-dive only. Never compiled.

Run `python3 tools/canon_build.py --help`.
"""
import argparse
import hashlib
import json
import os
import re
import sys

import yaml

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CANON = os.path.join(ROOT, "canon")
SOURCES = os.path.join(CANON, "sources.yaml")

MAX_QUOTE_WORDS = 40          # verbatim ceiling in the LOCAL archive
MAX_PARAPHRASE_RUN = 12       # no committed artefact may carry a >12-word verbatim run
BLIND_NGRAM = 8               # blindness gate n-gram width
SPOTCHECK_N = 5               # PM-confirmed records required per source before lock
PRINCIPLES_MIN, PRINCIPLES_MAX = 15, 120
METHOD_MIN_WORDS, METHOD_MAX_WORDS = 1500, 3000
METHOD_HEADINGS = ["preconditions", "sequence", "exceptions", "invalidators"]

EXTRACT_KINDS = {"rule", "observation", "caution", "definition"}
RELATIONS = {"agrees", "refines", "supersedes", "unique"}
STATUSES = {"verified", "pm_override", "unsourced_retained"}


# ---------------------------------------------------------------- helpers

def die(msg):
    sys.exit(f"CANON BUILD FAILED — {msg}")


def load_registry():
    if not os.path.isfile(SOURCES):
        die(f"no registry at {SOURCES}")
    return yaml.safe_load(open(SOURCES))


def voice_sources(vkey, reg=None):
    reg = reg or load_registry()
    v = (reg.get("voices") or {}).get(vkey)
    if not v:
        die(f"voice '{vkey}' is not in canon/sources.yaml")
    return v["sources"]


def sdir(vkey, skey):
    return os.path.join(CANON, vkey, skey)


def vdir(vkey):
    return os.path.join(CANON, vkey)


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for blk in iter(lambda: fh.read(65536), b""):
            h.update(blk)
    return h.hexdigest()


def sha256_text(t):
    return hashlib.sha256(t.encode("utf-8")).hexdigest()


def norm_words(t):
    return re.findall(r"[a-z0-9']+", t.lower())


def ngrams(t, n):
    w = norm_words(t)
    return {" ".join(w[i:i + n]) for i in range(max(0, len(w) - n + 1))}


def card_path(vkey):
    return os.path.join(ROOT, "skills", f"voice-{vkey}", "SKILL.md")


def read_card(vkey):
    p = card_path(vkey)
    if not os.path.isfile(p):
        die(f"no voice card at {p}")
    return open(p).read()


def read_jsonl(path):
    out = []
    for i, line in enumerate(open(path), 1):
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError as e:
            die(f"{path}:{i} is not valid JSON — {e}")
    return out


def ok(msg):
    print(f"  ok   {msg}")


def warn(msg):
    print(f"  WARN {msg}")


# ---------------------------------------------------------------- init

def cmd_init(a):
    reg = load_registry()
    made = 0
    for vkey, v in (reg.get("voices") or {}).items():
        if a.voice and vkey != a.voice:
            continue
        os.makedirs(os.path.join(vdir(vkey), "methods"), exist_ok=True)
        os.makedirs(os.path.join(vdir(vkey), "prompts"), exist_ok=True)
        for s in v["sources"]:
            os.makedirs(os.path.join(sdir(vkey, s["key"]), "chunks"), exist_ok=True)
            made += 1
    print(f"initialised {made} source directories under canon/")
    print("NOTE: chunks/ and extract.jsonl are gitignored (copyright). "
          "Only sha256, diff, principles, methods and the lock are committed.")


# ---------------------------------------------------------------- chunk

def _pdf_pages(path):
    try:
        import pdfplumber
    except ImportError:
        pdfplumber = None
    if pdfplumber:
        with pdfplumber.open(path) as pdf:
            for i, page in enumerate(pdf.pages, 1):
                yield i, (page.extract_text() or "")
        return
    try:
        from pypdf import PdfReader
    except ImportError:
        die("neither pdfplumber nor pypdf is installed — pip install pdfplumber --break-system-packages")
    r = PdfReader(path)
    for i, page in enumerate(r.pages, 1):
        yield i, (page.extract_text() or "")


def cmd_chunk(a):
    srcs = {s["key"]: s for s in voice_sources(a.voice)}
    if a.source not in srcs:
        die(f"'{a.source}' is not a source of {a.voice}. Have: {', '.join(srcs)}")
    meta = srcs[a.source]
    if meta.get("rights") == "none" and not a.i_have_a_lawful_copy:
        die(f"canon/sources.yaml records rights: none for {a.source} — no lawful copy is registered. "
            "Acquire one, set rights: own_copy, or re-run with --i-have-a-lawful-copy to assert it.")
    d = sdir(a.voice, a.source)
    cd = os.path.join(d, "chunks")
    os.makedirs(cd, exist_ok=True)
    for f in os.listdir(cd):
        os.remove(os.path.join(cd, f))

    buf, buf_pages, n, manifest = [], [], 0, []
    target = a.words

    def flush():
        nonlocal buf, buf_pages, n
        if not buf:
            return
        n += 1
        text = "\n".join(buf)
        name = f"{n:04d}.txt"
        open(os.path.join(cd, name), "w").write(text)
        manifest.append({"chunk": f"{n:04d}", "pages": [buf_pages[0], buf_pages[-1]],
                         "words": len(norm_words(text)), "sha256": sha256_text(text)})
        buf, buf_pages = [], []

    if meta.get("kind") == "system_source":
        die("a system_source is extracted by `canon_build.py chunk-system`, not from a PDF")

    lo, hi = 1, 10 ** 9
    if getattr(a, "pages", None):
        try:
            lo, hi = (int(x) for x in a.pages.split("-", 1))
        except ValueError:
            die("--pages wants a range like 103-155")
        if lo > hi:
            die("--pages range is inverted")
    splits = set()
    if getattr(a, "split_at", None):
        try:
            splits = {int(x) for x in a.split_at.split(",") if x.strip()}
        except ValueError:
            die("--split-at wants comma-separated page numbers like 107,111,115")
        stray = sorted(p for p in splits if not lo <= p <= hi)
        if stray:
            die(f"--split-at pages outside --pages range: {stray}")

    for pageno, text in _pdf_pages(a.pdf):
        if not lo <= pageno <= hi:
            continue
        if not text.strip():
            continue
        if pageno in splits:
            flush()
        buf.append(f"[p.{pageno}]\n{text}")
        buf_pages.append(pageno)
        if sum(len(norm_words(b)) for b in buf) >= target:
            flush()
    flush()

    json.dump({"voice": a.voice, "source": a.source, "pdf_sha256": sha256_file(a.pdf),
               "chunk_words_target": target,
               "page_scope": (f"{lo}-{hi}" if getattr(a, "pages", None) else "whole file"),
               "split_at": sorted(splits) or None,
               "chunks": manifest},
              open(os.path.join(d, "chunk_manifest.json"), "w"), indent=1)
    print(f"{n} chunks written to {cd} (gitignored). Manifest committed.")
    print("Every chunk carries [p.N] page markers — page citation is not optional downstream.")


def cmd_chunk_system(a):
    """detect-lens has no book. Its source is the engine that computes its own fields."""
    d = sdir(a.voice, a.source)
    cd = os.path.join(d, "chunks")
    os.makedirs(cd, exist_ok=True)
    fd = json.load(open(os.path.join(ROOT, "contracts", "field_dictionary.json")))["fields"]
    n, manifest = 0, []
    items = sorted(fd.items())
    step = 25
    for i in range(0, len(items), step):
        n += 1
        text = "\n\n".join(
            f"[field:{k}]\n{v.get('definition','')}\nHOW: {v.get('how_computed','')}"
            for k, v in items[i:i + step])
        open(os.path.join(cd, f"{n:04d}.txt"), "w").write(text)
        manifest.append({"chunk": f"{n:04d}", "pages": [i + 1, i + step],
                         "words": len(norm_words(text)), "sha256": sha256_text(text)})
    json.dump({"voice": a.voice, "source": a.source, "pdf_sha256": None,
               "chunk_words_target": None, "chunks": manifest},
              open(os.path.join(d, "chunk_manifest.json"), "w"), indent=1)
    print(f"{n} system chunks written from contracts/field_dictionary.json")


# ---------------------------------------------------------------- prompt (BLINDNESS GATE)

EXTRACTOR_PROMPT = """# EXTRACTION TASK — {title} ({author}, {year})

You are reading a text and recording what its author actually says. You have NOT been
shown any existing summary, card, checklist or principle list, and none exists as far as
you are concerned. Do not try to infer what someone else might have concluded from this
book. Record the book.

## What to record
Go through the chunk below. For every place where the author states a RULE, a repeatable
OBSERVATION, a CAUTION, or a DEFINITION that a trader could act on, emit one JSON object
per line (JSONL), exactly this shape:

{{"id":"{source}#NNN","source":"{source}","chunk":"{chunk}","page":<int>,
 "quote":"<verbatim, <= 40 words, the author's own words>",
 "principle":"<one sentence, your words, what the author is asserting>",
 "operational":"<what a trader would have to observe or measure to apply it; if the author
   gives a threshold or a sequence, state it exactly as given>",
 "kind":"rule|observation|caution|definition",
 "extractor_confidence":<0.0-1.0>}}

## Rules
- `page` comes from the `[p.N]` marker the passage sits under. Never guess a page.
- `quote` must be verbatim and <= 40 words. If the passage needs more than 40 words to be
  fair, quote the 40 that carry the claim and put the rest in `principle`.
- Record what is there. If a chunk contains nothing operational, emit nothing for it.
- Do not generalise across the book. One record, one passage.
- Do not rank, prioritise, or select "the important ones". Completeness is the job.
- `extractor_confidence` is your confidence that the author is asserting this, not your
  confidence that it is good advice.

## Chunk {chunk}
<<<
{chunk_text}
>>>
"""


def _blindness_gate(vkey, prompt_text, this_source, quiet=False):
    """GATE 1. The extractor must never have seen (a) the voice card, or (b) any sibling
    source's extract. Enforced by n-gram overlap, asserted before the prompt may be used."""
    card = read_card(vkey)
    card_ng = ngrams(card, BLIND_NGRAM)
    p_ng = ngrams(prompt_text, BLIND_NGRAM)
    hit = card_ng & p_ng
    if hit:
        die("BLINDNESS GATE — the extractor prompt shares "
            f"{len(hit)}-gram text with skills/voice-{vkey}/SKILL.md, e.g. "
            f"\"{sorted(hit)[0]}\". The extractor must not see the card. "
            "This is exactly the confirmation-shopping the chain exists to prevent.")
    for s in voice_sources(vkey):
        if s["key"] == this_source:
            continue
        ex = os.path.join(sdir(vkey, s["key"]), "extract.jsonl")
        if not os.path.isfile(ex):
            continue
        sib = " ".join((r.get("quote", "") + " " + r.get("principle", ""))
                       for r in read_jsonl(ex))
        hit = ngrams(sib, BLIND_NGRAM) & p_ng
        if hit:
            die(f"BLINDNESS GATE — the prompt shares text with the '{s['key']}' extract, "
                f"e.g. \"{sorted(hit)[0]}\". Sources are extracted blind of EACH OTHER; "
                "they meet for the first time at the diff (§4.1b).")
    if not quiet:
        ok(f"blindness gate passed — prompt is clean of the card and of "
           f"{len(voice_sources(vkey)) - 1} sibling source(s)")


def cmd_prompt(a):
    srcs = {s["key"]: s for s in voice_sources(a.voice)}
    if a.source not in srcs:
        die(f"'{a.source}' is not a source of {a.voice}")
    meta = srcs[a.source]
    d = sdir(a.voice, a.source)
    man = os.path.join(d, "chunk_manifest.json")
    if not os.path.isfile(man):
        die(f"no chunk manifest — run `canon_build.py chunk {a.voice} {a.source} --pdf ...` first")
    chunks = json.load(open(man))["chunks"]
    pdir = os.path.join(vdir(a.voice), "prompts")
    os.makedirs(pdir, exist_ok=True)
    written = 0
    for c in chunks:
        cid = c["chunk"]
        if a.chunk and cid != a.chunk:
            continue
        text = open(os.path.join(d, "chunks", f"{cid}.txt")).read()
        p = EXTRACTOR_PROMPT.format(title=meta["title"], author=meta["author"],
                                    year=meta["year"], source=a.source, chunk=cid,
                                    chunk_text=text)
        _blindness_gate(a.voice, p, a.source, quiet=(written > 0))
        open(os.path.join(pdir, f"{a.source}.{cid}.extract.md"), "w").write(p)
        written += 1
    print(f"{written} extractor prompt(s) written to canon/{a.voice}/prompts/ (gitignored — they embed the text).")
    print("Feed each to a FRESH extractor with no other context. Append its JSONL to "
          f"canon/{a.voice}/{a.source}/extract.jsonl, then run `seal`.")


# ---------------------------------------------------------------- seal (FREEZE GATE part 1)

def cmd_seal(a):
    d = sdir(a.voice, a.source)
    ex = os.path.join(d, "extract.jsonl")
    if not os.path.isfile(ex):
        die(f"no extract at {ex}")
    recs = read_jsonl(ex)
    if not recs:
        die("extract is empty")
    man = json.load(open(os.path.join(d, "chunk_manifest.json")))
    valid_chunks = {c["chunk"] for c in man["chunks"]}
    seen = set()
    for i, r in enumerate(recs, 1):
        for k in ("id", "source", "chunk", "page", "quote", "principle", "operational", "kind"):
            if k not in r:
                die(f"record {i} is missing '{k}'")
        if r["source"] != a.source:
            die(f"record {i} claims source '{r['source']}' but sits in {a.source}/ — "
                "provenance must be unambiguous")
        if not r["id"].startswith(f"{a.source}#"):
            die(f"record {i} id '{r['id']}' is not namespaced '{a.source}#NNN'")
        if r["id"] in seen:
            die(f"duplicate id {r['id']}")
        seen.add(r["id"])
        if r["chunk"] not in valid_chunks:
            die(f"record {i} cites chunk {r['chunk']} which is not in the manifest")
        if r["kind"] not in EXTRACT_KINDS:
            die(f"record {i} kind '{r['kind']}' not in {sorted(EXTRACT_KINDS)}")
        if not isinstance(r["page"], int) or r["page"] < 1:
            die(f"record {i} has no usable page number — a canon line without a page is not citable")
        w = len(norm_words(r["quote"]))
        if w > MAX_QUOTE_WORDS:
            die(f"record {i} quote is {w} words (max {MAX_QUOTE_WORDS})")
    sha = sha256_file(ex)
    open(os.path.join(d, "extract.sha256"), "w").write(sha + "\n")
    print(f"sealed {len(recs)} records — {a.voice}/{a.source}")
    print(f"  extract.sha256 = {sha}")
    print("  Edit extract.jsonl after this point and every downstream artefact breaks its hash. "
          "That is the freeze gate.")


# ---------------------------------------------------------------- diff (DIRECTION GATE)

def _extract_shas(vkey):
    out = {}
    for s in voice_sources(vkey):
        p = os.path.join(sdir(vkey, s["key"]), "extract.sha256")
        if os.path.isfile(p):
            out[s["key"]] = open(p).read().strip()
    return out


def _all_extract_ids(vkey):
    ids = {}
    for s in voice_sources(vkey):
        p = os.path.join(sdir(vkey, s["key"]), "extract.jsonl")
        if os.path.isfile(p):
            for r in read_jsonl(p):
                ids[r["id"]] = r
    return ids


DIFF_TEMPLATE = {
    "voice": None,
    "extract_sha": {},
    "direction": "extract -> card (never the reverse; see §2 direction gate)",
    "book_supports_card": [],
    "book_missing_from_card": [],
    "card_unsupported_by_book": [],
    "cross_source": [],
}


def cmd_diff(a):
    p = os.path.join(vdir(a.voice), "diff.json")
    shas = _extract_shas(a.voice)
    if a.scaffold:
        if os.path.isfile(p) and not a.force:
            die(f"{p} already exists — pass --force to overwrite")
        d = dict(DIFF_TEMPLATE)
        d["voice"] = a.voice
        d["extract_sha"] = shas
        json.dump(d, open(p, "w"), indent=1)
        print(f"scaffolded {p} with {len(shas)} source hash(es). Fill the four buckets, then re-run "
              "`canon_build.py diff <voice>` to validate.")
        return
    if not os.path.isfile(p):
        die(f"no diff at {p} — run with --scaffold first")
    d = json.load(open(p))
    if d.get("voice") != a.voice:
        die("diff.json voice mismatch")

    # FREEZE GATE part 2
    for k, v in shas.items():
        if d.get("extract_sha", {}).get(k) != v:
            die(f"FREEZE GATE — diff.json records extract_sha[{k}]="
                f"{d.get('extract_sha', {}).get(k)} but the sealed extract is {v}. "
                "The extract changed after the diff was written. Re-diff; do not edit the hash.")
    ok(f"freeze gate passed — {len(shas)} extract hash(es) match")

    ids = _all_extract_ids(a.voice)
    keys = {s["key"] for s in voice_sources(a.voice)}
    for b in ("book_supports_card", "book_missing_from_card"):
        for i, e in enumerate(d.get(b, []), 1):
            for f in ("extract_id", "note"):
                if f not in e:
                    die(f"{b}[{i}] missing '{f}'")
            if ids and e["extract_id"] not in ids:
                die(f"{b}[{i}] cites extract id '{e['extract_id']}' that does not exist")

    # DIRECTION GATE: a card line is only a DEFECT if every source was searched and is silent.
    for i, e in enumerate(d.get("card_unsupported_by_book", []), 1):
        if "card_line" not in e:
            die(f"card_unsupported_by_book[{i}] missing 'card_line'")
        searched = set(e.get("searched_sources") or [])
        if searched != keys:
            die(f"card_unsupported_by_book[{i}] searched {sorted(searched) or 'nothing'} but this "
                f"voice has {sorted(keys)}. A card line is a defect only if ALL its texts are silent.")
    ok("direction gate passed — every card_unsupported entry searched every source")

    for i, e in enumerate(d.get("cross_source", []), 1):
        if e.get("relation") not in RELATIONS:
            die(f"cross_source[{i}] relation '{e.get('relation')}' not in {sorted(RELATIONS)}")
        cites = e.get("extract_ids") or []
        if len(cites) < 2:
            die(f"cross_source[{i}] needs >= 2 extract_ids — it is a claim ABOUT two sources")
        if ids:
            for c in cites:
                if c not in ids:
                    die(f"cross_source[{i}] cites unknown extract id '{c}'")
        if e["relation"] == "supersedes" and not e.get("superseded_by"):
            die(f"cross_source[{i}] is 'supersedes' but names no superseded_by — "
                "the earlier line is KEPT and marked, never deleted")
    ok(f"cross-source relations valid ({len(d.get('cross_source', []))})")

    sha = sha256_file(p)
    open(os.path.join(vdir(a.voice), "diff.sha256"), "w").write(sha + "\n")
    print(f"diff valid — {len(d.get('book_supports_card', []))} supported, "
          f"{len(d.get('book_missing_from_card', []))} findings, "
          f"{len(d.get('card_unsupported_by_book', []))} defects")
    print(f"  diff.sha256 = {sha}")


# ---------------------------------------------------------------- spotcheck (GATE ON LOCK)

def cmd_spotcheck(a):
    """§10: the hash chain proves the extractor never saw the card. It does NOT prove the
    extractor read the page correctly. Only a human opening the book proves that. Five per
    source, PM-confirmed. This is a GATE on lock, not an option."""
    d = sdir(a.voice, a.source)
    ex = os.path.join(d, "extract.jsonl")
    if not os.path.isfile(ex):
        die(f"no extract at {ex}")
    recs = read_jsonl(ex)
    sha = open(os.path.join(d, "extract.sha256")).read().strip()
    # deterministic sample seeded by the sealed hash — same extract, same five records
    seed = int(sha[:16], 16)
    cand = {(seed * (i + 7)) % len(recs) for i in range(SPOTCHECK_N * 3)}
    if len(cand) < SPOTCHECK_N:
        # MULTIPLICATIVE COLLAPSE. (seed * k) mod n only lands on multiples of gcd(seed, n),
        # so a large gcd yields a SHORT sample — elder-lens offered 4 of 5 on a 456-record
        # extract, which makes the lock gate unreachable rather than merely strict. Fall
        # back to an ADDITIVE walk with a prime stride, coprime to any n < 9973 and so
        # unable to collapse. Still seeded by the sealed hash: deterministic, un-re-rollable.
        # Entered ONLY when the original is short, so every already-locked source keeps the
        # exact sample it was confirmed against.
        cand = {(seed + (i + 7) * 9973) % len(recs) for i in range(SPOTCHECK_N * 3)}
    idx = sorted(cand)[:SPOTCHECK_N]
    sample = [recs[i] for i in idx]
    spath = os.path.join(vdir(a.voice), "spotcheck.json")
    if a.confirm is None:
        print(f"SPOTCHECK — {a.voice}/{a.source}. Open the book to these {len(sample)} pages "
              "and confirm the quote is on the page and says what the record says.\n")
        for r in sample:
            print(f"  {r['id']}  p.{r['page']}  [{r['kind']}]")
            print(f"    quote: \"{r['quote']}\"")
            print(f"    read as: {r['principle']}\n")
        print("Then: canon_build.py spotcheck <voice> <source> --confirm <n> --by <name>")
        return
    if a.confirm < SPOTCHECK_N:
        warn(f"only {a.confirm}/{SPOTCHECK_N} confirmed — lock will refuse this source")
    doc = json.load(open(spath)) if os.path.isfile(spath) else {"voice": a.voice, "per_source": {}}
    doc["per_source"][a.source] = {"sampled": len(sample), "confirmed": a.confirm,
                                   "by": a.by, "extract_sha": sha,
                                   "ids": [r["id"] for r in sample]}
    doc["sampled"] = sum(v["sampled"] for v in doc["per_source"].values())
    doc["confirmed"] = sum(v["confirmed"] for v in doc["per_source"].values())
    doc["by"] = a.by
    json.dump(doc, open(spath, "w"), indent=1)
    print(f"recorded {a.confirm}/{len(sample)} confirmed for {a.source} by {a.by}")


# ---------------------------------------------------------------- methods (LAYER 2)

def _method_files(vkey):
    md = os.path.join(vdir(vkey), "methods")
    if not os.path.isdir(md):
        return []
    return sorted(os.path.join(md, f) for f in os.listdir(md) if f.endswith(".md"))


def cmd_methods(a):
    """LAYER 2 — the anti-summarisation layer. A principle is a spine; a method section is
    the author's actual procedure at enough length to be followed. Injected at deep-dive
    only, keyed to the checklist steps that fired."""
    files = _method_files(a.voice)
    if not files:
        warn(f"no method sections for {a.voice} — layer 2 is empty; deep-dive will fall back to principles only")
        return
    ids = _all_extract_ids(a.voice)
    quotes = [r["quote"] for r in ids.values()]
    q_ng = set()
    for q in quotes:
        q_ng |= ngrams(q, MAX_PARAPHRASE_RUN + 1)
    for f in files:
        text = open(f).read()
        fm = yaml.safe_load(text.split("---")[1]) if text.startswith("---") else {}
        body = text.split("---", 2)[2] if text.startswith("---") else text
        base = os.path.basename(f)
        for k in ("method_id", "steps", "cite"):
            if k not in fm:
                die(f"methods/{base} frontmatter missing '{k}' "
                    "(method_id, steps: [checklist step numbers], cite: [{code,page}])")
        w = len(norm_words(body))
        if w < METHOD_MIN_WORDS:
            die(f"methods/{base} is {w} words (min {METHOD_MIN_WORDS}). Layer 2 exists precisely "
                "because a summary loses the procedure. Do not compress it.")
        if w > METHOD_MAX_WORDS:
            die(f"methods/{base} is {w} words (max {METHOD_MAX_WORDS}) — it is becoming the book, "
                "not the method. Split it.")
        low = body.lower()
        missing = [h for h in METHOD_HEADINGS if h not in low]
        if missing:
            die(f"methods/{base} has no {', '.join(missing)} section. A method without "
                "invalidators is a recipe with no way to be wrong.")
        if q_ng and (ngrams(body, MAX_PARAPHRASE_RUN + 1) & q_ng):
            die(f"methods/{base} carries a verbatim run longer than {MAX_PARAPHRASE_RUN} words from "
                "the extract. Method sections are COMMITTED to a public repo — they must be "
                "paraphrase with page citation, never transcription.")
        ok(f"methods/{base} — {w} words, steps {fm['steps']}, {len(fm['cite'])} citation(s)")
    print(f"{len(files)} method section(s) valid for {a.voice}")


# ---------------------------------------------------------------- lock

def cmd_lock(a):
    v = a.voice
    pfile = os.path.join(vdir(v), "principles.yaml")
    if not os.path.isfile(pfile):
        die(f"no {pfile}. The spine is authored FROM the diff, not from the card. "
            "Write principles.yaml: {principles: [{id, text, cite:[{code,page,extract_id}], "
            "status, relation?}], recognisers: [{id, if, then, fields}]}")
    doc = yaml.safe_load(open(pfile))
    prins = doc.get("principles") or []
    recs = doc.get("recognisers") or []
    if not (PRINCIPLES_MIN <= len(prins) <= PRINCIPLES_MAX):
        die(f"{len(prins)} principles — the spine must be {PRINCIPLES_MIN}–{PRINCIPLES_MAX} lines. "
            "Fewer is a bumper sticker; more is the book.")

    dpath = os.path.join(vdir(v), "diff.json")
    if not os.path.isfile(dpath):
        die("no diff.json — the lock is built from the diff, never straight from the extract")
    shas = _extract_shas(v)
    diff = json.load(open(dpath))
    for k, s in shas.items():
        if diff.get("extract_sha", {}).get(k) != s:
            die(f"FREEZE GATE — diff.json is stale for source '{k}'")

    ids = _all_extract_ids(v)
    seen = set()
    n_unsourced = 0
    for p in prins:
        for f in ("id", "text", "status"):
            if f not in p:
                die(f"principle {p.get('id','?')} missing '{f}'")
        if not re.fullmatch(r"C[0-9]{1,2}", p["id"]):
            die(f"principle id '{p['id']}' must match C1..C99 — the voice cites these ids in checklist_trace")
        if p["id"] in seen:
            die(f"duplicate principle id {p['id']}")
        seen.add(p["id"])
        if p["status"] not in STATUSES:
            die(f"{p['id']} status '{p['status']}' not in {sorted(STATUSES)}")
        cites = p.get("cite") or []
        if p["status"] == "verified":
            if not cites:
                die(f"{p['id']} is 'verified' with no citation. Verified means a page number exists.")
            for c in cites:
                for f in ("code", "page", "extract_id"):
                    if f not in c:
                        die(f"{p['id']} citation missing '{f}'")
                if ids and c["extract_id"] not in ids:
                    die(f"{p['id']} cites extract id '{c['extract_id']}' that does not exist")
        elif p["status"] == "unsourced_retained":
            n_unsourced += 1
            if cites:
                die(f"{p['id']} is 'unsourced_retained' but carries citations — pick one")
        if p.get("relation") and p["relation"] not in RELATIONS:
            die(f"{p['id']} relation '{p['relation']}' invalid")
        if p.get("relation") == "supersedes" and not p.get("supersedes"):
            die(f"{p['id']} claims 'supersedes' but names nothing superseded")

    for r in recs:
        for f in ("id", "if", "then", "fields"):
            if f not in r:
                die(f"recogniser {r.get('id','?')} missing '{f}'")

    spath = os.path.join(vdir(v), "spotcheck.json")
    if not os.path.isfile(spath):
        die("SPOTCHECK GATE — no spotcheck.json. The hash chain proves the extractor never saw "
            "the card; it does not prove it read the page right. Five records per source, "
            "confirmed against the physical text, before anything locks.")
    sc = json.load(open(spath))
    for k in shas:
        got = (sc.get("per_source") or {}).get(k, {})
        if got.get("confirmed", 0) < SPOTCHECK_N:
            die(f"SPOTCHECK GATE — source '{k}' has {got.get('confirmed',0)}/{SPOTCHECK_N} confirmed")
        if got.get("extract_sha") != shas[k]:
            die(f"SPOTCHECK GATE — the spotcheck for '{k}' was done against a different extract")

    if not a.sign:
        die("the lock must be signed: --sign \"<PM name>\". Unsigned canon does not compile.")

    methods = []
    for f in _method_files(v):
        text = open(f).read()
        fm = yaml.safe_load(text.split("---")[1]) if text.startswith("---") else {}
        methods.append({"method_id": fm.get("method_id"), "file": os.path.relpath(f, ROOT),
                        "steps": fm.get("steps"), "cite": fm.get("cite"),
                        "words": len(norm_words(text.split("---", 2)[-1])),
                        "sha256": sha256_file(f)})

    lock = {
        "voice": v,
        "pm_signed": a.sign,
        "extract_sha": shas,
        "diff_sha": sha256_file(dpath),
        "sources": [{k: s[k] for k in ("key", "title", "author", "year", "code", "weight", "kind")}
                    for s in voice_sources(v) if s["key"] in shas],
        "pm_spot_check": {"sampled": sc.get("sampled"), "confirmed": sc.get("confirmed"),
                          "by": sc.get("by"), "per_source": sc.get("per_source")},
        "principles": prins,
        "recognisers": recs,
        "methods": methods,
        "counts": {"principles": len(prins), "unsourced": n_unsourced,
                   "recognisers": len(recs), "methods": len(methods)},
    }
    lpath = os.path.join(vdir(v), "canon.lock.yaml")
    yaml.safe_dump(lock, open(lpath, "w"), sort_keys=False, allow_unicode=True, width=100)
    print(f"locked {v} — {len(prins)} principles ({n_unsourced} unsourced), "
          f"{len(recs)} recognisers, {len(methods)} method sections")
    print(f"  signed: {a.sign}   spot-checked: {sc.get('confirmed')}/{sc.get('sampled')}")
    print(f"  → {lpath}")


# ---------------------------------------------------------------- index

def cmd_index(a):
    """contracts/canon_index.json — what the ORCHESTRATOR reads. Two jobs:
       (1) canon_validate.py checks every canon_ref a voice cites against it;
       (2) the two-pass runtime uses steps→method_id to inject the right method
           section at deep-dive DETERMINISTICALLY — a lookup, never an agent search.
           If the voice searched for its own methods, isolation would be gone."""
    reg = load_registry()
    out = {"generated_from": "canon/*/canon.lock.yaml", "voices": {}}
    for vkey in sorted((reg.get("voices") or {})):
        lp = os.path.join(vdir(vkey), "canon.lock.yaml")
        if not os.path.isfile(lp):
            out["voices"][vkey] = {"grounded": False, "principles": [], "step_methods": {}}
            continue
        lock = yaml.safe_load(open(lp))
        step_methods = {}
        for m in lock.get("methods") or []:
            for s in (m.get("steps") or []):
                step_methods.setdefault(str(s), []).append(m["method_id"])
        out["voices"][vkey] = {
            "grounded": True,
            "pm_signed": lock["pm_signed"],
            "sources": [s["code"] for s in lock["sources"]],
            "principles": [p["id"] for p in lock["principles"]],
            "unsourced": [p["id"] for p in lock["principles"] if p["status"] == "unsourced_retained"],
            "recognisers": [r["id"] for r in lock.get("recognisers") or []],
            "methods": {m["method_id"]: {"file": m["file"], "steps": m["steps"]}
                        for m in lock.get("methods") or []},
            "step_methods": step_methods,
        }
    p = os.path.join(ROOT, "contracts", "canon_index.json")
    json.dump(out, open(p, "w"), indent=1)
    g = sum(1 for v in out["voices"].values() if v["grounded"])
    print(f"wrote {p} — {g}/{len(out['voices'])} voices grounded")


# ---------------------------------------------------------------- verify

def cmd_verify(a):
    reg = load_registry()
    bad = 0
    for vkey in sorted((reg.get("voices") or {})):
        lp = os.path.join(vdir(vkey), "canon.lock.yaml")
        if not os.path.isfile(lp):
            print(f"{vkey:16s} UNGROUNDED (no lock)")
            continue
        lock = yaml.safe_load(open(lp))
        errs = []
        if not lock.get("pm_signed"):
            errs.append("unsigned")
        for k, s in (lock.get("extract_sha") or {}).items():
            live = os.path.join(sdir(vkey, k), "extract.sha256")
            if os.path.isfile(live):
                if open(live).read().strip() != s:
                    errs.append(f"extract hash drift [{k}]")
            elif a.strict:
                errs.append(f"extract.sha256 absent [{k}]")
        dp = os.path.join(vdir(vkey), "diff.json")
        if os.path.isfile(dp) and sha256_file(dp) != lock.get("diff_sha"):
            errs.append("diff hash drift")
        for m in lock.get("methods") or []:
            mp = os.path.join(ROOT, m["file"])
            if not os.path.isfile(mp):
                errs.append(f"method missing {m['method_id']}")
            elif sha256_file(mp) != m["sha256"]:
                errs.append(f"method hash drift {m['method_id']}")
        if errs:
            bad += 1
            print(f"{vkey:16s} FAIL — {'; '.join(errs)}")
        else:
            c = lock["counts"]
            print(f"{vkey:16s} ok — {c['principles']}P/{c['recognisers']}R/{c['methods']}M, "
                  f"signed {lock['pm_signed']}")
    if bad:
        die(f"{bad} voice(s) failed hash verification")


# ---------------------------------------------------------------- cli

def main():
    ap = argparse.ArgumentParser(prog="canon_build.py", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("init", help="create canon/ directories from sources.yaml")
    p.add_argument("--voice"); p.set_defaults(fn=cmd_init)

    p = sub.add_parser("chunk", help="PDF → page-marked chunks (gitignored)")
    p.add_argument("voice"); p.add_argument("source")
    p.add_argument("--pdf", required=True); p.add_argument("--words", type=int, default=1200)
    p.add_argument("--pages", help="restrict to a PDF page range, e.g. 103-155. Pages outside "
                                   "are never chunked and never reach an extractor. Use when a "
                                   "source is only partly in scope (sources.yaml `scope`).")
    p.add_argument("--split-at", help="comma-separated PDF page numbers that must START a new "
                                      "chunk, e.g. 107,111,115. Enforces the runbook's "
                                      "chapter-boundary rule instead of leaving it to the word "
                                      "target. --words still applies within a range.")
    p.add_argument("--i-have-a-lawful-copy", action="store_true")
    p.set_defaults(fn=cmd_chunk)

    p = sub.add_parser("chunk-system", help="field dictionary → chunks (detect-lens)")
    p.add_argument("voice"); p.add_argument("source"); p.set_defaults(fn=cmd_chunk_system)

    p = sub.add_parser("prompt", help="write extractor prompts + run the BLINDNESS GATE")
    p.add_argument("voice"); p.add_argument("source"); p.add_argument("--chunk")
    p.set_defaults(fn=cmd_prompt)

    p = sub.add_parser("seal", help="validate extract.jsonl and freeze its hash")
    p.add_argument("voice"); p.add_argument("source"); p.set_defaults(fn=cmd_seal)

    p = sub.add_parser("diff", help="scaffold/validate the extract→card diff")
    p.add_argument("voice"); p.add_argument("--scaffold", action="store_true")
    p.add_argument("--force", action="store_true"); p.set_defaults(fn=cmd_diff)

    p = sub.add_parser("spotcheck", help="sample 5 records for PM confirmation (GATE on lock)")
    p.add_argument("voice"); p.add_argument("source")
    p.add_argument("--confirm", type=int); p.add_argument("--by", default="PM")
    p.set_defaults(fn=cmd_spotcheck)

    p = sub.add_parser("methods", help="validate layer-2 method sections")
    p.add_argument("voice"); p.set_defaults(fn=cmd_methods)

    p = sub.add_parser("lock", help="principles + methods + spotcheck → canon.lock.yaml")
    p.add_argument("voice"); p.add_argument("--sign"); p.set_defaults(fn=cmd_lock)

    p = sub.add_parser("index", help="generate contracts/canon_index.json")
    p.set_defaults(fn=cmd_index)

    p = sub.add_parser("verify", help="re-check every committed hash on disk")
    p.add_argument("--strict", action="store_true"); p.set_defaults(fn=cmd_verify)

    a = ap.parse_args()
    a.fn(a)


if __name__ == "__main__":
    main()
