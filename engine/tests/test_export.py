"""JSON 导出：schema 完整性、中文不转义、evolution 幂等。"""

from __future__ import annotations

import json

import numpy as np
import pytest

from wcsim.export import writer
from wcsim.models.bundle import ModelBundle
from wcsim.models.dc_attack import DcAttackParams
from wcsim.models.dc_elo import DcEloParams
from wcsim.models.score_model import DcEloModel
from wcsim.tournament.simulate import CODES, simulate
from wcsim.tournament.structure import GROUP_LETTERS, MATCHES, TEAMS


@pytest.fixture(scope="module")
def params():
    return DcEloParams(
        beta0=0.10, beta1=0.73, gamma=0.23, rho=-0.043,
        half_life_days=730, n_matches=7768, cutoff="2026-06-11",
    )


@pytest.fixture(scope="module")
def elo():
    return {c: 2000.0 - 8.0 * i for i, c in enumerate(CODES)}


@pytest.fixture(scope="module")
def bundle(params, elo):
    att = DcAttackParams(
        mu=0.1, home_adv=0.25, rho=-0.04,
        att={c: 0.5 - 0.02 * i for i, c in enumerate(CODES)},
        def_={c: -0.5 + 0.02 * i for i, c in enumerate(CODES)},
        half_life_days=730, n_matches=7000, cutoff="2026-06-11", teams=CODES,
    )
    return ModelBundle(dc_elo=params, dc_attack=att, weight_dc_elo=0.6, half_life_days=730,
                       backtest={"best": {"weight_dc_elo": 0.6}})


@pytest.fixture(scope="module")
def model(bundle, elo):
    return bundle.build_model(elo)


@pytest.fixture(scope="module")
def sim(params, elo):
    tk = dict(elo)
    return simulate(params, elo, n_sims=2000, tiebreak_key=tk, seed=5)


def test_build_teams_complete(elo):
    teams = writer.build_teams(elo)
    assert len(teams) == 48
    for c, t in teams.items():
        assert set(t) == {"name_zh", "name_en", "group", "flag", "elo", "fifa_rank", "host"}
        assert t["name_zh"] == TEAMS[c].name_zh


def _components(bundle, elo):
    from wcsim.models.score_model import DcAttackModel
    return [("dc_elo", DcEloModel(bundle.dc_elo, elo)), ("dc_attack", DcAttackModel(bundle.dc_attack))]


def test_build_matches_104_with_forecast(bundle, model, elo, sim):
    matches = writer.build_matches(model, _components(bundle, elo), {}, sim)
    assert len(matches) == 104
    group_matches = [m for m in matches if m["stage"] == "group"]
    assert len(group_matches) == 72
    for m in group_matches:
        fc = m["forecast"]
        assert abs(fc["p_home"] + fc["p_draw"] + fc["p_away"] - 1.0) < 1e-3
        assert len(fc["top_scores"]) == 8
        assert len(fc["score_matrix"]) == 6 and len(fc["score_matrix"][0]) == 6
        # 双模型分解
        assert set(m["model_breakdown"]) == {"dc_elo", "dc_attack"}
    # 淘汰赛有 slot_dist
    r32 = [m for m in matches if m["stage"] == "r32"]
    assert len(r32) == 16
    assert all("slot_dist" in m for m in r32)


def test_build_matches_finished_status(bundle, model, elo, sim):
    results = {1: {"h": 2, "a": 1, "after": "FT"}}
    matches = writer.build_matches(model, _components(bundle, elo), results, sim)
    m1 = next(m for m in matches if m["id"] == 1)
    assert m1["status"] == "finished"
    assert m1["result"] == {"h": 2, "a": 1, "after": "FT"}


def test_build_groups_probabilities(sim):
    groups = writer.build_groups({}, sim)
    assert set(groups) == set(GROUP_LETTERS)
    for g, teams in groups.items():
        assert len(teams) == 4
        for c, info in teams.items():
            assert abs(sum(info["p_rank"]) - 1.0) < 1e-3
            assert info["p_top2"] == pytest.approx(info["p_rank"][0] + info["p_rank"][1], abs=1e-3)
            assert 0 <= info["p_advance"] <= 1
            assert info["current"]["played"] == 0


def test_build_groups_current_standings():
    # 给 A 组 M1 一个真实结果，current 应反映
    p = DcEloParams(beta0=0.1, beta1=0.7, gamma=0.2, rho=-0.04, half_life_days=730, n_matches=1, cutoff="2026-06-11")
    e = {c: 1800.0 for c in CODES}
    s = simulate(p, e, n_sims=200, seed=1)
    results = {1: {"h": 3, "a": 0, "after": "FT"}}  # 墨西哥 3-0 南非
    groups = writer.build_groups(results, s)
    assert groups["A"]["MEX"]["current"] == {"pts": 3, "gd": 3, "gf": 3, "played": 1}
    assert groups["A"]["RSA"]["current"] == {"pts": 0, "gd": -3, "gf": 0, "played": 1}


def test_build_knockout_monotonic(sim):
    ko = writer.build_knockout(sim)
    assert len(ko["teams"]) == 48
    for c, t in ko["teams"].items():
        seq = [t["p_r32"], t["p_r16"], t["p_qf"], t["p_sf"], t["p_final"], t["p_champion"]]
        for a, b in zip(seq, seq[1:]):
            assert a >= b - 1e-9
    # bracket 覆盖全部 32 场淘汰赛
    assert len(ko["bracket"]) == 32


def test_full_export_writes_all_files(bundle, elo, sim, tmp_path):
    writer.export_all(
        run_id="20260612T0000Z",
        generated_at="2026-06-12T00:00:00Z",
        bundle=bundle,
        elo=elo,
        results={},
        sim=sim,
        data_info={"martj42_rows": 49477, "elo_through": "2026-06-11", "results_count": 0},
        out_dir=tmp_path,
    )
    for name in ("meta", "teams", "matches", "groups", "knockout", "evolution"):
        assert (tmp_path / f"{name}.json").exists()
    assert (tmp_path / "history" / "20260612T0000Z.json").exists()
    # 中文未被转义
    raw = (tmp_path / "teams.json").read_text(encoding="utf-8")
    assert "墨西哥" in raw and "\\u" not in raw


def test_evolution_append_idempotent(sim, tmp_path):
    path = tmp_path / "evolution.json"
    args = ("20260612T0000Z", "2026-06-12T00:00:00Z", sim, {})
    evo1 = writer.update_evolution(path, *args)
    path.write_text(json.dumps(evo1), encoding="utf-8")
    # 同 run_id 再次追加 → 不变
    evo2 = writer.update_evolution(path, *args)
    assert len(evo2["snapshots"]) == 1
    # 新 run_id → 追加
    evo3 = writer.update_evolution(path, "20260612T0600Z", "2026-06-12T06:00:00Z", sim, {})
    assert len(evo3["snapshots"]) == 2
    assert len(evo3["teams"]["ESP"]["champion"]) == 2


def test_match_forecast_stronger_team_favored(model):
    # CODES[0] 远强于 CODES[-1]
    fc = writer.match_forecast(model, CODES[0], CODES[-1])
    assert fc["p_home"] > fc["p_away"]
    assert fc["lambda_home"] > fc["lambda_away"]
