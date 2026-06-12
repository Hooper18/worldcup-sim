"""wcsim 命令行入口。

    wcsim fetch                  拉取 martj42 历史数据 + fixturedownload feed
    wcsim fit                    拟合 DC-on-Elo 并落 params.json（赛前一次性）
    wcsim simulate [-n N]        蒙特卡洛模拟（自动条件化已完赛场次）
    wcsim export [-n N]          模拟 + 导出 web/public/data/ 全套 JSON
    wcsim update [-n N]          一条龙：刷新赛果 → 有新完赛才重模拟 → 导出（cron 用）
    wcsim backtest --year 2018   回测（M1 实现）
"""

from __future__ import annotations

import argparse
import sys

from . import config, pipeline
from .data import fetch


def _cmd_fetch(args: argparse.Namespace) -> int:
    fetch.fetch_results_csv(force=True)
    fetch.fetch_shootouts_csv(force=True)
    fetch.fetch_fixture_feed(force=True)
    print("[fetch] 已更新 results.csv / shootouts.csv / fixtures.json")
    return 0


def _cmd_fit(args: argparse.Namespace) -> int:
    bundle = pipeline.fit_bundle(force_fetch=args.force)
    e = bundle.dc_elo
    print(f"[fit] DC-on-Elo（{e.n_matches} 场）β0={e.beta0:.4f} β1={e.beta1:.4f} "
          f"γ={e.gamma:.4f} ρ={e.rho:.4f}")
    print(f"[fit] 纯攻防（{bundle.dc_attack.n_matches} 场）μ={bundle.dc_attack.mu:.4f} "
          f"host={bundle.dc_attack.home_adv:.4f} ρ={bundle.dc_attack.rho:.4f}")
    print(f"[fit] 权重 DC-on-Elo={bundle.weight_dc_elo} 攻防={bundle.weight_dc_attack:.2f} "
          f"H={bundle.half_life_days} → {config.PARAMS_PATH}")
    return 0


def _cmd_simulate(args: argparse.Namespace) -> int:
    ctx = pipeline.build_context(force_fetch=args.force)
    sim = pipeline.run_simulation(ctx, n_sims=args.n)
    champ = sorted(
        ((sim.stage_counts[c]["champion"] / sim.n_sims, c) for c in sim.stage_counts), reverse=True
    )
    print(f"[simulate] {args.n} 次，已完赛 {len(ctx.results)} 场。夺冠 Top5：")
    for p, c in champ[:5]:
        print(f"  {p:6.1%}  {c}")
    return 0


def _cmd_export(args: argparse.Namespace) -> int:
    ctx = pipeline.build_context(force_fetch=args.force)
    sim = pipeline.run_simulation(ctx, n_sims=args.n)
    rid = pipeline.export(ctx, sim)
    print(f"[export] run_id={rid}，已写 {config.WEB_DATA_DIR}")
    return 0


def _cmd_update(args: argparse.Namespace) -> int:
    """刷新赛果；有新完赛才重模拟 + 导出，否则 no-op（Actions 据此跳过 commit）。"""
    from .data import results_store

    before = results_store.load_store()
    ctx = pipeline.build_context(force_fetch=True, refresh_results=True)
    new = results_store.new_finished(before, ctx.results)
    if not new and config.WEB_DATA_DIR.joinpath("meta.json").exists():
        print("[update] 无新完赛场次，跳过重模拟")
        return 0
    sim = pipeline.run_simulation(ctx, n_sims=args.n)
    rid = pipeline.export(ctx, sim)
    # 有新赛果时一并刷新 bootstrap 不确定性区间（保持与点估计一致；约 1-2 分钟）
    pipeline.bootstrap_uncertainty(n_boot=30, n_sims=4000, force_fetch=False)
    print(f"[update] 新完赛 {len(new)} 场 {new}，run_id={rid} 重模拟 {args.n} 次 + 刷新不确定性完成")
    return 0


