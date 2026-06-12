"""蒙特卡洛整届模拟：小组赛 → 32 强 → 决赛，输出各阶段晋级概率。

性能策略：
- 比分抽样向量化：小组赛每场一次性抽 N 个比分；淘汰赛用 48×48 预计算 cdf 张量 gather 抽样。
- 小组排名：先按总积分粗排，只有"存在同分球队"的少数 sim 回落到精确头对头排名器。
- 条件模拟：已完赛场次代入真实比分（含点球胜者），只对未赛场次抽样——这是"赛果回填后
  重模拟剩余赛程"的核心。

淘汰赛按中立场建模（忽略东道主本土加成，世界杯淘汰赛传统视为中立；东道主优势主要在
小组赛体现，小组赛场地与队伍绑定，照常加 host）。
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .. import config
from ..models.dc_elo import DcEloParams
from ..models.score_model import DcEloModel, ScoreModel
from . import annexe_c
from .structure import (
    GROUP_LETTERS,
    GROUPS,
    KO_CHAIN,
    MATCHES,
    R32_SLOTS,
    TEAMS,
    THIRD_SLOT_MATCHES,
    has_host_advantage,
)
from .tiebreak import rank_group

# 全局队伍顺序（48 队），淘汰赛抽样用 index
CODES: list[str] = list(TEAMS)
CODE_IDX: dict[str, int] = {c: i for i, c in enumerate(CODES)}
GRID = config.MAX_GOALS + 1

KO_STAGES = ("r32", "r16", "qf", "sf", "final", "champion")
_KO_STAGE_OF = {
    **{m: "r16" for m in range(89, 97)},
    **{m: "qf" for m in range(97, 101)},
    101: "sf",
    102: "sf",
    103: "third",
    104: "final",
}


@dataclass
class SimResult:
    n_sims: int
    group_rank_counts: dict[str, np.ndarray]  # 组 -> (4 队按 GROUPS 顺序, 4 名次)
    group_exp_pts: dict[str, np.ndarray]  # 组 -> (4,) 期望积分（GROUPS 顺序）
    group_exp_gd: dict[str, np.ndarray]  # 组 -> (4,) 期望净胜球
    advance_counts: dict[str, int]  # 进 32 强（前 2 + 最佳第三）
    third_advance_counts: dict[str, int]  # 作为最佳第三晋级
    stage_counts: dict[str, dict[str, int]]  # team -> {r32,r16,qf,sf,final,champion}
    match_side_counts: dict[int, dict[str, np.ndarray]]  # 淘汰赛场 -> {home/away: (48,)}


class ScoreSampler:
    """用任意 ScoreModel（DC-on-Elo / 攻防 / 融合）生成比分。"""

    def __init__(self, model: ScoreModel):
        self.model = model
        self._neutral_cdf: np.ndarray | None = None
        self._neutral_et_cdf: np.ndarray | None = None

    def group_match_goals(
        self, match: dict, n: int, rng: np.random.Generator
    ) -> tuple[np.ndarray, np.ndarray]:
        hc, ac = match["home"], match["away"]
        mat = self.model.matrix(
            hc,
            ac,
            host_home=has_host_advantage(hc, match["venue"]),
            host_away=has_host_advantage(ac, match["venue"]),
        ).ravel()
        flat = rng.choice(mat.size, size=n, p=mat / mat.sum())
        return flat // GRID, flat % GRID

    def _build_cdf(self, et: bool) -> np.ndarray:
        factor = config.EXTRA_TIME_LAMBDA_FACTOR if et else 1.0
        tensor = np.empty((48, 48, GRID * GRID))
        for i, ci in enumerate(CODES):
            for j, cj in enumerate(CODES):
                mat = self.model.matrix(
                    ci, cj, host_home=False, host_away=False, factor=factor
                ).ravel()
                tensor[i, j] = np.cumsum(mat / mat.sum())
        return tensor

    def neutral_cdf(self) -> np.ndarray:
        if self._neutral_cdf is None:
            self._neutral_cdf = self._build_cdf(et=False)
        return self._neutral_cdf

    def neutral_et_cdf(self) -> np.ndarray:
        if self._neutral_et_cdf is None:
            self._neutral_et_cdf = self._build_cdf(et=True)
        return self._neutral_et_cdf

    def sample_neutral(
        self,
        home_idx: np.ndarray,
        away_idx: np.ndarray,
        rng: np.random.Generator,
        *,
        et: bool = False,
    ) -> tuple[np.ndarray, np.ndarray]:
        cdf = self.neutral_et_cdf() if et else self.neutral_cdf()
        sel = cdf[home_idx, away_idx]  # (N, GRID²)
        u = rng.random(home_idx.shape[0])
        flat = (sel < u[:, None]).sum(axis=1)
        np.clip(flat, 0, GRID * GRID - 1, out=flat)
        return flat // GRID, flat % GRID


# ---------------------------------------------------------------------------
# 小组赛
# ---------------------------------------------------------------------------


def _group_match_ids(group: str) -> list[int]:
    return sorted(
        m["id"] for m in MATCHES.values() if m["stage"] == "group" and m["group"] == group
    )


def _simulate_group(
    group: str,
    sampler: ScoreSampler,
    n: int,
    rng: np.random.Generator,
    fixed: dict[int, dict],
    tiebreak_key: dict[str, float],
):
    """返回 (teams, placement, pts, gd, gf)。placement[i,s]=队 teams[i] 在 sim s 的名次。"""
    teams = GROUPS[group]
    local = {c: i for i, c in enumerate(teams)}

    home_goals: list[np.ndarray] = []
    away_goals: list[np.ndarray] = []
    meta: list[tuple[int, int, str, str]] = []
    for mid in _group_match_ids(group):
        m = MATCHES[mid]
        hc, ac = m["home"], m["away"]
        if mid in fixed:
            hg = np.full(n, fixed[mid]["h"], dtype=np.int64)
            ag = np.full(n, fixed[mid]["a"], dtype=np.int64)
        else:
            hg, ag = sampler.group_match_goals(m, n, rng)
        home_goals.append(hg)
        away_goals.append(ag)
        meta.append((local[hc], local[ac], hc, ac))

    pts = np.zeros((4, n), dtype=np.int64)
    gf = np.zeros((4, n), dtype=np.int64)
    ga = np.zeros((4, n), dtype=np.int64)
    for (hi, ai, _, _), hg, ag in zip(meta, home_goals, away_goals):
        gf[hi] += hg
        ga[hi] += ag
        gf[ai] += ag
        ga[ai] += hg
        home_win = hg > ag
        away_win = hg < ag
        draw = ~(home_win | away_win)
        pts[hi] += 3 * home_win + draw
        pts[ai] += 3 * away_win + draw
    gd = gf - ga

    # 粗排：pts 唯一时即最终名次
    order = np.argsort(-pts, axis=0, kind="stable")
    placement = np.empty((4, n), dtype=np.int64)
    np.put_along_axis(placement, order, np.broadcast_to(np.arange(4)[:, None], (4, n)), axis=0)

    # 存在同分的 sim 回落精确头对头排名
    sp = np.sort(pts, axis=0)
    dup_sims = np.nonzero((np.diff(sp, axis=0) == 0).any(axis=0))[0]
    for s in dup_sims:
        ms = [
            (hc, ac, int(home_goals[k][s]), int(away_goals[k][s]))
            for k, (_, _, hc, ac) in enumerate(meta)
        ]
        for rank, st in enumerate(rank_group(ms, tiebreak_key=tiebreak_key)):
            placement[local[st.code], s] = rank

    return teams, placement, pts, gd, gf


# ---------------------------------------------------------------------------
# 主流程
# ---------------------------------------------------------------------------


def simulate(
    model: ScoreModel | DcEloParams,
    elo_by_code: dict[str, float] | None = None,
    *,
    n_sims: int = config.N_SIMS_DEFAULT,
    fixed_results: dict[int, dict] | None = None,
    tiebreak_key: dict[str, float] | None = None,
    seed: int = 12345,
) -> SimResult:
    """跑 n_sims 次整届模拟。

    model: ScoreModel（DC-on-Elo / 攻防 / 融合）。为向后兼容也接受 (DcEloParams, elo_by_code)。
    fixed_results: {match_id: {"h","a","after","pen_winner?"}}，已完赛场次固定不抽样。
    tiebreak_key: {code: 数值}，小组/第三名最终兜底（建议用赛前 Elo），缺省全 0。
    """
    if isinstance(model, DcEloParams):
        assert elo_by_code is not None, "传 DcEloParams 时需同时给 elo_by_code"
        model = DcEloModel(model, elo_by_code)
    fixed = fixed_results or {}
    tiebreak_key = tiebreak_key or {}
    rng = np.random.default_rng(seed)
    sampler = ScoreSampler(model)
    tk_by_global = np.array([tiebreak_key.get(c, 0.0) for c in CODES])

    first_idx: dict[str, np.ndarray] = {}
    second_idx: dict[str, np.ndarray] = {}
    third_idx: dict[str, np.ndarray] = {}
    third_stats: dict[str, tuple[np.ndarray, np.ndarray, np.ndarray]] = {}
    group_rank_counts: dict[str, np.ndarray] = {}
    group_exp_pts: dict[str, np.ndarray] = {}
    group_exp_gd: dict[str, np.ndarray] = {}

    rows = np.arange(n_sims)
    for g in GROUP_LETTERS:
        teams, placement, pts, gd, gf = _simulate_group(
            g, sampler, n_sims, rng, fixed, tiebreak_key
        )
        rc = np.zeros((4, 4), dtype=np.int64)
        for i in range(4):
            rc[i] = np.bincount(placement[i], minlength=4)
        group_rank_counts[g] = rc
        group_exp_pts[g] = pts.mean(axis=1)
        group_exp_gd[g] = gd.mean(axis=1)

        glob = np.array([CODE_IDX[c] for c in teams])
        # placement[i,s]==r 的队 i：argmax 找每个 sim 在名次 r 的本地队号
        local_at = {r: np.argmax(placement == r, axis=0) for r in range(4)}
        first_idx[g] = glob[local_at[0]]
        second_idx[g] = glob[local_at[1]]
        third_local = local_at[2]
        third_idx[g] = glob[third_local]
        third_stats[g] = (pts[third_local, rows], gd[third_local, rows], gf[third_local, rows])

    third_team_by_match = _resolve_third_places(third_idx, third_stats, tk_by_global, n_sims)

    # 晋级 32 强计数
    advance_arr = np.zeros(48, dtype=np.int64)
    third_adv_arr = np.zeros(48, dtype=np.int64)
    for g in GROUP_LETTERS:
        advance_arr += np.bincount(first_idx[g], minlength=48)
        advance_arr += np.bincount(second_idx[g], minlength=48)
    for mid in THIRD_SLOT_MATCHES:
        bc = np.bincount(third_team_by_match[mid], minlength=48)
        advance_arr += bc
        third_adv_arr += bc

    # R32 对阵解析
    home_of = {
        mid: _resolve_slot(s_h, mid, first_idx, second_idx, third_team_by_match)
        for mid, (s_h, _) in R32_SLOTS.items()
    }
    away_of = {
        mid: _resolve_slot(s_a, mid, first_idx, second_idx, third_team_by_match)
        for mid, (_, s_a) in R32_SLOTS.items()
    }

    # 逐轮淘汰赛（"third"=季军赛参赛者，单独收集不进单调链导出）
    stage_arr = {s: np.zeros(48, dtype=np.int64) for s in (*KO_STAGES, "third")}
    match_side_counts: dict[int, dict[str, np.ndarray]] = {}
    winners: dict[int, np.ndarray] = {}
    losers: dict[int, np.ndarray] = {}

    def play(mid: int, h: np.ndarray, a: np.ndarray, stage: str) -> None:
        bc_h = np.bincount(h, minlength=48)
        bc_a = np.bincount(a, minlength=48)
        match_side_counts[mid] = {"home": bc_h, "away": bc_a}
        stage_arr[stage] += bc_h + bc_a
        winners[mid], losers[mid] = _decide(sampler, h, a, rng)

    for mid in sorted(R32_SLOTS):
        play(mid, home_of[mid], away_of[mid], "r32")
    for mid in range(89, 105):
        (kind_h, src_h), (kind_a, src_a) = KO_CHAIN[mid]
        h = winners[src_h] if kind_h == "W" else losers[src_h]
        a = winners[src_a] if kind_a == "W" else losers[src_a]
        play(mid, h, a, _KO_STAGE_OF[mid])

    stage_arr["champion"] = np.bincount(winners[104], minlength=48)

    stage_counts = {
        c: {s: int(stage_arr[s][i]) for s in KO_STAGES} for i, c in enumerate(CODES)
    }
    return SimResult(
        n_sims=n_sims,
        group_rank_counts=group_rank_counts,
        group_exp_pts=group_exp_pts,
        group_exp_gd=group_exp_gd,
        advance_counts={c: int(advance_arr[i]) for i, c in enumerate(CODES)},
        third_advance_counts={c: int(third_adv_arr[i]) for i, c in enumerate(CODES)},
        stage_counts=stage_counts,
        match_side_counts=match_side_counts,
    )


# ---------------------------------------------------------------------------
# 辅助
# ---------------------------------------------------------------------------


def _decide(
    sampler: ScoreSampler, h: np.ndarray, a: np.ndarray, rng: np.random.Generator
) -> tuple[np.ndarray, np.ndarray]:
    """淘汰赛定胜负：90 分钟 → 平则加时 λ/3 → 仍平则点球 50:50。返回 (胜者, 负者)。"""
    hg, ag = sampler.sample_neutral(h, a, rng)
    draw = hg == ag
    if draw.any():
        eg_h, eg_a = sampler.sample_neutral(h, a, rng, et=True)
        hg = hg + np.where(draw, eg_h, 0)
        ag = ag + np.where(draw, eg_a, 0)
    home_win = hg > ag
    away_win = hg < ag
    pen_home = rng.random(h.shape[0]) < config.PENALTY_WIN_PROB
    w = np.where(home_win, h, np.where(away_win, a, np.where(pen_home, h, a)))
    return w, np.where(w == h, a, h)


def _resolve_slot(
    slot: str,
    mid: int,
    first_idx: dict[str, np.ndarray],
    second_idx: dict[str, np.ndarray],
    third_team_by_match: dict[int, np.ndarray],
) -> np.ndarray:
    if slot[0] == "1":
        return first_idx[slot[1]]
    if slot[0] == "2":
        return second_idx[slot[1]]
    return third_team_by_match[mid]


def _resolve_third_places(
    third_idx: dict[str, np.ndarray],
    third_stats: dict[str, tuple[np.ndarray, np.ndarray, np.ndarray]],
    tk_by_global: np.ndarray,
    n: int,
) -> dict[int, np.ndarray]:
    """逐 sim：12 组第三名按总成绩排序取前 8 → Annexe C 落位。

    返回 {match_id: (n,) 全局队 index}，仅含 THIRD_SLOT_MATCHES 的 8 个场次。
    """
    letters = list(GROUP_LETTERS)
    keys = np.empty((12, n))
    for gi, g in enumerate(letters):
        pts, gd, gf = third_stats[g]
        tk_vec = tk_by_global[third_idx[g]]
        keys[gi] = pts * 1e6 + gd * 1e3 + gf + tk_vec * 1e-4

    top8_rows = np.argsort(-keys, axis=0, kind="stable")[:8]  # (8,n)

    out = {mid: np.empty(n, dtype=np.int64) for mid in THIRD_SLOT_MATCHES}
    table = annexe_c.TABLE
    for s in range(n):
        combo = "".join(sorted(letters[r] for r in top8_rows[:, s]))
        assign = table[combo]
        for k, mid in enumerate(THIRD_SLOT_MATCHES):
            out[mid][s] = third_idx[assign[k]][s]
    return out
