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


def rps_per_match(probs: np.ndarray, outcomes: np.ndarray) -> np.ndarray:
    """逐场 RPS（不取均值），供配对 bootstrap 等显著性分析。返回 (N,)。"""
    probs = np.asarray(probs, dtype=float)
    k = probs.shape[1]
    cdf_pred = np.cumsum(probs, axis=1)[:, : k - 1]  # 前 K-1 个累积（最后一个恒为 1）
    obs = np.zeros_like(probs)
    obs[np.arange(len(outcomes)), outcomes] = 1.0
    cdf_obs = np.cumsum(obs, axis=1)[:, : k - 1]
    # 归一化除以 (K-1)，使完全错误的确定性预测 RPS=1、完美预测 RPS=0
    return np.sum((cdf_pred - cdf_obs) ** 2, axis=1) / (k - 1)


def rps(probs: np.ndarray, outcomes: np.ndarray) -> float:
    """Ranked Probability Score（越低越好）。

    probs: (N, 3) 主胜/平/客胜概率；outcomes: (N,) ∈ {0,1,2}。
    有序 RPS = 1/(K-1) · Σ_k (CDF_pred_k − CDF_obs_k)²，K=3。
    """
    return float(np.mean(rps_per_match(probs, outcomes)))


def paired_bootstrap_rps_diff(
    probs_a: np.ndarray,
    probs_b: np.ndarray,
    outcomes: np.ndarray,
    *,
    n_boot: int = 2000,
    seed: int = 0,
) -> dict:
    """配对 bootstrap：mean(RPS_a − RPS_b) 的点估计与 95% 区间（负=a 更好）。

    对**同一批比赛**重抽（保留 a/b 在每场上的配对），得到差值均值的抽样分布。
    `significant=True` 当且仅当 95% 区间不含 0——这是把"A 比 B 好 0.003"从噪声里区分出来
    所需的显著性工具（此前 repo 缺它，故所有"提升"声明都不可证）。
    """
    da = rps_per_match(probs_a, outcomes)
    db = rps_per_match(probs_b, outcomes)
    diff = da - db
    n = len(diff)
    rng = np.random.default_rng(seed)
    means = np.array([diff[rng.integers(0, n, n)].mean() for _ in range(n_boot)])
    lo, hi = np.percentile(means, [2.5, 97.5])
    return {
        "mean_diff": round(float(diff.mean()), 4),
        "ci_lo": round(float(lo), 4),
        "ci_hi": round(float(hi), 4),
        "significant": bool(lo > 0 or hi < 0),
    }


def log_loss(probs: np.ndarray, outcomes: np.ndarray) -> float:
    probs = np.asarray(probs, dtype=float)
    p = probs[np.arange(len(outcomes)), outcomes]
    return float(-np.mean(np.log(np.clip(p, 1e-12, None))))


def brier_score(probs: np.ndarray, outcomes: np.ndarray) -> float:
    """多类 Brier 评分（越低越好）：Σ (p_k − [y=k])² 的样本均值。

    与 RPS 不同，Brier 对类别无序惩罚——RPS 罚"差很远的预测"更重（有序性），
    Brier 罚"概率离一热编码的距离"。两者互补：RPS 看序、Brier 看概率精度。
    """
    probs = np.asarray(probs, dtype=float)
    onehot = np.zeros_like(probs)
    onehot[np.arange(len(outcomes)), outcomes] = 1.0
    return float(np.mean(np.sum((probs - onehot) ** 2, axis=1)))


def _wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    """Wilson 二项比例置信区间（小样本下比正态近似可靠）。"""
    if n == 0:
        return 0.0, 1.0
    p = k / n
    denom = 1 + z * z / n
    center = (p + z * z / (2 * n)) / denom
    half = z * np.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return max(0.0, center - half), min(1.0, center + half)


def reliability_diagram(probs: np.ndarray, outcomes: np.ndarray, bins: int = 10) -> list[dict]:
    """可靠性图分桶：每桶 {平均预测概率, 经验频率, Wilson 95% 区间, 样本数}。

    三类结果的每个预测概率展开为独立二元事件（预测 p、是否发生）。点越贴近对角线、
    区间越窄，说明概率越可信。
    """
    probs = np.asarray(probs, dtype=float)
    n = len(outcomes)
    onehot = np.zeros_like(probs)
    onehot[np.arange(n), outcomes] = 1.0
    p_flat = probs.ravel()
    y_flat = onehot.ravel().astype(int)
    edges = np.linspace(0, 1, bins + 1)
    idx = np.clip(np.digitize(p_flat, edges) - 1, 0, bins - 1)
    out = []
    for b in range(bins):
        m = idx == b
        cnt = int(m.sum())
        if cnt == 0:
            continue
        k = int(y_flat[m].sum())
        lo, hi = _wilson(k, cnt)
        out.append(
            {
                "p_pred": round(float(p_flat[m].mean()), 4),
                "freq": round(k / cnt, 4),
                "ci_lo": round(lo, 4),
                "ci_hi": round(hi, 4),
                "n": cnt,
            }
        )
    return out


def calibration(probs: np.ndarray, outcomes: np.ndarray, bins: int = 10) -> list[list[float]]:
    """旧接口（兼容前端 ModelPage）：[[平均预测, 经验频率, 样本数], ...]。"""
    return [[d["p_pred"], d["freq"], d["n"]] for d in reliability_diagram(probs, outcomes, bins)]


def ece(probs: np.ndarray, outcomes: np.ndarray, bins: int = 10) -> float:
    """Expected Calibration Error：各桶 |平均预测 − 经验频率| 按样本量加权平均（越低越校准）。"""
    diag = reliability_diagram(probs, outcomes, bins)
    total = sum(d["n"] for d in diag)
    if total == 0:
        return 0.0
    return float(sum(d["n"] * abs(d["p_pred"] - d["freq"]) for d in diag) / total)
