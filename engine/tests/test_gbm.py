"""XGBoost 梯度提升只读基准（gbm.py）。

需可选依赖 xgboost——未安装时整个模块跳过（pytest.importorskip），CI 默认不装 ml 组、不跑这里。
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

pytest.importorskip("xgboost")

from wcsim.backtest import gbm, metrics  # noqa: E402

# 40 支队，各有固定强度（队名↔Elo 一一对应，使 probs() 的 elo 字典能复现训练特征）
_N_TEAMS = 40
_TEAM_ELO = {f"T{i}": 1300.0 + 500.0 * i / (_N_TEAMS - 1) for i in range(_N_TEAMS)}


def _hist(n: int = 3000, seed: int = 7) -> pd.DataFrame:
    """合成带 home_elo_pre/away_elo_pre 的历史明细：每队固定 Elo，Elo 差越大主队越可能赢。"""
    rng = np.random.default_rng(seed)
    teams = list(_TEAM_ELO)
    hi = rng.integers(0, _N_TEAMS, n)
    ai = rng.integers(0, _N_TEAMS, n)
    ai = np.where(ai == hi, (ai + 1) % _N_TEAMS, ai)  # 避免自己打自己
    home_team = [teams[i] for i in hi]
    away_team = [teams[i] for i in ai]
    home_elo = np.array([_TEAM_ELO[t] for t in home_team])
    away_elo = np.array([_TEAM_ELO[t] for t in away_team])
    z = 1.3 * (home_elo - away_elo) / 400.0
    ph = 1 / (1 + np.exp(-(z - 0.4)))
    pa = 1 / (1 + np.exp(-(-z - 0.4)))
    pdr = np.clip(1 - ph - pa, 0, None)
    hs = np.empty(n, int)
    as_ = np.empty(n, int)
    for i in range(n):
        probs = np.array([ph[i], pdr[i], pa[i]])
        o = rng.choice([0, 1, 2], p=probs / probs.sum())
        hs[i], as_[i] = {0: (1, 0), 1: (1, 1), 2: (0, 1)}[o]
    return pd.DataFrame(
        {
            "date": pd.Timestamp("2026-01-01") - pd.to_timedelta(rng.integers(0, 700, n), unit="D"),
            "home_team": home_team,
            "away_team": away_team,
            "home_score": hs,
            "away_score": as_,
            "home_elo_pre": home_elo,
            "away_elo_pre": away_elo,
            "neutral": rng.random(n) < 0.3,
            "tournament": "Friendly",
        }
    )


def test_probs_shape_normalized():
    params = gbm.fit(_hist(), cutoff="2026-01-01", window_years=3)
    elo = {"A": 1800.0, "B": 1500.0, "C": 1400.0}
    matches = pd.DataFrame({"home_team": ["A", "C"], "away_team": ["B", "A"]})
    p = gbm.probs(params, elo, matches)
    assert p.shape == (2, 3)
    assert np.allclose(p.sum(axis=1), 1.0)
    assert (p > 0).all()


def test_stronger_team_favored():
    params = gbm.fit(_hist(), cutoff="2026-01-01", window_years=3)
    elo = {"STRONG": 1950.0, "WEAK": 1450.0}
    m = pd.DataFrame({"home_team": ["STRONG"], "away_team": ["WEAK"]})
    p = gbm.probs(params, elo, m)
    assert p[0, 0] > p[0, 2]  # 主胜概率 > 客胜概率


def test_deterministic():
    """单线程 + 固定种子 → 两次独立拟合给出完全一致的概率（可复现）。"""
    hist = _hist()
    elo = {"A": 1700.0, "B": 1500.0}
    m = pd.DataFrame({"home_team": ["A"], "away_team": ["B"]})
    p1 = gbm.probs(gbm.fit(hist, cutoff="2026-01-01", window_years=3), elo, m)
    p2 = gbm.probs(gbm.fit(hist, cutoff="2026-01-01", window_years=3), elo, m)
    assert np.array_equal(p1, p2)


def test_beats_climatology_in_sample():
    """在可分的合成数据上，GBM 应优于永远报固定概率的 climatology。"""
    hist = _hist()
    params = gbm.fit(hist, cutoff="2026-01-01", window_years=3)
    # 队名↔Elo 固定，用训练集自身的对阵评估（仅作"强于 climatology"的合理性检查，非样本外）
    m = hist[["home_team", "away_team"]].copy()
    p = gbm.probs(params, _TEAM_ELO, m)
    outc = np.array(
        [
            metrics.outcome_of(h, a)
            for h, a in zip(hist["home_score"], hist["away_score"], strict=True)
        ]
    )
    clim = np.tile(np.array([0.40, 0.27, 0.33]), (len(outc), 1))
    assert metrics.rps(p, outc) < metrics.rps(clim, outc)


def test_probs_columns_are_home_draw_away():
    """multi:softprob 原生列序即 [主胜, 平, 客胜]：强主队主胜列最大、弱主队客胜列最大。"""
    params = gbm.fit(_hist(), cutoff="2026-01-01", window_years=3)
    m = pd.DataFrame({"home_team": ["T39", "T0"], "away_team": ["T0", "T39"]})
    p = gbm.probs(params, _TEAM_ELO, m)
    assert int(np.argmax(p[0])) == 0  # 最强打最弱 → 主胜列(0)最大
    assert int(np.argmax(p[1])) == 2  # 最弱打最强 → 客胜列(2)最大
