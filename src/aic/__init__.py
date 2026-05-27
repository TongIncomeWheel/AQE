"""Aegis Investment Committee (AIC) -- LLM committee layer on top of AQE.

Build per AEGIS_POC_BUILD_SPEC_v2.md. AQE compute layer (src/scanner, src/engines,
src/analyzer, src/data, src/pipeline, src/ui) is FROZEN -- this package is
strictly additive and reads the AQE export as the only bridge.

Quick smoke-test (no LLM credentials required):
    python -m src.aic.prompts.prompt_builder           # writes 12 voice prompts
    python -m src.aic.committee.literature_loader      # shows literature slot status
    python -m src.aic.state.db                         # init session-state SQLite
    python -m src.aic.data.dsg13_extender              # add DSG-13 fields to AQE export
"""

VERSION = "0.1.0-poc"
SPEC_VERSION = "AEGIS_POC_BUILD_SPEC_v2.md"
CHARTER_VERSION = "v1.8.2"