def _cmd_uncertainty(args: argparse.Namespace) -> int:
    """bootstrap 参数不确定性 → 夺冠/晋级概率置信区间，写 uncertainty.json。"""
    out = pipeline.bootstrap_uncertainty(n_boot=args.boot, n_sims=args.n, force_fetch=args.force)
    top = sorted(out["teams"].items(), key=lambda kv: -kv[1]["champion"][1])[:6]
    print(f"[uncertainty] {args.boot} 次 bootstrap × {args.n} 模拟。夺冠概率 中位数[95% 区间]：")
    for c, t in top:
        lo, med, hi = t["champion"]
        print(f"  {c}: {med:.1%}  [{lo:.1%}, {hi:.1%}]")
    return 0


def _cmd_backtest(args: argparse.Namespace) -> int:
    """跨赛事回测 + LOTO 交叉验证选最优 H 与融合权重，按需重拟合 2026 参数。"""
    from .backtest import runner
    from .data import fetch

    df = fetch.load_results(force=args.force)
    print("[backtest] 枚举赛事并拟合（每赛事×H 一次双模型拟合，约数分钟）…")
    res = runner.select_best(df)
    best = res["best"]
    loto = res["loto"]
    print(f"=== 跨赛事回测：{best['n_events']} 届决赛圈 / {best['n_matches']} 场（RPS 越低越好）===")
    for year, m in res["years"].items():
        print(f"[世界杯 {year}] {m['n_matches']} 场  基准={m['rps_baseline']}  "
              f"DC-Elo={m['rps_dc_elo']}  攻防={m['rps_dc_attack']}  融合={m['rps_ensemble']}")
    print(f"[生产参数] H={best['half_life_days']} 天  权重 DC-Elo={best['weight_dc_elo']}/"
          f"攻防={best['weight_dc_attack']}（全量 pooled RPS={best['pooled_rps']}）")
    print(f"[诚实性能] LOTO 留一届样本外 RPS={best['oos_rps']}"
          f"（climatology 基准={best['rps_baseline']}，更强的 Elo 基准={best['rps_elo_baseline']}）")
    print(f"[选择稳定性] 各折选中 H 分布={loto['selected_H_counts']}  权重分布={loto['selected_w_counts']}")
    if args.apply:
        pipeline.fit_bundle(
            force_fetch=False,
            half_life_days=best["half_life_days"],
            weight_dc_elo=best["weight_dc_elo"],
            backtest=res,
        )
        print(f"[backtest] 已用最优参数重拟合并写入 {config.PARAMS_PATH}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="wcsim", description="2026 世界杯预测与模拟引擎")
    sub = parser.add_subparsers(dest="command", required=True)

    p_fetch = sub.add_parser("fetch", help="拉取数据")
    p_fetch.set_defaults(func=_cmd_fetch)

    p_fit = sub.add_parser("fit", help="拟合模型参数")
    p_fit.add_argument("--force", action="store_true", help="强制重新下载数据")
    p_fit.set_defaults(func=_cmd_fit)

    for name, fn, helptext in [
        ("simulate", _cmd_simulate, "蒙特卡洛模拟"),
        ("export", _cmd_export, "模拟并导出 JSON"),
        ("update", _cmd_update, "刷新赛果并条件重模拟"),
    ]:
        p = sub.add_parser(name, help=helptext)
        p.add_argument("-n", type=int, default=config.N_SIMS_DEFAULT, help="模拟次数")
        p.add_argument("--force", action="store_true", help="强制重新下载数据")
        p.set_defaults(func=fn)

    p_bt = sub.add_parser("backtest", help="跨赛事回测 + LOTO 选最优 H/权重")
    p_bt.add_argument("--apply", action="store_true", help="用最优参数重拟合并写 params.json")
    p_bt.add_argument("--force", action="store_true", help="强制重新下载数据")
    p_bt.set_defaults(func=_cmd_backtest)

    p_un = sub.add_parser("uncertainty", help="bootstrap 参数不确定性 → 概率置信区间")
    p_un.add_argument("-n", type=int, default=5000, help="每次 bootstrap 的模拟次数")
    p_un.add_argument("--boot", type=int, default=40, help="bootstrap 重抽次数")
    p_un.add_argument("--force", action="store_true", help="强制重新下载数据")
    p_un.set_defaults(func=_cmd_uncertainty)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
