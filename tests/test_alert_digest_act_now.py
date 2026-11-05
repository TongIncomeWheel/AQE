"""PM 2026-11-05: "the AQE alerts have the same messages and clarity; highlight daily move vs last COB; actionable items at the top."
ACT NOW first (a buy fired, b near its buy line, c held, d failed), every headline carries the move vs the previous completed close."""
import re
from datetime import datetime
from zoneinfo import ZoneInfo

from src.alerts import emailer as E

ET = ZoneInfo("America/New_York")
NOW = datetime(2026, 11, 5, 15, 19, tzinfo=ET)


def _row(tk="AAA", level=100.0, **kw):
    r = {"ticker": tk, "class": "ADVANCE", "levels": {"stop": 96.0, "tp": [104.0, 108.0]},
         "conditions": {"shared": {"buy": [{"w": "h1_close_above", "level": level, "plain": f"an hourly candle closes above {level:g}"}],
                                   "confirm": [{"w": "vol_x_ge", "x": 1.4, "plain": "volume at least 1.4x normal for the time of day"}]}, "exits": []}}
    r.update(kw)
    return r


def _ev(**kw):
    base = {"buy_met": True, "lit": [], "wrong_lit": [], "chased": False, "exit_warn": None, "exit_hit": None, "n_counting": 0, "n_lit": 0,
            "no_shared_buy": False, "shared_buy_detail": [], "shared_confirm_detail": []}
    base.update(kw)
    return base


def _live(price=100.5, prev=98.2, atr=2.0, **kw):
    d = {"price": price, "prev_close": prev, "atr": atr, "vol_x": {"so_far": 1.6}, "unr": {"armed": [], "levels": [], "stop": None, "volume": {}}}
    d.update(kw)
    return d


def _held(tk="V", px=199.10, chg=-1.2, **kw):
    ev = {"ticker": tk, "is_held": True, "source": "pma", "level": "x-stopnear", "kind": "near_stops", "label": "Near your stops", "level_price": None,
          "live_px": px, "chg_pct": chg, "priority": "WARN", "broker_stop": 197.05, "committee_exit": 199.84, "action": "Price is close to your broker stop."}
    ev.update(kw)
    return ev


# ------------------------------------------------------------------ the move vs last close
def test_move_is_signed_coloured_and_bold_only_when_it_is_more_than_one_atr():
    up = E.move_vs_close(95.80, 93.65, 2.0)                                   # +2.3%, a 2.15 move vs ATR 2.0 -> more than 1 ATR
    assert up["text"] == "+2.3% vs last close 93.65" and up["color"] == "#0a8a3a" and up["big"] is True
    assert "font-weight:700" in E._move_html(up)
    small = E.move_vs_close(94.60, 93.65, 2.0)                                # +1.0%, a 0.95 move -> not bold
    assert small["big"] is False and "font-weight:400" in E._move_html(small)
    down = E.move_vs_close(91.00, 93.65, 2.0)
    assert down["text"] == "-2.8% vs last close 93.65" and down["color"] == "#b3261e" and down["big"] is True
    edge = E.move_vs_close(95.65, 93.65, 2.0)                                 # exactly 1 ATR is NOT "more than 1 ATR"
    assert edge["big"] is False
    assert E.move_vs_close(95.66, 93.65, 2.0)["big"] is True
    assert E.move_vs_close(100.0, 100.0, 2.0)["color"] == "#777777"


def test_a_missing_previous_close_says_so_never_blank():
    m = E.move_vs_close(95.8, None, 2.0)
    assert m["pct"] is None and "not available" in m["text"] and "previous close" in m["text"]
    assert E.move_vs_close(None, 93.65, 2.0) is None
    card = E.build_condition_card("AAA", _row(), _ev(), ["CONDITION_MET"], _live(prev=None))
    assert "vs last close: not available" in card["headline"]


