"""跨赛事回测 + 留一届交叉验证（LOTO）：诚实评估模型并选时间衰减 H 与融合权重。

相比旧版只用 2018/2022 两届世界杯（128 场、且在同一集上既选参又评估 → 数据泄漏乐观偏置）：
- **扩样本**：纳入 2014 年以来各大洲决赛圈（世界杯/欧洲杯/美洲杯/非洲杯/亚洲杯），上千场。
- **修泄漏**：用 leave-one-tournament-out 嵌套 CV——每折的 (H, 权重) 只在其余赛事上选，
  在留出赛事上做**样本外**评估，报告无偏 RPS。生产用 (H,权重) 仍在全量上选（refit-on-all），
  但headline 性能用 LOTO 的样本外估计，并报告各折选择的稳定性。
- 每个赛事的 cutoff（开幕前一天）与窗口自数据自动推导，无需硬编码日期。

融合权重用概率级混合精确评估（outcome_probs 对比分矩阵线性 → 矩阵混合=概率混合）。
"""

from __future__ import annotations

from collections import Counter

import numpy as np
import pandas as pd

from ..models import dc_attack, dc_elo
from ..models.poisson import outcome_probs, score_matrix
from ..ratings.elo import replay
from . import baselines, metrics

# 纳入回测的洲际/世界决赛圈（martj42 tournament 字段值）
TRACKED_TOURNAMENTS = [
    "FIFA World Cup",
    "UEFA Euro",
    "Copa América",
    "African Cup of Nations",
    "AFC Asian Cup",
]
MIN_EVENT_YEAR = 2014  # 纳入 2014 年以来的决赛圈
MIN_EVENT_MATCHES = 16  # 少于此场次的赛事（如仅开幕的 2026）跳过

# 历史 W/D/L 基础概率（climatology 基准；更强的 Elo/赔率基准见 baselines.py）
BASE_RATE = np.array([0.40, 0.27, 0.33])

DEFAULT_HALF_LIVES = [365.0, 540.0, 730.0, 1095.0]
# 融合权重网格。样本扩大后放宽到 [0.2,0.8]，仍保留两个去相关信号都参与（避免退化为单模型）。
DEFAULT_WEIGHT_GRID = [round(w, 2) for w in np.arange(0.2, 0.81, 0.05)]


# ---------------------------------------------------------------------------
# 赛事枚举与单赛事预测
# ---------------------------------------------------------------------------


def list_events(
    results: pd.DataFrame,
    *,
    tournaments: list[str] = TRACKED_TOURNAMENTS,
    min_year: int = MIN_EVENT_YEAR,
) -> list[dict]:
    """从数据自动枚举回测赛事。results 须为 load_results 输出（仅已完赛行）。

    按"同一赛事内相邻比赛间隔 >60 天"切分届次——而非按日历年，否则跨年举办的赛事
    （如非洲杯 2025 年 12 月至 2026 年 1 月）会被拆成两个残缺事件。届次年份取首场年份。
    """
    events: list[dict] = []
    for t in tournaments:
        sub = results[results["tournament"] == t].sort_values("date")
        if sub.empty:
            continue
        session = (sub["date"].diff() > pd.Timedelta(days=60)).cumsum()
        for _, g in sub.groupby(session):
            if len(g) < MIN_EVENT_MATCHES:
                continue
            year = int(g["date"].iloc[0].year)
            if year < min_year:
                continue
            events.append(
                {
                    "name": f"{t} {year}",
                    "tournament": t,
                    "year": year,
                    "cutoff": g["date"].min() - pd.Timedelta(days=1),
                    "matches": g,
                }
            )
    events.sort(key=lambda e: e["cutoff"])
    return events


def _elo_probs(
    params: dc_elo.DcEloParams, elo: dict[str, float], actual: pd.DataFrame
) -> np.ndarray:
    rows = []
    for m in actual.itertuples(index=False):
        lh, la = dc_elo.predict_lambdas(
            params, elo.get(m.home_team, 1500.0), elo.get(m.away_team, 1500.0)
        )
        rows.append(outcome_probs(score_matrix(lh, la, params.rho)))
    return np.array(rows)


