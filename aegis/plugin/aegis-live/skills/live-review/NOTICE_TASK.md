# AQE notice -> cockpit: the scheduled-task spec (PM 2026-11-02)

**Model: `claude-sonnet-5-5` (cost-efficient tier). Never opus for this task** -- it renders a file the
engine already computed; there is no judgment in it (RB:model_tiers.watch).

- Session: the PMA desk (`parameters.desk_session` in `aegis-core/skills/pma/RUN.yaml`).
- Window: 22:45 -> 05:15 SGT on US standard time (21:45 -> 04:15 on daylight time), Mon-Fri US sessions, every 30 min.
- Each firing runs ONE command and posts ONLY its stdout, and only on exit 0 or 4:

      cd <AQE checkout> && python3 aegis/plugin/aegis-live/tools/aqe_notice.py render --repo . --fetch --state $AEGIS_LIVE_DIR/aqe_notice_state.json

  exit 0 = actionable table (post verbatim) · 3 = quiet cycle (post nothing) · 4 = AQE ALERT ENGINE SILENT or
  the dead-man ALARM record (post it, first) · 5 = no notice published yet (say so once).
- Read-only: it never recomputes, never sizes, never places anything. Share counts in the table are arithmetic on
  `aegis_fund.md one_r_usd`, not a recommendation.
- Contract: `aegis-core/contracts/aqe_alert_notice.schema.json`. Writer: AQE `src/alerts/notice.py`.
