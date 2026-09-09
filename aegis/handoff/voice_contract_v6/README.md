# voice_contract_v6 — pickup point for Claude Code on AQE

**Read first:** `../10_VOICE_DATA_CONTRACT_V6.md` — the instructions. Governing rule: ADDITIVE ONLY on `aqe_daily_export.json`; voice packets narrow, the main file only grows.

## What is on this branch
- `../10_VOICE_DATA_CONTRACT_V6.md` — the edit list (§2 main file additive, §3 packets, §4 builds, §5 needs-PM-ruling, §6 order of work + done-criteria)
- `bind.py`, `render.py` — generators: canon → binding → reading cards + v6 menus
- `voice_menus.v6.json` — generated menus (what each voice is served)
- `menu_diff.md` — per-voice diff vs `aegis/contracts/voice_menus.json`
- `nomination_v6.schema.json` — conductor-side R1 form (field names must agree)
- `canon_declared_gaps.txt` — what the PM-signed canons already declare NOT_SERVED
- `glossary.sha256` — sha256 of the merged `glossary.lock.json`

## The glossary (413 fields, engine-sourced) — NOT YET ON THIS BRANCH
The 400 KB `glossary.lock.json` (and the pre-rendered `binding/`, `cards/`) could not be pushed through the connector this session. Two ways to get it:
1. PM adds `TongIncomeWheel/AQE` to the Cowork session's repository sources → the conductor session pushes `parts/glossary_{A,B,C,D}.json` + `parts/merge_glossary.py` here directly.
2. Or: unpack `aqe_data_contract_v6_2026-09-09.tar.gz` (attached in the PM's Cowork chat, 2026-09-09) — its `contract/` folder is this folder; copy `glossary.lock.json`, `binding/`, `cards/`, `aqe_deliverables.json`, `AQE_DATA_CONTRACT_v6.md` in.

Then verify: `sha256sum glossary.lock.json` (parts route: `python3 parts/merge_glossary.py` first) and regenerate:
```
pip install pyyaml
python3 bind.py     # -> binding/<voice>.binding.yaml, aqe_deliverables.json
python3 render.py   # -> cards/<voice>.glossary.md, voice_menus.v6.json, menu_diff.md
```
Until the glossary lands, §2a–§2c and §3 of the handoff can be started from the handoff text alone (the new-key table and the packet rules do not depend on it); §2d and the `# NOTE` rendering wait for it.