def _attack_probs(params: dc_attack.DcAttackParams, actual: pd.DataFrame) -> np.ndarray:
    rows = []
    for m in actual.itertuples(index=False):
        lh, la = dc_attack.predict_lambdas(params, m.home_team, m.away_team)
        rows.append(outcome_probs(score_matrix(lh, la, params.rho)))
    return np.array(rows)


def _outcomes(matches: pd.DataFrame) -> np.ndarray:
    return np.array(
        [
            metrics.outcome_of(int(m.home_score), int(m.away_score))
            for m in matches.itertuples(index=False)
        ]
    )


def event_probs(
    results: pd.DataFrame, cutoff, matches: pd.DataFrame, H: float, *, with_gbm: bool = False
):
    """在 cutoff 前拟合模型，预测该赛事比赛 W/D/L。

    返回 (elo_p, att_p, outcomes, elo_baseline_p, gbm_p)。第 5 臂 gbm_p 仅在 with_gbm=True 时
    计算（仅 `wcsim gbm-eval` 只读评估用，需可选依赖 xgboost），生产回测默认 None——保证
    `wcsim backtest`/选参完全不依赖 xgboost、行为不变。
    """
    train = results[results["date"] <= pd.Timestamp(cutoff)]
    ratings, hist = replay(train, with_history=True)
    elo_params = dc_elo.fit(hist, cutoff=cutoff, half_life_days=H)
    # 与生产 fit_bundle 同一套流程：先时序 CV 选岭再拟合
    # （消除旧版 backtest 用默认 0.02、生产用 CV 选的 0.005 的训练/评估口径不一致）
    ridge, _ = dc_attack.select_ridge(train, cutoff=cutoff, half_life_days=H)
    att_params = dc_attack.fit(train, cutoff=cutoff, half_life_days=H, ridge=ridge)
    b, c = baselines.fit(hist, cutoff=cutoff, half_life_days=H)
    gbm_p = None
    if with_gbm:
        from . import gbm  # 惰性：仅 gbm-eval 路径触发，避免顶层引入 xgboost 依赖

        gbm_params = gbm.fit(hist, cutoff=cutoff, half_life_days=H)
        gbm_p = gbm.probs(gbm_params, ratings, matches)
    return (
        _elo_probs(elo_params, ratings, matches),
        _attack_probs(att_params, matches),
        _outcomes(matches),
        baselines.probs(b, c, ratings, matches),
        gbm_p,
    )


def build_cache(
    results: pd.DataFrame, events: list[dict], half_lives: list[float], *, with_gbm: bool = False
) -> dict:
    """预计算每 (赛事, H) 的逐场概率与结果（最贵的一步：events × H 次模型拟合）。"""
    cache: dict[tuple[str, float], tuple] = {}
    for ev in events:
        for H in half_lives:
            cache[(ev["name"], H)] = event_probs(
                results, ev["cutoff"], ev["matches"], H, with_gbm=with_gbm
            )
    return cache


# ---------------------------------------------------------------------------
# 选参（pooled）与 LOTO 交叉验证
# ---------------------------------------------------------------------------


def _ensemble_rps(cache, names, H, w) -> float:
    elo = np.vstack([cache[(n, H)][0] for n in names])
    att = np.vstack([cache[(n, H)][1] for n in names])
    outc = np.concatenate([cache[(n, H)][2] for n in names])
    return metrics.rps(w * elo + (1 - w) * att, outc)


def _best_hw(cache, names, half_lives, weight_grid) -> tuple[float, float, float]:
    best = None
    for H in half_lives:
        for w in weight_grid:
            r = _ensemble_rps(cache, names, H, w)
            if best is None or r < best[2]:
                best = (H, w, r)
    return best


