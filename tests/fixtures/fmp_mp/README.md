Real FMP /stable payloads for MP (MP Materials), captured 2026-11-02/03 through the FMP connector, which returns
the REST API's own JSON. Used by tests/test_committee_data.py as the "known FMP response". Fields not read by the
fetch step are dropped from profile / ratios_ttm / income_statement_growth to keep the files small; every
field the step reads is real. intraday_1hour and intraday_15min are complete, unedited, for 2026-11-02.
