#!/usr/bin/env python3
"""Live sector pulse (intraday SRM) — D-13. The feed's sector read is end-of-day; this is the
live wind-check the review pod uses when an alert fires mid-session.

IN:  one FMP batch quote call — 11 sector ETFs + macro proxies (SPY, IWM, UUP, TLT, HYG)
LOGIC: day-change per sector ETF -> classify TAILWIND (>= +0.4%), NEUTRAL, HEADWIND (<= -0.6%);
       breadth proxy = share of the 11 sectors green; macro tone = SPY sign + credit (HYG vs TLT) + dollar (UUP)
OUT: data/intraday/DATE/sector_pulse.json {as_of, sectors:{XLK:{chg,label}...}, breadth_pct, macro:{...}, tone}
FAIL: FMP unreachable -> exit 1 with reason; the pod treats a missing pulse as NEUTRAL-UNKNOWN and says so.
Usage: python3 srm_live.py [--out data/intraday/DATE/] ; needs FMP_API_KEY.
"""
import json, os, sys, urllib.request
from datetime import datetime, date

SECTORS=["XLK","XLF","XLV","XLE","XLI","XLY","XLP","XLU","XLB","XLRE","XLC"]
MACRO=["SPY","IWM","UUP","TLT","HYG"]
KEY=os.environ.get("FMP_API_KEY","")
TAIL, HEAD = 0.4, -0.6   # tunable via parameters if promoted

def main():
    out = sys.argv[sys.argv.index("--out")+1] if "--out" in sys.argv else f"data/intraday/{date.today()}"
    syms=",".join(SECTORS+MACRO)
    try:
        with urllib.request.urlopen(f"https://financialmodelingprep.com/stable/batch-quote-short?symbols={syms}&apikey={KEY}", timeout=30) as r:
            rows={q["symbol"]: q for q in json.load(r)}
    except Exception as e:
        print(f"PULSE UNAVAILABLE: {e}"); sys.exit(1)
    def chg(s):
        q=rows.get(s) or {}
        c=q.get("change"); p=q.get("price")
        return round(100*c/(p-c),2) if (c is not None and p) else None
    sectors={s:{"chg":chg(s),"label":("TAILWIND" if (chg(s) or 0)>=TAIL else "HEADWIND" if (chg(s) or 0)<=HEAD else "NEUTRAL")} for s in SECTORS}
    greens=sum(1 for s in SECTORS if (sectors[s]["chg"] or 0)>0)
    spy,iwm,uup,tlt,hyg=(chg(x) for x in MACRO)
    credit = None if (hyg is None or tlt is None) else round(hyg-tlt,2)
    tone = "RISK_ON" if (spy or 0)>0.3 and (credit or 0)>=0 else "RISK_OFF" if (spy or 0)<-0.3 or (credit or 0)<-0.5 else "MIXED"
    doc={"as_of":datetime.now().isoformat(timespec="seconds"),"sectors":sectors,
         "breadth_pct":round(100*greens/len(SECTORS)),"macro":{"spy":spy,"iwm":iwm,"uup":uup,"tlt":tlt,"credit_hyg_minus_tlt":credit},"tone":tone}
    os.makedirs(out,exist_ok=True)
    json.dump(doc,open(os.path.join(out,"sector_pulse.json"),"w"),indent=1)
    print(f"pulse: tone={tone} breadth={doc['breadth_pct']}% -> {out}/sector_pulse.json")

if __name__=="__main__": main()