def loto_cv(cache, events, half_lives, weight_grid) -> dict:
    """留一届交叉验证：每折在其余赛事上选 (H,w)，留出赛事上样本外评估。

    若 cache 含第 5 臂 gbm_p（with_gbm=True 构建），额外用**逐折选中的 H** 给 GBM 打分（GBM
    不进融合权重网格，只作去相关的独立基准），并报告 GBM vs 融合 / vs Elo 基准的配对 bootstrap CI。
    """
    names = [e["name"] for e in events]
    per_fold = []
    oos_probs, oos_outc, oos_base, oos_gbm = [], [], [], []
    for test in events:
        others = [n for n in names if n != test["name"]]
        H, w, _ = _best_hw(cache, others, half_lives, weight_grid)
        elo_p, att_p, outc, base_p, gbm_p = cache[(test["name"], H)]
        ens = w * elo_p + (1 - w) * att_p
        fold = {
            "event": test["name"],
            "n": int(len(outc)),
            "selected_H": H,
            "selected_w": round(w, 3),
            "oos_rps": round(metrics.rps(ens, outc), 4),
        }
        if gbm_p is not None:
            fold["gbm_rps"] = round(metrics.rps(gbm_p, outc), 4)
            oos_gbm.append(gbm_p)
        per_fold.append(fold)
        oos_probs.append(ens)
        oos_outc.append(outc)
        oos_base.append(base_p)
    all_probs = np.vstack(oos_probs)
    all_outc = np.concatenate(oos_outc)
    all_base = np.vstack(oos_base)
    sel_H = Counter(f["selected_H"] for f in per_fold)
    sel_w = Counter(f["selected_w"] for f in per_fold)
    clim = np.tile(BASE_RATE, (len(all_outc), 1))
    out = {
        "oos_rps": round(metrics.rps(all_probs, all_outc), 4),
        "oos_logloss": round(metrics.log_loss(all_probs, all_outc), 4),
        "oos_brier": round(metrics.brier_score(all_probs, all_outc), 4),
        "oos_ece": round(metrics.ece(all_probs, all_outc), 4),
        "climatology_rps": round(metrics.rps(clim, all_outc), 4),
        "elo_baseline_rps": round(metrics.rps(all_base, all_outc), 4),
        "elo_baseline_logloss": round(metrics.log_loss(all_base, all_outc), 4),
        "logloss_gain_vs_elo": round(
            metrics.log_loss(all_base, all_outc) - metrics.log_loss(all_probs, all_outc), 4
        ),
        "reliability": metrics.reliability_diagram(all_probs, all_outc),
        "n_folds": len(events),
        "n_matches": int(len(all_outc)),
        "per_fold": per_fold,
        "selected_H_counts": dict(sel_H),
        "selected_w_counts": {str(k): v for k, v in sel_w.items()},
    }
    if oos_gbm:
        all_gbm = np.vstack(oos_gbm)
        out["gbm_rps"] = round(metrics.rps(all_gbm, all_outc), 4)
        out["gbm_logloss"] = round(metrics.log_loss(all_gbm, all_outc), 4)
        # 显著性：GBM 与融合/Elo 基准的逐场 RPS 差的配对 bootstrap 95% 区间（含 0 = 无可测差异）
        out["gbm_vs_fused_ci"] = metrics.paired_bootstrap_rps_diff(all_gbm, all_probs, all_outc)
        out["gbm_vs_elo_ci"] = metrics.paired_bootstrap_rps_diff(all_gbm, all_base, all_outc)
    return out


