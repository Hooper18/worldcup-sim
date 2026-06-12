"""2018/2022 世界杯截断回测：验证模型并选最优时间衰减 H 与融合权重。

对每届：数据截断到开幕前一天 → 拟合两个模型 → 对该届实际比赛预测 W/D/L → 算 RPS/log-loss/
校准，与基准（历史基础概率）对比。融合权重用概率级混合精确评估（因 outcome_probs 对比分矩阵
线性，矩阵混合与概率混合等价）。
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from ..models import dc_attack, dc_elo
from ..models.poisson import outcome_probs, score_matrix
from ..ratings.elo import replay
from . import metrics

# (cutoff, 开幕, 闭幕)
WC_WINDOWS: dict[int, tuple[str, str, str]] = {
    2018: ("2018-06-13", "2018-06-14", "2018-07-15"),
    2022: ("2022-11-19", "2022-11-20", "2022-12-18"),
}

# 历史世界杯 W/D/L 基础概率（climatology 基准）
BASE_RATE = np.array([0.40, 0.27, 0.33])

DEFAULT_HALF_LIVES = [365.0, 540.0, 730.0, 1095.0]
# 融合权重约束在 [0.3, 0.7]：刻意保留两个去相关信号都参与。
# 无约束回测在 128 场样本上常偏向单一模型（极端 0/1），但样本太薄不足以据此丢掉一个模型；
# 集成在样本外更稳健，故限定为真正的混合区间。
DEFAULT_WEIGHT_GRID = [round(w, 2) for w in np.arange(0.3, 0.71, 0.05)]


def _actual_matches(results: pd.DataFrame, year: int) -> pd.DataFrame:
    _, open_, end = WC_WINDOWS[year]
    wc = results[
        (results["tournament"] == "FIFA World Cup")
        & (results["date"] >= open_)
        & (results["date"] <= end)
    ]
    return wc


def _elo_probs(params: dc_elo.DcEloParams, elo: dict[str, float], actual: pd.DataFrame) -> np.ndarray:
    rows = []
    for m in actual.itertuples(index=False):
        eh = elo.get(m.home_team, 1500.0)
        ea = elo.get(m.away_team, 1500.0)
        lh, la = dc_elo.predict_lambdas(params, eh, ea)
        rows.append(outcome_probs(score_matrix(lh, la, params.rho)))
    return np.array(rows)


def _attack_probs(params: dc_attack.DcAttackParams, actual: pd.DataFrame) -> np.ndarray:
    rows = []
    for m in actual.itertuples(index=False):
        lh, la = dc_attack.predict_lambdas(params, m.home_team, m.away_team)
        rows.append(outcome_probs(score_matrix(lh, la, params.rho)))
    return np.array(rows)


def backtest_year(
    results: pd.DataFrame,
    year: int,
    *,
    half_lives: list[float] = DEFAULT_HALF_LIVES,
    weight_grid: list[float] = DEFAULT_WEIGHT_GRID,
) -> dict:
    cutoff, _, _ = WC_WINDOWS[year]
    train = results[results["date"] <= cutoff]
    ratings, hist = replay(train, with_history=True)
    actual = _actual_matches(results, year)
    outcomes = np.array(
        [metrics.outcome_of(int(m.home_score), int(m.away_score)) for m in actual.itertuples(index=False)]
    )

    per_h = {}
    for H in half_lives:
        elo_params = dc_elo.fit(hist, cutoff=cutoff, half_life_days=H)
        att_params = dc_attack.fit(train, cutoff=cutoff, half_life_days=H)
        elo_p = _elo_probs(elo_params, ratings, actual)
        att_p = _attack_probs(att_params, actual)
        # 融合权重扫描（dc_elo 权重 w，dc_attack 权重 1−w）
        weight_scan = {}
        for w in weight_grid:
            ens_p = w * elo_p + (1 - w) * att_p
            weight_scan[w] = metrics.rps(ens_p, outcomes)
        best_w = min(weight_scan, key=weight_scan.get)
        per_h[H] = {
            "rps_dc_elo": metrics.rps(elo_p, outcomes),
            "rps_dc_attack": metrics.rps(att_p, outcomes),
            "rps_ensemble_best": weight_scan[best_w],
            "best_weight_dc_elo": best_w,
            "weight_scan": weight_scan,
            "logloss_dc_elo": metrics.log_loss(elo_p, outcomes),
            "logloss_dc_attack": metrics.log_loss(att_p, outcomes),
            "_elo_p": elo_p,
            "_att_p": att_p,
        }

    base_p = np.tile(BASE_RATE, (len(outcomes), 1))
    return {
        "year": year,
        "n_matches": int(len(actual)),
        "rps_baseline": metrics.rps(base_p, outcomes),
        "logloss_baseline": metrics.log_loss(base_p, outcomes),
        "per_half_life": per_h,
        "_outcomes": outcomes,
    }


def select_best(
    results: pd.DataFrame,
    *,
    years: list[int] = (2018, 2022),
    half_lives: list[float] = DEFAULT_HALF_LIVES,
    weight_grid: list[float] = DEFAULT_WEIGHT_GRID,
) -> dict:
    """跨年选最优 (H, 融合权重)：合并各年实际比赛后最小化总 RPS。"""
    years = list(years)
    year_results = {y: backtest_year(results, y, half_lives=half_lives, weight_grid=weight_grid) for y in years}

    best = None
    for H in half_lives:
        # 合并各年的逐场概率与结果
        elo_p = np.vstack([year_results[y]["per_half_life"][H]["_elo_p"] for y in years])
        att_p = np.vstack([year_results[y]["per_half_life"][H]["_att_p"] for y in years])
        outc = np.concatenate([year_results[y]["_outcomes"] for y in years])
        for w in weight_grid:
            ens_p = w * elo_p + (1 - w) * att_p
            score = metrics.rps(ens_p, outc)
            if best is None or score < best["rps"]:
                best = {"half_life_days": H, "weight_dc_elo": w, "rps": score}

    # 整理对外摘要（去掉内部大数组）
    summary = {}
    for y in years:
        yr = year_results[y]
        H = best["half_life_days"]
        ph = yr["per_half_life"][H]
        summary[str(y)] = {
            "n_matches": yr["n_matches"],
            "rps_baseline": round(yr["rps_baseline"], 4),
            "rps_dc_elo": round(ph["rps_dc_elo"], 4),
            "rps_dc_attack": round(ph["rps_dc_attack"], 4),
            "rps_ensemble": round(
                metrics.rps(
                    best["weight_dc_elo"] * ph["_elo_p"] + (1 - best["weight_dc_elo"]) * ph["_att_p"],
                    yr["_outcomes"],
                ),
                4,
            ),
            "logloss_dc_elo": round(ph["logloss_dc_elo"], 4),
            "calibration": metrics.calibration(
                best["weight_dc_elo"] * ph["_elo_p"] + (1 - best["weight_dc_elo"]) * ph["_att_p"],
                yr["_outcomes"],
            ),
        }

    return {
        "best": {
            "half_life_days": best["half_life_days"],
            "weight_dc_elo": round(best["weight_dc_elo"], 3),
            "weight_dc_attack": round(1 - best["weight_dc_elo"], 3),
            "combined_rps": round(best["rps"], 4),
        },
        "years": summary,
    }
