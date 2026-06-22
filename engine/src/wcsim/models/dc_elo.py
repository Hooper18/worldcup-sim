"""主模型 DC-on-Elo：以 Elo 差为协变量的 Dixon-Coles Poisson 回归。

    log λ_home = β0 + β1·(R_home − R_away)/400 + γ·host_home
    log λ_away = β0 + β1·(R_away − R_home)/400 + γ·host_away
    P(x, y)    = τ_{λh,λa,ρ}(x, y) · Pois(x; λh) · Pois(y; λa)

仅 4 个参数 (β0, β1, γ, ρ)，把全部国家队的信息池化到 Elo 上——国家队每年比赛少，
逐队 att/def 参数有效样本不足，Elo 协变量是更稳健的选择（Gilch 路线）。

拟合用加权极大似然：
    w = (1/2)^(距今天数 / H) × K_elo(赛事) / 20
时间衰减半衰期 H 默认 730 天（回测网格选优），赛事权重把友谊赛降权到 1、世界杯升到 3。
"""

from __future__ import annotations

from dataclasses import asdict, dataclass

import numpy as np
import pandas as pd
from scipy.optimize import minimize

from .. import config
from ..ratings.elo import k_factor


@dataclass(frozen=True)
class DcEloParams:
    beta0: float
    beta1: float
    gamma: float  # 真主场对 log λ 的加成
    rho: float  # DC 低比分修正
    half_life_days: float
    n_matches: int
    cutoff: str  # 训练数据截止日期（ISO）

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> DcEloParams:
        return cls(**d)


def _lambdas(
    theta: np.ndarray, x_elo: np.ndarray, home_ind: np.ndarray
) -> tuple[np.ndarray, np.ndarray]:
    beta0, beta1, gamma = theta[0], theta[1], theta[2]
    lam_h = np.exp(beta0 + beta1 * x_elo + gamma * home_ind)
    lam_a = np.exp(beta0 - beta1 * x_elo)
    return lam_h, lam_a


def _tau_log(
    hs: np.ndarray, as_: np.ndarray, lam_h: np.ndarray, lam_a: np.ndarray, rho: float
) -> np.ndarray:
    """log τ，向量化（只有四个低比分格非 0）。"""
    tau = np.ones_like(lam_h)
    m00 = (hs == 0) & (as_ == 0)
    m10 = (hs == 1) & (as_ == 0)
    m01 = (hs == 0) & (as_ == 1)
    m11 = (hs == 1) & (as_ == 1)
    tau = np.where(m00, 1.0 - lam_h * lam_a * rho, tau)
    tau = np.where(m10, 1.0 + lam_a * rho, tau)
    tau = np.where(m01, 1.0 + lam_h * rho, tau)
    tau = np.where(m11, 1.0 - rho, tau)
    return np.log(np.clip(tau, 1e-10, None))


def fit(
    hist: pd.DataFrame,
    *,
    cutoff: str | pd.Timestamp,
    half_life_days: float = config.TIME_DECAY_HALF_LIFE_DAYS,
    window_years: float = config.FIT_WINDOW_YEARS,
) -> DcEloParams:
    """对带 home_elo_pre/away_elo_pre 列的历史明细做加权 MLE。

    hist 须为 elo.replay(with_history=True) 的输出（全部已完赛国际 A 级赛）。
    只用 cutoff 往前 window_years 年内的比赛。
    """
    cutoff_ts = pd.Timestamp(cutoff)
    lo = cutoff_ts - pd.Timedelta(days=window_years * 365.25)
    df = hist[(hist["date"] > lo) & (hist["date"] <= cutoff_ts)]

    hs = df["home_score"].to_numpy(dtype=float)
    as_ = df["away_score"].to_numpy(dtype=float)
    x_elo = (df["home_elo_pre"].to_numpy() - df["away_elo_pre"].to_numpy()) / 400.0
    home_ind = (~df["neutral"].to_numpy(dtype=bool)).astype(float)

    days_ago = (cutoff_ts - df["date"]).dt.days.to_numpy(dtype=float)
    w_time = 0.5 ** (days_ago / half_life_days)
    w_imp = df["tournament"].map(k_factor).to_numpy(dtype=float) / 20.0
    w = w_time * w_imp

    def nll(theta: np.ndarray) -> float:
        lam_h, lam_a = _lambdas(theta, x_elo, home_ind)
        rho = theta[3]
        ll = (
            _tau_log(hs, as_, lam_h, lam_a, rho)
            + hs * np.log(lam_h)
            - lam_h
            + as_ * np.log(lam_a)
            - lam_a
        )
        return -float(np.sum(w * ll))

    x0 = np.array([np.log(1.3), 1.0, 0.25, 0.0])
    bounds = [(-2.0, 2.0), (0.0, 5.0), (0.0, 1.0), (-0.2, 0.2)]
    res = minimize(nll, x0, method="L-BFGS-B", bounds=bounds)
    if not res.success:
        raise RuntimeError(f"DC-on-Elo 拟合未收敛: {res.message}")

    beta0, beta1, gamma, rho = (float(v) for v in res.x)
    return DcEloParams(
        beta0=beta0,
        beta1=beta1,
        gamma=gamma,
        rho=rho,
        half_life_days=float(half_life_days),
        n_matches=int(len(df)),
        cutoff=str(cutoff_ts.date()),
    )


def predict_lambdas(
    params: DcEloParams,
    elo_home: float,
    elo_away: float,
    *,
    host_home: bool = False,
    host_away: bool = False,
) -> tuple[float, float]:
    """单场预期进球 (λ_home, λ_away)。host_* 表示该侧享有真主场加成。"""
    x = (elo_home - elo_away) / 400.0
    lam_h = float(np.exp(params.beta0 + params.beta1 * x + params.gamma * host_home))
    lam_a = float(np.exp(params.beta0 - params.beta1 * x + params.gamma * host_away))
    return lam_h, lam_a
