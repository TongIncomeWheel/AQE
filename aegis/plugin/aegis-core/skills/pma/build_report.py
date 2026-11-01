#!/usr/bin/env python3
"""RETIRED 2026-10-23 (R23). This file used to hold a one-off 25-Sep report with that day's prose
hard-coded inside it, and was rewritten by hand every morning -- which is why the report format kept
changing. The card report is now built by tools/pma_cards.py:

    pma_cards.py triggers ...   (cards.json for LEVELS, at CONDITIONS)
    pma_cards.py render --text cards_text.json --out pma_cards_<date>.html   (at REPORT)
"""
import sys
sys.exit("build_report.py is retired -- use tools/pma_cards.py render (R23).")
