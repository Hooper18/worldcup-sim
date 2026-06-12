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
    params = pipeline.fit_params(force_fetch=args.force)
    print(f"[fit] {params.n_matches} 场拟合：β0={params.beta0:.4f} β1={params.beta1:.4f} "
          f"γ={params.gamma:.4f} ρ={params.rho:.4f} → {config.PARAMS_PATH}")
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
    print("[backtest] 将在 M1 实现（2018/2022 截断回测）")
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

    p_bt = sub.add_parser("backtest", help="回测")
    p_bt.add_argument("--year", type=int, choices=[2018, 2022], required=True)
    p_bt.set_defaults(func=_cmd_backtest)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