def test_every_card_headline_carries_the_move_in_plain_and_html():
    card = E.build_condition_card("AAA", _row(), _ev(), ["CONDITION_MET"], _live(price=95.80, prev=93.65))
    assert card["headline"].startswith("AAA $95.80 · +2.3% vs last close 93.65 · ")
    assert "color:#0a8a3a;font-weight:700" in E._card_html(card)
    held = E.build_held_card(_held())
    assert held["headline"].startswith("V @ 199.10 · -1.2% vs last close 201.52 · ")


# ------------------------------------------------------------------ ACT NOW first, in order
def test_act_now_table_comes_first_and_is_ordered_a_then_b_then_c_then_d():
    cards = [("FAIL", _row("FAIL"), _ev(buy_met=False), ["FAILED_PUSH"], _live()),
             ("BUY", _row("BUY"), _ev(), ["CONDITION_MET"], _live()),
             ("WCH", _row("WCH"), _ev(buy_met=False), ["CHASED"], _live())]
    near = [{"ticker": "NEAR", "line": 100.0, "price": 99.4, "prev_close": 98.0, "atr": 2.0, "dist_atr": 0.3, "trade": "Committee trade: entry 100.00"}]
    subj, plain, html = E.build_condition_digest(cards, NOW, held_events=[_held()], meta={"near_trigger": near, "pma_run": "2026-11-05", "aqe_date": "2026-11-04"})
    assert subj == "[AQE] 15:19 ET · ACT NOW 1 · near trigger 1 · held 1 · failed 1 · PMA 11-05 · AQE 11-04"
    assert plain.index("ACT NOW") < plain.index("BUY $") and plain.index("ACT NOW") < plain.index("Watching, no action")
    i = [plain.index(f"[{k}]") for k in ("Buy trigger fired", "Near its buy line", "Held position", "Failed / confirmation lost")]
    assert i == sorted(i)                                                     # (a) < (b) < (c) < (d) in the table
    # the cards follow in the same order: buy card, then the held card, then the failed card; the watched name is one line at the bottom
    head = plain.split("Watching, no action")[0]
    assert head.index("BUY $") < head.index("V @ 199.10") < head.index("FAIL $")
    assert "WCH $100.50" in plain.split("Watching, no action")[1] and "WCH $100.50" not in head.split("ACT NOW")[1].split("\n\n")[0]
    assert html.index("ACT NOW") < html.index("BUY $") and "Price 100.50" in html


def test_the_act_now_rows_carry_price_move_trigger_stop_reward_and_the_1r_line():
    cards = [("BUY", _row("BUY"), _ev(), ["CONDITION_MET"], _live(price=100.5, prev=98.2))]
    _s, plain, _h = E.build_condition_digest(cards, NOW)
    line = next(l for l in plain.splitlines() if l.startswith("- [Buy trigger fired]"))
    assert "BUY" in line and "Price 100.50 · +2.3% vs last close 98.20" in line
    assert "hourly candle closes above 100" in line and "on at least 1.4x normal volume" in line
    assert "stop 96.00" in line and "shares" in line                          # the same trade line the card prints


def test_a_digest_with_nothing_to_act_on_has_no_act_now_table_and_says_zero_in_the_subject():
    cards = [("WCH", _row("WCH"), _ev(buy_met=False), ["CHASED"], _live())]
    subj, plain, _h = E.build_condition_digest(cards, NOW)
    assert "ACT NOW 0 · near trigger 0 · held 0" in subj and "\nACT NOW\n" not in plain


