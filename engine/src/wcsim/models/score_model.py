"""统一的"对阵 → 比分矩阵"模型接口，供模拟器与导出复用。

DcEloModel / DcAttackModel 各自实现 matrix()；EnsembleModel 按权重融合多个模型的比分矩阵。
模拟器只依赖该接口，不关心底层是 Elo 还是攻防还是融合。
"""

from __future__ import annotations

from typing import Protocol

import numpy as np

from . import dc_attack, dc_elo
from .poisson import score_matrix


class ScoreModel(Protocol):
    def matrix(
        self, home: str, away: str, *, host_home: bool, host_away: bool, factor: float = 1.0
    ) -> np.ndarray:
        """归一化比分矩阵 P[h,a]，factor 用于加时（λ×factor）。"""
        ...

    def lambdas(
        self, home: str, away: str, *, host_home: bool, host_away: bool
    ) -> tuple[float, float]: ...


class DcEloModel:
    id = "dc_elo"
    name_zh = "DC-on-Elo"

    def __init__(self, params: dc_elo.DcEloParams, elo_by_code: dict[str, float]):
        self.params = params
        self.elo = elo_by_code

    def lambdas(self, home, away, *, host_home=False, host_away=False):
        return dc_elo.predict_lambdas(
            self.params, self.elo[home], self.elo[away], host_home=host_home, host_away=host_away
        )

    def matrix(self, home, away, *, host_home=False, host_away=False, factor=1.0):
        lh, la = self.lambdas(home, away, host_home=host_home, host_away=host_away)
        return score_matrix(lh * factor, la * factor, self.params.rho)


class DcAttackModel:
    id = "dc_attack"
    name_zh = "纯攻防 Dixon-Coles"

    def __init__(self, params: dc_attack.DcAttackParams):
        self.params = params

    def lambdas(self, home, away, *, host_home=False, host_away=False):
        return dc_attack.predict_lambdas(
            self.params, home, away, host_home=host_home, host_away=host_away
        )

    def matrix(self, home, away, *, host_home=False, host_away=False, factor=1.0):
        lh, la = self.lambdas(home, away, host_home=host_home, host_away=host_away)
        return score_matrix(lh * factor, la * factor, self.params.rho)


class EnsembleModel:
    id = "ensemble"
    name_zh = "融合"

    def __init__(self, components: list[tuple[ScoreModel, float]]):
        total = sum(w for _, w in components)
        self.components = [(m, w / total) for m, w in components]

    def lambdas(self, home, away, *, host_home=False, host_away=False):
        # 融合 λ = 权重加权（仅用于展示，矩阵融合才是真正口径）
        lh = sum(
            w * m.lambdas(home, away, host_home=host_home, host_away=host_away)[0]
            for m, w in self.components
        )
        la = sum(
            w * m.lambdas(home, away, host_home=host_home, host_away=host_away)[1]
            for m, w in self.components
        )
        return lh, la

    def matrix(self, home, away, *, host_home=False, host_away=False, factor=1.0):
        mat = None
        for m, w in self.components:
            comp = m.matrix(home, away, host_home=host_home, host_away=host_away, factor=factor)
            mat = comp * w if mat is None else mat + comp * w
        return mat / mat.sum()
