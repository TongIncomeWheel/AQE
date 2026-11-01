#!/usr/bin/env python3
"""Read the Aegis sub-fund config from config/aegis_fund.md (D-23).

The config is a plain Markdown file the PM edits by hand; the machine-readable part
is the YAML front-matter between the first pair of '---' lines. Everything else is prose.
ONE accessor so every tool reads the fund the same way — no field lives in two places.

Usage:
  python3 tools/fund_config.py            # print the parsed config as JSON
  python3 tools/fund_config.py allocated_capital_usd   # print one field
"""
import json, os, sys, yaml

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FUND_MD = os.path.join(ROOT, "config", "aegis_fund.md")


def load(path=FUND_MD):
    """Return the front-matter dict. Raises if the file or front-matter is missing —
    a missing fund config is a hard stop, never a silent default (fail-closed)."""
    text = open(path, encoding="utf-8").read()
    if not text.startswith("---"):
        raise ValueError(f"{path}: no YAML front-matter (expected '---' on line 1)")
    _, fm, _ = text.split("---", 2)
    cfg = yaml.safe_load(fm) or {}
    if cfg.get("strategy_tag") != "AEGIS":
        raise ValueError(f"{path}: strategy_tag must be AEGIS, got {cfg.get('strategy_tag')!r}")
    return cfg


def allocated_capital(path=FUND_MD):
    """The PM's Aegis allocation, or None if unset. Callers (sizing) must refuse on None."""
    return load(path).get("allocated_capital_usd")


def dyncap(path=FUND_MD):
    """Dynamic capital: explicit value if set, else seed to allocation (day-one behaviour)."""
    cfg = load(path)
    dc = cfg.get("dyncap_usd")
    return dc if dc is not None else cfg.get("allocated_capital_usd")


def one_r_usd(path=FUND_MD):
    """THE ONE risk-per-trade figure (PM 2026-10-27: $620, fixed dollars). None when unset -- callers then
    fall back to parameters.yaml capital.one_r_pct_of_dyncap. Never computed from capital here."""
    v = load(path).get("one_r_usd")
    if v is None:
        return None
    if not isinstance(v, (int, float)) or v <= 0:
        raise ValueError(f"{path}: one_r_usd must be a positive number, got {v!r}")
    return float(v)


def one_r_pct_equivalent(dyncap_usd, path=FUND_MD):
    """The percent of dynCap that reproduces the fixed one_r_usd exactly, so sizing.size() (which takes a
    percent) returns a budget of one_r_usd * r_multiple without a second code path. None when one_r_usd is unset."""
    r = one_r_usd(path)
    if r is None or not dyncap_usd or dyncap_usd <= 0:
        return None
    return r / float(dyncap_usd) * 100.0


if __name__ == "__main__":
    cfg = load()
    if len(sys.argv) > 1:
        print(cfg.get(sys.argv[1]))
    else:
        print(json.dumps(cfg, indent=1))
