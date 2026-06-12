"""博彩赔率 → 公平概率：去除 overround（庄家抽水），多家共识。

赔率隐含概率之和 >1（overround = 庄家利润空间）。去 overround 得到"公平"概率有几种方法：
- proportional：直接归一化（最简单，但高估热门）
- power：找指数 k 使 Σ(1/o_i)^k = 1（更贴近真实概率）
- shin：Shin (1992) 模型，显式建模内幕交易比例 z（业界与学界常用，对热门/冷门更平衡）

注：本项目**默认不接入实时赔率**——免费稳定的国家队大赛历史 1X2 赔率源不存在（公开数据集多为
俱乐部联赛）。本模块是"市场信号"的现成机械与插桩：若提供一份 {date,home,away,o_home,o_draw,o_away}
的 CSV（config.CACHE_DIR/odds.csv），即可去 overround → 共识概率，用作基准或融合成分。
"""

from __future__ import annotations

import numpy as np
from scipy.optimize import brentq


def implied(odds: np.ndarray) -> np.ndarray:
    """十进制赔率 → 原始隐含概率 1/o（未归一，和 >1）。"""
    return 1.0 / np.asarray(odds, dtype=float)


def deoverround_proportional(odds: np.ndarray) -> np.ndarray:
    p = implied(odds)
    return p / p.sum()


def deoverround_power(odds: np.ndarray) -> np.ndarray:
    """幂方法：求 k 使 Σ(1/o_i)^k = 1。"""
    r = implied(odds)
    f = lambda k: np.sum(r**k) - 1.0  # noqa: E731
    k = brentq(f, 0.5, 5.0)
    p = r**k
    return p / p.sum()


def deoverround_shin(odds: np.ndarray) -> np.ndarray:
    """Shin (1992) 方法：建模内幕交易比例 z，对热门/冷门更平衡。"""
    r = implied(odds)
    s = r.sum()
    pi = r / s  # 归一化基

    def p_of_z(z):
        return (np.sqrt(z * z + 4 * (1 - z) * pi * pi * s) - z) / (2 * (1 - z))

    f = lambda z: p_of_z(z).sum() - 1.0  # noqa: E731
    try:
        z = brentq(f, 1e-6, 0.2)
    except ValueError:
        return deoverround_proportional(odds)
    p = p_of_z(z)
    return p / p.sum()


def fair_probs(odds: np.ndarray, method: str = "shin") -> np.ndarray:
    return {
        "proportional": deoverround_proportional,
        "power": deoverround_power,
        "shin": deoverround_shin,
    }[method](odds)


def consensus(prob_vectors: list[np.ndarray]) -> np.ndarray:
    """多家庄家的公平概率 → 共识：在 logit 尺度按结果平均后归一（Zeileis/Leitner 做法）。"""
    arr = np.asarray(prob_vectors, dtype=float)  # (n_books, k)
    arr = np.clip(arr, 1e-9, 1 - 1e-9)
    logit = np.log(arr / (1 - arr))
    avg = logit.mean(axis=0)
    p = 1.0 / (1.0 + np.exp(-avg))
    return p / p.sum()
