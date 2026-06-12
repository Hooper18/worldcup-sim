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
from .models import dc_attack, dc_elo
from .models.bundle import ModelBundle
from .models.dc_attack import DcAttackParams
from .models.score_model import EnsembleModel
from .ratings.elo import replay
from .tournament.simulate import CODES, SimResult, simulate


@dataclass
class PipelineContext:
    bundle: ModelBundle
    model: EnsembleModel
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


CUTOFF = "2026-06-11"  # 赛前拟合截止（开幕日），之后模型参数冻结


def load_bundle() -> ModelBundle | None:
    if config.PARAMS_PATH.exists():
        return ModelBundle.load(config.PARAMS_PATH)
    return None


def _attack_params_by_code(att_params: DcAttackParams) -> DcAttackParams:
    """把按 martj42 队名键的攻防参数重映射为按 48 队代码键（模拟只查 48 队）。"""
    att_code, def_code = {}, {}
    for c in CODES:
        name = code_to_martj42(c)
        att_code[c] = att_params.att.get(name, 0.0)
        def_code[c] = att_params.def_.get(name, 0.0)
    return DcAttackParams(
        mu=att_params.mu,
        home_adv=att_params.home_adv,
        rho=att_params.rho,
        att=att_code,
        def_=def_code,
        half_life_days=att_params.half_life_days,
        n_matches=att_params.n_matches,
        cutoff=att_params.cutoff,
        teams=CODES,
    )


def fit_bundle(
    *, force_fetch: bool = False, half_life_days: float | None = None,
    weight_dc_elo: float = 0.5, backtest: dict | None = None,
) -> ModelBundle:
    """拟合两个模型并落 params.json（赛前一次性，之后冻结）。

    weight_dc_elo / half_life_days / backtest 通常由 `wcsim backtest` 选优后传入；
    缺省用 H=730、权重 0.5/0.5。
    """
    df = fetch.load_results(force=force_fetch)
    H = half_life_days or config.TIME_DECAY_HALF_LIFE_DAYS
    _, hist = replay(df, with_history=True)
    elo_params = dc_elo.fit(hist, cutoff=CUTOFF, half_life_days=H)
    att_params = dc_attack.fit(df, cutoff=CUTOFF, half_life_days=H)
    bundle = ModelBundle(
        dc_elo=elo_params,
        dc_attack=_attack_params_by_code(att_params),
        weight_dc_elo=weight_dc_elo,
        half_life_days=H,
        backtest=backtest or {},
    )
    bundle.save(config.PARAMS_PATH)
    return bundle


def build_context(*, force_fetch: bool = False, refresh_results: bool = True) -> PipelineContext:
    """准备模拟所需的一切：Elo、参数、真实赛果、数据元信息。"""
    df = fetch.load_results(force=force_fetch)
    ratings, _ = replay(df)
    elo_by_code = {c: ratings[code_to_martj42(c)] for c in CODES}
    tiebreak_key = dict(elo_by_code)

    bundle = load_bundle()
    if bundle is None:
        bundle = fit_bundle(force_fetch=False)
    model = bundle.build_model(elo_by_code)

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
    return PipelineContext(bundle, model, elo_by_code, tiebreak_key, results, data_info)


def run_simulation(ctx: PipelineContext, *, n_sims: int, seed: int = 12345) -> SimResult:
    return simulate(
        ctx.model,
        ctx.elo_by_code,
        n_sims=n_sims,
        fixed_results=ctx.results,
        tiebreak_key=ctx.tiebreak_key,
        seed=seed,
    )


def export(ctx: PipelineContext, sim: SimResult) -> str:
    from .export import writer

    generated_at = _now_iso()
    rid = run_id_from(generated_at)
    writer.export_all(
        run_id=rid,
        generated_at=generated_at,
        bundle=ctx.bundle,
        elo=ctx.elo_by_code,
        results=ctx.results,
        sim=sim,
        data_info=ctx.data_info,
    )
    return rid
