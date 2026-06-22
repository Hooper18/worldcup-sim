"""本届实战表现：用冻结模型重建每场已完赛的"赛前"预测，对真实赛果打分。

关键口径：模型参数（DC β/ρ、攻防 att/def、融合权重）赛前冻结，**只有 Elo 随赛果更新**。
所以一场比赛的真·赛前融合 1X2 = 冻结 bundle + 重放到该场开赛前的 Elo。

实现：一次 `replay(df, with_history=True)` 即给每行带上 `home_elo_pre/away_elo_pre`
（该场开赛前两队的 Elo），按 martj42 队名 + 日期窗口匹配回 results_store 的 match_id，
重建赛前预测 → 对真实赛果算 RPS/Brier/命中率，并和 Elo-logistic 基准、climatology 对比。

输出 web/public/data/performance.json：本届汇总 + 每场明细（供单场复盘）+ 累计走势（供折线图）。
当前只评小组赛（淘汰赛未开打；其参赛队码不在 MATCHES 静态表里，待开赛后另行接入）。
"""

from __future__ import annotations

import datetime as dt

import numpy as np
import pandas as pd

from .. import config
from ..data import fetch, results_store
from ..data.normalize import code_to_martj42
from ..models.bundle import ModelBundle
from ..models.poisson import outcome_probs, top_scores
from ..ratings.elo import replay
from ..tournament.structure import MATCHES, has_host_advantage
from . import baselines, metrics
from .runner import BASE_RATE

_OUTCOME_LABEL = ("home", "draw", "away")


