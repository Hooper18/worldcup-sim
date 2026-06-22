"""端到端编排：抓数据 → Elo 重放 → 拟合 → 加载赛果 → 模拟 → 导出。

被 CLI 各子命令复用。模型参数（β/ρ/H/融合权重）冻结在赛前拟合值并落 params.json；
Elo 随真实赛果更新（每次 update 都重放到最新完赛）；这样概率演变只反映赛果信息。
"""

from __future__ import annotations

import datetime as dt
import json
from dataclasses import dataclass

from . import config
from .data import fetch, results_store
from .data.normalize import code_to_martj42
from .models import dc_attack, dc_elo
from .models.bundle import ModelBundle
from .models.dc_attack import DcAttackParams
from .models.score_model import DcAttackModel, DcEloModel, EnsembleModel
from .ratings import penalty
from .ratings.elo import replay
from .tournament.simulate import CODES, SimResult, simulate


@dataclass
class PipelineContext:
    bundle: ModelBundle
    model: EnsembleModel
    elo_by_code: dict[str, float]
    tiebreak_key: dict[str, float]
    penalty_theta: dict[str, float]
    results: dict[int, dict]
    data_info: dict
    refresh_failed: bool = False  # feed 刷新是否失败（供 update 告警，非静默）
    refresh_error: str | None = None


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
    *,
    force_fetch: bool = False,
    half_life_days: float | None = None,
    weight_dc_elo: float = 0.5,
    backtest: dict | None = None,
) -> ModelBundle:
    """拟合两个模型并落 params.json（赛前一次性，之后冻结）。

    weight_dc_elo / half_life_days / backtest 通常由 `wcsim backtest` 选优后传入；
    缺省用 H=730、权重 0.5/0.5。
    """
    df = fetch.load_results(force=force_fetch)
    H = half_life_days or config.TIME_DECAY_HALF_LIFE_DAYS
    _, hist = replay(df, with_history=True)
    elo_params = dc_elo.fit(hist, cutoff=CUTOFF, half_life_days=H)
    # 岭强度由时序留出 CV 数据驱动选定（而非硬编码常数）
    ridge, ridge_scan = dc_attack.select_ridge(df, cutoff=CUTOFF, half_life_days=H)
    att_params = dc_attack.fit(df, cutoff=CUTOFF, half_life_days=H, ridge=ridge)
    diagnostics = {
        "selected_ridge": ridge,
        "ridge_scan": {str(k): round(v, 4) for k, v in ridge_scan.items()},
        "empirical_home_advantage": dc_attack.empirical_home_advantage(df, since="2016-01-01"),
    }
    bundle = ModelBundle(
        dc_elo=elo_params,
        dc_attack=_attack_params_by_code(att_params),
        weight_dc_elo=weight_dc_elo,
        half_life_days=H,
        backtest=backtest or {},
        diagnostics=diagnostics,
    )
    bundle.save(config.PARAMS_PATH)
    return bundle


def build_context(*, force_fetch: bool = False, refresh_results: bool = True) -> PipelineContext:
    """准备模拟所需的一切：Elo、参数、真实赛果、数据元信息。"""
    df = fetch.load_results(force=force_fetch)
    ratings, _ = replay(df)
    elo_by_code = {c: ratings[code_to_martj42(c)] for c in CODES}
    tiebreak_key = dict(elo_by_code)

    # 点球能力（Bradley-Terry，随历史更新，非冻结模型参数）
    shootouts = fetch.load_shootouts(force=force_fetch)
    pen_by_name = penalty.fit_penalty_ratings(shootouts)
    penalty_theta = {c: pen_by_name.get(code_to_martj42(c), 0.0) for c in CODES}

    bundle = load_bundle()
    if bundle is None:
        bundle = fit_bundle(force_fetch=False)
    model = bundle.build_model(elo_by_code)

    # 真实赛果：feed 优先，解析后并入 store
    results = results_store.load_store()
    refresh_failed = False
    refresh_error: str | None = None
    if refresh_results:
        try:
            feed = fetch.load_fixture_feed(force=force_fetch)
            parsed = results_store.parse_feed(feed)
            new = results_store.new_finished(results, parsed)
            for mid in new:
                results[mid] = parsed[mid]
            if new:
                results_store.save_store(results)
        except (
            Exception
        ) as e:  # 失败不阻断模拟（用已有 store），但记录状态供 update 告警，不再静默吞掉
            refresh_failed = True
            refresh_error = str(e)
            print(f"[pipeline] 警告：刷新赛果失败（{e}），沿用已存赛果")

    data_info = {
        "martj42_rows": int(len(df)),
        "elo_through": str(df["date"].max().date()),
        "results_count": len(results),
        "feed_ok": not refresh_failed,
    }
    return PipelineContext(
        bundle,
        model,
        elo_by_code,
        tiebreak_key,
        penalty_theta,
        results,
        data_info,
        refresh_failed=refresh_failed,
        refresh_error=refresh_error,
    )


