"""把模型 + 模拟结果写成前端读取的 JSON（全部 UTF-8，中文不转义，LF 换行）。

产出 web/public/data/ 下：meta / teams / matches / groups / knockout / evolution，
以及 history/<run_id>.json 全量留档。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np

from .. import config
from ..models.bundle import ModelBundle
from ..models.poisson import outcome_probs, top_scores
from ..models.score_model import DcAttackModel, DcEloModel, ScoreModel
from ..tournament.simulate import CODES, SimResult
from ..tournament.structure import (
    GROUP_LETTERS,
    GROUPS,
    KO_CHAIN,
    MATCHES,
    R32_SLOTS,
    TEAMS,
    has_host_advantage,
)
from ..tournament.tiebreak import compute_standings

DISPLAY_GRID = 6  # matches.json 的 score_matrix 截断到 0-5 球


def _write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n"
    )


def _round(x: float, n: int = 4) -> float:
    return round(float(x), n)


# ---------------------------------------------------------------------------
# 单场预测（解析自 DC 模型，不依赖模拟）
# ---------------------------------------------------------------------------


def match_forecast(
    model: ScoreModel,
    home: str,
    away: str,
    *,
    host_home: bool = False,
    host_away: bool = False,
) -> dict:
    lh, la = model.lambdas(home, away, host_home=host_home, host_away=host_away)
    mat = model.matrix(home, away, host_home=host_home, host_away=host_away)
    ph, pd_, pa = outcome_probs(mat)
    return {
        "p_home": _round(ph),
        "p_draw": _round(pd_),
        "p_away": _round(pa),
        "lambda_home": _round(lh, 3),
        "lambda_away": _round(la, 3),
        "top_scores": [{"h": h, "a": a, "p": _round(p)} for h, a, p in top_scores(mat, 8)],
        "score_matrix": [
            [_round(mat[h, a]) for a in range(DISPLAY_GRID)] for h in range(DISPLAY_GRID)
        ],
    }


def _model_breakdown(
    components: list[tuple[str, ScoreModel]], home: str, away: str, host_home: bool, host_away: bool
) -> dict:
    out = {}
    for mid, m in components:
        ph, pd_, pa = outcome_probs(m.matrix(home, away, host_home=host_home, host_away=host_away))
        out[mid] = {"p_home": _round(ph), "p_draw": _round(pd_), "p_away": _round(pa)}
    return out


# ---------------------------------------------------------------------------
# 各 JSON
# ---------------------------------------------------------------------------


def build_teams(elo: dict[str, float], fifa_rank: dict[str, int] | None = None) -> dict:
    fifa_rank = fifa_rank or {}
    out = {}
    for c, t in TEAMS.items():
        out[c] = {
            "name_zh": t.name_zh,
            "name_en": t.name_en,
            "group": t.group,
            "elo": round(elo[c]),
            "fifa_rank": fifa_rank.get(c),
            "host": t.host,
        }
    return out


def build_matches(
    model: ScoreModel,
    components: list[tuple[str, ScoreModel]],
    results: dict[int, dict],
    sim: SimResult,
) -> list[dict]:
    out = []
    for mid in sorted(MATCHES):
        m = MATCHES[mid]
        entry: dict = {
            "id": mid,
            "stage": m["stage"],
            "group": m["group"],
            "kickoff_utc": m["kickoff_utc"],
            "venue": m["venue"],
            "status": "finished" if mid in results else "scheduled",
            "result": results.get(mid),
        }
        if m["stage"] == "group":
            hc, ac = m["home"], m["away"]
            hh = has_host_advantage(hc, m["venue"])
            ha = has_host_advantage(ac, m["venue"])
            entry["home"] = hc
            entry["away"] = ac
            entry["forecast"] = match_forecast(model, hc, ac, host_home=hh, host_away=ha)
            entry["model_breakdown"] = _model_breakdown(components, hc, ac, hh, ha)
        else:
            # 淘汰赛：占位记号 + 槽位归属分布（谁最可能占这个位置）
            entry["home"] = m["home"] if m["stage"] == "r32" else None
            entry["away"] = m["away"] if m["stage"] == "r32" else None
            if mid in sim.match_side_counts:
                entry["slot_dist"] = {
                    "home": _side_dist(sim.match_side_counts[mid]["home"], sim.n_sims),
                    "away": _side_dist(sim.match_side_counts[mid]["away"], sim.n_sims),
                }
        out.append(entry)
    return out


def _side_dist(counts: np.ndarray, n: int, top: int = 6) -> list[dict]:
    order = np.argsort(-counts)
    out = []
    for i in order[:top]:
        if counts[i] == 0:
            break
        out.append({"team": CODES[i], "p": _round(counts[i] / n)})
    return out


def build_groups(results: dict[int, dict], sim: SimResult) -> dict:
    # 真实积分榜（仅已完赛小组赛）
    current = _current_standings(results)
    out = {}
    for g in GROUP_LETTERS:
        rc = sim.group_rank_counts[g]
        teams = GROUPS[g]
        gout = {}
        for i, c in enumerate(teams):
            p_rank = [_round(rc[i, r] / sim.n_sims) for r in range(4)]
            cur = current.get(c)
            gout[c] = {
                "p_rank": p_rank,
                "p_top2": _round(p_rank[0] + p_rank[1]),
                "p_third_advance": _round(sim.third_advance_counts[c] / sim.n_sims),
                "p_advance": _round(sim.advance_counts[c] / sim.n_sims),
                "exp_pts": _round(sim.group_exp_pts[g][i], 2),
                "exp_gd": _round(sim.group_exp_gd[g][i], 2),
                "current": cur,
            }
        out[g] = gout
    return out


def _current_standings(results: dict[int, dict]) -> dict[str, dict]:
    out: dict[str, dict] = {}
    for g in GROUP_LETTERS:
        matches = []
        for mid in (m["id"] for m in MATCHES.values() if m["stage"] == "group" and m["group"] == g):
            if mid in results:
                m = MATCHES[mid]
                r = results[mid]
                matches.append((m["home"], m["away"], r["h"], r["a"]))
        st = compute_standings(GROUPS[g], matches)
        for c in GROUPS[g]:
            s = st[c]
            out[c] = {"pts": s.pts, "gd": s.gd, "gf": s.gf, "played": s.played}
    return out


def build_knockout(sim: SimResult) -> dict:
    teams = {}
    for c in CODES:
        sc = sim.stage_counts[c]
        teams[c] = {
            f"p_{s}": _round(sc[s] / sim.n_sims)
            for s in ("r32", "r16", "qf", "sf", "final", "champion")
        }
    bracket = {}
    for mid, (sh, sa) in R32_SLOTS.items():
        bracket[str(mid)] = {"home_slot": sh, "away_slot": sa}
    for mid, ((kh, sh), (ka, sa)) in KO_CHAIN.items():
        bracket[str(mid)] = {"home_src": f"{kh}{sh}", "away_src": f"{ka}{sa}"}
    return {"teams": teams, "bracket": bracket}


def build_meta(
    run_id: str,
    generated_at: str,
    sim: SimResult,
    bundle: ModelBundle,
    results: dict[int, dict],
    data_info: dict,
) -> dict:
    elo_p = bundle.dc_elo
    return {
        "run_id": run_id,
        "generated_at": generated_at,
        "n_sims": sim.n_sims,
        "matches_played": len(results),
        "data": data_info,
        "models": {
            "components": [
                {
                    "id": "dc_elo",
                    "name_zh": "DC-on-Elo（Dixon-Coles × Elo）",
                    "weight": _round(bundle.weight_dc_elo, 3),
                    "params": {
                        "beta0": _round(elo_p.beta0),
                        "beta1": _round(elo_p.beta1),
                        "gamma": _round(elo_p.gamma),
                        "rho": _round(elo_p.rho),
                    },
                },
                {
                    "id": "dc_attack",
                    "name_zh": "纯攻防 Dixon-Coles",
                    "weight": _round(bundle.weight_dc_attack, 3),
                    "params": {
                        "mu": _round(bundle.dc_attack.mu),
                        "home_adv": _round(bundle.dc_attack.home_adv),
                        "rho": _round(bundle.dc_attack.rho),
                    },
                },
            ],
            "half_life_days": bundle.half_life_days,
            "backtest": bundle.backtest or {},
            "diagnostics": bundle.diagnostics or {},
        },
    }


# ---------------------------------------------------------------------------
# evolution（追加快照）
# ---------------------------------------------------------------------------

_EVOLUTION_METRICS = ("champion", "final", "sf", "advance")


def update_evolution(
    path: Path, run_id: str, generated_at: str, sim: SimResult, results: dict[int, dict]
) -> dict:
    if path.exists():
        evo = json.loads(path.read_text(encoding="utf-8"))
    else:
        evo = {"snapshots": [], "teams": {c: {m: [] for m in _EVOLUTION_METRICS} for c in CODES}}

    # 幂等：同 run_id 已存在则不重复追加
    if any(s["run_id"] == run_id for s in evo["snapshots"]):
        return evo

    evo["snapshots"].append({"run_id": run_id, "at": generated_at, "matches_played": len(results)})
    for c in CODES:
        sc = sim.stage_counts[c]
        vals = {
            "champion": sc["champion"],
            "final": sc["final"],
            "sf": sc["sf"],
            "advance": sim.advance_counts[c],
        }
        for m in _EVOLUTION_METRICS:
            evo["teams"].setdefault(c, {mm: [] for mm in _EVOLUTION_METRICS})
            evo["teams"][c][m].append(_round(vals[m] / sim.n_sims))
    return evo


# ---------------------------------------------------------------------------
# 总入口
# ---------------------------------------------------------------------------


def export_all(
    *,
    run_id: str,
    generated_at: str,
    bundle: ModelBundle,
    elo: dict[str, float],
    results: dict[int, dict],
    sim: SimResult,
    data_info: dict,
    fifa_rank: dict[str, int] | None = None,
    out_dir: Path | None = None,
) -> None:
    out_dir = out_dir or config.WEB_DATA_DIR
    model = bundle.build_model(elo)
    components: list[tuple[str, ScoreModel]] = [
        ("dc_elo", DcEloModel(bundle.dc_elo, elo)),
        ("dc_attack", DcAttackModel(bundle.dc_attack)),
    ]
    teams = build_teams(elo, fifa_rank)
    matches = build_matches(model, components, results, sim)
    groups = build_groups(results, sim)
    knockout = build_knockout(sim)
    meta = build_meta(run_id, generated_at, sim, bundle, results, data_info)

    _write_json(out_dir / "meta.json", meta)
    _write_json(out_dir / "teams.json", teams)
    _write_json(out_dir / "matches.json", matches)
    _write_json(out_dir / "groups.json", groups)
    _write_json(out_dir / "knockout.json", knockout)

    evo = update_evolution(out_dir / "evolution.json", run_id, generated_at, sim, results)
    _write_json(out_dir / "evolution.json", evo)

    _write_json(
        out_dir / "history" / f"{run_id}.json",
        {"meta": meta, "groups": groups, "knockout": knockout},
    )
