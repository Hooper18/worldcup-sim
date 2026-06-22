"""点球 Bradley-Terry 评分测试。"""

from __future__ import annotations

import pandas as pd
import pytest

from wcsim.ratings import penalty


def _shootouts(rows):
    return pd.DataFrame(rows, columns=["home_team", "away_team", "winner"])


def test_ridge_shrinks_toward_zero():
    # 单场点球：强岭惩罚下 θ 应接近 0（点球近随机的先验）
    df = _shootouts([("A", "B", "A")])
    theta = penalty.fit_penalty_ratings(df, ridge=10.0)
    assert abs(theta["A"]) < 0.2 and abs(theta["B"]) < 0.2
    assert theta["A"] > theta["B"]  # 赢家 θ 更高


def test_consistent_winner_gets_higher_theta():
    # A 多次赢 B → A 的 θ 明显高于 B
    df = _shootouts([("A", "B", "A")] * 8 + [("B", "A", "A")] * 2)
    theta = penalty.fit_penalty_ratings(df, ridge=1.0)
    assert theta["A"] > theta["B"]
    assert penalty.win_prob(theta["A"], theta["B"]) > 0.5


def test_centered():
    df = _shootouts([("A", "B", "A"), ("C", "D", "C"), ("B", "C", "B")])
    theta = penalty.fit_penalty_ratings(df, ridge=2.0)
    assert sum(theta.values()) == pytest.approx(0.0, abs=1e-6)


def test_win_prob_symmetry():
    assert penalty.win_prob(0.0, 0.0) == pytest.approx(0.5)
    assert penalty.win_prob(0.5, -0.5) + penalty.win_prob(-0.5, 0.5) == pytest.approx(1.0)


def test_code_map_and_unseen_team():
    df = _shootouts([("Germany", "England", "Germany")])
    theta = penalty.fit_penalty_ratings(df, ridge=2.0, code_map={"Germany": "GER", "England": "ENG"})
    assert "GER" in theta and "ENG" in theta
    assert theta["GER"] > theta["ENG"]


def test_empty():
    assert penalty.fit_penalty_ratings(_shootouts([]).dropna()) == {}
