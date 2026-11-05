"""Render a SAMPLE alert digest from real levels + a mock quote set (PM 2026-11-05: "preview first"). Nothing is sent.

  python -m scripts.alert_preview <levels.json> <export.json> <card_fields.json> <out_dir>

Mock quotes are built from each name's own levels: a buy that has printed (ADP), a name 0.3 ATR under its buy line (KO), a failed push, a held name
near its stop, a setup forming. The previous close is the export's last close, so the move vs last close is real arithmetic on real closes."""
from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from src.alerts import condition_cycle as CC
from src.alerts import condition_evaluator as CE
from src.alerts import emailer as E

ET = ZoneInfo("America/New_York")
NOW = datetime(2026, 11, 5, 15, 19, tzinfo=ET)


def main(levels_p, export_p, fields_p, out_dir):
    lv = json.load(open(levels_p))
    ex = json.load(open(export_p))
    cf = json.load(open(fields_p)).get("cards") or {}
    rec = {r["ticker"]: r for r in ex["daily_list"]}
    rows = {r["ticker"]: dict(r, card_fields=cf.get(r["ticker"])) for r in lv["rows"] if r.get("conditions")}
    cards, near, held = [], [], []

    def live_for(tk, price, hourly=None, vol=1.6):
        r = rec[tk]
        return {"price": price, "prev_close": r["entry"], "atr": r.get("atr_14d"), "last_hourly_close": hourly if hourly is not None else price,
                "vol_x": {"so_far": vol}, "unr": {"armed": [], "levels": [], "stop": None, "volume": {}}, "vwap": {"vwap": price, "provisional": False}}

    def line(tk):
        return CE.entry_level(rows[tk]["conditions"]["shared"]["buy"][0])

    # (a) buy trigger fired: the supplemental ADVANCE ADP prints through its line on volume
    for tk, bump in (("ADP", 1.002),):
        lv_ = live_for(tk, round(line(tk) * bump, 2), hourly=round(line(tk) * 1.001, 2))
        ev = CE.evaluate_conditions(rows[tk], lv_, NOW)
        cards.append((tk, rows[tk], ev, ["CONDITION_MET"], lv_))
    # (b) near its buy line: committee names 0.3 ATR under the line, evaluated for real
    for tk in ("KO", "PK"):
        if tk not in rows:
            continue
        l_ = line(tk)
        lv_ = live_for(tk, round(l_ - 0.3 * (rec[tk].get("atr_14d") or 1), 2), vol=0.9)
        ev = CE.evaluate_conditions(rows[tk], lv_, NOW)
        n = CC._near_buy_line(tk, rows[tk], ev, lv_)
        if n:
            near.append(n)
    # (c) held name near its stop (event shaped like the engine's)
    if "V" in rec:
        v = rec["V"]
        px = round(v["entry"] * 0.988, 2)
        held.append({"ticker": "V", "is_held": True, "source": "pma", "level": "V-stopnear", "kind": "near_stops", "label": "Near your stops", "level_price": None,
                     "live_px": px, "chg_pct": round((px / v["entry"] - 1) * 100, 2), "priority": "WARN", "broker_stop": round(v["entry"] * 0.975, 2),
                     "committee_exit": None, "action": "Price is close to your broker stop."})
    # (d) a failed push
    for tk in ("WCN", "BBY"):
        if tk in rows:
            l_ = line(tk)
            lv_ = live_for(tk, round(l_ * 0.995, 2))
            ev = CE.evaluate_conditions(rows[tk], lv_, NOW)
            ev["buy_met"] = False
            cards.append((tk, rows[tk], ev, ["FAILED_PUSH"], lv_))
            break
    # watching, no action: a setup forming and an extended name
    for tk in ("CAH", "MFC"):
        if tk in rows:
            l_ = line(tk)
            lv_ = live_for(tk, round(l_ * 1.04, 2))
            ev = CE.evaluate_conditions(rows[tk], lv_, NOW)
            cards.append((tk, rows[tk], ev, ["CHASED"], lv_))
            break
    meta = {"near_trigger": near, "pma_run": "2026-11-05", "pma_session": "2026-11-05", "aqe_date": "2026-11-05", "aqe_covers": "2026-11-04"}
    subject, plain, html = E.build_condition_digest(cards, NOW, held, meta)
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    (out / "alert_preview.txt").write_text(f"SUBJECT: {subject}\n\n{plain}\n")
    (out / "alert_preview.html").write_text(
        f"<!doctype html><meta charset='utf-8'><title>AQE alert preview</title><body style='font-family:Arial,sans-serif;max-width:820px;margin:16px auto'>"
        f"<p style='color:#777;font-size:12px'>PREVIEW built from the real 5 Nov levels and a MOCK quote set. Nothing was sent.</p>"
        f"<h3 style='margin:4px 0'>{subject}</h3>{html}</body>")
    print(subject)
    print(f"cards {len(cards)} near {len(near)} held {len(held)}")


if __name__ == "__main__":
    main(*sys.argv[1:5])
