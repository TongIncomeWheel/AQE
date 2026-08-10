"""The reading guide must not drift from the thing it describes.

`docs/AQE_CROWN_READING_GUIDE.md` teaches people how to interpret the layer. A
teaching document that quietly falls out of step with the code is worse than no
document — it trains readers to look for fields that no longer exist and to
trust thresholds that have since moved.

So the guide is checked against the source the same way `explain.py` is: every
field it names must exist, every family it lists must be a real family, and the
numbers it quotes must be the constants actually in force.
"""

from __future__ import annotations

import pathlib
import re

import pytest

from src.macro import scenarios as SC
from src.macro.crown import spec as S

GUIDE = pathlib.Path("docs/AQE_CROWN_READING_GUIDE.md")
SRC = "\n".join(p.read_text(encoding="utf-8")
                for p in pathlib.Path("src/macro").rglob("*.py"))


@pytest.fixture(scope="module")
def guide() -> str:
    assert GUIDE.exists(), "the reading guide is missing"
    return GUIDE.read_text(encoding="utf-8")


def test_every_field_it_names_exists_in_the_code(guide):
    """A guide that sends readers to a field we deleted is actively harmful."""
    ignore = {"true", "false", "null", "none", "output", "docs", "src"}
    named = {m for m in re.findall(r"`([a-z_]{4,})`", guide)} - ignore
    missing = [n for n in sorted(named)
               if f'"{n}"' not in SRC and f"'{n}'" not in SRC
               and f"def {n}" not in SRC and f"{n} =" not in SRC]
    assert not missing, f"guide names fields that do not exist: {missing}"


def test_every_expression_family_it_lists_is_real(guide):
    for fam in S.EXPRESSION_FAMILIES:
        if fam == "NONE":
            continue
        assert fam in guide, f"guide never explains the {fam} family"


def test_it_does_not_invent_families(guide):
    listed = set(re.findall(r"`([A-Z_]{6,})`", guide))
    families = {f for f in listed if f.endswith(("CARRY", "CONCENTRATED",
                                                 "DOWNSIDE", "SHORT", "PREMIUM"))}
    assert families <= set(S.EXPRESSION_FAMILIES), \
        f"guide describes families that do not exist: {families - set(S.EXPRESSION_FAMILIES)}"


def test_the_gate_it_quotes_is_the_gate_in_force(guide):
    assert f"{S.HB_CONFIDENCE_GATE:.2f}" in guide or "0.40" in guide
    assert str(S.HB_LOOKBACK_DAYS) in guide          # the 252-day range
    assert str(S.DIV_LOOKBACK) in guide              # the 120-session pivot window


def test_the_measured_false_positive_rates_match_the_spec(guide):
    """These numbers are the reason the slope read is a readout and not a
    trigger. If they are edited in one place and not the other, the guide is
    teaching a rule the code no longer follows."""
    spec_src = pathlib.Path("src/macro/crown/spec.py").read_text(encoding="utf-8")
    for rate in ("2.5%", "14.1%", "0.6%"):
        assert rate in guide, f"guide dropped the measured rate {rate}"
        assert rate in spec_src, f"spec.py no longer records {rate}"


def test_the_dispersion_states_it_teaches_are_the_ones_emitted(guide):
    for state in ("ELEVATED_RISING", "ELEVATED_EASING"):
        assert state in guide
        assert state in SRC


def test_it_names_the_scenario_artifact_and_the_merge_point(guide):
    assert "macro_scenarios.json" in guide
    assert "merge point" in guide.lower()
    assert len(SC.SCENARIOS) >= 5


def test_it_states_what_the_layer_refuses_to_do(guide):
    """The four standing limits. If any of these disappears from the guide,
    someone will eventually read a family as a trade and a score as a
    probability."""
    low = guide.lower()
    assert "does not size" in low
    assert "does not name a ticker" in low
    assert "no base rate" in low or "no base rates" in low
    assert "share of conditions" in low


def test_it_carries_the_known_gaps(guide):
    low = guide.lower()
    for gap in ("gamma is off", "plan-gated", "cannot time anything"):
        assert gap in low, f"guide dropped a known limitation: {gap}"


def test_it_is_anchored_to_the_kernel_sections(guide):
    """The whole point is reading the build against the spec. Losing the section
    anchors turns it back into a standalone doc that can drift on its own."""
    for section in ("§2.1", "§2.2", "§2.3", "§2.4", "§2.5", "§3", "§4"):
        assert section in guide, f"guide lost its anchor to kernel {section}"
    assert "v1.4" in guide
