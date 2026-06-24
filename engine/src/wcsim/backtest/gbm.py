"""XGBoost 梯度提升基准（**只读评估，不进生产**）。

为什么只读、不动 params.json（对抗式调研的结论，理由很硬）：
- 目标增益太小且埋在噪声里：融合 LOTO 样本外 RPS 0.189 vs Elo-logistic 基准 0.192，差仅 0.003，
  而逐折 OOS RPS 跨度 0.145–0.229、折间 SD≈0.022——要声称提升，必须 paired-bootstrap CI 排除 0。
- 架构不匹配：生产融合的是**比分矩阵**（喂模拟器/加时/比分展示），GBM 只出 1X2 向量，
  进不了 EnsembleModel，硬接会出两条不一致的融合路径。
- 万行级国家队史上柔性 booster 是过拟合陷阱；xgboost 默认多线程非确定 → 破坏可复现。

故 GBM 定位为「去相关的交叉验证臂」：与 Elo-logistic 基准同口径，只在 `wcsim gbm-eval` 里
并排报告 OOS RPS + 配对 bootstrap 显著性，production 一行不碰。xgboost 为**可选依赖**
（`uv sync --extra ml` 或 `pip install 'wcsim[ml]'`），测试用 `pytest.importorskip` 跳过。
**只用 xgboost 原生 Booster/DMatrix API**（不引入 sklearn），保持可选依赖最小。

接口仿 `baselines.py`：
    fit(hist, *, cutoff, half_life_days, window_years) -> GbmParams
    probs(params, elo, matches) -> (N, 3)  主胜/平/客胜

特征（4 维，与 DC-on-Elo 同源信息但交给提升树自由组合）：
    d_elo      = (home_elo_pre − away_elo_pre)/400
    host       = 1 − neutral（主队是否真主场；预测世界杯统一取 0=中立场，同淘汰赛口径）
    home_level = home_elo_pre/400      两个 Elo 绝对水平：让树能区分"两强相遇"与"两弱相遇"
    away_level = away_elo_pre/400
样本权重 = 0.5^(days/H) · k_factor(tournament)/20（与 DC/Elo/攻防模型完全同口径）。
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from ..ratings.elo import k_factor
from . import metrics

FEATURES = ("d_elo", "host", "home_level", "away_level")

# 浅树 + 强正则（防万行国家队史上过拟合）；nthread=1 + 固定 seed → 可复现（缓解 xgboost 非确定性）。
_XGB_PARAMS = {
    "objective": "multi:softprob",
    "num_class": 3,
    "max_depth": 2,
    "eta": 0.05,
    "subsample": 0.8,
    "colsample_bytree": 0.8,
    "min_child_weight": 5.0,
    "lambda": 2.0,
    "tree_method": "hist",
    "nthread": 1,
    "seed": 0,
}
_NUM_ROUND = 300


@dataclass
class GbmParams:
    booster: object  # xgboost.Booster（惰性类型，避免模块顶层 import xgboost）
    n_matches: int
    half_life_days: float
    cutoff: str


def _features(
    d_elo: np.ndarray, host: np.ndarray, home_level: np.ndarray, away_level: np.ndarray
) -> np.ndarray:
    return np.column_stack([d_elo, host, home_level, away_level]).astype(float)


def fit(
    hist: pd.DataFrame, *, cutoff, half_life_days: float = 730.0, window_years: float = 8.0
) -> GbmParams:
    """在带 home_elo_pre/away_elo_pre 的历史明细上训练多类 softprob 提升树。

    hist 须为 elo.replay(with_history=True) 的输出。只用 cutoff 往前 window_years 年内的比赛。
    """
    import xgboost as xgb  # 惰性导入：可选依赖 'ml'

    cutoff_ts = pd.Timestamp(cutoff)
    lo = cutoff_ts - pd.Timedelta(days=window_years * 365.25)
    df = hist[(hist["date"] > lo) & (hist["date"] <= cutoff_ts)]

    home_elo = df["home_elo_pre"].to_numpy(dtype=float)
    away_elo = df["away_elo_pre"].to_numpy(dtype=float)
    host = (~df["neutral"].to_numpy(dtype=bool)).astype(float)
    x = _features((home_elo - away_elo) / 400.0, host, home_elo / 400.0, away_elo / 400.0)
    y = np.array(
        [
            metrics.outcome_of(int(h), int(a))
            for h, a in zip(df["home_score"], df["away_score"], strict=True)
        ]
    )
    days = (cutoff_ts - df["date"]).dt.days.to_numpy(dtype=float)
    w = 0.5 ** (days / half_life_days) * df["tournament"].map(k_factor).to_numpy(dtype=float) / 20.0

    dtrain = xgb.DMatrix(x, label=y, weight=w, feature_names=list(FEATURES))
    booster = xgb.train(_XGB_PARAMS, dtrain, num_boost_round=_NUM_ROUND)
    return GbmParams(
        booster=booster,
        n_matches=int(len(df)),
        half_life_days=float(half_life_days),
        cutoff=str(cutoff),
    )


def probs(params: GbmParams, elo: dict[str, float], matches: pd.DataFrame) -> np.ndarray:
    """对 matches（含 home_team/away_team）按当前 elo 预测 (N,3)。世界杯统一中立场 host=0。

    multi:softprob 原生输出列序即类索引 [0=主胜, 1=平, 2=客胜]，无需再对齐。
    """
    import xgboost as xgb

    home_elo = np.array(
        [elo.get(m.home_team, 1500.0) for m in matches.itertuples(index=False)], dtype=float
    )
    away_elo = np.array(
        [elo.get(m.away_team, 1500.0) for m in matches.itertuples(index=False)], dtype=float
    )
    host = np.zeros(len(home_elo), dtype=float)
    x = _features((home_elo - away_elo) / 400.0, host, home_elo / 400.0, away_elo / 400.0)
    dpred = xgb.DMatrix(x, feature_names=list(FEATURES))
    return params.booster.predict(dpred)
