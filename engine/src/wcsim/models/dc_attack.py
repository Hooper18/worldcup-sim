"""第二模型：纯攻防 Dixon-Coles（每队独立攻击力/防守力，不依赖 Elo）。

    log λ_home = μ + att[home] − def[away] + h·host_home
    log λ_away = μ + att[away] − def[home] + h·host_away
    P(x,y)     = τ_{λh,λa,ρ}(x,y) · Pois(x;λh) · Pois(y;λa)

提供与 DC-on-Elo 互补的信号：Elo 把球队压成单一数值，攻防模型则分别刻画"进球能力"与
"失球倾向"。对全部国际队联合拟合（含 48 强的所有对手），用岭惩罚正则化稀疏球队的攻防参数
（替代 Σatt=Σdef=0 约束、自然把少赛球队拉向均值）。

拟合分两步（保证速度）：① 攻防/μ/host 用解析梯度的加权 Poisson MLE（L-BFGS-B，可达数百参数）；
② ρ 用一维优化在固定攻防下拟合 DC 低比分修正。
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd
from scipy.optimize import minimize, minimize_scalar

from .. import config
from ..ratings.elo import k_factor

RIDGE = 0.02  # 攻防参数岭惩罚强度


@dataclass
class DcAttackParams:
    mu: float
    home_adv: float
    rho: float
    att: dict[str, float]
    def_: dict[str, float]
    half_life_days: float
    n_matches: int
    cutoff: str
    teams: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "mu": self.mu,
            "home_adv": self.home_adv,
            "rho": self.rho,
            "att": self.att,
            "def_": self.def_,
            "half_life_days": self.half_life_days,
            "n_matches": self.n_matches,
            "cutoff": self.cutoff,
            "teams": self.teams,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "DcAttackParams":
        return cls(**d)


def _weights(df: pd.DataFrame, cutoff: pd.Timestamp, half_life_days: float) -> np.ndarray:
    days = (cutoff - df["date"]).dt.days.to_numpy(dtype=float)
    w_time = 0.5 ** (days / half_life_days)
    w_imp = df["tournament"].map(k_factor).to_numpy(dtype=float) / 20.0
    return w_time * w_imp


def fit(
    results: pd.DataFrame,
    *,
    cutoff: str | pd.Timestamp,
    half_life_days: float = config.TIME_DECAY_HALF_LIFE_DAYS,
    window_years: float = config.FIT_WINDOW_YEARS,
    code_map: dict[str, str] | None = None,
    restrict_teams: list[str] | None = None,
) -> DcAttackParams:
    """对 results（load_results 输出，martj42 队名）拟合攻防模型。

    code_map: martj42 队名 → 输出 key（如队伍代码）；未提供则用 martj42 原名。
    restrict_teams: 若给定，只保留至少一方在该集合内的比赛（聚焦 48 强相关对手，减小规模）。
    """
    cutoff_ts = pd.Timestamp(cutoff)
    lo = cutoff_ts - pd.Timedelta(days=window_years * 365.25)
    df = results[(results["date"] > lo) & (results["date"] <= cutoff_ts)].copy()

    if code_map is not None:
        df["home_key"] = df["home_team"].map(code_map)
        df["away_key"] = df["away_team"].map(code_map)
    else:
        df["home_key"] = df["home_team"]
        df["away_key"] = df["away_team"]

    if restrict_teams is not None:
        keep = set(restrict_teams)
        df = df[df["home_key"].isin(keep) | df["away_key"].isin(keep)]

    df = df.dropna(subset=["home_key", "away_key"])

    teams = sorted(set(df["home_key"]) | set(df["away_key"]))
    idx = {t: i for i, t in enumerate(teams)}
    T = len(teams)

    h = df["home_key"].map(idx).to_numpy()
    a = df["away_key"].map(idx).to_numpy()
    yh = df["home_score"].to_numpy(dtype=float)
    ya = df["away_score"].to_numpy(dtype=float)
    host_h = (~df["neutral"].to_numpy(dtype=bool)).astype(float)
    host_a = np.zeros_like(host_h)  # 客队从不享主场
    w = _weights(df, cutoff_ts, half_life_days)

    # 参数布局：[mu, home_adv, att(T), def(T)]
    def unpack(theta):
        mu, home_adv = theta[0], theta[1]
        att = theta[2 : 2 + T]
        dff = theta[2 + T :]
        return mu, home_adv, att, dff

    def nll_grad(theta):
        mu, home_adv, att, dff = unpack(theta)
        eta_h = mu + att[h] - dff[a] + home_adv * host_h
        eta_a = mu + att[a] - dff[h] + home_adv * host_a
        lam_h = np.exp(eta_h)
        lam_a = np.exp(eta_a)
        nll = np.sum(w * (lam_h - yh * eta_h)) + np.sum(w * (lam_a - ya * eta_a))
        nll += 0.5 * RIDGE * (np.sum(att**2) + np.sum(dff**2))

        r_h = w * (lam_h - yh)
        r_a = w * (lam_a - ya)
        g_mu = np.sum(r_h) + np.sum(r_a)
        g_home = np.sum(r_h * host_h) + np.sum(r_a * host_a)
        g_att = np.zeros(T)
        g_def = np.zeros(T)
        np.add.at(g_att, h, r_h)  # att[home] in eta_h
        np.add.at(g_att, a, r_a)  # att[away] in eta_a
        np.add.at(g_def, a, -r_h)  # -def[away] in eta_h
        np.add.at(g_def, h, -r_a)  # -def[home] in eta_a
        g_att += RIDGE * att
        g_def += RIDGE * dff
        grad = np.concatenate([[g_mu, g_home], g_att, g_def])
        return nll, grad

    x0 = np.zeros(2 + 2 * T)
    x0[0] = np.log(max(yh.mean(), 0.5))  # mu 初值 ≈ log 平均进球
    res = minimize(nll_grad, x0, jac=True, method="L-BFGS-B")
    if not res.success and res.status != 1:  # status 1 = 迭代上限，通常已足够收敛
        raise RuntimeError(f"DC-attack 攻防拟合失败: {res.message}")
    mu, home_adv, att, dff = unpack(res.x)

    # 第二步：固定攻防，一维拟合 ρ（DC 低比分修正）
    rho = _fit_rho(h, a, yh, ya, host_h, host_a, w, mu, home_adv, att, dff)

    att_map = {t: float(att[idx[t]]) for t in teams}
    def_map = {t: float(dff[idx[t]]) for t in teams}
    return DcAttackParams(
        mu=float(mu),
        home_adv=float(home_adv),
        rho=float(rho),
        att=att_map,
        def_=def_map,
        half_life_days=float(half_life_days),
        n_matches=int(len(df)),
        cutoff=str(cutoff_ts.date()),
        teams=teams,
    )


def _fit_rho(h, a, yh, ya, host_h, host_a, w, mu, home_adv, att, dff) -> float:
    lam_h = np.exp(mu + att[h] - dff[a] + home_adv * host_h)
    lam_a = np.exp(mu + att[a] - dff[h] + home_adv * host_a)

    def tau_log(rho):
        tau = np.ones_like(lam_h)
        m00 = (yh == 0) & (ya == 0)
        m10 = (yh == 1) & (ya == 0)
        m01 = (yh == 0) & (ya == 1)
        m11 = (yh == 1) & (ya == 1)
        tau = np.where(m00, 1.0 - lam_h * lam_a * rho, tau)
        tau = np.where(m10, 1.0 + lam_a * rho, tau)
        tau = np.where(m01, 1.0 + lam_h * rho, tau)
        tau = np.where(m11, 1.0 - rho, tau)
        return np.log(np.clip(tau, 1e-10, None))

    def nll(rho):
        return -float(np.sum(w * tau_log(rho)))

    res = minimize_scalar(nll, bounds=(-0.2, 0.2), method="bounded")
    return float(res.x)


def predict_lambdas(
    params: DcAttackParams,
    home: str,
    away: str,
    *,
    host_home: bool = False,
    host_away: bool = False,
) -> tuple[float, float]:
    """单场预期进球。未在训练集出现的队攻防取 0（均值）。"""
    ah = params.att.get(home, 0.0)
    aa = params.att.get(away, 0.0)
    dh = params.def_.get(home, 0.0)
    da = params.def_.get(away, 0.0)
    lam_h = float(np.exp(params.mu + ah - da + params.home_adv * host_home))
    lam_a = float(np.exp(params.mu + aa - dh + params.home_adv * host_away))
    return lam_h, lam_a
