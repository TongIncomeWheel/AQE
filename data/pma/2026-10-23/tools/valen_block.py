import json
ex=json.load(open('aqe_daily_export.json')); v=json.load(open('valen_section.json'))
rows={r['ticker']:r for r in ex['daily_list']}
for h in ex.get('held_positions') or []: rows.setdefault(h['ticker'],h)
room=json.load(open('phase4.json'))['deliberation_set']
L=["","==== VALEN (AQE's VIV-System market weather + house setups; AQE data, render as context) ====",
"Market weather (as of "+v['read_me_first']['as_of']+"): stance "+v['stance']['word']+" | trend regime "+v['regime']+" | "+v['read_me_first']['so_what']]
for t in v['trend']: L.append(f"  trend {t['symbol']}: daily_buy_signal {t['daily_buy_signal']} weekly_buy_signal {t['weekly_buy_signal']} above_rising_5d {t['above_rising_5d']}")
for e in v['extension']: L.append(f"  extension {e['label']}: {e['value']}")
for b in v['breadth']: L.append(f"  breadth {b['label']}: {b.get('display') or b['value']}")
g=v['gex']; L.append(f"  gamma SPY: regime {g['regime']} flip {g['flip']} call_wall {g['call_wall']} put_wall {g['put_wall']} ({g['commentary']})")
L.append("  leadership: "+" / ".join(v['neighbourhood']))
L.append("Per-name house setups (status + checklist passes; levels omitted under R1) and U&R (undercut-and-rally) read:")
def best(r):
    out=[]
    for gr in (r.get('setups') or {}).get('grades',[]) if isinstance(r.get('setups'),dict) else (r.get('setups') or []):
        ch=gr.get('checks') or []
        out.append(f"{gr['setup']} {gr['status']} ({sum(1 for c in ch if c['result']=='PASS')}/{len(ch)})")
    return out
for t in room:
    r=rows.get(t,{})
    s=best(r)
    unr=f"U&R {r.get('unr_status')}"+(f": {r.get('unr_note')}" if r.get('unr_note') else "")
    nb=v['no_buy_list'].get(t)
    L.append(f"  {t}: setups "+("; ".join(s) if s else "no house setup present")+f" | {unr}"+(f" | NO-BUY flags: {', '.join(nb)}" if nb else ""))
open('valen_vote_block.txt','w').write("\n".join(L)+"\n")
print("\n".join(L)[:4000]); print(len("\n".join(L)))
