"""真实赛果状态：feed 解析、diff、读写。"""

from __future__ import annotations

import pandas as pd
import pytest

from wcsim import config
from wcsim.data import results_store as rs
from wcsim.data.normalize import code_to_martj42


def _feed_row(mid, home, away, hs, as_, winner="", group="Group A"):
    return {
        "MatchNumber": mid,
        "RoundNumber": 1,
        "HomeTeam": home,
        "AwayTeam": away,
        "HomeTeamScore": hs,
        "AwayTeamScore": as_,
        "Winner": winner,
        "Group": group,
    }


def test_parse_feed_group_match():
    feed = [_feed_row(1, "Mexico", "South Africa", 2, 1)]
    out = rs.parse_feed(feed)
    assert out == {1: {"h": 2, "a": 1, "after": "FT"}}


def test_parse_feed_skips_unplayed():
    feed = [_feed_row(1, "Mexico", "South Africa", None, None)]
    assert rs.parse_feed(feed) == {}


def test_parse_feed_rejects_wrong_group_pairing():
    # M1 是 墨西哥 v 南非；feed 若给出别的对阵说明数据错位，必须中止
    feed = [_feed_row(1, "Mexico", "Canada", 1, 0)]
    with pytest.raises(ValueError):
        rs.parse_feed(feed)


def test_parse_feed_knockout_draw_resolves_pen_winner():
    feed = [
        {
            "MatchNumber": 73,
            "RoundNumber": 4,
            "HomeTeam": "Mexico",
            "AwayTeam": "Canada",
            "HomeTeamScore": 1,
            "AwayTeamScore": 1,
            "Winner": "Canada",
            "Group": None,
        }
    ]
    out = rs.parse_feed(feed)
    assert out == {73: {"h": 1, "a": 1, "after": "PEN", "pen_winner": "away"}}


def test_parse_feed_knockout_draw_without_winner_skipped():
    feed = [
        {
            "MatchNumber": 73,
            "RoundNumber": 4,
            "HomeTeam": "Mexico",
            "AwayTeam": "Canada",
            "HomeTeamScore": 0,
            "AwayTeamScore": 0,
            "Winner": "",
            "Group": None,
        }
    ]
    assert rs.parse_feed(feed) == {}


def test_new_finished_diff():
    old = {1: {"h": 2, "a": 1, "after": "FT"}}
    new = {
        1: {"h": 2, "a": 1, "after": "FT"},
        2: {"h": 0, "a": 0, "after": "FT"},
        5: {"h": 3, "a": 1, "after": "FT"},
    }
    assert rs.new_finished(old, new) == [2, 5]


def test_store_round_trip(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "RESULTS_PATH", tmp_path / "results.json")
    store = {
        1: {"h": 2, "a": 1, "after": "FT"},
        77: {"h": 1, "a": 1, "after": "PEN", "pen_winner": "home"},
    }
    rs.save_store(store)
    assert rs.load_store() == store


def test_load_store_missing_file(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "RESULTS_PATH", tmp_path / "nope.json")
    assert rs.load_store() == {}


# ---------------------------------------------------------------------------
# parse_martj42（feed 失败时的回退；当前未接线，测试锁定其行为）
# ---------------------------------------------------------------------------


def _martj42_df(rows):
    # rows: (tournament, date_str, home_name, away_name, home_score, away_score)
    return pd.DataFrame(
        [
            {
                "tournament": t,
                "date": pd.Timestamp(d),
                "home_team": h,
                "away_team": a,
                "home_score": hs,
                "away_score": as_,
            }
            for (t, d, h, a, hs, as_) in rows
        ]
    )


def test_parse_martj42_group_match():
    # M1 = 墨西哥 v 南非（开幕日 2026-06-11），martj42 行按队码+日期窗口匹配
    df = _martj42_df(
        [("FIFA World Cup", "2026-06-11", code_to_martj42("MEX"), code_to_martj42("RSA"), 2, 0)]
    )
    assert rs.parse_martj42(df, {1: ("MEX", "RSA")}) == {1: {"h": 2, "a": 0, "after": "FT"}}


def test_parse_martj42_skips_knockout_draw():
    # 淘汰赛平比分需点球胜者，martj42 主表给不了 ⇒ 跳过等 shootouts/feed
    df = _martj42_df(
        [("FIFA World Cup", "2026-06-28", code_to_martj42("MEX"), code_to_martj42("CAN"), 1, 1)]
    )
    assert rs.parse_martj42(df, {73: ("MEX", "CAN")}) == {}


def test_parse_martj42_ignores_out_of_window():
    # 日期落在 kickoff ±1 天之外 ⇒ 不匹配
    df = _martj42_df(
        [("FIFA World Cup", "2026-06-20", code_to_martj42("MEX"), code_to_martj42("RSA"), 2, 0)]
    )
    assert rs.parse_martj42(df, {1: ("MEX", "RSA")}) == {}
