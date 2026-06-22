"""Poisson 比分矩阵工具：λ → 比分概率网格、Dixon-Coles 低比分修正、概率聚合。

Dixon-Coles tau 修正只改四个低比分格（本参数化下 ρ<0 上调 0-0/1-1、下调 1-0/0-1）：
    τ(0,0) = 1 − λμρ     τ(1,0) = 1 + μρ
    τ(0,1) = 1 + λρ      τ(1,1) = 1 − ρ
"""

from __future__ import annotations

import math

import numpy as np

from .. import config


def poisson_pmf_vector(lam: float, max_goals: int) -> np.ndarray:
    """[P(0), P(1), ..., P(max_goals)]，末项吸收尾部概率使总和为 1。"""
    ks = np.arange(max_goals + 1)
    log_p = ks * math.log(lam) - lam - np.array([math.lgamma(k + 1) for k in ks])
    p = np.exp(log_p)
    p[-1] += max(0.0, 1.0 - p.sum())  # 尾部截断概率并入末格
    return p


def score_matrix(
    lam_home: float,
    lam_away: float,
    rho: float = 0.0,
    max_goals: int = config.MAX_GOALS,
) -> np.ndarray:
    """P[h, a] = 主队进 h 球且客队进 a 球的概率，(max_goals+1)² 网格，总和归一。"""
    ph = poisson_pmf_vector(lam_home, max_goals)
    pa = poisson_pmf_vector(lam_away, max_goals)
    mat = np.outer(ph, pa)

    if rho != 0.0:
        tau = np.ones_like(mat)
        tau[0, 0] = 1.0 - lam_home * lam_away * rho
        tau[1, 0] = 1.0 + lam_away * rho
        tau[0, 1] = 1.0 + lam_home * rho
        tau[1, 1] = 1.0 - rho
        mat = mat * np.clip(tau, 1e-10, None)

    return mat / mat.sum()


def outcome_probs(mat: np.ndarray) -> tuple[float, float, float]:
    """(主胜, 平, 客胜) 概率。"""
    p_home = float(np.tril(mat, -1).sum())  # h > a：下三角
    p_draw = float(np.trace(mat))
    p_away = float(np.triu(mat, 1).sum())
    return p_home, p_draw, p_away


def top_scores(mat: np.ndarray, n: int = 8) -> list[tuple[int, int, float]]:
    """概率最高的 n 个比分 [(h, a, p), ...]。"""
    flat = [
        (int(h), int(a), float(mat[h, a])) for h in range(mat.shape[0]) for a in range(mat.shape[1])
    ]
    flat.sort(key=lambda t: -t[2])
    return flat[:n]


def draw_prob_vector(mat: np.ndarray) -> np.ndarray:
    """各平局比分 (0-0, 1-1, ...) 的概率向量（淘汰赛加时入口用）。"""
    return np.diagonal(mat).copy()


def sample_scores(
    mat: np.ndarray, n: int, rng: np.random.Generator
) -> tuple[np.ndarray, np.ndarray]:
    """从比分矩阵抽 n 个比分，返回 (home_goals, away_goals) 两个 int 数组。"""
    size = mat.shape[0]
    flat = mat.ravel()
    idx = rng.choice(flat.size, size=n, p=flat / flat.sum())
    return idx // size, idx % size
