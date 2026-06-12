"""端到端编排：抓数据 → Elo 重放 → 拟合 → 加载赛果 → 模拟 → 导出。

被 CLI 各子命令复用。模型参数（β/ρ/H/融合权重）冻结在赛前拟合值并落 params.json；
Elo 随真实赛果更新（每次 update 都重放到最新完赛）；这样概率演变只反映赛果信息。
"""

from __future__ import annotations

import datetime as dt
import json
from dataclasses import dataclass

import pandas as pd

from . import config
from .data import fetch, results_store
from .data.normalize import code_to_martj42
from .models.dc_elo import DcEloParams, fit
from .ratings.elo import replay
from .tournament.simulate import CODES, SimResult, simulate


@dataclass
class PipelineContext:
    params: DcEloParams
    elo_by_code: dict[str, float]
    tiebreak_key: dict[str, float]
    results: dict[int, dict]
    data_info: dict


def _now_iso() -> str:
    return dt.datetime.now(dt.UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def run_id_from(generated_at: str) -> str:
    # "2026-06-12T08:30:00Z" -> "20260612T0830Z"
    d = dt.datetime.fromisoformat(generated_at.replace("Z", "+00:00"))
    return d.strftime("%Y%m%dT%H%MZ")


def load_params() -> DcEloParams | None:
    if config.PARAMS_PATH.exists():
        return DcEloParams.from_dict(json.loads(config.PARAMS_PATH.read_text(encoding="utf-8")))
    return None


def save_params(params: DcEloParams) -> None:
    config.PARAMS_PATH.parent.mkdir(parents=True, exist_ok=True)
    config.PARAMS_PATH.write_text(
        json.dumps(params.to_dict(), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def fit_params(*, force_fetch: bool = False) -> DcEloParams:
    """拟合 DC-on-Elo 并落 params.json（赛前一次性，之后冻结）。"""
    df = fetch.load_results(force=force_fetch)
    _, hist = replay(df, with_history=True)
    params = fit(hist, cutoff="2026-06-11")
    save_params(params)
    return params


def build_context(*, force_fetch: bool = False, refresh_results: bool = True) -> PipelineContext:
    """准备模拟所需的一切：Elo、参数、真实赛果、数据元信息。"""
    df = fetch.load_results(force=force_fetch)
    ratings, _ = replay(df)
    elo_by_code = {c: ratings[code_to_martj42(c)] for c in CODES}
    tiebreak_key = dict(elo_by_code)

    params = load_params()
    if params is None:
        params = fit_params(force_fetch=False)

    # 真实赛果：feed 优先，解析后并入 store
    results = results_store.load_store()
    if refresh_results:
        try:
            feed = fetch.load_fixture_feed(force=force_fetch)
            parsed = results_store.parse_feed(feed)
            new = results_store.new_finished(results, parsed)
            for mid in new:
                results[mid] = parsed[mid]
            if new:
                results_store.save_store(results)
        except Exception as e:  # 网络/解析失败不阻断模拟，用已有 store
            print(f"[pipeline] 警告：刷新赛果失败（{e}），沿用已存赛果")

    data_info = {
        "martj42_rows": int(len(df)),
        "elo_through": str(df["date"].max().date()),
        "results_count": len(results),
    }
    return PipelineContext(params, elo_by_code, tiebreak_key, results, data_info)


def run_simulation(ctx: PipelineContext, *, n_sims: int, seed: int = 12345) -> SimResult:
    return simulate(
        ctx.params,
        ctx.elo_by_code,
        n_sims=n_sims,
        fixed_results=ctx.results,
        tiebreak_key=ctx.tiebreak_key,
        seed=seed,
    )


def export(ctx: PipelineContext, sim: SimResult, *, backtest: dict | None = None) -> str:
    from .export import writer

    generated_at = _now_iso()
    rid = run_id_from(generated_at)
    writer.export_all(
        run_id=rid,
        generated_at=generated_at,
        params=ctx.params,
        elo=ctx.elo_by_code,
        results=ctx.results,
        sim=sim,
        data_info=ctx.data_info,
        backtest=backtest,
    )
    return rid