def run_simulation(ctx: PipelineContext, *, n_sims: int, seed: int = 12345) -> SimResult:
    return simulate(
        ctx.model,
        ctx.elo_by_code,
        n_sims=n_sims,
        fixed_results=ctx.results,
        tiebreak_key=ctx.tiebreak_key,
        penalty_theta=ctx.penalty_theta,
        seed=seed,
    )


def bootstrap_uncertainty(
    *, n_boot: int = 40, n_sims: int = 5000, force_fetch: bool = False, seed: int = 0
) -> dict:
    """参数不确定性：case-resampling bootstrap 重抽训练史、重拟 DC 两模型（Elo 固定为点估计），
    每个 bootstrap 抽样跑一次模拟，统计夺冠/晋级概率在抽样间的分布 → 置信区间。

    捕捉"若历史样本略有不同，参数(进而概率)会差多少"——这是点估计完全忽略的估计不确定性。
    Elo（49k 场，远更稳）与点球能力固定为点估计；不确定性主要来自 DC 系数与 48 队攻防。
    写 web/public/data/uncertainty.json。
    """
    import numpy as np

    df = fetch.load_results(force=force_fetch)
    ratings, hist = replay(df, with_history=True)
    elo_by_code = {c: ratings[code_to_martj42(c)] for c in CODES}
    tiebreak_key = dict(elo_by_code)
    shootouts = fetch.load_shootouts(force=force_fetch)
    pen_by_name = penalty.fit_penalty_ratings(shootouts)
    penalty_theta = {c: pen_by_name.get(code_to_martj42(c), 0.0) for c in CODES}

    bundle = load_bundle() or fit_bundle(force_fetch=False)
    H = bundle.half_life_days
    ridge = bundle.diagnostics.get("selected_ridge", dc_attack.RIDGE)
    w_elo = bundle.weight_dc_elo
    results = results_store.load_store()

    champ = np.zeros((n_boot, 48))
    advance = np.zeros((n_boot, 48))
    for b in range(n_boot):
        hist_b = hist.sample(frac=1.0, replace=True, random_state=b)
        df_b = df.sample(frac=1.0, replace=True, random_state=10_000 + b)
        elo_p = dc_elo.fit(hist_b, cutoff=CUTOFF, half_life_days=H)
        att_p = _attack_params_by_code(
            dc_attack.fit(df_b, cutoff=CUTOFF, half_life_days=H, ridge=ridge)
        )
        model = EnsembleModel(
            [(DcEloModel(elo_p, elo_by_code), w_elo), (DcAttackModel(att_p), 1 - w_elo)]
        )
        sim = simulate(
            model,
            elo_by_code,
            n_sims=n_sims,
            fixed_results=results,
            tiebreak_key=tiebreak_key,
            penalty_theta=penalty_theta,
            seed=b,
        )
        for i, c in enumerate(CODES):
            champ[b, i] = sim.stage_counts[c]["champion"] / n_sims
            advance[b, i] = sim.advance_counts[c] / n_sims

    def ci(arr):
        lo, med, hi = np.percentile(arr, [2.5, 50, 97.5], axis=0)
        return lo, med, hi

    c_lo, c_med, c_hi = ci(champ)
    a_lo, a_med, a_hi = ci(advance)
    teams = {
        c: {
            "champion": [
                round(float(c_lo[i]), 4),
                round(float(c_med[i]), 4),
                round(float(c_hi[i]), 4),
            ],
            "advance": [
                round(float(a_lo[i]), 4),
                round(float(a_med[i]), 4),
                round(float(a_hi[i]), 4),
            ],
        }
        for i, c in enumerate(CODES)
    }
    out = {
        "n_boot": n_boot,
        "n_sims": n_sims,
        "generated_at": _now_iso(),
        "note": "bootstrap 重抽训练史重拟 DC 模型(Elo 固定)的参数不确定性,区间为 2.5/50/97.5 百分位",
        "teams": teams,
    }
    path = config.WEB_DATA_DIR / "uncertainty.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n"
    )
    return out


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
    # 本届实战表现（重建赛前预测打分，便宜、无需模拟）
    from .backtest import performance

    performance.write_performance(bundle=ctx.bundle, results=ctx.results)
    return rid
