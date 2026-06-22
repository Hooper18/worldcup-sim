"""赔率去 overround / 共识，以及 Elo-logistic 基准。"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from wcsim.backtest import baselines, metrics
from wcsim.models import odds

# ---------------------------------------------------------------------------
# 去 overround
# ---------------------------------------------------------------------------

def test_fair_probs_sum_to_one():
    o = np.array([2.0, 3.5, 4.0])  # 含 overround
    for method in ("proportional", "power", "shin"):
        p = odds.fair_probs(o, method)
        assert p.sum() == pytest.approx(1.0)
        assert (p > 0).all()


def test_overround_removed_lowers_total():
    o = np.array([2.0, 3.5, 4.0])
    raw = odds.implied(o)
    assert raw.sum() > 1.0  # 庄家抽水
    assert odds.fair_probs(o, "proportional").sum() == pytest.approx(1.0)


def test_fair_order_preserved():
    # 赔率越低 → 概率越高，去 overround 后顺序不变
    o = np.array([1.5, 4.0, 6.0])
    for method in ("proportional", "power", "shin"):
        p = odds.fair_probs(o, method)
        assert p[0] > p[1] > p[2]


def test_consensus_averages_books():
    # 两家庄家，共识应在两者之间
    p1 = odds.fair_probs(np.array([2.0, 3.3, 4.0]))
    p2 = odds.fair_probs(np.array([2.2, 3.1, 3.8]))
    cons = odds.consensus([p1, p2])
    assert cons.sum() == pytest.approx(1.0)
    assert min(p1[0], p2[0]) - 1e-6 <= cons[0] <= max(p1[0], p2[0]) + 1e-6


# ---------------------------------------------------------------------------
# Elo-logistic 基准
# ---------------------------------------------------------------------------

def _hist(n=4000, seed=1):
    rng = np.random.default_rng(seed)
    dz = rng.uniform(-1.5, 1.5, n)  # ΔElo/400
    # 真实生成：z=1.2*dz, 阈值 0.45
    z = 1.2 * dz
    ph = 1 / (1 + np.exp(-(z - 0.45)))
    pa = 1 / (1 + np.exp(-(-z - 0.45)))
    pd_ = np.clip(1 - ph - pa, 0, None)
    hs = np.empty(n, int)
    as_ = np.empty(n, int)
    for i in range(n):
        o = rng.choice([0, 1, 2], p=[ph[i], pd_[i], pa[i]] / np.sum([ph[i], pd_[i], pa[i]]))
        if o == 0:
            hs[i], as_[i] = 1, 0
        elif o == 1:
            hs[i], as_[i] = 1, 1
        else:
            hs[i], as_[i] = 0, 1
    return pd.DataFrame(
        {
            "date": pd.Timestamp("2026-01-01") - pd.to_timedelta(rng.integers(0, 700, n), unit="D"),
            "home_score": hs,
            "away_score": as_,
            "home_elo_pre": 1500 + 400 * dz,
            "away_elo_pre": 1500.0,
        }
    )


def test_elo_baseline_recovers_and_beats_climatology():
    hist = _hist()
    b, c = baselines.fit(hist, cutoff="2026-01-01", half_life_days=1e9, window_years=3)
    assert b > 0 and c > 0
    # 在样本上，Elo 基准应优于 climatology（永远报固定概率）
    dz = (hist["home_elo_pre"] - hist["away_elo_pre"]) / 400.0
    p = baselines._probs(b, c, dz.to_numpy())
    outc = np.array([metrics.outcome_of(h, a) for h, a in zip(hist["home_score"], hist["away_score"], strict=True)])
    clim = np.tile(np.array([0.4, 0.27, 0.33]), (len(outc), 1))
    assert metrics.rps(p, outc) < metrics.rps(clim, outc)


def test_elo_baseline_probs_normalized():
    b, c = 1.0, 0.4
    elo = {"A": 1900.0, "B": 1600.0}
    m = pd.DataFrame({"home_team": ["A"], "away_team": ["B"]})
    p = baselines.probs(b, c, elo, m)
    assert p.shape == (1, 3)
    assert p.sum() == pytest.approx(1.0)
    assert p[0, 0] > p[0, 2]  # 强队主场更可能赢
