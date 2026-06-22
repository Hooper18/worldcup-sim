"""蒙特卡洛模拟器的统计性质与条件模拟测试。"""

from __future__ import annotations

import pytest

from wcsim.models.dc_elo import DcEloParams
from wcsim.tournament import simulate as sim
from wcsim.tournament.simulate import CODES, simulate
from wcsim.tournament.structure import GROUP_LETTERS, GROUPS, MATCHES


@pytest.fixture(scope="module")
def params():
    return DcEloParams(
        beta0=0.10,
        beta1=0.73,
        gamma=0.23,
        rho=-0.043,
        half_life_days=730,
        n_matches=7768,
        cutoff="2026-06-11",
    )


@pytest.fixture(scope="module")
def elo():
    # 给 48 队一个有区分度的 Elo（按 CODES 顺序线性下降），便于测单调性
    return {c: 2100.0 - 10.0 * i for i, c in enumerate(CODES)}


@pytest.fixture(scope="module")
def result(params, elo):
    tk = {c: elo[c] for c in CODES}
    return simulate(params, elo, n_sims=4000, tiebreak_key=tk, seed=1)


def test_group_rank_probabilities_normalized(result):
    # 每组每队 4 个名次概率之和 = 1；每个名次恰好分配给 4 队之和 = n_sims
    for g in GROUP_LETTERS:
        rc = result.group_rank_counts[g]
        assert rc.sum() == 4 * result.n_sims
        assert (rc.sum(axis=1) == result.n_sims).all()  # 每队占满 n_sims 个名次
        assert (rc.sum(axis=0) == result.n_sims).all()  # 每名次恰 n_sims 个队


def test_exactly_32_advance_each_sim(result):
    # 每次模拟恰好 32 队进 32 强（24 前二 + 8 第三）
    total_advance = sum(result.advance_counts.values())
    assert total_advance == 32 * result.n_sims
    total_third = sum(result.third_advance_counts.values())
    assert total_third == 8 * result.n_sims


def test_champion_probabilities_sum_to_one(result):
    champ = {c: result.stage_counts[c]["champion"] for c in CODES}
    assert sum(champ.values()) == result.n_sims


def test_stage_monotonicity(result):
    # 每队 p(r32) >= p(r16) >= p(qf) >= p(sf) >= p(final) >= p(champion)
    for c in CODES:
        sc = result.stage_counts[c]
        seq = [sc["r32"], sc["r16"], sc["qf"], sc["sf"], sc["final"], sc["champion"]]
        for a, b in zip(seq, seq[1:], strict=False):
            assert a >= b, f"{c} 阶段概率非单调: {seq}"


def test_each_stage_has_correct_total(result):
    # 每阶段参赛队总数 = 该阶段场次 × 2 × n_sims
    totals = {"r32": 32, "r16": 16, "qf": 8, "sf": 4, "final": 2}
    for stage, n_teams in totals.items():
        s = sum(result.stage_counts[c][stage] for c in CODES)
        assert s == n_teams * result.n_sims


def test_stronger_team_advances_more(result):
    # Elo 最高的队（CODES[0]）进 32 强概率应高于 Elo 最低的队
    best, worst = CODES[0], CODES[-1]
    assert result.advance_counts[best] > result.advance_counts[worst]


def test_advance_equals_top2_plus_third(result):
    # advance = (前二名次数) + (第三名晋级次数)
    for g in GROUP_LETTERS:
        rc = result.group_rank_counts[g]
        for i, c in enumerate(GROUPS[g]):
            top2 = int(rc[i, 0] + rc[i, 1])
            third_adv = result.third_advance_counts[c]
            assert result.advance_counts[c] == top2 + third_adv


def test_conditional_simulation_fixes_match(params, elo):
    # 固定 M1 = 墨西哥(home) 0-5 南非(away)，墨西哥该场必负
    tk = {c: elo[c] for c in CODES}
    fixed = {1: {"h": 0, "a": 5, "after": "FT"}}
    res = simulate(params, elo, n_sims=2000, fixed_results=fixed, tiebreak_key=tk, seed=2)
    # 南非（A 组）拿满这 5 个净胜球，墨西哥进 32 强概率应被显著拉低
    base = simulate(params, elo, n_sims=2000, tiebreak_key=tk, seed=2)
    assert res.advance_counts["RSA"] > base.advance_counts["RSA"]
    assert res.advance_counts["MEX"] < base.advance_counts["MEX"]


