# Handover: PMA fixes from the 21 Oct run

Four defects came out of today's run. Each entry below says what is wrong, why it matters, the fix, and how to check the fix worked.

Repo: TongIncomeWheel/AQE `main`. Plugin: `aegis-core` (installed copy, read-only in chat).

---

## 1. AQE builds voice packets with an old copy of the committee code

**Who fixes:** Claude Code in the AQE repo. Run `pytest -q` before pushing.

**What is wrong**
- `src/pipeline/voice_packets.py` loads `aegis/skills/premarket-analysis/tools/pma_pipeline.py` (1,339 lines) and calls `cmd_trim` and `cmd_packets`.
- The plugin's `skills/pma/tools/pma_pipeline.py` (2,005 lines) is a different version, and the two have drifted apart in both directions:
  - **Only in AQE:** `load_menus_from_canon()`, from D-119 (15 Sep). It reads menus from `aegis/canon/<voice>/canon.lock.yaml`.
  - **Only in the plugin:** the R12 held-book floor (16 Sep). `cmd_trim` carries `export.held_positions` onto the universe whole, and `cmd_packets` refuses to build without it. The plugin also has `cmd_brackets`, `cmd_repeatmarks`, `_lane`, `_strength_door`, `_elder_hi7_streak`, `_ref_px` and `_bracket_calc_path`.
- AQE main also has no `RULINGS.yaml`, and its `SKILL.md` is v5.3.

**Why it matters**
- AQE's published packets for 21 Oct had no MP row. MP is the PM's only held position, and every seat would have reviewed the book without it.
- The run rebuilt the packets locally to get around this. That workaround should not be needed every day.

**Fix**
1. Take the plugin's `pma_pipeline.py` as the base, because it has the newer rulings (R12–R21).
2. Port `load_menus_from_canon()` into it from AQE's copy. Keep `cmd_packets` accepting either `--menus` or `--canon-dir`, so both callers work.
3. Replace `aegis/skills/premarket-analysis/tools/pma_pipeline.py` with the merged file.
4. Copy the plugin's `RUN.yaml`, `RULINGS.yaml`, `SKILL.md`, `contracts/` and the other `tools/` beside it, so main stops lagging.
5. Push the same merged file back into the plugin build, so there is one copy.

**Verify**
- `python -m src.pipeline.voice_packets` on today's export produces packets that contain an MP row (or whatever the held book holds) in every nominator TSV.
- `pytest -q` passes.
- The plugin's `preflight_run.py run` passes against the merged copy.

**Side effect:** this is a change under `aegis/skills/`, which `deploy-hf.yml` re-adds for the Space, so it redeploys the Space once. Do it outside 21:30–04:00 SGT.

---

## 2. The verdict history stopped reaching AQE after 8 Sep

**Who fixes:** the PMA run (now done each run) plus a one-off repair.

**What is wrong**
- `record-verdicts` writes `verdict_ledger.json` in the run's local folder. No run pushed it to main after 8 Sep, and each container wipe lost it.
- `data/pma/verdict_ledger.json` stops at 8 Sep. `aegis/data/pma/verdict_ledger.json` held only 31 Aug until today.
- This is why repeat-watch reported 805 gaps and why the scorecard had nothing to grade.

**Done today**
- Today's 197 rows were pushed to `aegis/data/pma/verdict_ledger.json`.
- Runs 15, 19 and 20 Oct were rebuilt from the published level files (`levels/2026-10-15.json`, the 19 Oct `pma_levels.json`, and the 20 Oct `levels_parts`). This covers ADVANCE and HOLD rows only. Each rebuilt row is tagged `record_source: reconstructed_from_published_levels:<file>`.
- PASS and NEAR-MISS rows for 15, 19 and 20 Oct have no source and are not rebuilt.

**Still to fix (plugin)**
- Add the ledger files to RUN.yaml's PUBLISH step: push `verdict_ledger.json` and `phase4_ledger.json` to `aegis/data/pma/` every run, with a read-back check.
- Pick one ledger path. `data/pma/` and `aegis/data/pma/` both exist; retire `data/pma/verdict_ledger.json` or point it at the other.

**Verify:** tomorrow's repeat-watch shows real rows for 15–21 Oct instead of gaps.

---

## 3. The voice seat agents cannot read files

**Who fixes:** the plugin owner (aegis-voices), or a PM ruling on how seats are spawned.

**What is wrong**
- In this harness the `aegis-voices:voice-*` agent types only have the SubagentHandback tool.
- R2 says the conductor must paste each packet into the prompt. The packets are 80–180 KB each, about 1 MB per round, which is too heavy for the conductor to carry.
- On 21 Oct all 9 first spawns correctly refused to work blind.

**What worked today**
- Each seat was spawned as a general-purpose agent.
- It was told to read only its own card (`agents/voice-<seat>.md`) and its own packet, and to write its form.
- The registrar's figure audit (`validate --packet`) checked every quoted number, and none were invented.

**Fix: pick one**
- (a) Give the voice agent definitions the `Read` and `Write` tools, scoped to the run folder. Then change R2 to "packet read by path; figure audit is the check".
- (b) Make RUN.yaml spawn seats as general-purpose with the card path, the way WRITE already does for the brief-writer, and record that as the standard.

**Verify:** a fresh run's NOMINATE files 9 of 9 on the first spawn.

---

## 4. Livermore's seat status contradicts the run map

**Who fixes:** the PM rules; the plugin owner applies it.

**What is wrong**
- `agents/voice-livermore.md` opens with "SEAT STATUS — NOT DECIDED … not wired into the premarket swarm".
- RUN.yaml seats livermore in NOMINATE and VOTE.
- He ran on 21 Oct and his votes counted.

**PM decision needed**
- Is Livermore a counting seat, a 10th seat, or a replacement for another seat?
- Whichever you choose, edit either the card header or RUN.yaml so that they agree.

---

## Not defects (for the record)

- **Fundamentals:** pulled for the 54-name room after RANK, not the whole universe. This was a time choice, and coverage was 54/54.
- **Scorecard:** run as of the 20 Oct close. ADVANCE is +1.37 vs SPY and 19 of 25 beat SPY. The log line was appended to `aegis/output/pma/scorecard_log.jsonl`.
- **Repo access:** checkpoint pushes were skipped because push access was only attached at PUBLISH. In future runs, attach the AQE repo with push access at the start.

DRAFT — PM approval required. Nothing is staged, nothing is armed.
