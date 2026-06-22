"""Elo 公式与重放的手算对拍测试。"""

from __future__ import annotations

import pandas as pd
import pytest

from wcsim import config
from wcsim.ratings import elo


def _df(rows):
    return pd.DataFrame(
        rows,
        columns=[
            "date",
            "home_team",
            "away_team",
            "home_score",
            "away_score",
            "tournament",
            "city",
            "country",
            "neutral",
        ],
    ).assign(date=lambda d: pd.to_datetime(d["date"]))


def test_k_factor_classification():
    assert elo.k_factor("FIFA World Cup") == 60
    assert elo.k_factor("UEFA Euro") == 50
    assert elo.k_factor("Copa América") == 50
    assert elo.k_factor("FIFA World Cup qualification") == 40
    assert elo.k_factor("UEFA Euro qualification") == 40
    assert elo.k_factor("UEFA Nations League") == 40
    assert elo.k_factor("Friendly") == 20
    assert elo.k_factor("King's Cup") == 30


def test_goal_multiplier():
    assert elo.goal_multiplier(0) == 1.0
    assert elo.goal_multiplier(1) == 1.0
    assert elo.goal_multiplier(-1) == 1.0
    assert elo.goal_multiplier(2) == 1.5
    assert elo.goal_multiplier(3) == 1.75
    assert elo.goal_multiplier(5) == pytest.approx(2.0)  # 1.75 + 2/8
    assert elo.goal_multiplier(-4) == pytest.approx(1.875)


def test_expected_score_symmetry():
    assert elo.expected_score(1500, 1500) == pytest.approx(0.5)
    we = elo.expected_score(1600, 1500)
    assert we + elo.expected_score(1500, 1600) == pytest.approx(1.0)
    assert we > 0.5


def test_update_pair_home_win_with_home_advantage():
    # 同分两队，真主场，友谊赛 1-0：We = 1/(10^(-100/400)+1)
    nh, na = elo.update_pair(1500, 1500, 1, 0, neutral=False, tournament="Friendly")
    we = 1.0 / (10.0 ** (-100.0 / 400.0) + 1.0)
    assert nh == pytest.approx(1500 + 20 * (1 - we))
    assert na == pytest.approx(1500 - 20 * (1 - we))
    assert nh + na == pytest.approx(3000)  # 零和


def test_update_pair_draw_neutral_equal_no_change():
    nh, na = elo.update_pair(1500, 1500, 1, 1, neutral=True, tournament="Friendly")
    assert nh == pytest.approx(1500)
    assert na == pytest.approx(1500)


def test_update_pair_upset_gains_more():
    # 弱队(1400)中立场击败强队(1700)，K=60 G=1
    nh, na = elo.update_pair(1400, 1700, 1, 0, neutral=True, tournament="FIFA World Cup")
    we = 1.0 / (10.0 ** (300.0 / 400.0) + 1.0)  # 弱队期望
    assert nh - 1400 == pytest.approx(60 * (1 - we))
    assert nh - 1400 > 50  # 爆冷收益大
    assert na == pytest.approx(1700 - (nh - 1400))


def test_replay_chronological_and_through():
    df = _df(
        [
            ("2024-01-01", "Alpha", "Beta", 2, 0, "Friendly", "x", "y", True),
            ("2024-06-01", "Alpha", "Beta", 0, 1, "Friendly", "x", "y", True),
        ]
    )
    full, _ = elo.replay(df)
    cut, _ = elo.replay(df, through="2024-03-01")
    # 截止 3 月时只重放了第一场
    we = 0.5
    assert cut["Alpha"] == pytest.approx(1500 + 20 * 1.5 * (1 - we))
    assert full["Alpha"] < cut["Alpha"]  # 第二场输球扣分


def test_replay_with_history_records_pre_match_elo():
    df = _df(
        [
            ("2024-01-01", "Alpha", "Beta", 2, 0, "Friendly", "x", "y", True),
            ("2024-06-01", "Alpha", "Beta", 0, 1, "Friendly", "x", "y", True),
        ]
    )
    ratings, hist = elo.replay(df, with_history=True)
    assert hist is not None
    assert list(hist["home_elo_pre"])[0] == pytest.approx(config.ELO_START)
    # 第二场赛前 Elo = 第一场赛后
    after_first = 1500 + 20 * 1.5 * 0.5
    assert list(hist["home_elo_pre"])[1] == pytest.approx(after_first)
    assert ratings["Beta"] == pytest.approx(
        elo.update_pair(after_first, 3000 - after_first, 0, 1, neutral=True, tournament="Friendly")[
            1
        ]
    )
