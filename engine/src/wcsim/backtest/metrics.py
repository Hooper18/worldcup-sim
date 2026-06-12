"""预测评分指标：RPS、log-loss、校准曲线。

W/D/L 三类有序结果（主胜 > 平 > 客胜）。outcome 编码：0=主胜, 1=平, 2=客胜。
"""

from __future__ import annotations

import numpy as np


def outcome_of(home_goals: int, away_goals: int) -> int:
    if home_goals > away_goals:
        return 0
    if home_goals == away_goals:
        return 1
    return 2


def rps(probs: np.ndarray, outcomes: np.ndarray) -> float:
    """Ranked Probability Score（越低越好）。

    probs: (N, 3) 主胜/平/客胜概率；outcomes: (N,) ∈ {0,1,2}。
    有序 RPS = 1/(K-1) · Σ_k (CDF_pred_k − CDF_obs_k)²，K=3。
    """
    probs = np.asarray(probs, dtype=float)
    k = probs.shape[1]
    cdf_pred = np.cumsum(probs, axis=1)[:, : k - 1]  # 前 K-1 个累积（最后一个恒为 1）
    obs = np.zeros_like(probs)
    obs[np.arange(len(outcomes)), outcomes] = 1.0
    cdf_obs = np.cumsum(obs, axis=1)[:, : k - 1]
    # 归一化除以 (K-1)，使完全错误的确定性预测 RPS=1、完美预测 RPS=0
    return float(np.mean(np.sum((cdf_pred - cdf_obs) ** 2, axis=1)) / (k - 1))


def log_loss(probs: np.ndarray, outcomes: np.ndarray) -> float:
    probs = np.asarray(probs, dtype=float)
    p = probs[np.arange(len(outcomes)), outcomes]
    return float(-np.mean(np.log(np.clip(p, 1e-12, None))))


def calibration(probs: np.ndarray, outcomes: np.ndarray, bins: int = 10) -> list[list[float]]:
    """把所有 (预测概率, 是否发生) 对分桶，返回 [[平均预测, 经验频率, 样本数], ...]。

    展开三类结果的每个概率为独立的二元事件。
    """
    probs = np.asarray(probs, dtype=float)
    n = len(outcomes)
    onehot = np.zeros_like(probs)
    onehot[np.arange(n), outcomes] = 1.0
    p_flat = probs.ravel()
    y_flat = onehot.ravel()
    edges = np.linspace(0, 1, bins + 1)
    idx = np.clip(np.digitize(p_flat, edges) - 1, 0, bins - 1)
    out = []
    for b in range(bins):
        m = idx == b
        if m.sum() == 0:
            continue
        out.append([round(float(p_flat[m].mean()), 4), round(float(y_flat[m].mean()), 4), int(m.sum())])
    return out
