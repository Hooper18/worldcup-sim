"""DC-on-Elo 拟合：合成数据恢复已知参数。"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from wcsim.models import dc_elo, poisson

TRUE = {"beta0": 0.20, "beta1": 1.10, "gamma": 0.30, "rho": -0.06}


def _synthetic(n: int = 25_000, seed: int = 7) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    x = rng.uniform(-1.0, 1.0, n)  # ΔElo/400 ∈ [-1, 1]（±400 分差）
    home_ind = rng.random(n) < 0.5
    lam_h = np.exp(TRUE["beta0"] + TRUE["beta1"] * x + TRUE["gamma"] * home_ind)
    lam_a = np.exp(TRUE["beta0"] - TRUE["beta1"] * x)

    hs = np.empty(n, dtype=int)
    as_ = np.empty(n, dtype=int)
    for i in range(n):
        mat = poisson.score_matrix(float(lam_h[i]), float(lam_a[i]), rho=TRUE["rho"], max_goals=10)
        h, a = poisson.sample_scores(mat, 1, rng)
        hs[i], as_[i] = h[0], a[0]

    dates = pd.Timestamp("2026-01-01") - pd.to_timedelta(rng.integers(0, 365, n), unit="D")
    return pd.DataFrame(
        {
            "date": dates,
            "home_team": "H",
            "away_team": "A",
            "home_score": hs,
            "away_score": as_,
            "tournament": "Friendly",
            "neutral": ~home_ind,
            "home_elo_pre": 1500 + 400 * x,
            "away_elo_pre": 1500.0,
        }
    )


def test_fit_recovers_true_parameters():
    hist = _synthetic()
    params = dc_elo.fit(hist, cutoff="2026-01-01", half_life_days=1e9, window_years=2)
    assert params.beta0 == pytest.approx(TRUE["beta0"], abs=0.04)
    assert params.beta1 == pytest.approx(TRUE["beta1"], abs=0.06)
    assert params.gamma == pytest.approx(TRUE["gamma"], abs=0.04)
    assert params.rho == pytest.approx(TRUE["rho"], abs=0.03)
    assert params.n_matches == 25_000


def test_predict_lambdas_symmetry_and_host():
    p = dc_elo.DcEloParams(
        beta0=0.2,
        beta1=1.1,
        gamma=0.3,
        rho=-0.05,
        half_life_days=730,
        n_matches=0,
        cutoff="2026-06-11",
    )
    lh, la = dc_elo.predict_lambdas(p, 1800, 1800)
    assert lh == pytest.approx(la)  # 同分中立场对称
    lh2, la2 = dc_elo.predict_lambdas(p, 1800, 1800, host_home=True)
    assert lh2 == pytest.approx(lh * np.exp(0.3))
    assert la2 == pytest.approx(la)
    # Elo 高 400 分 ⇒ λ 比 e^β1 放大
    lh3, la3 = dc_elo.predict_lambdas(p, 1900, 1500)
    assert lh3 / la3 == pytest.approx(np.exp(2 * 1.1))


def test_params_round_trip():
    p = dc_elo.DcEloParams(
        beta0=0.1,
        beta1=1.0,
        gamma=0.25,
        rho=-0.04,
        half_life_days=540,
        n_matches=123,
        cutoff="2026-06-11",
    )
    assert dc_elo.DcEloParams.from_dict(p.to_dict()) == p
