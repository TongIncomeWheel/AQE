#!/usr/bin/env python3
"""Parametric portfolio VaR — single-factor variance-covariance (D-42, PM ruling: parametric).

95% one-month Value-at-Risk on the Aegis book, computed the standard parametric way against a
one-factor (market) model, using the data AQE already provides per name — no simulation, no
history replay (that would be historical VaR; the PM chose parametric).

Model (deterministic, law 4):
  For each position i: signed dollar exposure E_i, market beta β_i, total annual vol σ_i.
  Market (SPY) annual vol σ_m (from the historical store — historical_store.stats('SPY')).
  Systematic annual $-vol   = (Σ E_i·β_i)·σ_m           (net-beta dollar × market vol)
  Idiosyncratic annual var  = Σ E_i²·max(σ_i² − β_i²·σ_m², 0)   (residual, assumed independent)
  Portfolio annual var ($²) = (Σ E_i·β_i)²·σ_m² + idiosyncratic var
  Portfolio 1-month $-vol   = sqrt(annual var) / sqrt(12)
  VaR_95_1m ($)             = z·(1-month $-vol),  z = 1.645 (95% one-tailed, normal)
  VaR as % of dynCap        = VaR$ / dynCap · 100  → gated vs RB:risk.gates.var_95_1m (soft 18 / hard 20)

Gate is controlled by SIZE, not refusal of a name (D-38 spirit): a VaR breach flags/HALTS new adds,
it is the portfolio-level check the staging-gatekeeper reads as `var_ok` (post-add value).

Usage: python3 var_parametric.py <positions.json> [--market-vol-pct N] [--dyncap N]
  positions.json: [{"ticker","exposure_usd","beta","ann_vol_pct"}, ...]  (exposure signed; short<0)
"""
import json, os, sys, math

Z_95 = 1.645
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))


def _market_vol_ann_pct(default=15.74):
    """SPY annual vol from the historical store (the market factor). Falls back to a default."""
    try:
        import historical_store as h
        s = h.stats("SPY")
        if s and s.get("ann_vol_pct"):
            return float(s["ann_vol_pct"])
    except Exception:
        pass
    return default


def parametric_var(positions, market_vol_ann_pct=None, dyncap=None,
                   soft_pct=18.0, hard_pct=20.0, z=Z_95):
    """Single-factor parametric 95% 1-month VaR. positions: list of
    {exposure_usd (signed), beta, ann_vol_pct}. Returns the VaR + decomposition + gate flags."""
    mkt = (market_vol_ann_pct if market_vol_ann_pct is not None else _market_vol_ann_pct()) / 100.0
    net_beta_dollar = 0.0
    idio_var = 0.0
    gross = 0.0
    for p in positions:
        E = float(p.get("exposure_usd", 0) or 0)
        b = float(p.get("beta", 0) or 0)
        s = float(p.get("ann_vol_pct", 0) or 0) / 100.0
        net_beta_dollar += E * b
        resid = max(s * s - b * b * mkt * mkt, 0.0)   # idiosyncratic variance fraction
        idio_var += E * E * resid
        gross += abs(E)
    systematic_ann = abs(net_beta_dollar) * mkt                 # annual $ systematic vol
    port_ann_var = (net_beta_dollar ** 2) * (mkt ** 2) + idio_var
    port_ann_vol = math.sqrt(port_ann_var)
    port_1m_vol = port_ann_vol / math.sqrt(12)
    var_usd = z * port_1m_vol
    out = {
        "var_95_1m_usd": round(var_usd, 2),
        "systematic_ann_usd": round(systematic_ann, 2),
        "idiosyncratic_ann_usd": round(math.sqrt(idio_var), 2),
        "net_beta_dollar": round(net_beta_dollar, 2),
        "gross_exposure_usd": round(gross, 2),
        "market_vol_ann_pct": round(mkt * 100, 2),
        "method": "single-factor parametric (variance-covariance), 95% 1-month, z=1.645 (D-42)",
    }
    if dyncap:
        pct = var_usd / dyncap * 100.0
        out.update({
            "dyncap_usd": dyncap,
            "var_pct_of_dyncap": round(pct, 2),
            "soft_pct": soft_pct, "hard_pct": hard_pct,
            "soft_breach": pct > soft_pct,
            "var_ok": pct <= hard_pct,   # the boolean the gatekeeper/gate_check reads (post-add)
        })
    return out


if __name__ == "__main__":
    a = sys.argv[1:]
    if a and a[0] != "--self-test":
        positions = json.load(open(a[0]))
        if isinstance(positions, dict):
            positions = positions.get("positions") or positions.get("open_positions") or []
        mv = float(a[a.index("--market-vol-pct") + 1]) if "--market-vol-pct" in a else None
        dc = float(a[a.index("--dyncap") + 1]) if "--dyncap" in a else None
        print(json.dumps(parametric_var(positions, mv, dc), indent=1)); sys.exit(0)

    # self-test: two-name book, verify systematic + idiosyncratic decomposition and the gate
    pos = [{"exposure_usd": 20000, "beta": 1.2, "ann_vol_pct": 30.0},
           {"exposure_usd": 10000, "beta": 0.8, "ann_vol_pct": 25.0}]
    r = parametric_var(pos, market_vol_ann_pct=16.0, dyncap=66699)
    # hand-check: netβ$ = 20000*1.2 + 10000*0.8 = 32000; sys_ann = 32000*0.16 = 5120
    assert abs(r["net_beta_dollar"] - 32000) < 1e-6
    assert abs(r["systematic_ann_usd"] - 5120) < 1e-2
    # idio: 20000^2*(0.30^2-1.2^2*0.16^2) + 10000^2*(0.25^2-0.8^2*0.16^2)
    #     = 4e8*(0.09-0.036864) + 1e8*(0.0625-0.0163840) = 4e8*0.053136 + 1e8*0.046116
    idio = 4e8 * (0.09 - (1.2**2)*(0.16**2)) + 1e8 * (0.0625 - (0.8**2)*(0.16**2))
    ann_var = 32000**2 * 0.16**2 + idio
    exp_var = 1.645 * math.sqrt(ann_var) / math.sqrt(12)
    assert abs(r["var_95_1m_usd"] - round(exp_var, 2)) < 1.0, (r["var_95_1m_usd"], exp_var)
    assert r["var_ok"] in (True, False)
    print("var_parametric self-test PASSED —", json.dumps(r))