def select_best(
    results: pd.DataFrame,
    *,
    half_lives: list[float] = DEFAULT_HALF_LIVES,
    weight_grid: list[float] = DEFAULT_WEIGHT_GRID,
    detail_events: tuple[str, ...] = ("FIFA World Cup 2018", "FIFA World Cup 2022"),
) -> dict:
    """全流程：枚举赛事 → 缓存预测 → pooled 选生产 (H,w) → LOTO 报告无偏性能与稳定性。

    返回结构兼容前端：best{...} + years{2018,2022}（保留世界杯两届明细表）+ loto{...}。
    """
    events = list_events(results)
    if not events:
        raise RuntimeError("无可用回测赛事")
    cache = build_cache(results, events, half_lives)
    names = [e["name"] for e in events]

    # 生产 (H,w)：全量 pooled 选优（refit-on-all，标准做法）
    H_star, w_star, pooled_rps = _best_hw(cache, names, half_lives, weight_grid)

    # 诚实性能：LOTO 样本外
    loto = loto_cv(cache, events, half_lives, weight_grid)

    base_all = []
    outc_all = []
    for ev in events:
        outc = cache[(ev["name"], H_star)][2]
        outc_all.append(outc)
        base_all.append(np.tile(BASE_RATE, (len(outc), 1)))
    base_all = np.vstack(base_all)
    outc_all = np.concatenate(outc_all)

    # 前端明细：指定两届世界杯，用生产 (H,w)
    years = {}
    ev_by_name = {e["name"]: e for e in events}
    for dn in detail_events:
        if dn not in ev_by_name:
            continue
        elo_p, att_p, outc, base_p, _gbm = cache[(dn, H_star)]
        ens = w_star * elo_p + (1 - w_star) * att_p
        clim = np.tile(BASE_RATE, (len(outc), 1))
        yr = ev_by_name[dn]["year"]
        years[str(yr)] = {
            "n_matches": int(len(outc)),
            "rps_baseline": round(metrics.rps(clim, outc), 4),
            "rps_elo_baseline": round(metrics.rps(base_p, outc), 4),
            "rps_dc_elo": round(metrics.rps(elo_p, outc), 4),
            "rps_dc_attack": round(metrics.rps(att_p, outc), 4),
            "rps_ensemble": round(metrics.rps(ens, outc), 4),
            "logloss_dc_elo": round(metrics.log_loss(elo_p, outc), 4),
            "calibration": metrics.calibration(ens, outc),
        }

    return {
        "best": {
            "half_life_days": H_star,
            "weight_dc_elo": round(w_star, 3),
            "weight_dc_attack": round(1 - w_star, 3),
            "pooled_rps": round(pooled_rps, 4),
            "oos_rps": loto["oos_rps"],  # 诚实的样本外 headline
            "n_events": len(events),
            "n_matches": loto["n_matches"],
            "rps_baseline": round(metrics.rps(base_all, outc_all), 4),
            "rps_elo_baseline": loto["elo_baseline_rps"],  # 更强的"简单 Elo 模型"基准
        },
        "years": years,
        "loto": loto,
        "events": [{"name": e["name"], "n": int(len(e["matches"]))} for e in events],
    }


# ---------------------------------------------------------------------------
# XGBoost 只读评估（不进生产；需可选依赖 xgboost）
# ---------------------------------------------------------------------------


def gbm_eval(
    results: pd.DataFrame,
    *,
    half_lives: list[float] = DEFAULT_HALF_LIVES,
    weight_grid: list[float] = DEFAULT_WEIGHT_GRID,
) -> dict:
    """只读评估 GBM 第三模型：与生产融合、Elo-logistic 基准同口径并排比 LOTO 样本外 RPS。

    构建带第 5 臂的缓存（with_gbm=True，触发 xgboost），跑 LOTO——GBM 用逐折选中的 H 作独立基准，
    **不进**融合权重网格、**不改** params.json。返回供 CLI 并排打印 + 配对 bootstrap 显著性判定。
    """
    events = list_events(results)
    if not events:
        raise RuntimeError("无可用回测赛事")
    cache = build_cache(results, events, half_lives, with_gbm=True)
    loto = loto_cv(cache, events, half_lives, weight_grid)
    return {
        "n_events": len(events),
        "n_matches": loto["n_matches"],
        "gbm_rps": loto["gbm_rps"],
        "elo_baseline_rps": loto["elo_baseline_rps"],
        "fused_oos_rps": loto["oos_rps"],
        "gbm_logloss": loto["gbm_logloss"],
        "gbm_vs_fused_ci": loto["gbm_vs_fused_ci"],
        "gbm_vs_elo_ci": loto["gbm_vs_elo_ci"],
        "selected_H_counts": loto["selected_H_counts"],
        "per_fold": loto["per_fold"],
    }
