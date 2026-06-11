"""自算国家队 Elo：对 martj42 全量历史逐场重放（eloratings.net 公式）。

    Rn = Ro + K·G·(W − We)
    We = 1 / (10^(−dr/400) + 1)，dr = 自身 − 对手（真主场 +100，中立不加）
    K  = 60 世界杯决赛圈 | 50 洲际决赛圈 | 40 预选赛/国家联赛 | 30 其他 | 20 友谊赛
    G  = 1（净胜 ≤1）| 1.5（净胜 2）| 1.75 + (N−3)/8（净胜 N ≥3）

用 CC0 的 martj42 数据自算（而非抓 eloratings.net），保证可复现、口径可控；
eloratings TSV 仅作交叉校验。
"""

from __future__ import annotations

import pandas as pd

from .. import config

# 洲际决赛圈（K=50）。martj42 的 tournament 字段实测值。
_CONTINENTAL_FINALS = {
    "Copa América",
    "UEFA Euro",
    "African Cup of Nations",
    "AFC Asian Cup",
    "CONCACAF Gold Cup",
    "CONCACAF Championship",
    "Oceania Nations Cup",
    "Confederations Cup",
    "CONMEBOL–UEFA Cup of Champions",
}


def k_factor(tournament: str) -> float:
    """赛事 → Elo K 值。"""
    if tournament == "FIFA World Cup":
        return config.ELO_K_WORLD_CUP
    if tournament in _CONTINENTAL_FINALS:
        return config.ELO_K_CONTINENTAL
    if "qualification" in tournament or "Nations League" in tournament:
        return config.ELO_K_QUALIFIER
    if tournament == "Friendly":
        return config.ELO_K_FRIENDLY
    return config.ELO_K_OTHER


def goal_multiplier(margin: int) -> float:
    """净胜球放大系数 G。"""
    margin = abs(margin)
    if margin <= 1:
        return 1.0
    if margin == 2:
        return 1.5
    return 1.75 + (margin - 3) / 8.0


def expected_score(rating: float, opp_rating: float) -> float:
    """胜率期望 We（dr 已含主场加成时直接传入差值前的两个评分）。"""
    dr = rating - opp_rating
    return 1.0 / (10.0 ** (-dr / 400.0) + 1.0)


def update_pair(
    home_elo: float,
    away_elo: float,
    home_score: int,
    away_score: int,
    *,
    neutral: bool,
    tournament: str,
) -> tuple[float, float]:
    """单场比赛后的 (home_elo, away_elo)。"""
    k = k_factor(tournament)
    g = goal_multiplier(home_score - away_score)
    home_adv = 0.0 if neutral else config.ELO_HOME_ADV
    we_home = expected_score(home_elo + home_adv, away_elo)
    if home_score > away_score:
        w_home = 1.0
    elif home_score < away_score:
        w_home = 0.0
    else:
        w_home = 0.5
    delta = k * g * (w_home - we_home)
    return home_elo + delta, away_elo - delta


def replay(
    df: pd.DataFrame,
    *,
    through: str | pd.Timestamp | None = None,
    with_history: bool = False,
) -> tuple[dict[str, float], pd.DataFrame | None]:
    """逐场重放，返回 (截止 through 的评分表, 带赛前 Elo 列的明细)。

    df 须为 load_results() 输出（已按日期升序、仅已完赛行）。
    with_history=True 时第二个返回值为 df 副本加 home_elo_pre / away_elo_pre 两列
    （该场开赛前双方评分，供模型拟合做特征）；否则为 None。
    """
    if through is not None:
        df = df[df["date"] <= pd.Timestamp(through)]

    ratings: dict[str, float] = {}
    home_pre: list[float] = []
    away_pre: list[float] = []

    for row in df.itertuples(index=False):
        h = ratings.get(row.home_team, config.ELO_START)
        a = ratings.get(row.away_team, config.ELO_START)
        if with_history:
            home_pre.append(h)
            away_pre.append(a)
        nh, na = update_pair(
            h,
            a,
            int(row.home_score),
            int(row.away_score),
            neutral=bool(row.neutral),
            tournament=row.tournament,
        )
        ratings[row.home_team] = nh
        ratings[row.away_team] = na

    if with_history:
        hist = df.copy()
        hist["home_elo_pre"] = home_pre
        hist["away_elo_pre"] = away_pre
        return ratings, hist
    return ratings, None
