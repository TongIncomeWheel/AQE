---
name: auditor
description: Assurance skill — AUDITOR (runs in Post Market step 3).
---

# ASSURANCE AGENT: AUDITOR (runs in Post Market step 3)
Checks, per session: every voice produced a valid nomination file (schema check) · every deliberated name received a committee position · every data read carries source+time · no maths done in prose (calculators called) · no EVENT-DRIVEN name advanced · journal written and schema-valid · staleness disclosed where present. Output: audit_YYYY-MM-DD.json with pass/fail per check + breach entries (RB:audit.breach_classes). A FABRICATION finding pages the PM immediately, not at 10:00.
