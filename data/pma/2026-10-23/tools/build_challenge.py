import json,sys
menus=json.load(open('/home/claude/pma/plugin/skills/pma/contracts/voice_menus.json'))
u=json.load(open('universe.json'))['universe']
urows={r['ticker']:r for r in u}
p=json.load(open('phase4.json'))
tal=json.load(open('tally.json'))
# tally per ticker
tl=tal
def get(r,f):
    x=r
    for part in f.split('.'):
        if isinstance(x,dict): x=x.get(part)
        else: return None
    return x
def tally_row(t):
    rk=[r for r in p['ranked'] if r['ticker']==t][0]
    seats=[];conv=[]
    for n in json.load(open('nominations.json')) if False else []: pass
    return rk
import glob
noms={}
for f in glob.glob('forms/r1/*.json'):
    d=json.load(open(f))
    for n in d['nominations']: noms.setdefault(n['ticker'],[]).append((d['voice'],n['conviction']))
held={'MP','V'}
tally=[]
for t in p['deliberation_set']:
    rk=[r for r in p['ranked'] if r['ticker']==t][0]
    ns=noms.get(t,[])
    tally.append({'ticker':t,'nomination_count':len(ns),'seats':[a for a,_ in ns],'convictions':[b for _,b in ns],'lane':rk['lane'],'doors':rk['doors'],'held':t in held})
for seat in sys.argv[1:]:
    fl=menus[seat]
    rows=[[t,{**{'ticker':t},**{f:get(urows[t],f) for f in fl}}] for t in p['deliberation_set']]
    d={'date':'2026-10-23','seat':seat,'tally':tally,'rows':rows}
    if seat=='lynch':
        d['fundamentals']=[[t,json.load(open('fundamentals_pack.json'))['tickers'].get(t)] for t in p['deliberation_set']]
    json.dump(d,open(f'seat_packets/challenge_{seat}.json','w'))
    print(seat,len(json.dumps(d)))
json.dump(tally,open('room_tally.json','w'))
