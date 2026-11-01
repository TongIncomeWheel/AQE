# aegis/plugin — THE ONE CODE TREE for the Aegis plugins

**PM ruling 2026-10-30 (BUILD_PLAN Phase 1): this directory is the truth. The installed plugins are generated from it, and so are the runtime copies AQE reads.** Refreshed 2026-11-01 from the handover kernel `aegis-kernel-2026-10-30.zip` (file list + sha256 in `KERNEL_MANIFEST_2026-10-30.json`).

| Tree | Version | What it is |
|---|---|---|
| `aegis-core/` | 1.31.0 | Charter, `/pma` conductor (`skills/pma/RUN.yaml`, `RULINGS.yaml`), agents, contracts, tools, the 307-test self-check |
| `aegis-voices/` | 1.9.0 | 15 seat cards, canon locks, shared voice engine |
| `aegis-daily/` | 1.2.1 | `/daily`, `/ptj`, `/premarket`, print-trade-journal |
| `aegis-stops/` | 0.1.0 | `/stops` reconcile |
| `aegis-live/` | 0.1.0 | 30-minute live review + session bootstrap hook |

## Rules
1. **Edit here, never the generated copies.** The nightly run imports `aegis/skills/premarket-analysis/tools/pma_pipeline.py` and `contracts/voice_menus.json` by path, and reads `aegis/canon/<voice>/canon.lock.yaml`. Those paths must not move (`src/pipeline/voice_packets.py`, `.github/workflows/deploy-hf.yml`), so they are **generated**:
   ```
   python3 aegis/plugin/sync_runtime.py          # plugin -> runtime copies + GENERATED.json
   python3 aegis/plugin/sync_runtime.py --check  # exit 1 on drift
   ```
   `tests/test_one_code_tree.py` fails the suite on drift. Before this existed AQE ran 1.24.1 / 1.8.0 against a live 1.31.0 / 1.9.0 for a week.
2. **Build installable zips:** `python3 aegis/plugin/build.py` → `dist/*.plugin` (gitignored). It refuses to build on drift.
3. **Plugin self-test:** `cd aegis/plugin/aegis-core/skills/pma && python3 tests/test_pipeline.py` → `307 passed, 0 failed` (self-running script, not pytest).
4. **No caches in the tree:** `.in_use`, `.pytest_cache`, `__pycache__`, `*.pyc`, `*.bak` are stripped on import and asserted absent.
5. `aegis-core/.mcp.json` is a Tiger placeholder (`REPLACE:` URL). claude.ai sessions use the account's `Tiger_MCPv7` connector; the placeholder is why the `aegis-core:tiger` MCP shows a connection error — harmless.

## The rest of `aegis/skills/premarket-analysis/`
Only the two generated files above are live. `SKILL.md`, `stages/`, `agents/`, the other `tools/` are the pre-1.24 vendored copies and are superseded by `aegis-core/skills/pma/`. Cleanup (archive, not delete) is on the Phase 4 list in `docs/BUILD_STATE.md`.