def _all_groups_fixed():
    # 固定全部 72 场小组赛：组内 CODES 序靠前（Elo 更高）者 1-0 取胜
    # → 每组 9/6/3/0 严格名次，整个 32 强对阵（含第三名 Annexe C 落位）逐 sim 完全确定。
    order = {c: i for i, c in enumerate(CODES)}
    fixed = {}
    for mid, m in MATCHES.items():
        if m["stage"] != "group":
            continue
        h, a = m["home"], m["away"]
        fixed[mid] = (
            {"h": 1, "a": 0, "after": "FT"}
            if order[h] < order[a]
            else {"h": 0, "a": 1, "after": "FT"}
        )
    return fixed


def test_conditional_simulation_fixes_knockout(params, elo):
    # 已完赛淘汰赛应代入真实赛果而非重新抽样（回归：旧版只对小组赛生效，淘汰赛仍抽样）。
    tk = {c: elo[c] for c in CODES}
    fixed = _all_groups_fixed()

    base = simulate(params, elo, n_sims=200, fixed_results=fixed, tiebreak_key=tk, seed=4)
    side = base.match_side_counts[73]
    assert side["home"].max() == 200 and side["away"].max() == 200  # 参赛队逐 sim 恒定
    home_team = CODES[int(side["home"].argmax())]
    away_team = CODES[int(side["away"].argmax())]
    # 不固定 M73 时主队不一定晋级（抽样胜率 < 1）
    assert base.stage_counts[home_team]["r16"] < 200

    # 固定 M73 = 主队 2-0：主队必进 16 强，负者必出局
    fixed[73] = {"h": 2, "a": 0, "after": "FT"}
    res = simulate(params, elo, n_sims=200, fixed_results=fixed, tiebreak_key=tk, seed=4)
    assert res.stage_counts[home_team]["r16"] == 200
    assert res.stage_counts[away_team]["r16"] == 0


def test_fixed_knockout_penalty_winner(params, elo):
    # 淘汰赛平局：由 pen_winner 决定晋级方，不抽样
    tk = {c: elo[c] for c in CODES}
    fixed = _all_groups_fixed()
    base = simulate(params, elo, n_sims=200, fixed_results=fixed, tiebreak_key=tk, seed=5)
    side = base.match_side_counts[73]
    home_team = CODES[int(side["home"].argmax())]
    away_team = CODES[int(side["away"].argmax())]

    fixed[73] = {"h": 1, "a": 1, "after": "PEN", "pen_winner": "away"}
    res = simulate(params, elo, n_sims=200, fixed_results=fixed, tiebreak_key=tk, seed=5)
    assert res.stage_counts[away_team]["r16"] == 200  # 点球胜者晋级
    assert res.stage_counts[home_team]["r16"] == 0


def test_fully_fixed_group_is_deterministic(params, elo):
    # 固定 A 组全部 6 场，让 rank 小的队 1-0 取胜 → 积分 9/6/3/0 严格区分，名次完全确定
    tk = {c: elo[c] for c in CODES}
    rank = {"MEX": 0, "KOR": 1, "CZE": 2, "RSA": 3}
    fixed = {}
    for mid in sim._group_match_ids("A"):
        m = MATCHES[mid]
        h, a = m["home"], m["away"]
        if rank[h] < rank[a]:
            fixed[mid] = {"h": 1, "a": 0, "after": "FT"}
        else:
            fixed[mid] = {"h": 0, "a": 1, "after": "FT"}
    res = simulate(params, elo, n_sims=500, fixed_results=fixed, tiebreak_key=tk, seed=3)
    rc = res.group_rank_counts["A"]
    idx = {c: i for i, c in enumerate(GROUPS["A"])}
    assert rc[idx["MEX"], 0] == 500  # 9 分,必第一
    assert rc[idx["KOR"], 1] == 500  # 6 分,必第二
    assert rc[idx["CZE"], 2] == 500  # 3 分,必第三
    assert rc[idx["RSA"], 3] == 500  # 0 分,必第四
