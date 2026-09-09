# voice_contract_v6

Start with `../10_VOICE_DATA_CONTRACT_V6.md` (the instructions). Then:

```
base64 -d glossary.lock.json.gz.b64 | gunzip > glossary.lock.json
sha256sum glossary.lock.json   # must equal glossary.sha256
pip install pyyaml
python3 bind.py     # -> binding/<voice>.binding.yaml, aqe_deliverables.json
python3 render.py   # -> cards/<voice>.glossary.md, voice_menus.v6.json, menu_diff.md
```

Rule: ADDITIVE ONLY on the export. Packets narrow; the main file only grows.