def _now_iso() -> str:
    return dt.datetime.now(dt.UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _find_pre_match_elo(
    wc: pd.DataFrame, home_code: str, away_code: str, kickoff: pd.Timestamp
) -> tuple[float, float] | None:
    """在已重放历史的 2026 WC 行里，按队名 + 日期 ±1 天窗口找该场，返回 (赛前主队 Elo, 赛前客队 Elo)。

    martj42 记当地日期、feed 记 UTC，故用 ±1 天窗口（同 results_store.parse_martj42）。
    按 MATCHES 的主客朝向取 home_elo_pre/away_elo_pre；若 martj42 行主客相反则交换。
    """
    hm, am = code_to_martj42(home_code), code_to_martj42(away_code)
    # 按 kickoff 的"日期"(归一到午夜)±1 天:martj42 记当地日期(午夜),用 UTC 时刻会把
    # 临界场刷掉(如 kickoff 02:00Z 减 1 天 = 前日 02:00,会漏掉前日 00:00 的 martj42 行)
    day = kickoff.normalize()
    lo, hi = day - pd.Timedelta(days=1), day + pd.Timedelta(days=1)
    win = wc[(wc["date"] >= lo) & (wc["date"] <= hi)]
    same = win[(win["home_team"] == hm) & (win["away_team"] == am)]
    if len(same) == 1:
        r = same.iloc[0]
        return float(r["home_elo_pre"]), float(r["away_elo_pre"])
    swap = win[(win["home_team"] == am) & (win["away_team"] == hm)]
    if len(swap) == 1:
        r = swap.iloc[0]
        return float(r["away_elo_pre"]), float(r["home_elo_pre"])  # 交换回 MATCHES 朝向
    return None


def compute_performance(
    df: pd.DataFrame | None = None,
    bundle: ModelBundle | None = None,
    results: dict[int, dict] | None = None,
) -> dict:
    """重建本届赛前预测并打分，返回 performance.json 的内容。"""
    df = df if df is not None else fetch.load_results()
    bundle = bundle or ModelBundle.load(config.PARAMS_PATH)
    results = results if results is not None else results_store.load_store()

    _, hist = replay(df, with_history=True)
    cutoff = bundle.dc_elo.cutoff  # 冻结截止（开幕前）
    hist_cut = hist[hist["date"] <= pd.Timestamp(cutoff)]
    b, c = baselines.fit(hist_cut, cutoff=cutoff, half_life_days=bundle.half_life_days)

    wc = hist[(hist["tournament"] == "FIFA World Cup") & (hist["date"] >= "2026-06-01")]

    per_match: list[dict] = []
    fused_rows: list[list[float]] = []
    elo_rows: list[list[float]] = []
    outcomes: list[int] = []
    n_finished_group = 0
    n_skipped = 0

    for mid in sorted(results):
        m = MATCHES[mid]
        if m["stage"] != "group":
            continue  # 淘汰赛参赛队码不在静态表，开赛后另行接入
        n_finished_group += 1
        home, away = m["home"], m["away"]
        kickoff = pd.Timestamp(m["kickoff_utc"].replace("Z", ""))
        pre = _find_pre_match_elo(wc, home, away, kickoff)
        if pre is None:
            n_skipped += 1  # martj42 尚未落该场 ⇒ 暂无赛前 Elo，跳过
            continue
        elo_h, elo_a = pre

        # 冻结 bundle + 赛前 Elo → 融合 1X2 + 预测比分
        model = bundle.build_model({home: elo_h, away: elo_a})
        host_h = has_host_advantage(home, m["venue"])
        host_a = has_host_advantage(away, m["venue"])
        mat = model.matrix(home, away, host_home=host_h, host_away=host_a)
        ph, pdr, pa = outcome_probs(mat)
        ts_h, ts_a, _ = top_scores(mat, 1)[0]

        res = results[mid]
        actual_h, actual_a = int(res["h"]), int(res["a"])
        oc = metrics.outcome_of(actual_h, actual_a)

        probs = [float(ph), float(pdr), float(pa)]
        elo_p = baselines._probs(b, c, np.array([(elo_h - elo_a) / 400.0]))[0]
        rps_i = metrics.rps(np.array([probs]), np.array([oc]))
        pick = int(np.argmax(probs))

        per_match.append(
            {
                "id": mid,
                "group": m["group"],
                "kickoff_utc": m["kickoff_utc"],
                "home": home,
                "away": away,
                "pred": {
                    "p_home": round(probs[0], 4),
                    "p_draw": round(probs[1], 4),
                    "p_away": round(probs[2], 4),
                    "pick": _OUTCOME_LABEL[pick],
                    "top_score": {"h": int(ts_h), "a": int(ts_a)},
                },
                "actual": {"h": actual_h, "a": actual_a, "outcome": _OUTCOME_LABEL[oc]},
                "rps": round(float(rps_i), 4),
                "hit": bool(pick == oc),
            }
        )
        fused_rows.append(probs)
        elo_rows.append([float(x) for x in elo_p])
        outcomes.append(oc)

    n = len(outcomes)
    out: dict = {
        "generated_at": _now_iso(),
        "cutoff": cutoff,
        "n_scored": n,
        "n_finished_group": n_finished_group,
        "n_skipped": n_skipped,
        "per_match": per_match,
    }
    if n == 0:
        out["fused"] = out["elo_baseline"] = out["climatology"] = None
        out["cumulative"] = []
        return out

    P = np.array(fused_rows)
    E = np.array(elo_rows)
    C = np.tile(BASE_RATE, (n, 1))
    obs = np.array(outcomes)

    def _summary(probs: np.ndarray) -> dict:
        picks = probs.argmax(axis=1)
        return {
            "rps": round(float(metrics.rps(probs, obs)), 4),
            "brier": round(float(metrics.brier_score(probs, obs)), 4),
            "log_loss": round(float(metrics.log_loss(probs, obs)), 4),
            "hit_rate": round(float(np.mean(picks == obs)), 4),
        }

    out["fused"] = _summary(P)
    out["elo_baseline"] = _summary(E)
    out["climatology"] = _summary(C)

    # 累计走势（按场序的运行均值 RPS），供前端折线图
    cumulative = []
    for k in range(1, n + 1):
        cumulative.append(
            {
                "id": per_match[k - 1]["id"],
                "n": k,
                "fused_rps": round(float(metrics.rps(P[:k], obs[:k])), 4),
                "elo_rps": round(float(metrics.rps(E[:k], obs[:k])), 4),
                "clim_rps": round(float(metrics.rps(C[:k], obs[:k])), 4),
            }
        )
    out["cumulative"] = cumulative
    return out


def write_performance(*, bundle: ModelBundle | None = None, results=None, out_dir=None) -> dict:
    """计算并写 performance.json（复用 writer 的 UTF-8/LF/ensure_ascii=False 约定）。"""
    from ..export.writer import _write_json

    out = compute_performance(bundle=bundle, results=results)
    target_dir = out_dir or config.WEB_DATA_DIR
    _write_json(target_dir / "performance.json", out)
    return out
