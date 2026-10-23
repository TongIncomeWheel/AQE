import json,collections
c=json.load(open('conditions.json')); ex=json.load(open('aqe_daily_export.json')); bs=json.load(open('broker_stops.json'))['positions']
xr={r['ticker']:r for r in ex['daily_list']}
for h in ex.get('held_positions') or []: xr.setdefault(h['ticker'],h)
def n(k): return f"{k} analysts'" if k!=1 else "1 analyst's"
def triggers(t,r):
    sh=r['shared']; buys=sh['buy']; tr=[]; label='shared'
    if not buys:
        label='not shared (no majority)'
        g=collections.OrderedDict()
        for a in r['analysts']:
            if a['vote']!='SUPPORT' or not a.get('counts'): continue
            for b in a.get('buy') or []:
                if not b['levels']: continue
                key=(b['w'],b['levels'][0]['value'])
                g.setdefault(key,{'w':b['w'],'value':key[1],'seats':[]})['seats'].append(a['seat'])
        buys=list(g.values())
    vx=[b.get('x') for b in sh['confirm'] if b['w']=='vol_x_ge' and b.get('x')]
    up=[b for b in buys if b['w'] in ('h1_close_above','close_above')]
    dn=[b for b in buys if b['w'] in ('in_zone','reclaim')]
    for i,b in enumerate(sorted(up,key=lambda b:-len(b['seats']))[:1]):
        d={'id':f'{t}-buy0','kind':'close_above','level':b['value'],'basis':'15m','priority':'ACTION','action':f"{t}: an hourly candle closes above {b['value']} ({n(len(b['seats']))} {label} buy line). Your decision."}
        if vx: d['volume_min_x']=max(vx)
        tr.append(d)
        bh=(xr.get(t) or {}).get('bar_high')
        if bh: tr.append({'id':f'{t}-touch','kind':'trade_above','level':bh,'basis':'15m','priority':'WARN','action':f"{t} traded through yesterday's intraday high {bh}: the buy line is in play, not met until an hourly close confirms."})
    for i,b in enumerate(dn[:2]):
        tr.append({'id':f'{t}-dip{i+1}','kind':'trade_below','level':b['value'],'basis':'15m','priority':'WARN','action':f"{t} traded down to {b['value']} ({n(len(b['seats']))} pullback line). The buy is an hourly close back above it, not the touch."})
    wz=sh.get('wait_zone')
    if wz and up and wz['hi']<up[0]['value'] and not any(x['level']==wz['hi'] for x in tr):
        tr.append({'id':f'{t}-wait','kind':'trade_below','level':wz['hi'],'basis':'15m','priority':'WARN','action':f"{t} is back in the wait area {wz['lo']}-{wz['hi']}."})
    ex_=sorted(r['exits'],key=lambda e:(-len(e['seats']),-e['value']))
    if ex_:
        e=ex_[0]; tr.append({'id':f'{t}-dead','kind':'close_below','level':e['value'],'basis':'daily','priority':'WARN','action':f"{t} closed under {e['value']}, the exit line most analysts share: the case is invalidated."})
    conf="; ".join([b['plain'] for b in (r['shared']['buy']+r['shared']['confirm'])]) or "no shared buy: "+"; ".join(f"{b['w']} {b['value']} ({len(b['seats'])})" for b in buys)
    kills=(f"A daily close under {ex_[0]['value']} ({n(len(ex_[0]['seats']))} exit line)." if ex_ else "no exit line filed")
    return tr,conf,kills,ex_
cards={'advance':[],'hold':[],'held':[]}
for r in c['rows']:
    t=r['ticker']; v=r['verdict']
    if t in bs:
        tr,conf,kills,ex_=triggers(t,r) if v in('ADVANCE','HOLD-FOR-CONDITIONS') else ([],'','',r['exits'])
        stop=bs[t]['stop']
        ok=[e for e in ex_ if e['value']>=stop]
        held={'committee_exit':(max(ok,key=lambda e:e['value'])['value'] if ok else None),'committee_exit_range':None,
              'for':f"Keep under the broker stop {stop} ({bs[t]['order']} {bs[t]['order_qty']}, {bs[t]['tif']}).",
              'against':("Every analyst exit line sits below the broker stop, so the broker stop is the tighter exit." if ex_ and not ok else "")}
        if v=='ADVANCE': held['add_triggers']=[x for x in tr if x['kind']!='close_below']; held['add_note']="Committee ADVANCE on the ADD question."
        cards['held'].append([t,held]); continue
    if v not in ('ADVANCE','HOLD-FOR-CONDITIONS'): continue
    tr,conf,kills,_=triggers(t,r)
    card={'triggers':tr,'confirms':conf,'kills':kills}
    if not any(x['priority']=='ACTION' or x['kind']=='trade_below' for x in tr): card['not_structured_yet']='no analyst buy level resolved'
    cards['advance' if v=='ADVANCE' else 'hold'].append([t,card])
cards={k:dict(v) for k,v in cards.items()}
json.dump(cards,open('cards.json','w'),indent=1)
print({k:len(v) for k,v in cards.items()})
for k in (): 
    for t,cd in cards[k]: print(t,[(x['kind'],x['level']) for x in cd['triggers']])
print(cards['held'])
