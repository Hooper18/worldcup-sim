"""纯攻防 Dixon-Coles 拟合与预测、融合模型、回测指标。"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from wcsim.backtest import metrics
from wcsim.models import dc_attack
from wcsim.models.score_model import DcAttackModel, DcEloModel, EnsembleModel
from wcsim.models.dc_elo import DcEloParams


def _synthetic_league(n_teams=12, n_matches=4000, seed=3):
    rng = np.random.default_rng(seed)
    teams = [f"T{i}" for i in range(n_teams)]
    true_att = {t: rng.normal(0, 0.4) for t in teams}
    true_def = {t: rng.normal(0, 0.4) for t in teams}
    mu = 0.1
    rows = []
    for _ in range(n_matches):
        h, a = rng.choice(teams, 2, replace=False)
        lam_h = np.exp(mu + true_att[h] - true_def[a])
        lam_a = np.exp(mu + true_att[a] - true_def[h])
        rows.append((rng.poisson(lam_h), rng.poisson(lam_a), h, a))
    dates = pd.Timestamp("2026-01-01") - pd.to_timedelta(rng.integers(0, 700, n_matches), unit="D")
    return pd.DataFrame(
        {
            "date": dates,
            "home_team": [r[2] for r in rows],
            "away_team": [r[3] for r in rows],
            "home_score": [r[0] for r in rows],
            "away_score": [r[1] for r in rows],
            "tournament": "Friendly",
            "neutral": True,
        }
    ), true_att, true_def


def test_attack_fit_recovers_relative_strength():
    df, true_att, _ = _synthetic_league()
    params = dc_attack.fit(df, cutoff="2026-01-01", half_life_days=1e9, window_years=3)
    # 攻击力排序应与真值高度相关（岭惩罚会收缩绝对值，故比相对排序）
    teams = list(true_att)
    fitted = [params.att[t] for t in teams]
    truth = [true_att[t] for t in teams]
    corr = np.corrcoef(fitted, truth)[0, 1]
    assert corr > 0.9


def test_attack_predict_stronger_scores_more():
    df, true_att, true_def = _synthetic_league()
    params = dc_attack.fit(df, cutoff="2026-01-01", window_years=3)
    # 攻击最强 vs 防守最弱
    best_att = max(true_att, key=true_att.get)
    worst_def = min(true_def, key=true_def.get)  # def 越小越易失球
    lh, la = dc_attack.predict_lambdas(params, best_att, worst_def)
    assert lh > la


def test_select_ridge_returns_grid_value():
    df, _, _ = _synthetic_league(n_matches=6000)
    grid = (0.01, 0.05, 0.2)
    best, scan = dc_attack.select_ridge(df, cutoff="2026-01-01", ridge_grid=grid, half_life_days=1e9)
    assert best in grid
    assert set(scan) == set(grid)
    assert all(v > 0 for v in scan.values())


def test_empirical_home_advantage():
    rows = [
        # 主队都赢、都进更多球 → 明显主场优势
        ("2025-01-01", "A", "B", 2, 0, "Friendly", False),
        ("2025-02-01", "C", "D", 3, 1, "Friendly", False),
        ("2025-03-01", "E", "F", 1, 0, "Friendly", True),  # 中立场，应被排除
    ]
    df = pd.DataFrame(
        rows, columns=["date", "home_team", "away_team", "home_score", "away_score", "tournament", "neutral"]
    ).assign(date=lambda d: pd.to_datetime(d["date"]))
    diag = dc_attack.empirical_home_advantage(df)
    assert diag["n"] == 2  # 中立场被排除
    assert diag["home_win_rate"] == 1.0
    assert diag["home_goal_diff"] == 2.0
    assert diag["log_lambda_adv"] > 0


def test_attack_unknown_team_uses_average():
    df, _, _ = _synthetic_league()
    params = dc_attack.fit(df, cutoff="2026-01-01", window_years=3)
    lh, la = dc_attack.predict_lambdas(params, "Atlantis", "Wakanda")
    assert lh == pytest.approx(np.exp(params.mu))
    assert la == pytest.approx(np.exp(params.mu))


def test_ensemble_matrix_blends_and_normalizes():
    elo_p = DcEloParams(beta0=0.1, beta1=0.7, gamma=0.2, rho=-0.04, half_life_days=730, n_matches=1, cutoff="2026-06-11")
    att_p = dc_attack.DcAttackParams(
        mu=0.1, home_adv=0.2, rho=-0.03,
        att={"A": 0.5, "B": -0.2}, def_={"A": 0.1, "B": -0.3},
        half_life_days=730, n_matches=1, cutoff="2026-06-11", teams=["A", "B"],
    )
    elo = {"A": 1900.0, "B": 1700.0}
    ens = EnsembleModel([(DcEloModel(elo_p, elo), 0.5), (DcAttackModel(att_p), 0.5)])
    mat = ens.matrix("A", "B", host_home=False, host_away=False)
    assert mat.sum() == pytest.approx(1.0)
    # 融合矩阵介于两成分之间
    m1 = DcEloModel(elo_p, elo).matrix("A", "B", host_home=False, host_away=False)
    m2 = DcAttackModel(att_p).matrix("A", "B", host_home=False, host_away=False)
    assert np.allclose(mat, 0.5 * m1 + 0.5 * m2)


def test_rps_perfect_and_worst():
    # 完美预测（概率全在正确类）→ RPS=0
    probs = np.array([[1.0, 0.0, 0.0], [0.0, 0.0, 1.0]])
    outcomes = np.array([0, 2])
    assert metrics.rps(probs, outcomes) == pytest.approx(0.0)
    # 完全错误（主胜预测但实际客胜）→ RPS=1
    assert metrics.rps(np.array([[1.0, 0.0, 0.0]]), np.array([2])) == pytest.approx(1.0)


def test_rps_ordered_better_than_uniform():
    # 有序性质：接近真值的概率分布 RPS 更低
    outcomes = np.array([0])
    good = metrics.rps(np.array([[0.7, 0.2, 0.1]]), outcomes)
    bad = metrics.rps(np.array([[0.1, 0.2, 0.7]]), outcomes)
    assert good < bad


def test_outcome_of():
    assert metrics.outcome_of(2, 1) == 0
    assert metrics.outcome_of(1, 1) == 1
    assert metrics.outcome_of(0, 3) == 2
