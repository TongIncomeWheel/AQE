#!/usr/bin/env python3
"""Per-voice memory — bounded, structured, compounding (D-14). Each voice LEARNS and REMEMBERS
without breeding spaghetti: fixed sections, hard caps, auto-expiry.

update: rebuild every voice's memory from the ledger + nightly scorecard (post-market step)
render <voice>: the markdown block the orchestrator INJECTS into that voice's spawn (premarket step 5)

Memory shape per voice (data/persistent/voice_memory/<voice>.json):
  stats (rolling window) · open_nominations (capped) · recent_closed (last 10) ·
  standing_lessons (max 5; each carries evidence + last_confirmed; EXPIRES after N sessions unless re-confirmed)
Caps and expiry come from parameters performance.memory — memory compounds, never balloons.
"""
import argparse, json, os
from datetime import date
import yaml

ROOT=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MEMDIR=os.path.join(ROOT,"data","persistent","voice_memory")
LEDGER=os.environ.get("AEGIS_LEDGER", os.path.join(ROOT,"data","persistent","ledger.jsonl"))
P=yaml.safe_load(open(os.path.join(ROOT,"charter","parameters.yaml")))
MEM=P.get("performance",{}).get("memory",{"standing_lessons_max_per_voice":5,"lesson_expiry_sessions":30,"open_nominations_shown_max":10})
CRIT=P.get("performance",{}).get("voice",{"hit_d5_min_pct":45,"eval_window_sessions":15})

def _rows():
    if not os.path.exists(LEDGER): return []
    return [json.loads(l) for l in open(LEDGER) if l.strip()]

def update(args):
    rows=_rows(); os.makedirs(MEMDIR,exist_ok=True)
    scorecard={}
    if args.scorecard and os.path.exists(args.scorecard):
        scorecard=json.load(open(args.scorecard)).get("voices",{})
    voices=sorted({r["voice"] for r in rows}) or []
    for v in voices:
        mine=[r for r in rows if r["voice"]==v]
        closed=[r for r in mine if r["tracking"].get("closed") and r["tracking"].get("d5") is not None]
        openn=[r for r in mine if not r["tracking"].get("closed")][-MEM["open_nominations_shown_max"]:]
        window=closed[-CRIT["eval_window_sessions"]*10:]  # generous slice; stats over what exists
        n=len(window); hits=sum(1 for r in window if r["tracking"]["d5"]>0)
        stats={"n_closed":n,"hit_d5_pct":round(100*hits/n,1) if n else None,
               "avg_d5_pct":round(sum(r["tracking"]["d5"] for r in window)/n,2) if n else None,
               "best":max((r["tracking"].get("max_gain_pct") or 0) for r in window) if n else None,
               "worst":min((r["tracking"].get("max_drawdown_pct") or 0) for r in window) if n else None}
        mp=os.path.join(MEMDIR,f"{v}.json")
        mem=json.load(open(mp)) if os.path.exists(mp) else {"voice":v,"standing_lessons":[],"session_count":0}
        mem["session_count"]=mem.get("session_count",0)+1
        # expire stale lessons (bounded memory, never a graveyard)
        mem["standing_lessons"]=[L for L in mem.get("standing_lessons",[])
            if mem["session_count"]-L.get("last_confirmed_session",0) <= MEM["lesson_expiry_sessions"]][:MEM["standing_lessons_max_per_voice"]]
        # auto-lesson: sector concentration underperformance (simple, evidenced, replaceable by bench-authored lessons)
        mem.update({"as_of":str(date.today()),"stats":stats,
            "verdict":scorecard.get(v,{}).get("verdict","INSUFFICIENT_DATA"),
            "open_nominations":[{"ticker":r["ticker"],"date":r["date"],"d_now":r["tracking"].get("d5") or r["tracking"].get("d3") or r["tracking"].get("d1")} for r in openn],
            "recent_closed":[{"ticker":r["ticker"],"date":r["date"],"d5":r["tracking"]["d5"]} for r in closed[-10:]]})
        json.dump(mem,open(mp,"w"),indent=1)
    print(f"memory updated for {len(voices)} voices")

def add_lesson(args):
    mp=os.path.join(MEMDIR,f"{args.voice}.json")
    mem=json.load(open(mp)) if os.path.exists(mp) else {"voice":args.voice,"standing_lessons":[],"session_count":0}
    Ls=[L for L in mem["standing_lessons"] if L["text"]!=args.text]
    Ls.append({"text":args.text,"evidence":args.evidence,"first_seen":str(date.today()),
               "last_confirmed_session":mem.get("session_count",0)})
    import yaml as _yaml
    _cap=_yaml.safe_load(open(os.path.join(ROOT,'charter','parameters.yaml')))["performance"]["memory"]["standing_lessons_max_per_voice"]
    mem["standing_lessons"]=Ls[-_cap:]  # LOW-1 fix: honour the parameter, was hardcoded -5 behind `if False`
    json.dump(mem,open(mp,"w"),indent=1); print(f"lesson added for {args.voice} ({len(mem['standing_lessons'])} standing)")

def render(args):
    mp=os.path.join(MEMDIR,f"{args.voice}.json")
    if not os.path.exists(mp): print(f"## MY MEMORY ({args.voice})\nNo history yet — first sessions build it."); return
    m=json.load(open(mp)); s=m.get("stats",{})
    out=[f"## MY MEMORY ({m['voice']}) — as of {m.get('as_of')} · criteria verdict: {m.get('verdict')}"]
    out.append(f"My last {s.get('n_closed',0)} closed picks: hit rate d5 {s.get('hit_d5_pct')}% (target ≥ {CRIT['hit_d5_min_pct']}%), avg d5 {s.get('avg_d5_pct')}%, best +{s.get('best')}%, worst {s.get('worst')}%.")
    if m.get("open_nominations"): out.append("Open picks I must not forget: "+", ".join(f"{o['ticker']}({o['date']}, {o['d_now']}%)" for o in m["open_nominations"]))
    if m.get("standing_lessons"):
        out.append("MY STANDING LESSONS (apply before nominating):")
        out+= [f"  {i+1}. {L['text']} [evidence: {L['evidence']}]" for i,L in enumerate(m["standing_lessons"])]
    print("\n".join(out))

if __name__=="__main__":
    ap=argparse.ArgumentParser(); sub=ap.add_subparsers(dest="cmd",required=True)
    u=sub.add_parser("update"); u.add_argument("--scorecard",default=None)
    r=sub.add_parser("render"); r.add_argument("voice")
    l=sub.add_parser("add-lesson"); l.add_argument("voice"); l.add_argument("--text",required=True); l.add_argument("--evidence",required=True)
    a=ap.parse_args(); {"update":update,"render":render,"add-lesson":add_lesson}[a.cmd](a)