# ------------------------------------------------------------------ the Cards' words on the alert
def test_an_alert_card_quotes_the_cards_ten_fields_verbatim_and_says_when_they_are_missing():
    fields = {"tag": "supplemental committee pass, contested",
              "fields": [{"id": "lane", "label": "Lane", "text": "Momentum"},
                         {"id": "why", "label": "Why it made the list", "text": "A market leader breaking to a new high on heavy buying."},
                         {"id": "contested", "label": "Contested or rejected", "text": "Contested: the trigger is read on the hourly chart."},
                         {"id": "triggers", "label": "Triggers", "text": "An hourly close above 100."},
                         {"id": "sector", "label": "Sector and theme", "text": "Technology: graded DEPLOY"},
                         {"id": "bracket", "label": "Bracket", "text": "Entry reference 100, stop 96."},
                         {"id": "verdict", "label": "Verdict and timing", "text": "Advance. Timing: act now."},
                         {"id": "wrong_if", "label": "Wrong if / exit line", "text": "Wrong if a daily close prints under 96."},
                         {"id": "event", "label": "Event risk", "text": "M&A: no pending deal flagged."},
                         {"id": "frames", "label": "Trend frames", "text": "Weekly: higher highs and higher lows."}]}
    card = E.build_condition_card("AAA", _row(card_fields=fields), _ev(), ["CONDITION_MET"], _live())
    body = "\n".join(card["lines"])
    assert "Why it made the list [supplemental committee pass, contested]: A market leader breaking to a new high on heavy buying." in body
    assert "Wrong if / exit line: Wrong if a daily close prints under 96." in body and "Trend frames: Weekly: higher highs and higher lows." in body
    assert "Triggers: An hourly close above 100." not in body                 # the live buy line is the card's own
    bare = E.build_condition_card("AAA", _row(), _ev(), ["CONDITION_MET"], _live())
    assert "The committee's card: not available: the card fields were not published for this run." in "\n".join(bare["lines"])


def test_the_whole_email_passes_the_plain_words_gate():
    cards = [("BUY", _row("BUY"), _ev(), ["CONDITION_MET"], _live()), ("FAIL", _row("FAIL"), _ev(buy_met=False), ["FAILED_PUSH"], _live(prev=None))]
    near = [{"ticker": "NEAR", "line": 100.0, "price": 99.4, "prev_close": 98.0, "atr": 2.0, "dist_atr": 0.3, "trade": "Committee trade: entry 100.00"}]
    _s, plain, html = E.build_condition_digest(cards, NOW, held_events=[_held()], meta={"near_trigger": near})
    text = re.sub(r"<[^>]+>", " ", html) + plain
    assert not re.findall(r"\b[A-Za-z][A-Za-z0-9]*(?:_[A-Za-z0-9]+)+\b", text)           # no raw field names
    assert not re.findall(r"\bC\d{1,2}\b", text) and "W/D/H1" not in text
    assert not any(s in text.lower() for s in ("livermore", "minervini", "oneil", "raschke", "seow", "wyckoff", "elder-lens"))
    assert plain.count("Information only.") == 1


# ------------------------------------------------------------------ the near-trigger list (cycle side)
def test_a_name_within_half_an_atr_under_its_buy_line_is_near_and_nothing_else_is():
    from src.alerts import condition_cycle as CC
    row = _row("NEAR", level=100.0)
    ev = _ev(buy_met=False)
    assert CC._near_buy_line("NEAR", row, ev, _live(price=99.0, atr=2.0))["dist_atr"] == 0.5          # exactly 0.5 ATR under: near
    assert CC._near_buy_line("NEAR", row, ev, _live(price=98.9, atr=2.0)) is None                      # 0.55 ATR under: not near
    assert CC._near_buy_line("NEAR", row, ev, _live(price=100.2, atr=2.0)) is None                     # at or over the line: it is a trigger, not "near"
    assert CC._near_buy_line("NEAR", row, _ev(buy_met=True), _live(price=99.5)) is None               # already met
    assert CC._near_buy_line("NEAR", dict(row, watch_only=True), ev, _live(price=99.5)) is None
    assert CC._near_buy_line("NEAR", dict(row, **{"class": "HELD"}), ev, _live(price=99.5)) is None
    assert CC._near_buy_line("NEAR", row, ev, _live(price=99.5, atr=None)) is None                     # no ATR: no claim
    n = CC._near_buy_line("NEAR", row, ev, _live(price=99.5, prev=98.0))
    assert n["line"] == 100.0 and n["prev_close"] == 98.0 and "Committee trade" in n["trade"]
