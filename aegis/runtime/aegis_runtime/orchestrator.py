"""
orchestrator.py — the TWO-LAYER orchestrator (Phase 1).

Layer 1 — the deterministic SEQUENCER: runs the fixed premarket pipeline in order
  (voices -> tally -> conviction funnel [real kernel tool] -> committee -> summary).
Layer 2 — the intelligent CHIEF: a MODEL that interprets the operator's free-form
  instruction into WHICH action to run and with what parameters. Minimal in Phase 1
  (one instruction -> premarket) but built as a model-driven interpreter from the start,
  because it is the piece that later turns natural-language commentary into orchestration.
"""
import os
import json
import asyncio
import subprocess

from .gateway import ModelGateway
from . import voices as voices_mod
from . import committee as committee_mod


class Orchestrator:
    def __init__(self, kernel, gateway=None):
        self.kernel = kernel
        self.gw = gateway or ModelGateway()

    # ---------- Layer 2 : the Chief (intelligent intent interpreter) ----------
    def chief_interpret(self, instruction, default_date):
        """Map free-form operator intent -> {action, params}. Model-driven in real mode."""
        if self.gw.mock or not instruction:
            return {"action": "premarket", "params": {"date": default_date}}
        system = ("You are the Aegis Chief orchestrator. Map the operator's instruction to ONE action. "
                  "Return JSON {\"action\": <premarket|status|funnel|unknown>, \"params\": {...}}. "
                  "Known: premarket(date), funnel(date, sc_floor?), status(). Nothing else.")
        raw = self.gw.complete("control", system, f"Instruction: {instruction}\nDefault date: {default_date}",
                               max_tokens=300)
        try:
            act = self.gw.extract_json(raw)
        except Exception:
            act = {"action": "premarket", "params": {"date": default_date}}
        act.setdefault("params", {}).setdefault("date", default_date)
        return act

    # ---------- Layer 1 : the deterministic sequencer ----------
    def _build_tally(self, noms, out_path):
        """Assemble the funnel-format tally.json from the voice nominations."""
        tally = {}
        for voice, nom in noms.items():
            for n in nom.get("nominations", []):
                t = n.get("ticker")
                if not t:
                    continue
                row = tally.setdefault(t, {"count": 0, "voices": [], "convictions": {}, "price": n.get("price_at_nomination")})
                row["count"] += 1
                row["voices"].append(voice)
                row["convictions"][voice] = n.get("conviction")
        json.dump({"date": os.path.basename(os.path.dirname(out_path)), "tally": tally}, open(out_path, "w"), indent=1)
        return tally

    def _run_funnel(self, date, tally_path, out_path):
        export = os.path.join(self.kernel, "output", "aqe_daily_export.json")
        tool = os.path.join(self.kernel, "tools", "conviction_funnel.py")
        cmd = ["python3", tool, "build", "--tally", tally_path, "--export", export, "--out", out_path]
        subprocess.run(cmd, check=True, cwd=self.kernel, capture_output=True)
        return json.load(open(out_path))

    def run_premarket(self, date):
        print(f"[premarket] date={date}  mock={self.gw.mock}")
        sod = os.path.join(self.kernel, "runtime", "out", date)
        os.makedirs(sod, exist_ok=True)

        print("[1/4] swarm — 11 voices (isolated, parallel)")
        noms = asyncio.run(voices_mod.run_swarm(self.gw, self.kernel, date, os.path.join(sod, "nominations")))
        if not noms:
            raise SystemExit("no valid nominations — check the SOD universe files exist for this date")

        print("[2/4] tally")
        tally_path = os.path.join(sod, "tally.json")
        tally = self._build_tally(noms, tally_path)
        print(f"      {len(tally)} distinct names nominated across {len(noms)} voices")

        print("[3/4] conviction funnel (kernel tool, D-78/79/80: data->lens->voices)")
        funnel = self._run_funnel(date, tally_path, os.path.join(sod, "conviction_funnel.json"))
        print(f"      shortlist {funnel['counts']['shortlist']} · "
              f"consensus-only contradictions {funnel['counts']['consensus_only_contradictions']}")

        print("[4/4] committee deliberation (Opus tier)")
        comm, ok, msg = committee_mod.deliberate(self.gw, self.kernel, date, funnel,
                                                 os.path.join(sod, "committee.json"))
        adv = sum(1 for v in comm.get("verdicts", []) if v.get("verdict") == "ADVANCE")
        print(f"      committee valid={ok} ({msg}) · {len(comm.get('verdicts', []))} verdicts · {adv} ADVANCE")

        summary = {
            "date": date, "voices_ran": len(noms), "nominated": len(tally),
            "shortlist": funnel["counts"]["shortlist"], "advance": adv,
            "out_dir": sod, "funnel_summary": funnel.get("summary"),
        }
        json.dump(summary, open(os.path.join(sod, "run_summary.json"), "w"), indent=1)
        return summary

    # ---------- entrypoint ----------
    def dispatch(self, instruction, default_date):
        act = self.chief_interpret(instruction, default_date)
        if act["action"] in ("premarket", "unknown"):
            return self.run_premarket(act["params"]["date"])
        raise SystemExit(f"Phase 1 supports 'premarket' only; Chief returned action={act['action']}")
