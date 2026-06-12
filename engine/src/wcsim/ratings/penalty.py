"""点球大战能力评分：对历史点球大战拟合正则化 Bradley-Terry 模型。

    P(主队赢点球) = logistic(θ_home − θ_away)

θ 是各队的"点球能力"(中心 0)。用 martj42 shootouts.csv（每场点球大战的胜负）拟合，
加较强岭惩罚——因为大样本研究表明点球大战接近随机（无系统性先罚优势、各队差异小），
强先验把 θ 收缩到 0 附近，只让历史上确实稳定强/弱的队（如德国 vs 英格兰）有微小偏移。
替代原来硬编码的 50:50。
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.optimize import minimize

RIDGE = 3.0  # 岭惩罚强度（点球近随机 → 强收缩）


def _logistic(x: np.ndarray) -> np.ndarray:
    return 1.0 / (1.0 + np.exp(-x))


def fit_penalty_ratings(
    shootouts: pd.DataFrame,
    *,
    ridge: float = RIDGE,
    code_map: dict[str, str] | None = None,
) -> dict[str, float]:
    """拟合点球能力 θ。code_map: martj42 队名→输出 key（缺省用原名）。

    返回 {key: θ}（仅含在点球大战中出现过的队；未出现的队 θ 取 0=中性）。
    """
    df = shootouts.dropna(subset=["winner"]).copy()
    if code_map is not None:
        df["home_key"] = df["home_team"].map(code_map)
        df["away_key"] = df["away_team"].map(code_map)
        df["win_key"] = df["winner"].map(code_map)
    else:
        df["home_key"] = df["home_team"]
        df["away_key"] = df["away_team"]
        df["win_key"] = df["winner"]
    df = df.dropna(subset=["home_key", "away_key", "win_key"])

    teams = sorted(set(df["home_key"]) | set(df["away_key"]))
    idx = {t: i for i, t in enumerate(teams)}
    T = len(teams)
    if T == 0:
        return {}

    # winner / loser 索引
    win = np.empty(len(df), dtype=int)
    los = np.empty(len(df), dtype=int)
    for r, row in enumerate(df.itertuples(index=False)):
        w = row.win_key
        h, a = row.home_key, row.away_key
        loser = a if w == h else h
        win[r] = idx[w]
        los[r] = idx[loser]

    def nll_grad(theta):
        d = theta[win] - theta[los]
        p = _logistic(d)
        nll = -np.sum(np.log(np.clip(p, 1e-12, None))) + 0.5 * ridge * np.sum(theta**2)
        # ∂/∂θ_k：每场 winner 得 (1−p)，loser 得 −(1−p)
        g = np.zeros(T)
        np.add.at(g, win, -(1 - p))
        np.add.at(g, los, (1 - p))
        g += ridge * theta
        return nll, g

    res = minimize(nll_grad, np.zeros(T), jac=True, method="L-BFGS-B")
    theta = res.x - res.x.mean()  # 中心化
    return {t: float(theta[idx[t]]) for t in teams}


def win_prob(theta_home: float, theta_away: float) -> float:
    """主队赢点球大战的概率。"""
    return float(_logistic(theta_home - theta_away))
