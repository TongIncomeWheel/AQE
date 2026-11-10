"""Cards: every condition word the vocabulary allows prints as plain English, never raw (PM 2026-11-10)."""
import importlib.util
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PMA = ROOT / "aegis/plugin/aegis-core/skills/pma"
spec = importlib.util.spec_from_file_location("card_words", PMA / "tools/card_words.py")
W = importlib.util.module_from_spec(spec); spec.loader.exec_module(W)
VOCAB = json.loads((PMA / "contracts/condition_vocab.json").read_text())


def test_every_word_and_every_level_the_vocabulary_allows_has_a_plain_phrase():
    assert set(VOCAB["words"]) == set(W.WORD_PLAIN), set(VOCAB["words"]) ^ set(W.WORD_PLAIN)
    assert set(VOCAB["levels"]) == set(W.LEVEL_PLAIN), set(VOCAB["levels"]) ^ set(W.LEVEL_PLAIN)


def test_no_phrase_contains_a_raw_word():
    for w in VOCAB["words"]:
        for lvl in (list(VOCAB["levels"])[:3] + [""]):
            out = W.cond_plain(f"{w}:{lvl}" if lvl else w)
            assert not re.search(r"[a-z]+_[a-z0-9_]+", out), (w, lvl, out)
            assert "{" not in out and "the the" not in out, out


def test_the_words_in_the_bug_reports():
    assert W.cond_plain("close_above:pivot_high") == "a daily close above the last pivot high"
    assert W.cond_plain("h1_close_above:bar_high") == "an hourly close above yesterday's high"
    assert W.cond_plain("reclaim:ma_20") == "a reclaim of the 20-day average"
    assert W.cond_plain("vol_x_ge:1.4") == "volume at least 1.4 times its average"
    assert W.no_raw_words("SPY close_below ma_50") == "SPY closes below the 50-day average"


def test_an_unmapped_word_falls_back_to_a_generic_phrase_never_the_raw_word():
    assert W.cond_plain("moon_phase:full") == W.GENERIC_COND
    assert W.no_raw_words("the new_thing_here fired") == f"the {W.GENERIC_COND} fired"


def test_the_gate_leaves_ordinary_sentences_alone_and_is_idempotent():
    s = "SPY closes below its 50-day average (SWK, SJM) and 5 above yesterday's high."
    assert W.no_raw_words(s) == s
    t = W.no_raw_words("2 close_above:pivot_high (SWK, SJM)")
    assert W.no_raw_words(t) == t and "_" not in t


def test_the_renderer_routes_the_triggers_sentence_and_the_market_kill_line_through_the_table():
    src = (PMA / "tools/pma_cards_v3.py").read_text()
    assert "from card_words import" in src
    assert "trg_txt = no_raw_words(trg_txt)" in src and "cond_plain(w)" in src
    assert "mk_plain = no_raw_words(mk_plain)" in src
