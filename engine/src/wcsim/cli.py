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
    print(f"[update] 新完赛 {len(new)} 场 {new}，run_id={rid} 重模拟 {args.n} 次完成")
    return 0


def _cmd_backtest(args: argparse.Namespace) -> int:
    """2018/2022 回测选最优 H 与融合权重，按需重拟合 2026 参数。"""
    from .backtest import runner
    from .data import fetch

    df = fetch.load_results(force=args.force)
    res = runner.select_best(df)
    best = res["best"]
    print("=== 回测结果（RPS 越低越好）===")
    for year, m in res["years"].items():
        print(f"[{year}] {m['n_matches']} 场  基准={m['rps_baseline']}  "
              f"DC-Elo={m['rps_dc_elo']}  攻防={m['rps_dc_attack']}  融合={m['rps_ensemble']}")
    print(f"[最优] H={best['half_life_days']} 天  权重 DC-Elo={best['weight_dc_elo']}/"
          f"攻防={best['weight_dc_attack']}  合并 RPS={best['combined_rps']}")
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

    p_bt = sub.add_parser("backtest", help="2018/2022 回测 + 选最优 H/权重")
    p_bt.add_argument("--apply", action="store_true", help="用最优参数重拟合并写 params.json")
    p_bt.add_argument("--force", action="store_true", help="强制重新下载数据")
    p_bt.set_defaults(func=_cmd_backtest)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
