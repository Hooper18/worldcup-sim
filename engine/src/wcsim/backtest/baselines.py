"""更强的对标基准：Elo-logistic（只用 Elo 差的 2 参数有序模型）。

climatology 基准（永远报历史平均 [0.40,0.27,0.33]）太弱，"跑赢它"说明不了什么。Elo-logistic
是一个"傻瓜也能做的简单 Elo 模型"：只用赛前 Elo 差、两个参数（斜率 b、平局阈值 c），不含
攻防分解/泊松/逐队拟合。我们的 DC 融合模型能否跑赢它，才是有意义的对标。

    z = b · (R_home − R_away)/400
    P(主胜) = σ(z − c),  P(客胜) = σ(−z − c),  P(平) = 1 − P(主胜) − P(客胜)

c>0 保证平局概率为正。b、c 由训练集 W/D/L 极大似然拟合。
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.optimize import minimize
from scipy.special import expit

from . import metrics


def _sigmoid(x):
    # expit 即数值稳定的 logistic，等价于 1/(1+exp(-x)) 但大负数不溢出（消除回测时的 overflow 警告）
    return expit(x)


def _probs(b: float, c: float, dz: np.ndarray) -> np.ndarray:
    z = b * dz
    p_home = _sigmoid(z - c)
    p_away = _sigmoid(-z - c)
    p_draw = np.clip(1.0 - p_home - p_away, 1e-9, None)
    p = np.stack([p_home, p_draw, p_away], axis=1)
    return p / p.sum(axis=1, keepdims=True)


def fit(
    hist: pd.DataFrame, *, cutoff, half_life_days: float = 730.0, window_years: float = 8.0
) -> tuple[float, float]:
    """在带 home_elo_pre/away_elo_pre 的历史明细上拟合 (b, c)。"""
    cutoff_ts = pd.Timestamp(cutoff)
    lo = cutoff_ts - pd.Timedelta(days=window_years * 365.25)
    df = hist[(hist["date"] > lo) & (hist["date"] <= cutoff_ts)]
    dz = (df["home_elo_pre"].to_numpy() - df["away_elo_pre"].to_numpy()) / 400.0
    outc = np.array(
        [
            metrics.outcome_of(int(h), int(a))
            for h, a in zip(df["home_score"], df["away_score"], strict=True)
        ]
    )
    w = 0.5 ** ((cutoff_ts - df["date"]).dt.days.to_numpy(dtype=float) / half_life_days)

    def nll(theta):
        p = _probs(theta[0], theta[1], dz)
        pick = p[np.arange(len(outc)), outc]
        return -float(np.sum(w * np.log(np.clip(pick, 1e-12, None))))

    res = minimize(nll, np.array([1.0, 0.4]), method="Nelder-Mead")
    return float(res.x[0]), float(max(res.x[1], 1e-3))


def probs(b: float, c: float, elo: dict[str, float], matches: pd.DataFrame) -> np.ndarray:
    dz = np.array(
        [
            (elo.get(m.home_team, 1500.0) - elo.get(m.away_team, 1500.0)) / 400.0
            for m in matches.itertuples(index=False)
        ]
    )
    return _probs(b, c, dz)
